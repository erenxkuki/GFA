from gfa.spatial.depth import SpatialEstimator


def test_depth_estimation():
    se = SpatialEstimator(frame_width=1920, frame_height=1080)
    se.register_known_size("enemy", 100)
    obj = {"label": "enemy", "x": 500, "y": 500, "w": 50, "h": 50}
    depth = se.estimate_depth(obj)
    assert 0.0 <= depth <= 1.0


def test_find_nearest():
    se = SpatialEstimator()
    objs = [{"label": "a", "x": 100, "y": 100, "w": 10, "h": 10},
            {"label": "b", "x": 900, "y": 900, "w": 10, "h": 10}]
    nearest = se.find_nearest(objs)
    assert nearest is not None
    assert nearest["label"] == "a"


def test_find_threats():
    se = SpatialEstimator(frame_width=1920, frame_height=1080)
    objs = [{"label": "enemy", "x": 100, "y": 100, "w": 20, "h": 20},
            {"label": "tree", "x": 1800, "y": 900, "w": 10, "h": 10}]
    threats = se.find_threats(objs, threat_labels=["enemy"])
    assert len(threats) >= 1
    assert threats[0]["label"] == "enemy"


def test_spatial_summary():
    se = SpatialEstimator()
    objs = [{"label": "enemy", "x": 100, "y": 200, "w": 30, "h": 30}]
    summary = se.spatial_summary(objs)
    assert "enemy" in summary
    assert "Nearest" in summary