# -*- coding: utf-8 -*-
"""Command-line entry point for rst4html."""

from __future__ import annotations

from rst4html import Reader, Writer


def main() -> None:
    """Run the rst4html CLI wrapper around docutils."""
    import locale

    locale.setlocale(locale.LC_ALL, '')

    from docutils.core import publish_cmdline, default_description

    reader = Reader()
    writer = Writer()

    description = (
        'Generates (X)HTML documents from reStructuredText '
        'sources with support for variables and image '
        'pre-processing  ' + default_description
    )

    publish_cmdline(
        reader=reader,
        reader_name='rst4html',
        writer=writer,
        writer_name='rst4html',
        description=description,
    )


if __name__ == '__main__':
    main()
