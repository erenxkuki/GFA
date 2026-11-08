from gfa.combat.combos import ComboLibrary, create_default_library, Combo, ComboStep


def test_default_library():
    lib = create_default_library()
    assert "dodge_left" in lib.list_combos()
    assert "combo_3hit" in lib.list_combos()
    assert len(lib.list_combos()) >= 7


def test_combo_can_use_cooldown():
    combo = Combo(name="test", cooldown_ms=1000, steps=[ComboStep(hold_ms=10)])
    assert combo.can_use() is True
    combo._last_used = __import__("time").time()
    assert combo.can_use() is False


def test_combo_execute_with_mock():
    from unittest.mock import MagicMock
    ctrl = MagicMock()
    combo = Combo(name="test", steps=[ComboStep(keys=["w"], hold_ms=10, delay_after=0)])
    ok = combo.execute(ctrl)
    assert ok is True
    ctrl.hold_keys.assert_called()
    ctrl.release_keys.assert_called()


def test_combo_library_execute_unknown():
    lib = ComboLibrary()
    from unittest.mock import MagicMock
    assert lib.execute("nonexistent", MagicMock()) is False