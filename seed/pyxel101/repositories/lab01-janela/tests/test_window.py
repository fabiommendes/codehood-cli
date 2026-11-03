from window import window_fps, window_height, window_title, window_width


def test_sizes_are_positive_ints():
    assert isinstance(window_width(), int)
    assert isinstance(window_height(), int)
    assert window_width() > 0
    assert window_height() > 0


def test_title_is_a_text():
    title = window_title()
    assert isinstance(title, str) and title.strip()


def test_fps_is_positive():
    assert window_fps() > 0


def test_window_is_wider_than_tall():
    assert window_width() > window_height()
