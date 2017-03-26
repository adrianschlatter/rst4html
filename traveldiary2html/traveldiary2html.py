# -*- coding: utf-8 -*-
"""
Reader and Writer supporting special features useful for travel-diary creation
"""

from docutils.readers.standalone import Reader as Standalone
from docutils.writers.html4css1 import Writer as HtmlWriter
from docutils.writers.html4css1 import HTMLTranslator
from .utils import export
from json import loads, JSONDecodeError
from os.path import join, basename, exists, isdir
from os import mkdir, listdir
from shutil import copyfile


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


@export
class Writer(HtmlWriter):
    """
    HtmlWriter that copies images from their original location into a
    configurable image directory.
    """

    settings_spec = HtmlWriter.settings_spec[0:2] + (
                        HtmlWriter.settings_spec[2] +
                        (('Copy images to this directory',
                          ['--imgtargetdir'],
                          {'type': str, 'default': 'img'}),
                         ),)

    def __init__(self):
        super().__init__()
        self.translator_class = ModifiedHTMLTranslator

    def write(self, document, destination):
        imgtargetdir = document.settings.imgtargetdir
        if exists(imgtargetdir):
            if not isdir(imgtargetdir):
                raise RuntimeError('imgtargetdir is not a directory')
            elif listdir(imgtargetdir):
                raise RuntimeError('imgtargetdir is not empty')
        else:
            mkdir(imgtargetdir)

        super().write(document, destination)


class ModifiedHTMLTranslator(HTMLTranslator):

    """
    Specialized HTMLTranslator that copies images from their original
    location and places them in a separate image directory.
    """

    def visit_image(self, node):
        uri = node['uri']
        newuri = join(self.settings.imgtargetdir, basename(uri))
        node['uri'] = newuri
        copyfile(uri, newuri)

        super().visit_image(node)
