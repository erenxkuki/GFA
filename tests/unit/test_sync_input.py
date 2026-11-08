from gfa.universal.sync_input import SyncInputController


def test_sync_input_state_tracking():
    si = SyncInputController()
    assert si.state.keys_held == set()
    # Can't actually send input in headless, but construction works
    assert si.emergency is False
    si.trigger_emergency_stop()
    assert si.emergency is True


def test_look_and_move_no_crash():
    si = SyncInputController()
    # Emergency stops prevent actual input; reset first
    si.reset_emergency()
    # We can't send real input in CI, but method should exist and be callable in emergency mode? 
    # In emergency mode it raises. Test that it raises.
    si.trigger_emergency_stop()
    try:
        si.look_and_move(10, 20, ["w"])
        assert False
    except RuntimeError:
        pass