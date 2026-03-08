"""Test suite for the rst4html package."""

from __future__ import annotations

import importlib
import types
from typing import Any, Callable, Dict, Tuple

import pytest
from docutils import nodes
from docutils import frontend
from docutils.io import StringInput
from docutils.parsers.rst import Parser
from docutils.utils import new_document

core = importlib.import_module("rst4html.rst4html")


def load_rst4html_module(monkeypatch: pytest.MonkeyPatch,
                         importer: Callable[..., Any],) -> Any:
    """Import the module via a custom import hook for PIL scenarios."""
    import builtins
    import importlib.util
    import sys
    from pathlib import Path

    original_import = builtins.__import__

    def wrapped_import(
        name: str,
        globals: Dict[str, Any] | None = None,
        locals: Dict[str, Any] | None = None,
        fromlist: Tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        """Proxy imports through the provided importer."""
        return importer(
            original_import,
            name,
            globals,
            locals,
            fromlist,
            level,
        )

    monkeypatch.setattr(builtins, "__import__", wrapped_import)
    path = (
        Path(__file__).resolve().parents[1]
        / "rst4html"
        / "rst4html.py"
    )
    module_name = "rst4html_testmod_{0}".format(id(importer))
    spec = importlib.util.spec_from_file_location(
        module_name,
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load test module")
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "rst4html"
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def make_reader_settings(reader: Any, parser: Any) -> Any:
    """Construct default reader settings for tests."""
    return frontend.get_default_settings(reader, parser)


def build_mosaic_doctree(content: str) -> nodes.document:
    """Parse mosaic directives into a docutils document tree."""
    parser = Parser()
    settings = frontend.get_default_settings(parser)
    document = new_document("test", settings=settings)
    parser.parse(content, document)
    return document


def test_export_decorator_adds_to_all() -> None:
    """Ensure export decorator populates __all__."""
    assert "Reader" in core.__all__
    assert "Writer" in core.__all__


def test_reader_substitution_success() -> None:
    """Verify variable substitution replaces placeholders."""
    reader = core.Reader()
    parser = Parser()
    settings = make_reader_settings(reader, parser)
    settings.varsubst = '{"name": "World"}'
    source = StringInput(source="Hello {name}")
    document = reader.read(source, parser, settings)
    assert document.astext() == "Hello World"


def test_reader_invalid_json() -> None:
    """Raise JSONDecodeError for invalid substitution JSON."""
    reader = core.Reader()
    parser = Parser()
    settings = make_reader_settings(reader, parser)
    settings.varsubst = "not-json"
    source = StringInput(source="Hello")
    with pytest.raises(core.JSONDecodeError) as exc:
        reader.read(source, parser, settings)
    assert exc.value.msg == "Unable to parse variable substitutions"


def test_reader_missing_variable() -> None:
    """Raise KeyError when a substitution key is missing."""
    reader = core.Reader()
    parser = Parser()
    settings = make_reader_settings(reader, parser)
    settings.varsubst = "{}"
    source = StringInput(source="Hello {missing}")
    with pytest.raises(KeyError) as exc:
        reader.read(source, parser, settings)
    assert "Error during substitution of variables" in str(exc.value)


def test_writer_rejects_non_empty_target_dir(tmp_path: Any) -> None:
    """Reject non-empty image target directories."""
    imgtargetdir = tmp_path / "imgs"
    imgtargetdir.mkdir()
    (imgtargetdir / "file.txt").write_text("data")
    document = types.SimpleNamespace(
        settings=types.SimpleNamespace(imgtargetdir=str(imgtargetdir))
    )
    writer = core.Writer()
    with pytest.raises(RuntimeError) as exc:
        writer.write(document, destination=None)
    assert "imgtargetdir is not empty" in str(exc.value)


def test_writer_rejects_file_target(tmp_path: Any) -> None:
    """Reject image target paths that are files."""
    file_target = tmp_path / "imgtarget_file"
    file_target.write_text("data")
    document = types.SimpleNamespace(
        settings=types.SimpleNamespace(imgtargetdir=str(file_target))
    )
    writer = core.Writer()
    with pytest.raises(RuntimeError) as exc:
        writer.write(document, destination=None)
    assert "imgtargetdir is not a directory" in str(exc.value)


def test_writer_creates_target_dir_and_writes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    """Create target dir and delegate writing."""
    imgtargetdir = tmp_path / "imgs"
    document = types.SimpleNamespace(
        settings=types.SimpleNamespace(
            imgtargetdir=str(imgtargetdir),
            targetlinewidth=100,
        )
    )
    writer = core.Writer()

    called: Dict[str, Any] = {}

    def fake_write(self: Any, document: Any, destination: Any) -> None:
        """Capture the document and destination passed to HtmlWriter."""
        called["document"] = document
        called["destination"] = destination

    monkeypatch.setattr(core.HtmlWriter, "write", fake_write)
    writer.write(document, destination=None)
    assert imgtargetdir.is_dir()
    assert called["document"] is document


def test_writer_keeps_empty_target_dir(monkeypatch: pytest.MonkeyPatch,
                                       tmp_path: Any) -> None:
    """Allow existing empty target directories."""
    imgtargetdir = tmp_path / "imgs"
    imgtargetdir.mkdir()
    document = types.SimpleNamespace(
        settings=types.SimpleNamespace(
            imgtargetdir=str(imgtargetdir),
            targetlinewidth=100,
        )
    )
    writer = core.Writer()

    called: Dict[str, Any] = {}

    def fake_write(self: Any, document: Any, destination: Any) -> None:
        """Capture the document and destination passed to HtmlWriter."""
        called["document"] = document
        called["destination"] = destination

    monkeypatch.setattr(core.HtmlWriter, "write", fake_write)
    writer.write(document, destination=None)
    assert called["document"] is document


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
                                    monkeypatch: pytest.MonkeyPatch) -> None:
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
                                    tmp_path: Any) -> None:
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
                                tmp_path: Any) -> None:
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
                                    tmp_path: Any) -> None:
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


def test_cmdl_main_invokes_docutils(monkeypatch: pytest.MonkeyPatch) -> None:
    """Call docutils publish_cmdline with expected args."""
    cmdl = importlib.import_module("rst4html.__cmdl__")
    docutils_core = importlib.import_module("docutils.core")
    locale_module = importlib.import_module("locale")
    called: Dict[str, Any] = {}

    def fake_publish_cmdline(**kwargs: Any) -> None:
        """Capture publish_cmdline invocation arguments."""
        called.update(kwargs)

    monkeypatch.setattr(docutils_core, "publish_cmdline", fake_publish_cmdline)
    monkeypatch.setattr(docutils_core, "default_description", "default-desc")

    def fake_setlocale(category: Any, value: Any) -> None:
        """Capture locale settings for the test."""
        called["locale"] = (category, value)

    monkeypatch.setattr(locale_module, "setlocale", fake_setlocale)
    cmdl.main()

    assert called["reader_name"] == "rst4html"
    assert called["writer_name"] == "rst4html"
    assert "default-desc" in called["description"]
    assert called["locale"][1] == ""


def test_cmdl_main_run_as_script(monkeypatch: pytest.MonkeyPatch) -> None:
    """Execute __cmdl__ main when run as a script."""
    import runpy

    docutils_core = importlib.import_module("docutils.core")
    locale_module = importlib.import_module("locale")
    called: Dict[str, Any] = {}

    def fake_publish_cmdline(**kwargs: Any) -> None:
        """Capture publish_cmdline invocation arguments."""
        called.update(kwargs)

    def noop_setlocale(*_: Any) -> None:
        """Disable locale side effects for the test."""
        return None

    monkeypatch.setattr(docutils_core, "publish_cmdline", fake_publish_cmdline)
    monkeypatch.setattr(docutils_core, "default_description", "default-desc")
    monkeypatch.setattr(locale_module, "setlocale", noop_setlocale)

    runpy.run_module("rst4html.__cmdl__", run_name="__main__")
    assert called["reader_name"] == "rst4html"


def test_cmdl_main_uses_custom_reader_writer(
                                    monkeypatch: pytest.MonkeyPatch) -> None:
    """Pass custom reader and writer instances."""
    cmdl = importlib.import_module("rst4html.__cmdl__")
    docutils_core = importlib.import_module("docutils.core")
    locale_module = importlib.import_module("locale")
    captured: Dict[str, Any] = {}

    def fake_publish_cmdline(**kwargs: Any) -> None:
        """Capture publish_cmdline invocation arguments."""
        captured.update(kwargs)

    def noop_setlocale(*_: Any) -> None:
        """Disable locale side effects for the test."""
        return None

    monkeypatch.setattr(docutils_core, "publish_cmdline", fake_publish_cmdline)
    monkeypatch.setattr(docutils_core, "default_description", "default-desc")
    monkeypatch.setattr(locale_module, "setlocale", noop_setlocale)
    cmdl.main()

    assert isinstance(captured["reader"], core.Reader)
    assert isinstance(captured["writer"], core.Writer)


def test_imports_with_pil_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Load module when PIL is available."""

    def importer(original: Any, name: str, *args: Any, **kwargs: Any) -> Any:
        """Use the standard import path."""
        return original(name, *args, **kwargs)

    module = load_rst4html_module(monkeypatch, importer)
    assert module.PIL is not None


def test_imports_with_legacy_pil(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fallback to legacy PIL imports when needed."""

    class DummyImage:
        """Legacy PIL image stub with transformation constants."""

        FLIP_LEFT_RIGHT = object()
        ROTATE_180 = object()
        FLIP_TOP_BOTTOM = object()
        TRANSPOSE = object()
        ROTATE_270 = object()
        ROTATE_90 = object()

    class DummyExifTags:
        """Legacy PIL ExifTags stub."""

        TAGS: Dict[int, str] = {}

    def importer(
        original: Any,
        name: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Simulate legacy PIL module locations."""
        if name.startswith("PIL"):
            raise ImportError("no PIL")
        if name == "Image":
            return DummyImage
        if name == "ExifTags":
            return DummyExifTags
        return original(name, *args, **kwargs)

    module = load_rst4html_module(monkeypatch, importer)
    assert module.PIL.Image is DummyImage
    assert module.PIL.ExifTags is DummyExifTags


def test_imports_with_no_pil(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail initialization when no PIL modules exist."""

    def importer(original: Any, name: str, *args: Any, **kwargs: Any,) -> Any:
        """Force ImportError for PIL-related imports."""
        if name.startswith("PIL") or name in {"Image", "ExifTags"}:
            raise ImportError("no PIL")
        return original(name, *args, **kwargs)

    with pytest.raises(AttributeError):
        load_rst4html_module(monkeypatch, importer)


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


def test_mosaic_directive_builds_rows_and_caption() -> None:
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


def test_mosaic_directive_reports_mismatch_and_renders() -> None:
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


def test_mosaic_directive_defaults_width_and_skips_width_caption() -> None:
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


def test_mosaic_directive_uses_specified_width_line() -> None:
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


def test_mosaic_directive_no_caption_when_only_img_and_width() -> None:
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


def test_mosaic_directive_invalid_argument_reports_error_only() -> None:
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
                                        tmp_path: Any) -> None:
    """Render mosaic rows by resizing images to a shared height."""
    translator = core.ModifiedHTMLTranslator.__new__(
        core.ModifiedHTMLTranslator
    )
    translator.settings = types.SimpleNamespace(
        imgtargetdir=str(tmp_path),
        targetlinewidth=200,
    )
    translator.body = []
    row = nodes.container(classes=["mosaic-row"])
    row["mosaic_width"] = "100%"
    row["mosaic_border"] = "2%"
    row += nodes.image(uri=str(tmp_path / "image1.png"))
    row += nodes.image(uri=str(tmp_path / "image2.png"))

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
                                                        tmp_path: Any) -> None:
    """Handle mosaic rows without images gracefully."""
    translator = core.ModifiedHTMLTranslator.__new__(
        core.ModifiedHTMLTranslator
    )
    translator.settings = types.SimpleNamespace(
        imgtargetdir=str(tmp_path),
        targetlinewidth=200,
    )
    translator.body = []
    row = nodes.container(classes=["mosaic-row"])
    row["mosaic_width"] = "100%"
    row["mosaic_border"] = "2%"

    with pytest.raises(nodes.SkipNode):
        core.ModifiedHTMLTranslator.visit_container(translator, row)

    html = "".join(translator.body)
    assert "<div class=\"mosaic\"" in html


def test_modified_translator_mosaic_border_px(monkeypatch: pytest.MonkeyPatch,
                                              tmp_path: Any) -> None:
    """Convert mosaic border px to percent."""
    translator = core.ModifiedHTMLTranslator.__new__(
        core.ModifiedHTMLTranslator
    )
    translator.settings = types.SimpleNamespace(
        imgtargetdir=str(tmp_path),
        targetlinewidth=200,
    )
    translator.body = []
    row = nodes.container(classes=["mosaic-row"])
    row["mosaic_width"] = "100%"
    row["mosaic_border"] = "10px"
    row += nodes.image(uri=str(tmp_path / "image1.png"))
    row += nodes.image(uri=str(tmp_path / "image2.png"))

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


def test_modified_translator_mosaic_no_upscale(monkeypatch: pytest.MonkeyPatch,
                                               tmp_path: Any) -> None:
    """Avoid upscaling mosaic images past their original size."""
    translator = core.ModifiedHTMLTranslator.__new__(
        core.ModifiedHTMLTranslator
    )
    translator.settings = types.SimpleNamespace(
        imgtargetdir=str(tmp_path),
        targetlinewidth=200,
    )
    translator.body = []
    row = nodes.container(classes=["mosaic-row"])
    row["mosaic_width"] = "100%"
    row["mosaic_border"] = "2%"
    row["mosaic_last"] = True
    row += nodes.image(uri=str(tmp_path / "image1.png"))

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
                                            tmp_path: Any) -> None:
    """Fallback to default border when border value is invalid."""
    translator = core.ModifiedHTMLTranslator.__new__(
        core.ModifiedHTMLTranslator
    )
    translator.settings = types.SimpleNamespace(
        imgtargetdir=str(tmp_path),
        targetlinewidth=200,
    )
    translator.body = []
    row = nodes.container(classes=["mosaic-row"])
    row["mosaic_width"] = "100%"
    row["mosaic_border"] = "bad"
    row += nodes.image(uri=str(tmp_path / "image1.png"))
    row += nodes.image(uri=str(tmp_path / "image2.png"))

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
                                            tmp_path: Any) -> None:
    """Clamp negative border percent to zero."""
    translator = core.ModifiedHTMLTranslator.__new__(
        core.ModifiedHTMLTranslator
    )
    translator.settings = types.SimpleNamespace(
        imgtargetdir=str(tmp_path),
        targetlinewidth=200,
    )
    translator.body = []
    row = nodes.container(classes=["mosaic-row"])
    row["mosaic_width"] = "100%"
    row["mosaic_border"] = "-5%"
    row += nodes.image(uri=str(tmp_path / "image1.png"))
    row += nodes.image(uri=str(tmp_path / "image2.png"))

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
                                            tmp_path: Any) -> None:
    """Handle images with zero height safely."""
    translator = core.ModifiedHTMLTranslator.__new__(
        core.ModifiedHTMLTranslator
    )
    translator.settings = types.SimpleNamespace(
        imgtargetdir=str(tmp_path),
        targetlinewidth=200,
    )
    translator.body = []
    row = nodes.container(classes=["mosaic-row"])
    row["mosaic_width"] = "100%"
    row["mosaic_border"] = "2%"
    row += nodes.image(uri=str(tmp_path / "image1.png"))

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


def test_mosaic_chunks_breaks_when_no_remaining() -> None:
    """Stop chunking once all images are consumed."""
    images = ["a.png", "b.png"]
    rows = core._chunk_images(images, [1, 1, 1])
    assert rows == [["a.png"], ["b.png"]]


def test_modified_translator_mosaic_width_numeric(
                                            monkeypatch: pytest.MonkeyPatch,
                                            tmp_path: Any) -> None:
    """Parse numeric mosaic width values."""
    translator = core.ModifiedHTMLTranslator.__new__(
        core.ModifiedHTMLTranslator
    )
    translator.settings = types.SimpleNamespace(
        imgtargetdir=str(tmp_path),
        targetlinewidth=200,
    )
    translator.body = []
    row = nodes.container(classes=["mosaic-row"])
    row["mosaic_width"] = "300"
    row["mosaic_border"] = "10px"
    row += nodes.image(uri=str(tmp_path / "image1.png"))

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
) -> None:
    """Parse pixel mosaic width values."""
    translator = core.ModifiedHTMLTranslator.__new__(
        core.ModifiedHTMLTranslator
    )
    translator.settings = types.SimpleNamespace(
        imgtargetdir=str(tmp_path),
        targetlinewidth=200,
    )
    translator.body = []
    row = nodes.container(classes=["mosaic-row"])
    row["mosaic_width"] = "300px"
    row["mosaic_border"] = "2%"
    row += nodes.image(uri=str(tmp_path / "image1.png"))

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
                                        tmp_path: Any) -> None:
    """Ignore invalid mosaic width values."""
    translator = core.ModifiedHTMLTranslator.__new__(
        core.ModifiedHTMLTranslator
    )
    translator.settings = types.SimpleNamespace(
        imgtargetdir=str(tmp_path),
        targetlinewidth=200,
    )
    translator.body = []
    row = nodes.container(classes=["mosaic-row"])
    row["mosaic_width"] = "bad"
    row["mosaic_border"] = "2%"
    row += nodes.image(uri=str(tmp_path / "image1.png"))

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
                                            tmp_path: Any) -> None:
    """Fallback when border percent is invalid."""
    translator = core.ModifiedHTMLTranslator.__new__(
        core.ModifiedHTMLTranslator
    )
    translator.settings = types.SimpleNamespace(
        imgtargetdir=str(tmp_path),
        targetlinewidth=200,
    )
    translator.body = []
    row = nodes.container(classes=["mosaic-row"])
    row["mosaic_width"] = "100%"
    row["mosaic_border"] = "bad%"
    row += nodes.image(uri=str(tmp_path / "image1.png"))

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
                                            tmp_path: Any) -> None:
    """Fallback when border px is invalid."""
    translator = core.ModifiedHTMLTranslator.__new__(
        core.ModifiedHTMLTranslator
    )
    translator.settings = types.SimpleNamespace(
        imgtargetdir=str(tmp_path),
        targetlinewidth=200,
    )
    translator.body = []
    row = nodes.container(classes=["mosaic-row"])
    row["mosaic_width"] = "100%"
    row["mosaic_border"] = "badpx"
    row += nodes.image(uri=str(tmp_path / "image1.png"))

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
                                            tmp_path: Any) -> None:
    """Resize mosaic images that exceed the max width."""
    translator = core.ModifiedHTMLTranslator.__new__(
        core.ModifiedHTMLTranslator
    )
    translator.settings = types.SimpleNamespace(
        imgtargetdir=str(tmp_path),
        targetlinewidth=200,
    )
    translator.body = []
    row = nodes.container(classes=["mosaic-row"])
    row["mosaic_width"] = "100%"
    row["mosaic_border"] = "2%"
    row += nodes.image(uri=str(tmp_path / "image1.png"))

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

    assert dummy.resize_args == (425, 212)


def test_modified_translator_mosaic_caption_container(tmp_path: Any) -> None:
    """Render mosaic caption containers with custom markup."""
    translator = core.ModifiedHTMLTranslator.__new__(
        core.ModifiedHTMLTranslator
    )
    translator.settings = types.SimpleNamespace(
        imgtargetdir=str(tmp_path),
        targetlinewidth=200,
    )
    translator.body = []
    node = nodes.container(classes=["mosaic-caption"])

    core.ModifiedHTMLTranslator.visit_container(translator, node)

    assert translator.body == [
        '<div class="docutils container mosaic-caption">'
    ]


def test_modified_translator_delegates_to_base(
                                    monkeypatch: pytest.MonkeyPatch) -> None:
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
