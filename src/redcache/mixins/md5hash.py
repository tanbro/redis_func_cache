"""Base class for single-pair cache."""

from __future__ import annotations

from .abstracthash import AbstractHashMixin

__all__ = ("Md5HashMixin",)


class Md5HashMixin(AbstractHashMixin):
    __algorithm__ = "md5"
