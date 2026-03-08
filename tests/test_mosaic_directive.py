from __future__ import annotations

import importlib
from typing import Any

import pytest
from docutils import nodes

core = importlib.import_module("rst4html.rst4html")


def test_mosaic_chunks_single_column_when_no_args() -> None:
    """Chunk images into single-column rows when no args provided."""
    images = ["a.png", "b.png", "c.png"]
    rows = core._chunk_images(images, [])
    assert rows == [["a.png"], ["b.png"], ["c.png"]]


def test_mosaic_chunks_adds_remaining_as_row_when_args_short() -> None:
    """Chunk images and append remaining images as one row."""
    images = ["a.png", "b.png", "c.png", "d.png", "e.png"]
    rows = core._chunk_images(images, [2])
    assert rows == [["a.png", "b.png"], ["c.png", "d.png", "e.png"]]


def test_mosaic_chunks_truncates_when_args_too_long() -> None:
    """Chunk images using args until images are exhausted."""
    images = ["a.png", "b.png", "c.png"]
    rows = core._chunk_images(images, [2, 2, 1])
    assert rows == [["a.png", "b.png"], ["c.png"]]


def test_mosaic_chunks_breaks_when_no_remaining() -> None:
    """Stop chunking once all images are consumed."""
    images = ["a.png", "b.png"]
    rows = core._chunk_images(images, [1, 1, 1])
    assert rows == [["a.png"], ["b.png"]]


def test_mosaic_parse_arguments_accepts_positive_counts() -> None:
    """Parse mosaic arguments into positive integers."""
    counts = core._parse_mosaic_arguments(["1", "3"])
    assert counts == [1, 3]


def test_mosaic_parse_arguments_rejects_zero() -> None:
    """Reject zero or negative mosaic arguments."""
    with pytest.raises(ValueError):
        core._parse_mosaic_arguments(["0"])


def test_mosaic_parse_arguments_rejects_negative() -> None:
    """Reject negative mosaic arguments."""
    with pytest.raises(ValueError):
        core._parse_mosaic_arguments(["-1"])


def test_mosaic_parse_arguments_rejects_non_integer() -> None:
    """Reject non-integer mosaic arguments."""
    with pytest.raises(ValueError):
        core._parse_mosaic_arguments(["two"])


def test_mosaic_directive_builds_rows_and_caption(
    build_mosaic_doctree: Any,
) -> None:
    """Parse mosaic directive into row containers and caption."""
    content = (
        ".. mosaic:: 2 1\n"
        "   :width: 80%\n"
        "   :img: image1.png\n"
        "   :img: image2.png\n"
        "   :img: image3.png\n"
        "\n"
        "   Mosaic caption.\n"
    )
    document = build_mosaic_doctree(content)
    containers = list(document.findall(nodes.container))
    rows = [
        node for node in containers if "mosaic-row" in node.get("classes", [])
    ]
    assert len(rows) == 2
    assert "figure" in rows[0].get("classes", [])
    assert rows[0]["mosaic_width"] == "80%"
    images_in_row_0 = [
        child for child in rows[0] if isinstance(child, nodes.image)
    ]
    images_in_row_1 = [
        child for child in rows[1] if isinstance(child, nodes.image)
    ]
    assert len(images_in_row_0) == 2
    assert len(images_in_row_1) == 1
    paragraphs = list(document.findall(nodes.paragraph))
    caption = next(
        node for node in paragraphs if "caption" in node.get("classes", [])
    )
    assert "2 1" not in caption.astext()


def test_mosaic_directive_reports_mismatch_and_renders(
    build_mosaic_doctree: Any,
) -> None:
    """Report mismatched arguments but still build mosaic rows."""
    content = (
        ".. mosaic:: 2 2\n"
        "   :img: image1.png\n"
        "   :img: image2.png\n"
        "   :img: image3.png\n"
    )
    document = build_mosaic_doctree(content)
    errors = list(document.findall(nodes.system_message))
    assert any("mosaic directive" in node.astext() for node in errors)
    containers = list(document.findall(nodes.container))
    rows = [
        node for node in containers if "mosaic-row" in node.get("classes", [])
    ]
    assert len(rows) == 2
    images_in_row_0 = [
        child for child in rows[0] if isinstance(child, nodes.image)
    ]
    images_in_row_1 = [
        child for child in rows[1] if isinstance(child, nodes.image)
    ]
    assert len(images_in_row_0) == 2
    assert len(images_in_row_1) == 1


def test_mosaic_directive_defaults_width_and_skips_width_caption(
    build_mosaic_doctree: Any,
) -> None:
    """Default width to 100% and ignore width line in caption."""
    content = (
        ".. mosaic::\n"
        "   :width: 60%\n"
        "   :border: 3%\n"
        "   :img: image1.png\n"
        "\n"
        "   Caption text.\n"
    )
    document = build_mosaic_doctree(content)
    containers = list(document.findall(nodes.container))
    rows = [
        node for node in containers if "mosaic-row" in node.get("classes", [])
    ]
    assert rows[0]["mosaic_width"] == "60%"
    assert rows[0]["mosaic_border"] == "3%"
    paragraphs = list(document.findall(nodes.paragraph))
    caption = next(
        node for node in paragraphs if "caption" in node.get("classes", [])
    )
    caption_text = caption.astext()
    assert ":width:" not in caption_text
    assert ":border:" not in caption_text


def test_mosaic_directive_uses_specified_width_line(
    build_mosaic_doctree: Any,
) -> None:
    """Use width parsed from content lines."""
    content = (
        ".. mosaic::\n"
        "   :width: 75%\n"
        "   :img: image1.png\n"
    )
    document = build_mosaic_doctree(content)
    containers = list(document.findall(nodes.container))
    rows = [
        node for node in containers if "mosaic-row" in node.get("classes", [])
    ]
    assert rows[0]["mosaic_width"] == "75%"
    assert rows[0]["mosaic_border"] == "2%"


def test_mosaic_directive_no_caption_when_only_img_and_width(
    build_mosaic_doctree: Any,
) -> None:
    """Do not create caption when no caption content exists."""
    content = (
        ".. mosaic::\n"
        "   :width: 80%\n"
        "   :img: image1.png\n"
    )
    document = build_mosaic_doctree(content)
    containers = list(document.findall(nodes.container))
    captions = [
        node for node in containers if isinstance(node, nodes.paragraph)
    ]
    captions = [
        node for node in captions if "caption" in node.get("classes", [])
    ]
    assert not captions


def test_mosaic_directive_invalid_argument_reports_error_only(
    build_mosaic_doctree: Any,
) -> None:
    """Invalid arguments return a system message node."""
    content = ".. mosaic:: 0\n   :img: image1.png\n"
    document = build_mosaic_doctree(content)
    errors = list(document.findall(nodes.system_message))
    assert errors
    containers = list(document.findall(nodes.container))
    rows = [
        node for node in containers if "mosaic-row" in node.get("classes", [])
    ]
    assert not rows
