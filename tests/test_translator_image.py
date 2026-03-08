from __future__ import annotations

import importlib
import types
from typing import Any, Dict, Tuple

import pytest
from docutils import nodes

core = importlib.import_module("rst4html.rst4html")


def test_modified_translator_requires_integer_targetlinewidth() -> None:
    """Require integer target linewidth for scaling."""
    translator = core.ModifiedHTMLTranslator.__new__(
        core.ModifiedHTMLTranslator
    )
    translator.settings = types.SimpleNamespace(
        imgtargetdir="/tmp",
        targetlinewidth="100",
    )
    node = nodes.image(uri="/tmp/image.jpg")
    with pytest.raises(TypeError) as exc:
        core.ModifiedHTMLTranslator.visit_image(translator, node)
    assert "--targetlinewidth" in str(exc.value)


def test_modified_translator_rejects_unknown_width(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject unsupported width formats."""
    translator = core.ModifiedHTMLTranslator.__new__(
        core.ModifiedHTMLTranslator
    )
    translator.settings = types.SimpleNamespace(
        imgtargetdir="/tmp",
        targetlinewidth=100,
    )
    node = nodes.image(uri="/tmp/image.jpg", width="2em")

    class DummyImage:
        """Stub image object without resizing."""

        format = "PNG"
        width = 100
        height = 50

        def resize(self, size: Tuple[int, int], resample: Any = None) -> Any:
            """Return self to mimic PIL resizing."""
            return self

        def save(self, path: str) -> None:
            """Pretend to save the image."""
            return None

    def fake_open(path: str) -> DummyImage:
        """Return a dummy image instance."""
        return DummyImage()

    monkeypatch.setattr(core.PIL.Image, "open", fake_open)
    with pytest.raises(NotImplementedError) as exc:
        core.ModifiedHTMLTranslator.visit_image(translator, node)
    assert "width 2em not understood" in str(exc.value)


def test_modified_translator_scales_percent_width(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    """Scale images based on percent widths."""
    translator = core.ModifiedHTMLTranslator.__new__(
        core.ModifiedHTMLTranslator
    )
    translator.settings = types.SimpleNamespace(
        imgtargetdir=str(tmp_path),
        targetlinewidth=200,
    )
    node = nodes.image(
        uri=str(tmp_path / "image.jpg"),
        width="50%",
    )

    class DummyImage:
        """Stub image object capturing resize arguments."""

        format = "PNG"
        width = 400
        height = 200

        def __init__(self) -> None:
            """Initialize placeholders for resize args."""
            self.resize_args: Tuple[Tuple[int, int], Any] | None = None
            self.saved: str | None = None

        def resize(self, size: Tuple[int, int], resample: Any = None) -> Any:
            """Capture resize arguments and return self."""
            self.resize_args = (size, resample)
            return self

        def save(self, path: str) -> None:
            """Capture the save path."""
            self.saved = path

    dummy = DummyImage()

    def fake_open(path: str) -> DummyImage:
        """Return the shared dummy image instance."""
        return dummy

    def noop_visit_image(*_: Any) -> None:
        """Disable base HTML image rendering for the test."""
        return None

    monkeypatch.setattr(core.PIL.Image, "open", fake_open)
    monkeypatch.setattr(core.HTMLTranslator, "visit_image", noop_visit_image)

    core.ModifiedHTMLTranslator.visit_image(translator, node)
    assert dummy.resize_args[0] == (100, 50)
    assert dummy.saved.endswith("image.jpg")


def test_modified_translator_scales_px_width(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    """Scale images based on pixel widths."""
    translator = core.ModifiedHTMLTranslator.__new__(
        core.ModifiedHTMLTranslator
    )
    translator.settings = types.SimpleNamespace(
        imgtargetdir=str(tmp_path),
        targetlinewidth=200,
    )
    node = nodes.image(
        uri=str(tmp_path / "image.jpg"),
        width="50px",
    )

    class DummyImage:
        """Stub image object capturing resize arguments."""

        format = "PNG"
        width = 400
        height = 200

        def __init__(self) -> None:
            """Initialize placeholders for resize args."""
            self.resize_args: Tuple[Tuple[int, int], Any] | None = None
            self.saved: str | None = None

        def resize(self, size: Tuple[int, int], resample: Any = None) -> Any:
            """Capture resize arguments and return self."""
            self.resize_args = (size, resample)
            return self

        def save(self, path: str) -> None:
            """Capture the save path."""
            self.saved = path

    dummy = DummyImage()

    def fake_open(path: str) -> DummyImage:
        """Return the shared dummy image instance."""
        return dummy

    def noop_visit_image(*_: Any) -> None:
        """Disable base HTML image rendering for the test."""
        return None

    monkeypatch.setattr(core.PIL.Image, "open", fake_open)
    monkeypatch.setattr(core.HTMLTranslator, "visit_image", noop_visit_image)

    core.ModifiedHTMLTranslator.visit_image(translator, node)
    assert dummy.resize_args[0] == (50, 25)
    assert dummy.saved.endswith("image.jpg")


def test_modified_translator_autorotates_jpeg(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    """Apply EXIF-based autorotation for JPEGs."""
    translator = core.ModifiedHTMLTranslator.__new__(
        core.ModifiedHTMLTranslator
    )
    translator.settings = types.SimpleNamespace(
        imgtargetdir=str(tmp_path),
        targetlinewidth=200,
    )
    node = nodes.image(
        uri=str(tmp_path / "image.jpg"),
        width="50px",
    )

    class DummyImage:
        """Stub JPEG image with EXIF orientation."""

        format = "JPEG"
        width = 100
        height = 50

        def __init__(self) -> None:
            """Initialize tracking for operations and save calls."""
            self.ops: list[Any] = []
            self.resize_args: Tuple[Tuple[int, int], Any] | None = None
            self.saved: str | None = None

        def _getexif(self) -> Dict[int, int]:
            """Return a fake EXIF orientation map."""
            return {274: 6}

        def transpose(self, op: Any) -> Any:
            """Record transpose operations and return self."""
            self.ops.append(op)
            return self

        def resize(self, size: Tuple[int, int], resample: Any = None) -> Any:
            """Capture resize arguments and return self."""
            self.resize_args = (size, resample)
            return self

        def save(self, path: str) -> None:
            """Capture the save path."""
            self.saved = path

    dummy = DummyImage()

    def fake_open(path: str) -> DummyImage:
        """Return the shared dummy image instance."""
        return dummy

    def noop_visit_image(*_: Any) -> None:
        """Disable base HTML image rendering for the test."""
        return None

    monkeypatch.setattr(core.PIL.Image, "open", fake_open)
    monkeypatch.setattr(core.PIL.ExifTags, "TAGS", {274: "Orientation"})
    monkeypatch.setattr(core.HTMLTranslator, "visit_image", noop_visit_image)

    core.ModifiedHTMLTranslator.visit_image(translator, node)
    assert dummy.ops == list(core.ModifiedHTMLTranslator.exiftrans[6])
    assert dummy.resize_args[0] == (50, 25)
