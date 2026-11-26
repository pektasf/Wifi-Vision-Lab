from scripts.ui_theme import LIGHT_PALETTE, get_theme_palette


def test_palette_is_light_only():
    palette = get_theme_palette("dark")
    assert palette["bg"] == "#F2F5F3"
    assert palette["surface"] == "#FFFFFF"
    assert palette["text"] == "#182B2A"
    assert palette["accent"] == "#087F78"


def test_palette_is_returned_as_a_copy():
    palette = get_theme_palette()
    palette["bg"] = "changed"
    assert get_theme_palette()["bg"] == "#F2F5F3"


def test_palette_has_semantic_status_colors():
    assert LIGHT_PALETTE["success"] == "#167A55"
    assert LIGHT_PALETTE["warning"] == "#A96B16"
    assert LIGHT_PALETTE["danger"] == "#B84040"
    assert LIGHT_PALETTE["info"] == "#426C8C"


def test_palette_has_no_dark_theme_variant():
    assert get_theme_palette("dark") == get_theme_palette("light")
