# -*- coding: utf-8 -*-
"""
"""

from docutils.readers.standalone import Reader as Standalone
from .utils import export


@export
class Reader(Standalone):
    """Standalone reader adding support for variable substitution at runtime"""

    def __init__(self, parser=None, parser_name=None):
        super().__init__(parser=parser, parser_name=parser_name)
        self.varsubst = {'imp': 'where/my/images/are'}

    def read(self, source, parser, settings):
        self.source = source
        if not self.parser:
            self.parser = parser
        self.settings = settings
        self.input = self.source.read().format(**self.varsubst)
        self.parse()
        return self.document
