"""Tri-state photo inclusion for hut conversion.

Services differ in where their photos come from: some carry them in the
source data already, others need additional requests per hut (or per image)
during [`convert()`][hut_services.BaseService.convert]. [`PhotosMode`][hut_services.PhotosMode]
lets callers pick the trade-off between completeness and cost.
"""

from enum import Enum

__all__ = ["PhotosMode", "normalize_photos_mode"]


class PhotosMode(str, Enum):
    """Which photos a conversion includes.

    Attributes:
        NONE: No photos at all - cheapest bulk imports.
        EMBEDDED: Only photos already part of the source data; never makes
            additional requests (the default).
        ALL: All photos, even when fetching them needs additional requests.
    """

    NONE = "none"
    EMBEDDED = "embedded"
    ALL = "all"


def normalize_photos_mode(value: "PhotosMode | bool") -> PhotosMode:
    """Normalize legacy bools and plain strings to [`PhotosMode`][hut_services.PhotosMode].

    Args:
        value: `True` -> `ALL`, `False` -> `NONE`, a `PhotosMode` as-is,
            or its string value (`"none"`, `"embedded"`, `"all"`).

    Returns:
        The normalized mode.
    """
    if value is True:
        return PhotosMode.ALL
    if value is False:
        return PhotosMode.NONE
    if isinstance(value, PhotosMode):
        return value
    return PhotosMode(value)
