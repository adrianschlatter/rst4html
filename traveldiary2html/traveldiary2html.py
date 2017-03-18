# -*- coding: utf-8 -*-
"""
"""

from docutils.readers.standalone import Reader as Standalone
from .utils import export
from json import loads, JSONDecodeError


@export
class Reader(Standalone):
    """Standalone reader adding support for variable substitution at runtime"""

    settings_spec = Standalone.settings_spec[0:2] + (
                        Standalone.settings_spec[2] +
                        (('Define variable substitutions as a JSON dictionary',
                          ['--subst'],
                          {'type': str, 'default': "{}", 'dest': 'varsubst'}),
                         ),)

    config_section = 'variable-substituting reader'
    config_section_dependencies = ('standalone reader', 'readers')

    def read(self, source, parser, settings):
        self.source = source
        if not self.parser:
            self.parser = parser
        try:
            settings.varsubst = loads(settings.varsubst)
        except JSONDecodeError as e:
            raise JSONDecodeError('Unable to parse variable substitutions',
                                  e.doc, e.pos)

        self.settings = settings
        self.input = self.source.read()
        try:
            self.input = self.input.format(**settings.varsubst)
        except KeyError:
            raise KeyError('Error during substitution of variables')
        self.parse()
        return self.document
