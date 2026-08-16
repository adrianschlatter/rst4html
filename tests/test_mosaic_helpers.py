from __future__ import annotations

import importlib
from typing import Any, Tuple

import pytest
from docutils import nodes

core = importlib.import_module("rst4html.rst4html")


def test_parse_mosaic_width_px() -> None:
    """Convert pixel widths to integers."""
    assert core._parse_mosaic_width("300px", 200) == 300


def test_parse_mosaic_border_px() -> None:
    """Convert pixel borders to percent."""
    assert core._parse_mosaic_border("10px", 200) == 5.0


def test_parse_mosaic_width_invalid_falls_back() -> None:
    """Fallback to target line width when width is invalid."""
    assert core._parse_mosaic_width("bad", 200) == 200


def test_parse_mosaic_width_negative_falls_back() -> None:
    """Fallback to target line width when width is negative."""
    assert core._parse_mosaic_width("-10", 200) == 200


def test_parse_mosaic_width_invalid_non_string_falls_back() -> None:
    """Fallback to target line width for unsupported width values."""
    assert core._parse_mosaic_width(object(), 200) == 200


def test_parse_mosaic_width_requires_positive_targetlinewidth() -> None:
    """Reject non-positive target line widths."""
    with pytest.raises(TypeError):
        core._parse_mosaic_width("100%", 0)


def test_parse_mosaic_border_invalid_falls_back() -> None:
    """Fallback to default border when border is invalid."""
    assert core._parse_mosaic_border("bad", 200) == 2.0


def test_parse_mosaic_border_negative_clamps() -> None:
    """Clamp negative border values to zero."""
    assert core._parse_mosaic_border("-5%", 200) == 0.0


def test_parse_mosaic_border_non_string_falls_back() -> None:
    """Fallback to default border for unsupported border values."""
    assert core._parse_mosaic_border(object(), 200) == 2.0


def test_parse_mosaic_border_requires_positive_width() -> None:
    """Reject non-positive width when parsing border."""
    with pytest.raises(ValueError):
        core._parse_mosaic_border("2%", 0)


def test_calculate_mosaic_image_geometry_empty() -> None:
    """Return empty geometry for empty input."""
    assert core._calculate_mosaic_image_geometry([], 200, 2.0) == []


def test_calculate_mosaic_image_geometry_requires_positive_width() -> None:
    """Reject non-positive mosaic widths."""
    with pytest.raises(ValueError):
        core._calculate_mosaic_image_geometry([(100, 50)], 0, 2.0)


def test_calculate_mosaic_image_geometry_requires_non_negative_border() -> None:
    """Reject negative border percent."""
    with pytest.raises(ValueError):
        core._calculate_mosaic_image_geometry([(100, 50)], 100, -1.0)


def test_calculate_mosaic_image_geometry_raises_when_gaps_exceed_width() -> None:
    """Reject border settings that leave no image space."""
    with pytest.raises(ValueError):
        core._calculate_mosaic_image_geometry([(100, 50), (100, 50)], 100, 100.0)


def test_calculate_mosaic_image_geometry_handles_zero_height() -> None:
    """Keep zero-height image geometry unchanged."""
    geometry = core._calculate_mosaic_image_geometry([(100, 0)], 200, 2.0)
    assert geometry == [(100, 0)]


def test_calculate_mosaic_image_geometry_respects_source_bounds() -> None:
    """Never upscale beyond source dimensions."""
    geometry = core._calculate_mosaic_image_geometry([(80, 40), (60, 60)], 400, 2.0)
    assert geometry[0][0] <= 80
    assert geometry[0][1] <= 40
    assert geometry[1][0] <= 60
    assert geometry[1][1] <= 60


def test_calculate_mosaic_image_geometry_distributes_remaining_width() -> None:
    """Distribute remaining width without exceeding source sizes."""
    geometry = core._calculate_mosaic_image_geometry([(200, 100), (200, 100)], 250, 2.0)
    assert geometry[0][0] + geometry[1][0] <= 250


def test_calculate_mosaic_image_geometry_keeps_default_width_for_bad_percent() -> None:
    """Invalid percent width falls back to target line width."""
    assert core._parse_mosaic_width("-5%", 200) == 200


def test_calculate_mosaic_image_geometry_keeps_default_width_for_bad_px() -> None:
    """Invalid pixel width falls back to target line width."""
    assert core._parse_mosaic_width("-5px", 200) == 200


def test_calculate_mosaic_image_geometry_rejects_non_positive_numeric_width() -> None:
    """Numeric widths less than one fall back to target line width."""
    assert core._parse_mosaic_width(0, 200) == 200


def test_calculate_mosaic_image_geometry_accepts_numeric_width() -> None:
    """Numeric width values parse directly."""
    assert core._parse_mosaic_width(150, 200) == 150


def test_calculate_mosaic_image_geometry_border_from_plain_number() -> None:
    """Plain numeric border values parse as percent."""
    assert core._parse_mosaic_border("3", 200) == 3.0


def test_calculate_mosaic_image_geometry_border_from_number() -> None:
    """Numeric border values parse as percent."""
    assert core._parse_mosaic_border(4, 200) == 4.0


def test_calculate_mosaic_image_geometry_border_from_invalid_px_falls_back() -> None:
    """Invalid px border falls back to default percent."""
    assert core._parse_mosaic_border("badpx", 200) == 2.0


def test_calculate_mosaic_image_geometry_border_from_invalid_percent_falls_back() -> None:
    """Invalid percent border falls back to default percent."""
    assert core._parse_mosaic_border("bad%", 200) == 2.0


def test_calculate_mosaic_image_geometry_skips_zero_width_image() -> None:
    """Preserve zero-width source dimensions."""
    geometry = core._calculate_mosaic_image_geometry([(0, 50), (100, 50)], 200, 2.0)
    assert geometry[0] == (0, 50)


def test_calculate_mosaic_image_geometry_skips_zero_source_dimensions() -> None:
    """Preserve zero-sized dimensions in output geometry."""
    geometry = core._calculate_mosaic_image_geometry([(10, 0), (100, 50)], 200, 2.0)
    assert geometry[0] == (10, 0)


def test_calculate_mosaic_image_geometry_handles_small_width_result() -> None:
    """Clamp computed width to at least one pixel for valid images."""
    geometry = core._calculate_mosaic_image_geometry([(5, 1000)], 1, 0.0)
    assert geometry[0][0] >= 1


def test_prepare_mosaic_image_resizes(tmp_path: Any) -> None:
    """Resize mosaic images that exceed max width."""
    node = nodes.image(uri=str(tmp_path / "image.png"))

    class DummyImage:
        """Stub image for resize tests."""

        def __init__(self) -> None:
            """Set oversize dimensions."""
            self.width = 500
            self.height = 250
            self.resize_args: Tuple[int, int] | None = None
            self.saved: str | None = None

        def resize(self, size: Tuple[int, int], resample: Any = None) -> Any:
            """Capture resize arguments and return self."""
            self.resize_args = size
            return self

        def save(self, path: str) -> None:
            """Capture the save path."""
            self.saved = path

    dummy = DummyImage()
    original_open = core.PIL.Image.open
    core.PIL.Image.open = lambda *_: dummy
    try:
        newuri, ratio = core._prepare_mosaic_image(node, str(tmp_path), 425)
    finally:
        core.PIL.Image.open = original_open

    assert newuri.endswith("image.png")
    assert ratio == 2.0
    assert dummy.resize_args == (425, 212)
    assert dummy.saved == newuri


def test_prepare_mosaic_image_no_resize(tmp_path: Any) -> None:
    """Keep mosaic images within max width unchanged."""
    node = nodes.image(uri=str(tmp_path / "image.png"))

    class DummyImage:
        """Stub image that should not be resized."""

        def __init__(self) -> None:
            """Set sample dimensions."""
            self.width = 200
            self.height = 100
            self.resized = False
            self.saved: str | None = None

        def resize(self, size: Tuple[int, int], resample: Any = None) -> Any:
            """Mark resize as called and return self."""
            self.resized = True
            return self

        def save(self, path: str) -> None:
            """Capture the save path."""
            self.saved = path

    dummy = DummyImage()
    original_open = core.PIL.Image.open
    core.PIL.Image.open = lambda *_: dummy
    try:
        newuri, ratio = core._prepare_mosaic_image(node, str(tmp_path), 425)
    finally:
        core.PIL.Image.open = original_open

    assert newuri.endswith("image.png")
    assert ratio == 2.0
    assert dummy.resized is False
    assert dummy.saved == newuri


def test_render_mosaic_images() -> None:
    """Build HTML snippets for mosaic images."""
    html = core._render_mosaic_images([
        ("/img/a.png", 2.0),
        ("/img/b.png", 1.0),
    ])
    assert html == (
        '    <img src="/img/a.png" style="--ar: 2.0000;">\n'
        '    <img src="/img/b.png" style="--ar: 1.0000;">\n'
    )


def test_render_mosaic_images_with_dimensions() -> None:
    """Build HTML snippets with explicit width and height."""
    html = core._render_mosaic_images([
        ("/img/a.png", 2.0, 100, 50),
    ])
    assert html == (
        '    <img src="/img/a.png" width="100" height="50" style="--ar: 2.0000;">\n'
    )
