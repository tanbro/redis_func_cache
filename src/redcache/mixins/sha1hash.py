"""Base class for single-pair cache."""

from __future__ import annotations

from .abstracthash import AbstractHashMixin

__all__ = ("Sha1HashMixin",)


class Sha1HashMixin(AbstractHashMixin):
    __algorithm__ = "sha1"
