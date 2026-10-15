# Universal Genre Foundation

Clip Finder shares one media-analysis and candidate-quality contract across all
supported genres. Genre-specific intelligence is layered on top of this
foundation; it must not bypass timestamp validation, evidence tracking, ranking,
deduplication, or real-media evaluation.

## Shared pipeline

1. Validate and probe the source media.
2. Extract audio, timestamped speech, sampled frames, scene changes, and optional
   on-screen text/action signals.
3. Generate candidate intervals from available modalities.
4. Enrich candidates with transcript, audio, visual, speaker, and provenance
   features when those signals are available.
5. Validate candidate timestamps and finite scores against source duration.
6. Apply genre-aware ranking and creator preferences as bounded adjustments.
7. Deduplicate, rank, persist, and expose real candidates to the editor.
8. Render from the source and validate the output artifact.

A missing optional model must be reported as unavailable, not represented as a
successful analysis. Visual-only candidates are allowed by the shared contract
when they include inspectable feature evidence.

## Genre foundations and next specialization

| Genre | Shared signals already useful | Specialized work still required |
|---|---|---|
| Gaming | Speech, audio energy, scene/motion change, OCR/action cues, gameplay-like frame features | Detect actual kills, clutches, wins, round endings, and setup-to-payoff sequence |
| IRL streams | Speech, face presence, audio energy, scene changes, optional stream-overlay OCR | Connect reactions to the event that caused them; model situational context |
| Podcasts | Transcript, semantic scoring, speaker-turn signals, questions and conversation changes | Better diarization, debate structure, complete memorable statements, turn-aware boundaries |
| Tech videos | Transcript semantics, scene changes, on-screen text where available | Detect demonstrations, UI/code changes, before/after outcomes, and useful insights |
| Knowledge / educational | Transcript semantics, sentence/story boundaries, speaker signals | Preserve complete explanations, definitions, examples, and conclusions |
| Facts | Transcript cues and semantic scoring | Prefer surprising, accurate, independently understandable claims; support verification rather than guessing truth |
| Movies / TV | Visual samples, scene changes, transcript semantics | Understand plot context, character/event continuity, and visually important scenes without inventing missing context |
| Anime | Visual samples, motion/scene changes, transcript semantics | Detect fights, transformations, reveals, and story payoffs with temporal context |

## Quality gates

Do not mark a genre as reliable based only on passing unit tests or keyword
matches. For each genre, collect representative, rights-authorized test videos
and human-labeled candidate ranges. Measure at least:

- timestamp validity and source-boundary correctness;
- precision among top-ranked clips;
- recall of labeled moments;
- boundary quality and setup/payoff completeness;
- duplicate rate;
- useful visual evidence for visual-first moments;
- processing time, peak RAM/VRAM, and recovery after failure.

Genre profiles currently provide explainable heuristics, not trained classifiers
or proof of genre-specific accuracy. Upgrade one genre at a time after the shared
pipeline is stable and measurable.
