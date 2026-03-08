"""
rst4html package
"""

try:
    from importlib_metadata import version
except ImportError:                                     # pragma: no cover
    from importlib.metadata import version              # pragma: no cover


__version__ = version(__name__)

from .rst4html import *
del rst4html
