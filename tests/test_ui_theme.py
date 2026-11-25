from scripts.ui_theme import get_theme_palette


def test_dark_theme_palette_has_dark_surfaces():
    palette = get_theme_palette("dark")
    assert palette["bg"] == "#0B1220"
    assert palette["surface"] == "#111C2E"
    assert palette["text"] == "#E8EEF7"


def test_light_theme_palette_has_light_surfaces():
    palette = get_theme_palette("light")
    assert palette["bg"] == "#F4F7FB"
    assert palette["surface"] == "#FFFFFF"
    assert palette["text"] == "#17243A"


def test_unknown_theme_falls_back_to_dark():
    assert get_theme_palette("unexpected") == get_theme_palette("dark")


def test_theme_palette_is_returned_as_a_copy():
    palette = get_theme_palette("dark")
    palette["bg"] = "changed"
    assert get_theme_palette("dark")["bg"] == "#0B1220"
