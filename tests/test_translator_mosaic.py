from __future__ import annotations

import importlib
from typing import Any, Callable, Tuple

import pytest
from docutils import nodes

core = importlib.import_module("rst4html.rst4html")


def test_modified_translator_mosaic_caption_paragraph() -> None:
    """Render mosaic captions as paragraph tags."""
    translator = core.ModifiedHTMLTranslator.__new__(
        core.ModifiedHTMLTranslator
    )
    translator.body = []
    node = nodes.paragraph(classes=["caption"])
    node["mosaic_caption"] = True

    core.ModifiedHTMLTranslator.visit_paragraph(translator, node)
    core.ModifiedHTMLTranslator.depart_paragraph(translator, node)

    html = "".join(translator.body)
    assert html == '<p class="caption"></p>\n'


def test_modified_translator_mosaic_row_renders_images(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    translator_factory: Callable[..., core.ModifiedHTMLTranslator],
    mosaic_row_factory: Callable[..., nodes.container],
) -> None:
    """Render mosaic rows by resizing images to a shared height."""
    translator = translator_factory(tmp_path)
    row = mosaic_row_factory(
        tmp_path,
        images=("image1.png", "image2.png"),
    )

    class DummyImage:
        """Stub image with fixed dimensions for mosaics."""

        def __init__(self, width: int, height: int) -> None:
            """Store the provided width and height."""
            self.width = width
            self.height = height

        def resize(self, size: Tuple[int, int], resample: Any = None) -> Any:
            """Update dimensions and return self."""
            self.width, self.height = size
            return self

        def save(self, path: str) -> None:
            """Pretend to save the image."""
            return None

    sequence = [
        DummyImage(100, 50),
        DummyImage(50, 50),
        DummyImage(100, 50),
        DummyImage(50, 50),
    ]
    monkeypatch.setattr(core.PIL.Image, "open", lambda *_: sequence.pop(0))

    with pytest.raises(nodes.SkipNode):
        core.ModifiedHTMLTranslator.visit_container(translator, row)

    html = "".join(translator.body)
    assert "\n<div class=\"mosaic\"" in html
    assert "<div class=\"mosaic\" style" not in html
    assert "margin-bottom" not in html
    assert "--ar: 2.0000;" in html
    assert "--ar: 1.0000;" in html
    assert "\n    <img" in html
    assert "margin-right" not in html
    assert "width:" not in html
    assert "height:" not in html


def test_modified_translator_mosaic_row_skips_when_no_images(
    tmp_path: Any,
    translator_factory: Callable[..., core.ModifiedHTMLTranslator],
    mosaic_row_factory: Callable[..., nodes.container],
) -> None:
    """Handle mosaic rows without images gracefully."""
    translator = translator_factory(tmp_path)
    row = mosaic_row_factory(tmp_path)

    with pytest.raises(nodes.SkipNode):
        core.ModifiedHTMLTranslator.visit_container(translator, row)

    html = "".join(translator.body)
    assert "<div class=\"mosaic\"" in html


def test_modified_translator_mosaic_border_px(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    translator_factory: Callable[..., core.ModifiedHTMLTranslator],
    mosaic_row_factory: Callable[..., nodes.container],
) -> None:
    """Convert mosaic border px to percent."""
    translator = translator_factory(tmp_path)
    row = mosaic_row_factory(
        tmp_path,
        border="10px",
        images=("image1.png", "image2.png"),
    )

    class DummyImage:
        """Stub image for border calculations."""

        def __init__(self, width: int, height: int) -> None:
            """Store dimensions for border tests."""
            self.width = width
            self.height = height

        def resize(self, size: Tuple[int, int], resample: Any = None) -> Any:
            """Return self without changes."""
            return self

        def save(self, path: str) -> None:
            """Pretend to save the image."""
            return None

    sequence = [DummyImage(100, 100), DummyImage(100, 100)]
    monkeypatch.setattr(core.PIL.Image, "open", lambda *_: sequence.pop(0))

    with pytest.raises(nodes.SkipNode):
        core.ModifiedHTMLTranslator.visit_container(translator, row)

    html = "".join(translator.body)
    assert "margin-right" not in html
    assert "--ar: 1.0000;" in html


def test_modified_translator_mosaic_no_upscale(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    translator_factory: Callable[..., core.ModifiedHTMLTranslator],
    mosaic_row_factory: Callable[..., nodes.container],
) -> None:
    """Avoid upscaling mosaic images past their original size."""
    translator = translator_factory(tmp_path)
    row = mosaic_row_factory(
        tmp_path,
        images=("image1.png",),
    )
    row["mosaic_last"] = True

    class DummyImage:
        """Stub image that tracks resize usage."""

        def __init__(self, width: int, height: int) -> None:
            """Store dimensions and resize flag."""
            self.width = width
            self.height = height
            self.resized = False

        def resize(self, size: Tuple[int, int], resample: Any = None) -> Any:
            """Mark the image as resized and return self."""
            self.resized = True
            return self

        def save(self, path: str) -> None:
            """Pretend to save the image."""
            return None

    dummy = DummyImage(200, 100)
    monkeypatch.setattr(core.PIL.Image, "open", lambda *_: dummy)

    with pytest.raises(nodes.SkipNode):
        core.ModifiedHTMLTranslator.visit_container(translator, row)

    html = "".join(translator.body)
    assert "margin-bottom" not in html
    assert dummy.resized is False


def test_modified_translator_mosaic_border_invalid_defaults(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    translator_factory: Callable[..., core.ModifiedHTMLTranslator],
    mosaic_row_factory: Callable[..., nodes.container],
) -> None:
    """Fallback to default border when border value is invalid."""
    translator = translator_factory(tmp_path)
    row = mosaic_row_factory(
        tmp_path,
        border="bad",
        images=("image1.png", "image2.png"),
    )

    class DummyImage:
        """Stub image for invalid border tests."""

        def __init__(self, width: int, height: int) -> None:
            """Store dimensions for border tests."""
            self.width = width
            self.height = height

        def resize(self, size: Tuple[int, int], resample: Any = None) -> Any:
            """Return self without changes."""
            return self

        def save(self, path: str) -> None:
            """Pretend to save the image."""
            return None

    sequence = [DummyImage(100, 50), DummyImage(50, 50)]
    monkeypatch.setattr(core.PIL.Image, "open", lambda *_: sequence.pop(0))

    with pytest.raises(nodes.SkipNode):
        core.ModifiedHTMLTranslator.visit_container(translator, row)

    html = "".join(translator.body)
    assert "margin-right" not in html


def test_modified_translator_mosaic_border_negative_clamped(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    translator_factory: Callable[..., core.ModifiedHTMLTranslator],
    mosaic_row_factory: Callable[..., nodes.container],
) -> None:
    """Clamp negative border percent to zero."""
    translator = translator_factory(tmp_path)
    row = mosaic_row_factory(
        tmp_path,
        border="-5%",
        images=("image1.png", "image2.png"),
    )

    class DummyImage:
        """Stub image for negative border tests."""

        def __init__(self, width: int, height: int) -> None:
            """Store dimensions for border tests."""
            self.width = width
            self.height = height

        def resize(self, size: Tuple[int, int], resample: Any = None) -> Any:
            """Return self without changes."""
            return self

        def save(self, path: str) -> None:
            """Pretend to save the image."""
            return None

    sequence = [DummyImage(100, 100), DummyImage(100, 100)]
    monkeypatch.setattr(core.PIL.Image, "open", lambda *_: sequence.pop(0))

    with pytest.raises(nodes.SkipNode):
        core.ModifiedHTMLTranslator.visit_container(translator, row)

    html = "".join(translator.body)
    assert "margin-right" not in html
    assert "margin-bottom" not in html


def test_modified_translator_mosaic_zero_height(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    translator_factory: Callable[..., core.ModifiedHTMLTranslator],
    mosaic_row_factory: Callable[..., nodes.container],
) -> None:
    """Handle images with zero height safely."""
    translator = translator_factory(tmp_path)
    row = mosaic_row_factory(
        tmp_path,
        images=("image1.png",),
    )

    class DummyImage:
        """Stub image for zero-height tests."""

        def __init__(self, width: int, height: int) -> None:
            """Store dimensions for zero-height tests."""
            self.width = width
            self.height = height

        def resize(self, size: Tuple[int, int], resample: Any = None) -> Any:
            """Return self without changes."""
            return self

        def save(self, path: str) -> None:
            """Pretend to save the image."""
            return None

    dummy = DummyImage(100, 0)
    monkeypatch.setattr(core.PIL.Image, "open", lambda *_: dummy)

    with pytest.raises(nodes.SkipNode):
        core.ModifiedHTMLTranslator.visit_container(translator, row)

    html = "".join(translator.body)
    assert "--ar: 0.0000;" in html
    assert "width:" not in html
    assert "height:" not in html


def test_modified_translator_mosaic_width_numeric(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    translator_factory: Callable[..., core.ModifiedHTMLTranslator],
    mosaic_row_factory: Callable[..., nodes.container],
) -> None:
    """Parse numeric mosaic width values."""
    translator = translator_factory(tmp_path)
    row = mosaic_row_factory(
        tmp_path,
        width="300",
        border="10px",
        images=("image1.png",),
    )

    class DummyImage:
        """Stub image for numeric width test."""

        def __init__(self) -> None:
            """Set sample dimensions."""
            self.width = 100
            self.height = 50

        def resize(self, size: Tuple[int, int], resample: Any = None) -> Any:
            """Return self without changes."""
            return self

        def save(self, path: str) -> None:
            """Pretend to save the image."""
            return None

    monkeypatch.setattr(core.PIL.Image, "open", lambda *_: DummyImage())

    with pytest.raises(nodes.SkipNode):
        core.ModifiedHTMLTranslator.visit_container(translator, row)

    assert "<div class=\"mosaic\">" in "".join(translator.body)


def test_modified_translator_mosaic_width_px(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    translator_factory: Callable[..., core.ModifiedHTMLTranslator],
    mosaic_row_factory: Callable[..., nodes.container],
) -> None:
    """Parse pixel mosaic width values."""
    translator = translator_factory(tmp_path)
    row = mosaic_row_factory(
        tmp_path,
        width="300px",
        images=("image1.png",),
    )

    class DummyImage:
        """Stub image for pixel width test."""

        def __init__(self) -> None:
            """Set sample dimensions."""
            self.width = 100
            self.height = 50

        def resize(self, size: Tuple[int, int], resample: Any = None) -> Any:
            """Return self without changes."""
            return self

        def save(self, path: str) -> None:
            """Pretend to save the image."""
            return None

    monkeypatch.setattr(core.PIL.Image, "open", lambda *_: DummyImage())

    with pytest.raises(nodes.SkipNode):
        core.ModifiedHTMLTranslator.visit_container(translator, row)

    assert "<div class=\"mosaic\">" in "".join(translator.body)


def test_modified_translator_mosaic_width_invalid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    translator_factory: Callable[..., core.ModifiedHTMLTranslator],
    mosaic_row_factory: Callable[..., nodes.container],
) -> None:
    """Ignore invalid mosaic width values."""
    translator = translator_factory(tmp_path)
    row = mosaic_row_factory(
        tmp_path,
        width="bad",
        images=("image1.png",),
    )

    class DummyImage:
        """Stub image for invalid width test."""

        def __init__(self) -> None:
            """Set sample dimensions."""
            self.width = 100
            self.height = 50

        def resize(self, size: Tuple[int, int], resample: Any = None) -> Any:
            """Return self without changes."""
            return self

        def save(self, path: str) -> None:
            """Pretend to save the image."""
            return None

    monkeypatch.setattr(core.PIL.Image, "open", lambda *_: DummyImage())

    with pytest.raises(nodes.SkipNode):
        core.ModifiedHTMLTranslator.visit_container(translator, row)

    assert "<div class=\"mosaic\">" in "".join(translator.body)


def test_modified_translator_mosaic_border_invalid_percent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    translator_factory: Callable[..., core.ModifiedHTMLTranslator],
    mosaic_row_factory: Callable[..., nodes.container],
) -> None:
    """Fallback when border percent is invalid."""
    translator = translator_factory(tmp_path)
    row = mosaic_row_factory(
        tmp_path,
        border="bad%",
        images=("image1.png",),
    )

    class DummyImage:
        """Stub image for invalid percent border."""

        def __init__(self) -> None:
            """Set sample dimensions."""
            self.width = 100
            self.height = 50

        def resize(self, size: Tuple[int, int], resample: Any = None) -> Any:
            """Return self without changes."""
            return self

        def save(self, path: str) -> None:
            """Pretend to save the image."""
            return None

    monkeypatch.setattr(core.PIL.Image, "open", lambda *_: DummyImage())

    with pytest.raises(nodes.SkipNode):
        core.ModifiedHTMLTranslator.visit_container(translator, row)

    assert "<div class=\"mosaic\">" in "".join(translator.body)


def test_modified_translator_mosaic_border_invalid_px(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    translator_factory: Callable[..., core.ModifiedHTMLTranslator],
    mosaic_row_factory: Callable[..., nodes.container],
) -> None:
    """Fallback when border px is invalid."""
    translator = translator_factory(tmp_path)
    row = mosaic_row_factory(
        tmp_path,
        border="badpx",
        images=("image1.png",),
    )

    class DummyImage:
        """Stub image for invalid px border."""

        def __init__(self) -> None:
            """Set sample dimensions."""
            self.width = 100
            self.height = 50

        def resize(self, size: Tuple[int, int], resample: Any = None) -> Any:
            """Return self without changes."""
            return self

        def save(self, path: str) -> None:
            """Pretend to save the image."""
            return None

    monkeypatch.setattr(core.PIL.Image, "open", lambda *_: DummyImage())

    with pytest.raises(nodes.SkipNode):
        core.ModifiedHTMLTranslator.visit_container(translator, row)

    assert "<div class=\"mosaic\">" in "".join(translator.body)


def test_modified_translator_mosaic_resizes_large_images(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    translator_factory: Callable[..., core.ModifiedHTMLTranslator],
    mosaic_row_factory: Callable[..., nodes.container],
) -> None:
    """Resize mosaic images to computed width from target linewidth."""
    translator = translator_factory(tmp_path)
    row = mosaic_row_factory(
        tmp_path,
        images=("image1.png",),
    )

    class DummyImage:
        """Stub image for max width resizing."""

        def __init__(self) -> None:
            """Set oversize dimensions."""
            self.width = 500
            self.height = 250
            self.resize_args: Tuple[int, int] | None = None

        def resize(self, size: Tuple[int, int], resample: Any = None) -> Any:
            """Capture resize arguments and return self."""
            self.resize_args = size
            return self

        def save(self, path: str) -> None:
            """Pretend to save the image."""
            return None

    dummy = DummyImage()
    monkeypatch.setattr(core.PIL.Image, "open", lambda *_: dummy)

    with pytest.raises(nodes.SkipNode):
        core.ModifiedHTMLTranslator.visit_container(translator, row)

    assert dummy.resize_args == (200, 100)


def test_modified_translator_mosaic_caption_container(
    tmp_path: Any,
    translator_factory: Callable[..., core.ModifiedHTMLTranslator],
) -> None:
    """Render mosaic caption containers with custom markup."""
    translator = translator_factory(tmp_path)
    node = nodes.container(classes=["mosaic-caption"])

    core.ModifiedHTMLTranslator.visit_container(translator, node)

    assert translator.body == [
        '<div class="docutils container mosaic-caption">'
    ]


def test_modified_translator_delegates_to_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Delegate to base translator when no mosaic special cases apply."""
    calls: list[str] = []

    def fake_visit_container(self: Any, node: nodes.Node) -> None:
        """Track container visits."""
        calls.append("visit_container")

    def fake_depart_container(self: Any, node: nodes.Node) -> None:
        """Track container departures."""
        calls.append("depart_container")

    def fake_visit_paragraph(self: Any, node: nodes.paragraph) -> None:
        """Track paragraph visits."""
        calls.append("visit_paragraph")

    def fake_depart_paragraph(self: Any, node: nodes.paragraph) -> None:
        """Track paragraph departures."""
        calls.append("depart_paragraph")

    monkeypatch.setattr(core.HTMLTranslator, "visit_container",
                        fake_visit_container)
    monkeypatch.setattr(core.HTMLTranslator, "depart_container",
                        fake_depart_container)
    monkeypatch.setattr(core.HTMLTranslator, "visit_paragraph",
                        fake_visit_paragraph)
    monkeypatch.setattr(core.HTMLTranslator, "depart_paragraph",
                        fake_depart_paragraph)

    translator = core.ModifiedHTMLTranslator.__new__(
        core.ModifiedHTMLTranslator
    )
    container = nodes.container(classes=["regular"])
    paragraph = nodes.paragraph()

    core.ModifiedHTMLTranslator.visit_container(translator, container)
    core.ModifiedHTMLTranslator.depart_container(translator, container)
    core.ModifiedHTMLTranslator.visit_paragraph(translator, paragraph)
    core.ModifiedHTMLTranslator.depart_paragraph(translator, paragraph)

    assert calls == [
        "visit_container",
        "depart_container",
        "visit_paragraph",
        "depart_paragraph",
    ]
