# -*- coding: utf-8 -*-
"""Shared helpers for module exports."""

from typing import Any
import sys


def export(obj: Any) -> Any:
    """Add the decorated object to its module ``__all__`` list."""
    mod = sys.modules[obj.__module__]
    mod.__all__ = getattr(mod, '__all__', []) + [obj.__name__]
    return obj
