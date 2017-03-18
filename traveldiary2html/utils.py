# -*- coding: utf-8 -*-
"""
Utilities
"""

import sys


def export(obj):
    """Decorator that adds obj to __all__"""

    mod = sys.modules[obj.__module__]
    mod.__all__ = getattr(mod, '__all__', []) + [obj.__name__]
    return(obj)
