from __future__ import annotations

import importlib
import types
from typing import Any, Callable, Tuple

import pytest
from docutils import frontend, nodes
from docutils.parsers.rst import Parser
from docutils.utils import new_document

core = importlib.import_module("rst4html.rst4html")


@pytest.fixture
def make_reader_settings() -> Callable[[Any, Any], Any]:
    def factory(reader: Any, parser: Any) -> Any:
        return frontend.get_default_settings(reader, parser)

    return factory


@pytest.fixture
def build_mosaic_doctree() -> Callable[[str], nodes.document]:
    def factory(content: str) -> nodes.document:
        parser = Parser()
        settings = frontend.get_default_settings(parser)
        document = new_document("test", settings=settings)
        parser.parse(content, document)
        return document

    return factory


@pytest.fixture
def translator_factory() -> Callable[[Any, int], core.ModifiedHTMLTranslator]:
    def factory(
        tmp_path: Any,
        targetlinewidth: int = 200,
    ) -> core.ModifiedHTMLTranslator:
        translator = core.ModifiedHTMLTranslator.__new__(
            core.ModifiedHTMLTranslator
        )
        translator.settings = types.SimpleNamespace(
            imgtargetdir=str(tmp_path),
            targetlinewidth=targetlinewidth,
        )
        translator.body = []
        return translator

    return factory


@pytest.fixture
def mosaic_row_factory(
            ) -> Callable[[Any, str, str, Tuple[str, ...]], nodes.container]:
    def factory(
        tmp_path: Any,
        width: str = "100%",
        border: str = "2%",
        images: Tuple[str, ...] = (),
    ) -> nodes.container:
        row = nodes.container(classes=["mosaic-row"])
        row["mosaic_width"] = width
        row["mosaic_border"] = border
        for image in images:
            row += nodes.image(uri=str(tmp_path / image))
        return row

    return factory
