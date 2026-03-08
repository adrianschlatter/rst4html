from __future__ import annotations

import importlib
from typing import Any, Dict

import pytest

core = importlib.import_module("rst4html.rst4html")


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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
