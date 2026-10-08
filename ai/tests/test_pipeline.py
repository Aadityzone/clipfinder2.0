from ai.highlights import candidates
from ai.services.dedup import deduplicate

def test_custom_instruction_changes_candidate_score():
    segments=[{"start":0,"end":12,"text":"This is a surprising story about the biggest mistake I ever made!"}]
    base=candidates(segments)
    targeted=candidates(segments,"find surprising stories",["AI Detect"])
    assert base and targeted
    assert targeted[0]["score"]>=base[0]["score"]

def test_selected_category_filters_candidates():
    segments=[{"start":0,"end":10,"text":"That was hilarious, everyone started to laugh!"}]
    result=candidates(segments,None,["Funny"])
    assert result
    assert result[0]["category"]=="funny"

def test_dedup_keeps_highest_scoring_overlap():
    items=[{"start":0,"end":10,"score":90},{"start":1,"end":9,"score":70},{"start":20,"end":30,"score":60}]
    result=deduplicate(items)
    assert len(result)==2
    assert result[0]["score"]==90
