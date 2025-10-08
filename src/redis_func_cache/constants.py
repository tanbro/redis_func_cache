"""Constants"""

from typing import Final

DEFAULT_MAXSIZE: Final = 1024
"""Default maximum size of the cache."""

DEFAULT_TTL: Final = 3600
"""Default time-to-live in seconds of the cache."""

DEFAULT_PREFIX: Final = "func-cache:"
"""Default prefix for the cache keys."""
