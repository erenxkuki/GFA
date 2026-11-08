from gfa.spatial.multiview.capture import SpatialMap, ViewCapture
from gfa.vision.perception import PerceptionResult, DetectedObject


def test_spatial_map_reconstruction():
    smap = SpatialMap()
    # Simulate two views
    view1 = ViewCapture(angle=0, frame=None, perception=PerceptionResult(
        objects=[DetectedObject(label="enemy", x=100, y=200, w=20, h=20, confidence=0.9)],
    ))
    view2 = ViewCapture(angle=90, frame=None, perception=PerceptionResult(
        objects=[DetectedObject(label="enemy", x=150, y=180, w=18, h=18, confidence=0.8)],
    ))
    smap.add_view(view1)
    smap.add_view(view2)
    assert smap.confidence >= 0.5
    assert "enemy" in smap.estimated_positions
    assert smap.object_seen_from("enemy") == 2
    assert "Spatial map" in smap.summary


def test_spatial_map_single_view():
    smap = SpatialMap()
    view = ViewCapture(angle=0, frame=None, perception=PerceptionResult(
        objects=[DetectedObject(label="tree", x=50, y=50, w=10, h=10)],
    ))
    smap.add_view(view)
    assert "tree" in smap.estimated_positions
    assert smap.object_seen_from("tree") == 1