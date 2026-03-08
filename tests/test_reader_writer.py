from __future__ import annotations

import importlib
import types
from typing import Any, Dict

import pytest
from docutils.io import StringInput
from docutils.parsers.rst import Parser

core = importlib.import_module("rst4html.rst4html")


def test_export_decorator_adds_to_all() -> None:
    """Ensure export decorator populates __all__."""
    assert "Reader" in core.__all__
    assert "Writer" in core.__all__


def test_reader_substitution_success(make_reader_settings: Any) -> None:
    """Verify variable substitution replaces placeholders."""
    reader = core.Reader()
    parser = Parser()
    settings = make_reader_settings(reader, parser)
    settings.varsubst = '{"name": "World"}'
    source = StringInput(source="Hello {name}")
    document = reader.read(source, parser, settings)
    assert document.astext() == "Hello World"


def test_reader_invalid_json(make_reader_settings: Any) -> None:
    """Raise JSONDecodeError for invalid substitution JSON."""
    reader = core.Reader()
    parser = Parser()
    settings = make_reader_settings(reader, parser)
    settings.varsubst = "not-json"
    source = StringInput(source="Hello")
    with pytest.raises(core.JSONDecodeError) as exc:
        reader.read(source, parser, settings)
    assert exc.value.msg == "Unable to parse variable substitutions"


def test_reader_missing_variable(make_reader_settings: Any) -> None:
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


def test_writer_keeps_empty_target_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
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
