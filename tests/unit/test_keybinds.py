from gfa.input_profiles.keybinds import (
    KeybindProfile, MouseConfig, fps_wasd, racing_wasd, get_preset, list_presets,
)


def test_presets_exist():
    assert "fps-wasd" in list_presets()
    assert "racing-wasd" in list_presets()


def test_fps_preset_keys():
    p = fps_wasd()
    assert p.move_forward_key == "w"
    assert p.keybinds["shoot"] == "mouse_left"


def test_mouse_config_apply_delta():
    p = fps_wasd()
    p.keybinds = {}
    adx, ady = p.apply_mouse_delta(100, 50)
    assert adx == 100
    assert ady == 50


def test_invert_y():
    p = fps_wasd()
    p.mouse.invert_y = True
    adx, ady = p.apply_mouse_delta(100, 50)
    assert ady == -50


def test_sensitivity():
    p = fps_wasd()
    p.mouse.sensitivity_x = 2.0
    p.look_sensitivity = 1.5
    adx, ady = p.apply_mouse_delta(10, 0)
    assert adx == 30


def test_roundtrip_save_load(tmp_path):
    p = racing_wasd()
    path = tmp_path / "profile.json"
    p.save(path)
    p2 = KeybindProfile.load(path)
    assert p2.name == p.name
    assert p2.mouse.sensitivity_x == p.mouse.sensitivity_x


def test_get_preset():
    p = get_preset("fps-wasd")
    assert p is not None
    assert get_preset("nonexistent") is None