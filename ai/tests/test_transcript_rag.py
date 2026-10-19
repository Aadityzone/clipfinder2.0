import numpy as np

from ai.services import transcript_rag as rag


class KeywordEmbedder:
    def __init__(self):
        self.calls = []

    def encode(self, texts):
        self.calls.append(list(texts))
        return np.asarray([
            [1.0, 0.0] if "cat" in text.lower() else [0.0, 1.0]
            for text in texts
        ], dtype=np.float32)


def test_chunking_preserves_nonzero_timestamps_and_overlap():
    words = [f"word{i}" for i in range(230)]
    chunks = rag.chunk_transcript(
        [{"start": 120, "end": 350, "text": " ".join(words)}],
        max_words=100, overlap_words=20,
    )

    assert len(chunks) == 3
    assert (chunks[0].start, chunks[0].end) == (120, 220)
    assert chunks[0].text.split()[-20:] == chunks[1].text.split()[:20]
    assert chunks[-1].end == 350
    assert all(chunk.start >= 120 for chunk in chunks)


def test_chunking_skips_missing_invalid_and_out_of_range_segments():
    chunks = rag.chunk_transcript([
        {"text": "missing timestamps"},
        {"start": 4, "end": 4, "text": "zero duration"},
        {"start": 5, "end": 8, "text": "before"},
        {"start": 12, "end": 15, "text": "inside selected range"},
        {"start": 20, "end": 22, "text": "after"},
    ], time_range=(10, 18))
    assert len(chunks) == 1
    assert (chunks[0].start, chunks[0].end) == (12, 15)


def test_empty_transcript_is_a_safe_noop():
    result = rag.retrieve_context([], "anything", candidate_start=0, candidate_end=1, embedder=KeywordEmbedder())
    assert result["status"] == "empty"
    assert result["chunks"] == []


def test_chunk_overlap_configuration_is_validated():
    try:
        rag.chunk_transcript([], max_words=5, overlap_words=5)
    except ValueError as error:
        assert "overlap" in str(error)
    else:
        raise AssertionError("invalid overlap should fail")


def test_retrieval_ranks_relevant_context_and_suppresses_candidate_overlap(monkeypatch):
    monkeypatch.setenv("RAG_ENABLED", "true")
    rag.reset_rag_state()
    embedder = KeywordEmbedder()
    rows = [
        {"start": 100, "end": 105, "text": "cat candidate moment"},
        {"start": 70, "end": 80, "text": "cat setup before payoff"},
        {"start": 200, "end": 210, "text": "unrelated weather report"},
    ]
    result = rag.retrieve_context(
        rows, "cat candidate", candidate_start=100, candidate_end=105,
        embedder=embedder, limit=2,
    )
    assert result["status"] == "available"
    assert result["chunks"][0]["text"] == "cat setup before payoff"
    assert result["chunks"][0]["start"] == 70
    assert all(not (item["start"] == 100) for item in result["chunks"])
    rag.reset_rag_state()


def test_selected_range_is_applied_before_retrieval():
    chunks = rag.chunk_transcript([
        {"start": 110, "end": 115, "text": "cat outside selected source range"},
        {"start": 125, "end": 130, "text": "cat inside selected source range"},
    ], time_range=(120, 140))
    assert len(chunks) == 1
    assert chunks[0].start == 125


def test_cache_reuses_embeddings_for_unchanged_chunk_and_query(monkeypatch):
    monkeypatch.setenv("RAG_EMBEDDING_MODEL", "test-model")
    rag.reset_rag_state()


def test_invalid_overlap_setting_is_clamped_without_failing_analysis(monkeypatch):
    monkeypatch.setenv("RAG_CHUNK_WORDS", "20")
    monkeypatch.setenv("RAG_CHUNK_OVERLAP_WORDS", "200")
    result = rag.retrieve_context(
        [{"start": 0, "end": 2, "text": "cat candidate words"}], "cat",
        candidate_start=0, candidate_end=1, embedder=KeywordEmbedder(),
    )
    assert result["status"] == "available"
    embedder = KeywordEmbedder()
    texts = ["cat one", "cat two"]
    rag._embed_texts(embedder, texts)
    rag._embed_texts(embedder, texts)
    assert len(embedder.calls) == 1
    rag.reset_rag_state()


def test_malformed_embedding_output_degrades_to_unavailable(monkeypatch):
    class BadEmbedder:
        def encode(self, texts):
            return [[float("nan")]] * len(texts)

    monkeypatch.setenv("RAG_ENABLED", "true")
    rag.reset_rag_state()
    result = rag.retrieve_context(
        [{"start": 0, "end": 2, "text": "candidate words here"}], "candidate",
        candidate_start=0, candidate_end=1, embedder=BadEmbedder(),
    )
    assert result["status"] == "unavailable"
    assert result["chunks"] == []
    rag.reset_rag_state()


def test_wrong_embedding_dimensions_are_rejected():
    class WrongShapeEmbedder:
        def encode(self, texts):
            return np.asarray([1.0, 2.0, 3.0], dtype=np.float32)

    result = rag.retrieve_context(
        [{"start": 0, "end": 2, "text": "candidate words here"}], "candidate",
        candidate_start=0, candidate_end=1, embedder=WrongShapeEmbedder(),
    )
    assert result["status"] == "unavailable"


def test_retrieved_context_obeys_character_budget():
    text = "cat " + ("relevant context " * 30)
    result = rag.retrieve_context(
        [{"start": 10, "end": 20, "text": text}], "cat", candidate_start=0,
        candidate_end=1, embedder=KeywordEmbedder(), max_chars=24,
    )
    assert result["status"] == "available"
    assert sum(len(row["text"]) for row in result["chunks"]) <= 24


def test_missing_local_model_is_nonfatal(monkeypatch):
    monkeypatch.setenv("RAG_ENABLED", "true")
    monkeypatch.setattr(rag, "LocalSentenceEmbedder", lambda: (_ for _ in ()).throw(ImportError()))
    rag.reset_rag_state()
    result = rag.retrieve_context(
        [{"start": 0, "end": 2, "text": "candidate words here"}], "candidate",
        candidate_start=0, candidate_end=1,
    )
    assert result["status"] == "unavailable"
    rag.reset_rag_state()


def test_disabled_rag_and_candidate_budget_do_not_change_scores(monkeypatch):
    monkeypatch.setenv("RAG_ENABLED", "false")
    candidates = [
        {"start": 0, "end": 1, "text": "cat", "score": 73, "features": {}},
        {"start": 2, "end": 3, "text": "cat", "score": 51, "features": {}},
    ]
    enriched, context = rag.enrich_candidates_with_context(candidates, [], limit_candidates=1)
    assert [item["score"] for item in enriched] == [73, 51]
    assert enriched[0]["features"]["transcriptRag"]["status"] == "disabled"
    assert enriched[1]["features"]["transcriptRag"]["status"] == "skipped_budget"
    assert context == {}


def test_transcript_text_supplies_a_query_for_visual_only_candidate(monkeypatch):
    monkeypatch.setenv("RAG_ENABLED", "true")
    rag.reset_rag_state()
    monkeypatch.setattr(rag, "_get_embedder", lambda: KeywordEmbedder())
    candidates = [{"start": 12, "end": 14, "text": "", "score": 60, "features": {}}]
    segments = [
        {"start": 10, "end": 11, "text": "cat setup before candidate"},
        {"start": 12, "end": 14, "text": "visual moment occurs"},
        {"start": 16, "end": 18, "text": "the cat payoff is clear"},
    ]
    enriched, context = rag.enrich_candidates_with_context(candidates, segments)
    assert enriched[0]["features"]["transcriptRag"]["status"] == "available"
    assert context[0]
    rag.reset_rag_state()
