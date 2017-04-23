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

# check for the Python Imaging Library
try:
    import PIL.Image
    import PIL.ExifTags
except ImportError:
    try:  # sometimes PIL modules are put in PYTHONPATH's root
        import Image
        import ExifTags

        class PIL(object):
            pass  # dummy wrapper

        PIL.Image = Image
        PIL.ExifTags = ExifTags
    except ImportError:
        PIL = None


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
                         ('Line width in pixels for picture size calculation',
                          ['--targetlinewidth'],
                          {'type': int})),
                    )

    config_section = 'html4css1 with image-copies writer'

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

    exiftrans = {1: (),
                 2: (PIL.Image.FLIP_LEFT_RIGHT,),
                 3: (PIL.Image.ROTATE_180,),
                 4: (PIL.Image.FLIP_TOP_BOTTOM,),
                 5: (PIL.Image.TRANSPOSE, ),
                 6: (PIL.Image.ROTATE_270,),
                 7: (PIL.Image.FLIP_LEFT_RIGHT, PIL.Image.ROTATE_270),
                 8: (PIL.Image.ROTATE_90,)}

    def visit_image(self, node):
        uri = node['uri']
        newuri = join(self.settings.imgtargetdir, basename(uri))
        node['uri'] = newuri

        if type(self.settings.targetlinewidth) != int:
            raise TypeError('You need to specify an integer '
                            'for --targetlinewidth')

        tlw = self.settings.targetlinewidth
        img = PIL.Image.open(uri)

        # autorotate jpegs:
        if img.format == 'JPEG':
            # determine orientation:
            tags = dict([(PIL.ExifTags.TAGS.get(k, k), v)
                         for k, v in img._getexif().items()])
            orientation = tags.get('Orientation', 1)  # default means 'upright'

            # rotate and scale image
            for op in self.exiftrans[orientation]:
                img = img.transpose(op)

        # scale image:
        width = img.width
        newwidth = img.width
        if node.hasattr('width'):
            if node['width'][-1] == '%':
                newwidth = int(float(node['width'][:-1]) * 1e-2 * tlw)
            elif node['width'][-2:] == 'px':
                newwidth = int(node['width'][:-2])
            else:
                raise NotImplemented('width {0} not understood'.format(
                                                            node['width']))
        height = img.height
        newheight = int(newwidth / width * height)
        img = img.resize((newwidth, newheight), resample=PIL.Image.LANCZOS)

        # store image:
        img.save(newuri)
        # XXX PIL loses EXIF information

        super().visit_image(node)
