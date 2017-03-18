# -*- coding: utf-8 -*-
"""
traveldiary2html command-line tool
"""

from traveldiary2html import Reader


def main():
    try:
        import locale
        locale.setlocale(locale.LC_ALL, '')
    except:
        pass

    from docutils.core import publish_cmdline, default_description

    diaryreader = Reader()

    description = ('Generates (X)HTML documents from reStructuredText '
                   'sources with support for variables and image '
                   'pre-processing  ' + default_description)

    publish_cmdline(reader=diaryreader, reader_name='traveldiary',
                    writer_name='html', description=description)


if __name__ == '__main__':
    main()
