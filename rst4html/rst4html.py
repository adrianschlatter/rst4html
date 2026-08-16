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

from math import floor
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
    if type(targetlinewidth) != int or targetlinewidth <= 0:
        raise TypeError('You need to specify a positive integer for --targetlinewidth')

    width = targetlinewidth
    if isinstance(mosaic_width, str):
        value = mosaic_width.strip()
        try:
            if value.endswith('%'):
                percent = float(value[:-1])
                if percent <= 0:
                    raise ValueError('mosaic width must be greater than 0')
                width = int(targetlinewidth * percent * 1e-2)
            elif value.endswith('px'):
                pixels = float(value[:-2])
                if pixels <= 0:
                    raise ValueError('mosaic width must be greater than 0')
                width = int(pixels)
            else:
                pixels = float(value)
                if pixels <= 0:
                    raise ValueError('mosaic width must be greater than 0')
                width = int(pixels)
        except ValueError:
            width = targetlinewidth
    else:
        try:
            pixels = int(mosaic_width)
            if pixels <= 0:
                raise ValueError
            width = pixels
        except (TypeError, ValueError):
            width = targetlinewidth

    return width


def _parse_mosaic_border(mosaic_border: Any, width: int) -> float:
    """Parse mosaic border values into percent."""
    if width <= 0:
        raise ValueError('mosaic width must be greater than 0')

    border_percent = 2.0
    if isinstance(mosaic_border, str):
        value = mosaic_border.strip()
        try:
            if value.endswith('%'):
                border_percent = float(value[:-1])
            elif value.endswith('px'):
                border_px = float(value[:-2])
                border_percent = border_px / width * 100
            else:
                border_percent = float(value)
        except ValueError:
            border_percent = 2.0
    else:
        try:
            border_percent = float(mosaic_border)
        except (TypeError, ValueError):
            border_percent = 2.0

    if border_percent < 0:
        border_percent = 0.0
    return border_percent


def _calculate_mosaic_image_geometry(
    image_dimensions: Sequence[Tuple[int, int]],
    mosaic_width: int,
    border_percent: float,
) -> List[Tuple[int, int]]:
    """Compute image widths and heights from the CSS sizing contract."""
    if mosaic_width <= 0:
        raise ValueError('mosaic width must be greater than 0')
    if border_percent < 0:
        raise ValueError('mosaic border cannot be negative')

    if not image_dimensions:
        return []

    image_count = len(image_dimensions)
    gap_count = image_count - 1
    gap_width = floor(mosaic_width * border_percent * 1e-2)
    gaps_total = gap_width * gap_count
    available_width = mosaic_width - gaps_total
    if available_width <= 0:
        raise ValueError('mosaic border leaves no room for images')

    aspect_ratios = [
        (width / height) if width > 0 and height > 0 else 0.0
        for width, height in image_dimensions
    ]

    positive_ratios = [ratio for ratio in aspect_ratios if ratio > 0]
    if not positive_ratios:
        return [(width, height) for width, height in image_dimensions]

    row_height = max(1, int(available_width / sum(positive_ratios)))

    constrained_height = row_height
    for ratio, (source_width, source_height) in zip(aspect_ratios, image_dimensions):
        if ratio <= 0 or source_width <= 0 or source_height <= 0:
            continue
        max_height = int(source_width / ratio)
        constrained_height = min(constrained_height, max_height)

    desired_widths: List[int] = []
    for ratio, (source_width, source_height) in zip(aspect_ratios, image_dimensions):
        if ratio <= 0 or source_width <= 0 or source_height <= 0:
            desired_widths.append(source_width)
            continue
        width = max(1, min(source_width, int(constrained_height * ratio)))
        desired_widths.append(width)

    total_width = sum(desired_widths)
    remaining = available_width - total_width
    if remaining > 0:
        for index in range(image_count):
            source_width = image_dimensions[index][0]
            if desired_widths[index] < source_width:
                room = source_width - desired_widths[index]
                add = min(remaining, room)
                desired_widths[index] += add
                remaining -= add
                if remaining <= 0:
                    break

    final_geometry: List[Tuple[int, int]] = []
    for index, ((source_width, source_height), ratio) in enumerate(
        zip(image_dimensions, aspect_ratios)
    ):
        width = desired_widths[index]
        if ratio <= 0 or source_width <= 0 or source_height <= 0:
            final_geometry.append((source_width, source_height))
            continue
        height = min(source_height, max(1, int(width / ratio)))
        final_geometry.append((width, height))

    return final_geometry


def _prepare_mosaic_images(
    images: Sequence[nodes.image],
    imgtargetdir: str,
    mosaic_width: int,
    border_percent: float,
) -> List[Tuple[str, float, int, int]]:
    """Copy and resize mosaic images as needed."""
    opened_images: List[Tuple[nodes.image, Any]] = []
    image_dimensions: List[Tuple[int, int]] = []
    for image in images:
        img = PIL.Image.open(image['uri'])
        opened_images.append((image, img))
        image_dimensions.append((img.width, img.height))

    geometry = _calculate_mosaic_image_geometry(
        image_dimensions,
        mosaic_width,
        border_percent,
    )

    image_entries: List[Tuple[str, float, int, int]] = []
    for (image, img), (target_width, target_height) in zip(opened_images, geometry):
        ratio = img.width / img.height if img.height else 0
        newuri = join(imgtargetdir, basename(image['uri']))

        newwidth = img.width
        newheight = img.height
        if img.width and img.height and target_width > 0 and target_height > 0:
            width = min(target_width, img.width)
            height = min(target_height, img.height)
            if ratio:
                height = min(height, max(1, int(width / ratio)))
                width = min(width, max(1, int(height * ratio)))
            if width != img.width or height != img.height:
                img = img.resize((width, height), resample=PIL.Image.LANCZOS)
                newwidth = width
                newheight = height

        img.save(newuri)
        image['uri'] = newuri
        image_entries.append((newuri, ratio, newwidth, newheight))

    return image_entries


def _prepare_mosaic_image(
    image: nodes.image,
    imgtargetdir: str,
    max_width: int,
) -> Tuple[str, float]:
    """Copy one mosaic image and cap width to preserve legacy behavior."""
    img = PIL.Image.open(image['uri'])
    ratio = img.width / img.height if img.height else 0
    newuri = join(imgtargetdir, basename(image['uri']))
    if img.width > max_width and img.height:
        newheight = int(max_width / ratio) if ratio else img.height
        img = img.resize((max_width, newheight), resample=PIL.Image.LANCZOS)
    img.save(newuri)
    image['uri'] = newuri
    return newuri, ratio


def _render_mosaic_images(
    image_entries: Sequence[Tuple[str, float, int, int] | Tuple[str, float]],
) -> str:
    """Render mosaic image HTML snippets."""
    lines = []
    for entry in image_entries:
        if len(entry) == 2:
            newuri, ratio = entry
            lines.append(
                '    <img src="{0}" style="--ar: {1:.4f};">\n'.format(
                    newuri,
                    ratio,
                )
            )
            continue

        newuri, ratio, width, height = entry
        lines.append(
            '    <img src="{0}" width="{1}" height="{2}" style="--ar: {3:.4f};">\n'.format(
                newuri,
                width,
                height,
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
            image_entries = _prepare_mosaic_images(
                images,
                self.settings.imgtargetdir,
                width,
                border_percent,
            )

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

        if type(self.settings.targetlinewidth) != int or self.settings.targetlinewidth <= 0:
            raise TypeError(
                'You need to specify a positive integer for --targetlinewidth'
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
