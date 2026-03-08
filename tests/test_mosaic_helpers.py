from __future__ import annotations

import importlib
from typing import Any, Tuple

from docutils import nodes

core = importlib.import_module("rst4html.rst4html")


def test_parse_mosaic_width_px() -> None:
    """Convert pixel widths to integers."""
    assert core._parse_mosaic_width("300px", 200) == 300


def test_parse_mosaic_border_px() -> None:
    """Convert pixel borders to percent."""
    assert core._parse_mosaic_border("10px", 200) == 5.0


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
