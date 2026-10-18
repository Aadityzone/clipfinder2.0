import pytest

from ai.services import visual_intelligence


def test_visual_capabilities_has_local_backend():
    caps = visual_intelligence.visual_capabilities()
    assert caps["local_features"] is (visual_intelligence.cv2 is not None)
    if visual_intelligence.cv2 is None:
        assert caps["local_features_reason"] == "OpenCV is unavailable"


def test_frame_signature_is_deterministic():
    if visual_intelligence.cv2 is None:
        pytest.skip("OpenCV native runtime is unavailable")
    import numpy as np
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    a = visual_intelligence._frame_signature(frame)
    b = visual_intelligence._frame_signature(frame)
    assert np.allclose(a, b)
