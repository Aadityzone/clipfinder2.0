from ai.services.visual_intelligence import visual_capabilities, _frame_signature


def test_visual_capabilities_has_local_backend():
    caps = visual_capabilities()
    assert caps["local_features"] is True


def test_frame_signature_is_deterministic():
    import numpy as np
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    a = _frame_signature(frame)
    b = _frame_signature(frame)
    assert np.allclose(a, b)
