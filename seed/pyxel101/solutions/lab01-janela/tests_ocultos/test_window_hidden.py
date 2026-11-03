from window import window_fps, window_height, window_title, window_width


def test_exact_values():
    assert window_width() == 160
    assert window_height() == 120
    assert window_title() == "Minha primeira janela"
    assert window_fps() == 30


def test_sizes_and_fps_are_ints():
    assert type(window_width()) is int
    assert type(window_height()) is int
    assert type(window_fps()) is int
