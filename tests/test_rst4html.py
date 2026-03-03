import importlib
import types

import pytest
from docutils import nodes
from docutils.frontend import OptionParser
from docutils.io import StringInput
from docutils.parsers.rst import Parser

core = importlib.import_module("rst4html.rst4html")


def load_rst4html_module(monkeypatch, importer):
    import builtins
    import importlib.util
    import sys
    from pathlib import Path

    original_import = builtins.__import__

    def wrapped_import(name, globals=None, locals=None, fromlist=(), level=0):
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
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "rst4html"
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def make_reader_settings(reader, parser):
    return OptionParser(components=(reader, parser)).get_default_values()


def test_export_decorator_adds_to_all():
    """Ensure export decorator populates __all__."""
    assert "Reader" in core.__all__
    assert "Writer" in core.__all__


def test_reader_substitution_success():
    """Verify variable substitution replaces placeholders."""
    reader = core.Reader()
    parser = Parser()
    settings = make_reader_settings(reader, parser)
    settings.varsubst = '{"name": "World"}'
    source = StringInput(source="Hello {name}")
    document = reader.read(source, parser, settings)
    assert document.astext() == "Hello World"


def test_reader_invalid_json():
    """Raise JSONDecodeError for invalid substitution JSON."""
    reader = core.Reader()
    parser = Parser()
    settings = make_reader_settings(reader, parser)
    settings.varsubst = "not-json"
    source = StringInput(source="Hello")
    with pytest.raises(core.JSONDecodeError) as exc:
        reader.read(source, parser, settings)
    assert exc.value.msg == "Unable to parse variable substitutions"


def test_reader_missing_variable():
    """Raise KeyError when a substitution key is missing."""
    reader = core.Reader()
    parser = Parser()
    settings = make_reader_settings(reader, parser)
    settings.varsubst = "{}"
    source = StringInput(source="Hello {missing}")
    with pytest.raises(KeyError) as exc:
        reader.read(source, parser, settings)
    assert "Error during substitution of variables" in str(exc.value)


def test_writer_rejects_non_empty_target_dir(tmp_path):
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


def test_writer_rejects_file_target(tmp_path):
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


def test_writer_creates_target_dir_and_writes(monkeypatch, tmp_path):
    """Create target dir and delegate writing."""
    imgtargetdir = tmp_path / "imgs"
    document = types.SimpleNamespace(
        settings=types.SimpleNamespace(
            imgtargetdir=str(imgtargetdir),
            targetlinewidth=100,
        )
    )
    writer = core.Writer()

    called = {}

    def fake_write(self, document, destination):
        called["document"] = document
        called["destination"] = destination

    monkeypatch.setattr(core.HtmlWriter, "write", fake_write)
    writer.write(document, destination=None)
    assert imgtargetdir.is_dir()
    assert called["document"] is document


def test_writer_keeps_empty_target_dir(monkeypatch, tmp_path):
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

    called = {}

    def fake_write(self, document, destination):
        called["document"] = document
        called["destination"] = destination

    monkeypatch.setattr(core.HtmlWriter, "write", fake_write)
    writer.write(document, destination=None)
    assert called["document"] is document


def test_modified_translator_requires_integer_targetlinewidth():
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


def test_modified_translator_rejects_unknown_width(monkeypatch):
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
        format = "PNG"
        width = 100
        height = 50

        def resize(self, size, resample=None):
            return self

        def save(self, path):
            return None

    def fake_open(path):
        return DummyImage()

    monkeypatch.setattr(core.PIL.Image, "open", fake_open)
    with pytest.raises(NotImplementedError) as exc:
        core.ModifiedHTMLTranslator.visit_image(translator, node)
    assert "width 2em not understood" in str(exc.value)


def test_modified_translator_scales_percent_width(monkeypatch, tmp_path):
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
        format = "PNG"
        width = 400
        height = 200

        def __init__(self):
            self.resize_args = None
            self.saved = None

        def resize(self, size, resample=None):
            self.resize_args = (size, resample)
            return self

        def save(self, path):
            self.saved = path

    dummy = DummyImage()

    def fake_open(path):
        return dummy

    monkeypatch.setattr(core.PIL.Image, "open", fake_open)
    monkeypatch.setattr(core.HTMLTranslator, "visit_image", lambda *_: None)

    core.ModifiedHTMLTranslator.visit_image(translator, node)
    assert dummy.resize_args[0] == (100, 50)
    assert dummy.saved.endswith("image.jpg")


def test_modified_translator_scales_px_width(monkeypatch, tmp_path):
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
        format = "PNG"
        width = 400
        height = 200

        def __init__(self):
            self.resize_args = None
            self.saved = None

        def resize(self, size, resample=None):
            self.resize_args = (size, resample)
            return self

        def save(self, path):
            self.saved = path

    dummy = DummyImage()

    def fake_open(path):
        return dummy

    monkeypatch.setattr(core.PIL.Image, "open", fake_open)
    monkeypatch.setattr(core.HTMLTranslator, "visit_image", lambda *_: None)

    core.ModifiedHTMLTranslator.visit_image(translator, node)
    assert dummy.resize_args[0] == (50, 25)
    assert dummy.saved.endswith("image.jpg")


def test_modified_translator_autorotates_jpeg(monkeypatch, tmp_path):
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
        format = "JPEG"
        width = 100
        height = 50

        def __init__(self):
            self.ops = []
            self.resize_args = None
            self.saved = None

        def _getexif(self):
            return {274: 6}

        def transpose(self, op):
            self.ops.append(op)
            return self

        def resize(self, size, resample=None):
            self.resize_args = (size, resample)
            return self

        def save(self, path):
            self.saved = path

    dummy = DummyImage()

    def fake_open(path):
        return dummy

    monkeypatch.setattr(core.PIL.Image, "open", fake_open)
    monkeypatch.setattr(core.PIL.ExifTags, "TAGS", {274: "Orientation"})
    monkeypatch.setattr(core.HTMLTranslator, "visit_image", lambda *_: None)

    core.ModifiedHTMLTranslator.visit_image(translator, node)
    assert dummy.ops == list(core.ModifiedHTMLTranslator.exiftrans[6])
    assert dummy.resize_args[0] == (50, 25)


def test_cmdl_main_invokes_docutils(monkeypatch):
    """Call docutils publish_cmdline with expected args."""
    cmdl = importlib.import_module("rst4html.__cmdl__")
    docutils_core = importlib.import_module("docutils.core")
    locale_module = importlib.import_module("locale")
    called = {}

    def fake_publish_cmdline(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(docutils_core, "publish_cmdline", fake_publish_cmdline)
    monkeypatch.setattr(docutils_core, "default_description", "default-desc")

    def fake_setlocale(category, value):
        called["locale"] = (category, value)

    monkeypatch.setattr(locale_module, "setlocale", fake_setlocale)
    cmdl.main()

    assert called["reader_name"] == "rst4html"
    assert called["writer_name"] == "rst4html"
    assert "default-desc" in called["description"]
    assert called["locale"][1] == ""


def test_cmdl_main_uses_custom_reader_writer(monkeypatch):
    """Pass custom reader and writer instances."""
    cmdl = importlib.import_module("rst4html.__cmdl__")
    docutils_core = importlib.import_module("docutils.core")
    locale_module = importlib.import_module("locale")
    captured = {}

    def fake_publish_cmdline(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(docutils_core, "publish_cmdline", fake_publish_cmdline)
    monkeypatch.setattr(docutils_core, "default_description", "default-desc")
    monkeypatch.setattr(locale_module, "setlocale", lambda *_: None)
    cmdl.main()

    assert isinstance(captured["reader"], core.Reader)
    assert isinstance(captured["writer"], core.Writer)


def test_imports_with_pil_available(monkeypatch):
    """Load module when PIL is available."""
    def importer(original, name, globals, locals, fromlist, level):
        return original(name, globals, locals, fromlist, level)

    module = load_rst4html_module(monkeypatch, importer)
    assert module.PIL is not None


def test_imports_with_legacy_pil(monkeypatch):
    """Fallback to legacy PIL imports when needed."""
    class DummyImage:
        FLIP_LEFT_RIGHT = object()
        ROTATE_180 = object()
        FLIP_TOP_BOTTOM = object()
        TRANSPOSE = object()
        ROTATE_270 = object()
        ROTATE_90 = object()

    class DummyExifTags:
        TAGS = {}

    def importer(original, name, globals, locals, fromlist, level):
        if name.startswith("PIL"):
            raise ImportError("no PIL")
        if name == "Image":
            return DummyImage
        if name == "ExifTags":
            return DummyExifTags
        return original(name, globals, locals, fromlist, level)

    module = load_rst4html_module(monkeypatch, importer)
    assert module.PIL.Image is DummyImage
    assert module.PIL.ExifTags is DummyExifTags


def test_imports_with_no_pil(monkeypatch):
    """Fail initialization when no PIL modules exist."""
    def importer(original, name, globals, locals, fromlist, level):
        if name.startswith("PIL") or name in {"Image", "ExifTags"}:
            raise ImportError("no PIL")
        return original(name, globals, locals, fromlist, level)

    with pytest.raises(AttributeError):
        load_rst4html_module(monkeypatch, importer)
