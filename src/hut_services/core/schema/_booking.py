#!/usr/bin/env python
import datetime
from enum import Enum

from pydantic import Field, computed_field, model_validator

from ._base import BaseSchema


class ReservationStatusEnum(str, Enum):
    """Enum with reservation status."""

    unknown = "unknown"
    possible = "possible"
    not_possible = "not_possible"
    not_online = "not_online"


class OccupancyStatusEnum(str, Enum):
    """Enum with occupancy status."""

    unknown = "unknown"
    free_unknown = "free_unknown"
    empty = "empty"
    low = "low"
    medium = "medium"
    high = "high"
    full = "full"

    # unknown = -1
    # empty = 0
    # low = 25
    # medium = 50
    # high = 75
    # full = 100


class PlacesSchema(BaseSchema):
    """Free/total places of a hut.

    `free`/`total` are `None` when the source does not publish them
    (e.g. bookable days without counts, or counts without totals).
    Occupancy is only computed when both are known and `total > 0`.
    """

    free: int | None = Field(None, description="Free places. None = not published by the source.")
    total: int | None = Field(None, description="Total places. None = not published by the source.")

    @model_validator(mode="after")
    def _total_at_least_free(self) -> "PlacesSchema":
        """Sources can report more free places than the (stale) total,
        e.g. online quota released or winter-room numbers. Clamp the total
        up to free so the occupancy stays >= 0 (free=6/total=5 -> total=6)."""
        if self.free is not None and self.total is not None and self.free > self.total:
            self.total = self.free
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def occupancy_percent(self) -> float | None:
        """Occupancy in percent. None if not computable (free/total unknown or total <= 0)."""
        if self.free is None or self.total is None or self.total <= 0:
            return None
        return (self.total - self.free) / self.total * 100

    @computed_field  # type: ignore[prop-decorator]
    @property
    def occupancy_steps(self) -> int | None:
        """Occupancy in steps of 10 percent. None if not computable."""
        percent = self.occupancy_percent
        if percent is None:
            return None
        steps_fine = round(percent / 10) * 10
        if 0 < percent < 5:
            steps_fine = 10
        elif 95 < percent < 100:
            steps_fine = 90
        return int(steps_fine)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def occupancy_status(self) -> OccupancyStatusEnum:
        if self.total is not None and self.total == 0:
            return OccupancyStatusEnum.unknown  # closed / no places
        if self.free is None and self.total is None:
            return OccupancyStatusEnum.unknown  # no occupancy information at all
        if self.free is None or self.total is None:
            # bookable ('dispo', count not published) or count without total:
            # occupancy ratio not computable, but free is confirmed
            return OccupancyStatusEnum.free_unknown
        percent = self.occupancy_percent
        assert percent is not None  # noqa: S101 (narrowing for mypy)
        if percent == 100:
            return OccupancyStatusEnum.full
        elif percent > 62:
            return OccupancyStatusEnum.high
        elif percent > 37:
            return OccupancyStatusEnum.medium
        elif percent > 0:
            return OccupancyStatusEnum.low
        return OccupancyStatusEnum.empty


class BookingSchema(BaseSchema):
    date: datetime.date
    reservation_status: ReservationStatusEnum = ReservationStatusEnum.unknown
    unattended: bool
    places: PlacesSchema
    link: str | None = None


class HutBookingsSchema(BaseSchema):
    source_id: int | str = Field(
        ...,
        description="ID of the booking provider, e.g. alpsonline.org. str for providers with non-numeric ids (e.g. FFCAM).",
    )
    start_date: datetime.date
    days: int
    link: str | None = None
    bookings: list[BookingSchema]
