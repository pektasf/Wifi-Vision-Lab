from scripts.ui_theme import LIGHT_PALETTE, get_theme_palette


def _luminance(hex_color):
    channels = [
        int(hex_color[index:index + 2], 16) / 255
        for index in (1, 3, 5)
    ]
    linear = [
        value / 12.92 if value <= 0.04045
        else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return (
        0.2126 * linear[0]
        + 0.7152 * linear[1]
        + 0.0722 * linear[2]
    )


def _contrast_ratio(foreground, background):
    first = _luminance(foreground)
    second = _luminance(background)
    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


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
    assert LIGHT_PALETTE["warning"] == "#8A5A12"
    assert LIGHT_PALETTE["danger"] == "#B84040"
    assert LIGHT_PALETTE["info"] == "#426C8C"


def test_text_and_status_colors_meet_aa_contrast_on_surface():
    surface = LIGHT_PALETTE["surface"]
    for token in ("text", "muted", "accent", "success", "warning", "danger", "info"):
        assert _contrast_ratio(LIGHT_PALETTE[token], surface) >= 4.5, token


def test_palette_has_no_dark_theme_variant():
    assert get_theme_palette("dark") == get_theme_palette("light")
