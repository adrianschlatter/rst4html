# -*- coding: utf-8 -*-
"""
Reader and writer helpers for docutils with image processing and mosaics.

Features include:

- copying images to a target directory
- autorotation of images
- scaling of images according to rst attributes
- mosaic directive rendering
"""

from __future__ import annotations

# flake8: noqa: W504

from typing import Any, Dict, List, Sequence, Tuple

from docutils import nodes
from docutils.parsers.rst import Directive, directives
from docutils.readers.standalone import Reader as Standalone
from docutils.statemachine import StringList
from docutils.writers.html4css1 import Writer as HtmlWriter
from docutils.writers.html4css1 import HTMLTranslator
from .utils import export
from json import loads, JSONDecodeError
from os.path import join, basename, exists, isdir
from os import mkdir, listdir
import PIL.Image
import PIL.ExifTags


DEFAULT_MOSAIC_WIDTH = '100%'
DEFAULT_MOSAIC_BORDER = '2%'
DEFAULT_MOSAIC_BORDER_PERCENT = 2.0
MOSAIC_MAX_WIDTH = 425


def _parse_mosaic_arguments(arguments: Sequence[str]) -> List[int]:
    """Parse mosaic row counts from directive arguments."""
    if not arguments:
        return []
    counts: List[int] = []
    for arg in arguments:
        value = int(arg)
        if value < 1:
            raise ValueError('mosaic arguments must be positive integers')
        counts.append(value)
    return counts


def _chunk_images(imgs: Sequence[str], counts: Sequence[int]) -> List[List[str]]:
    """Split image URIs into rows based on the provided counts."""
    if not counts:
        return [[img] for img in imgs]
    if sum(counts) <= len(imgs):
        rows: List[List[str]] = []
        start = 0
        for count in counts:
            rows.append(list(imgs[start:start + count]))
            start += count
        remaining = imgs[start:]
        if remaining:
            rows.append(list(remaining))
        return rows

    rows = []
    start = 0
    for count in counts:
        remaining = len(imgs) - start
        if remaining <= 0:
            break
        if remaining < count:
            rows.append(list(imgs[start:]))
            break
        rows.append(list(imgs[start:start + count]))
        start += count
    return rows


def _parse_mosaic_width(mosaic_width: Any, targetlinewidth: int) -> int:
    """Parse mosaic width values into pixels."""
    width = targetlinewidth
    if isinstance(mosaic_width, str) and mosaic_width.endswith('%'):
        width = int(float(mosaic_width[:-1]) * 1e-2 * width)
    elif isinstance(mosaic_width, str) and mosaic_width.endswith('px'):
        width = int(mosaic_width[:-2])
    else:
        try:
            width = int(mosaic_width)
        except (TypeError, ValueError):
            pass
    return width


def _parse_mosaic_border(mosaic_border: Any, width: int) -> float:
    """Parse mosaic border values into percent."""
    border_percent = DEFAULT_MOSAIC_BORDER_PERCENT
    if isinstance(mosaic_border, str) and mosaic_border.endswith('%'):
        try:
            border_percent = float(mosaic_border[:-1])
        except ValueError:
            border_percent = DEFAULT_MOSAIC_BORDER_PERCENT
    elif isinstance(mosaic_border, str) and mosaic_border.endswith('px'):
        try:
            border_px = float(mosaic_border[:-2])
            border_percent = (border_px / width * 100) if width else 0.0
        except ValueError:
            border_percent = DEFAULT_MOSAIC_BORDER_PERCENT
    else:
        try:
            border_percent = float(mosaic_border)
        except (TypeError, ValueError):
            border_percent = DEFAULT_MOSAIC_BORDER_PERCENT
    if border_percent < 0:
        border_percent = 0.0
    return border_percent


def _prepare_mosaic_image(
    image: nodes.image,
    imgtargetdir: str,
    max_width: int,
) -> Tuple[str, float]:
    """Copy and resize mosaic images as needed."""
    img = PIL.Image.open(image['uri'])
    ratio = img.width / img.height if img.height else 0
    newuri = join(imgtargetdir, basename(image['uri']))
    if img.width > max_width and img.height:
        newwidth = max_width
        newheight = int(newwidth / ratio) if ratio else img.height
        img = img.resize((newwidth, newheight), resample=PIL.Image.LANCZOS)
    img.save(newuri)
    image['uri'] = newuri
    return newuri, ratio


def _render_mosaic_images(image_entries: Sequence[Tuple[str, float]]) -> str:
    """Render mosaic image HTML snippets."""
    lines = []
    for newuri, ratio in image_entries:
        lines.append(
            '    <img src="{0}" style="--ar: {1:.4f};">\n'.format(
                newuri,
                ratio,
            )
        )
    return "".join(lines)


class Mosaic(Directive):
    """Directive that renders image mosaics with optional captions."""

    has_content = True
    option_spec: Dict[str, Any] = {}

    def run(self) -> List[nodes.Node]:
        """Parse the directive body into mosaic rows and caption nodes."""
        args_line = self.block_text.splitlines()[0]
        args_part = args_line.split('::', 1)[1].strip() if '::' in args_line else ''
        raw_args = args_part.split() if args_part else []
        try:
            counts = _parse_mosaic_arguments(raw_args)
        except ValueError as exc:
            return [self.state_machine.reporter.error(
                str(exc),
                line=self.lineno,
            )]

        images = []
        width = DEFAULT_MOSAIC_WIDTH
        border = DEFAULT_MOSAIC_BORDER
        for line in self.content:
            stripped = line.strip()
            if stripped.startswith(':img:'):
                images.append(stripped[5:].strip())
                continue
            if stripped.startswith(':width:'):
                width = stripped[7:].strip()
                continue
            if stripped.startswith(':border:'):
                border = stripped[8:].strip()
                continue

        specified_total = sum(counts) if counts else len(images)
        if counts and specified_total != len(images):
            message = (
                'mosaic directive on line {0}: arguments specify {1} '
                'images, but {2} were provided'
            ).format(self.lineno, specified_total, len(images))
            error = self.state_machine.reporter.error(message, line=self.lineno)
        else:
            error = None

        rows = _chunk_images(images, counts)
        non_empty_rows = [row for row in rows if row]
        row_nodes = []
        for row_index, row in enumerate(non_empty_rows):
            row_node = nodes.container(classes=['figure', 'mosaic-row'])
            row_node['mosaic_width'] = width
            row_node['mosaic_border'] = border
            row_node['mosaic_last'] = row_index == len(non_empty_rows) - 1
            for uri in row:
                image = nodes.image(uri=uri)
                row_node += image
            row_nodes.append(row_node)

        caption_lines = []
        for line in self.content:
            stripped = line.strip()
            if (
                stripped.startswith(':img:')
                or stripped.startswith(':width:')
                or stripped.startswith(':border:')
                or (args_part and stripped == args_part)
            ):
                continue
            caption_lines.append(line)
        caption_node = None
        if any(line.strip() for line in caption_lines):
            caption_node = nodes.paragraph(classes=['caption'])
            caption_node['mosaic_caption'] = True
            self.state.nested_parse(
                StringList(caption_lines),
                self.content_offset,
                caption_node,
            )

        nodes_out = [error] + row_nodes
        if caption_node is not None:
            nodes_out.append(caption_node)
        return [node for node in nodes_out if node]


directives.register_directive('mosaic', Mosaic)


@export
class Reader(Standalone):
    """Standalone reader adding support for variable substitution at runtime."""

    settings_spec = Standalone.settings_spec[0:2] + (
        Standalone.settings_spec[2]
        + (
            (
                'Define variable substitutions as a JSON dictionary',
                ['--subst'],
                {'type': str, 'default': "{}", 'dest': 'varsubst'},
            ),
        ),
    )

    config_section = 'variable-substituting reader'
    config_section_dependencies = ('standalone reader', 'readers')

    def read(
        self,
        source: Any,
        parser: Any,
        settings: Any,
    ) -> nodes.document:
        """Read, substitute variables, and parse into a document tree."""
        self.source = source
        if not self.parser:
            self.parser = parser
        try:
            settings.varsubst = loads(settings.varsubst)
        except JSONDecodeError as exc:
            raise JSONDecodeError(
                'Unable to parse variable substitutions',
                exc.doc,
                exc.pos,
            )

        self.settings = settings
        self.input = self.source.read()
        try:
            self.input = self.input.format(**settings.varsubst)
        except KeyError as exc:
            raise KeyError('Error during substitution of variables') from exc
        self.parse()
        return self.document


@export
class Writer(HtmlWriter):
    """HTML writer that copies images into a configurable output directory."""

    settings_spec = HtmlWriter.settings_spec[0:2] + (
        HtmlWriter.settings_spec[2]
        + (
            (
                'Copy images to this directory',
                ['--imgtargetdir'],
                {'type': str, 'default': 'img'},
            ),
            (
                'Line width in pixels for picture size calculation',
                ['--targetlinewidth'],
                {'type': int},
            ),
        ),
    )

    config_section = 'html4css1 with image-copies writer'

    def __init__(self) -> None:
        """Configure the custom HTML translator."""
        super().__init__()
        self.translator_class = ModifiedHTMLTranslator

    def write(self, document: Any, destination: Any) -> None:
        """Validate the target image directory before writing output."""
        imgtargetdir = document.settings.imgtargetdir
        if exists(imgtargetdir):
            if not isdir(imgtargetdir):
                raise RuntimeError('imgtargetdir is not a directory')
            if listdir(imgtargetdir):
                raise RuntimeError('imgtargetdir is not empty')
        else:
            mkdir(imgtargetdir)

        super().write(document, destination)


class ModifiedHTMLTranslator(HTMLTranslator):
    """HTML translator that copies and rescales images for output."""

    exiftrans = {
        1: (),
        2: (PIL.Image.FLIP_LEFT_RIGHT,),
        3: (PIL.Image.ROTATE_180,),
        4: (PIL.Image.FLIP_TOP_BOTTOM,),
        5: (PIL.Image.TRANSPOSE,),
        6: (PIL.Image.ROTATE_270,),
        7: (PIL.Image.FLIP_LEFT_RIGHT, PIL.Image.ROTATE_270),
        8: (PIL.Image.ROTATE_90,),
    }

    def visit_container(self, node: nodes.Node) -> None:
        """Render mosaic rows with custom HTML and image processing."""
        if 'mosaic-row' in node.get('classes', []):
            if not getattr(self, '_mosaic_opened', False):
                self.body.append('\n')
                self._mosaic_opened = True
            mosaic_width = node.get('mosaic_width', DEFAULT_MOSAIC_WIDTH)
            mosaic_border = node.get('mosaic_border', DEFAULT_MOSAIC_BORDER)
            width = _parse_mosaic_width(mosaic_width, self.settings.targetlinewidth)
            border_percent = _parse_mosaic_border(mosaic_border, width)

            images = [child for child in node if isinstance(child, nodes.image)]
            image_entries: List[Tuple[str, float]] = []
            max_width = MOSAIC_MAX_WIDTH
            for image in images:
                newuri, ratio = _prepare_mosaic_image(
                    image,
                    self.settings.imgtargetdir,
                    max_width,
                )
                image_entries.append((newuri, ratio))

            self.body.append('<div class="mosaic">\n')
            self.body.append(_render_mosaic_images(image_entries))
            self.body.append('</div>\n')
            raise nodes.SkipNode

        if 'mosaic-caption' in node.get('classes', []):
            self.body.append('<div class="docutils container mosaic-caption">')
            return

        super().visit_container(node)

    def depart_container(self, node: nodes.Node) -> None:
        """Defer to the base container handling."""
        super().depart_container(node)

    def visit_paragraph(self, node: nodes.paragraph) -> None:
        """Render mosaic captions as plain paragraph tags."""
        if node.get('mosaic_caption', False):
            self.body.append('<p class="caption">')
            return
        super().visit_paragraph(node)

    def depart_paragraph(self, node: nodes.paragraph) -> None:
        """Close mosaic caption paragraphs without extra whitespace."""
        if node.get('mosaic_caption', False):
            self.body.append('</p>\n')
            return
        super().depart_paragraph(node)

    def visit_image(self, node: nodes.image) -> None:
        """Copy, rotate, and resize images before emitting HTML."""
        uri = node['uri']
        newuri = join(self.settings.imgtargetdir, basename(uri))
        node['uri'] = newuri

        if type(self.settings.targetlinewidth) != int:
            raise TypeError(
                'You need to specify an integer for --targetlinewidth'
            )

        tlw = self.settings.targetlinewidth
        img = PIL.Image.open(uri)

        # autorotate jpegs:
        if img.format == 'JPEG':
            # determine orientation:
            tags = dict(
                [(PIL.ExifTags.TAGS.get(k, k), v) for k, v in img._getexif().items()]
            )
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
                raise NotImplementedError(
                    'width {0} not understood'.format(node['width'])
                )
        height = img.height
        newheight = int(newwidth / width * height)
        img = img.resize((newwidth, newheight), resample=PIL.Image.LANCZOS)

        # store image:
        img.save(newuri)
        # XXX PIL loses EXIF information

        super().visit_image(node)
