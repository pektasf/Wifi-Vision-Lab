from scripts.ui_theme import get_theme_palette


def test_palette_is_light_only():
    palette = get_theme_palette("dark")
    assert palette["bg"] == "#F5F7FA"
    assert palette["surface"] == "#FFFFFF"
    assert palette["text"] == "#182230"


def test_palette_is_returned_as_a_copy():
    palette = get_theme_palette()
    palette["bg"] = "changed"
    assert get_theme_palette()["bg"] == "#F5F7FA"
