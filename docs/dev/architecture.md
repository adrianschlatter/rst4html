# Architecture

## Docutils pipeline (short overview)

Docutils processes reStructuredText by reading a source, parsing it into a
document tree, and then writing that tree to a target format using a
writer/translator pair. The end‑to‑end pipeline is assembled by the
`docutils.core` publishing helpers and driven by a reader, parser, and writer
configuration [...](http://XXX). Document nodes are walked by an
`HTMLTranslator` to produce HTML output [...](http://XXX).


## How rst4html integrates

rst4html plugs into docutils by providing a custom Reader and Writer and wiring
them into `docutils.core.publish_cmdline` from the CLI entry point
(`rst4html/__cmdl__.py`). The Reader extends the standard standalone reader to
support runtime variable substitution. The Writer extends the standard HTML
writer to manage image copying and image transformation decisions.


## Reader, Writer, and ModifiedHTMLTranslator collaboration

* `Reader()` loads the source text and performs `{varname}` substitutions using
  the `--subst` JSON mapping before parsing, then delegates to the docutils
  parser to build the document tree.
* `Writer()` validates the image target directory (`--imgtargetdir`), creates
  it when missing, and hands the document off to the HTML writer. It sets its
  `translator_class` to `ModifiedHTMLTranslator` so that image handling is
  customized during node traversal.
* `ModifiedHTMLTranslator()` intercepts image nodes, rewrites their URIs to
  point at the target image directory, optionally autorotates JPEGs based on
  EXIF orientation, and rescales images according to the `:width:` attribute
  and `--targetlinewidth`. It then continues normal HTML translation so the
  final HTML includes the updated image references.

Together, these components ensure substitutions occur before parsing, and image
processing occurs during HTML generation, producing HTML that references copied
and transformed images.
