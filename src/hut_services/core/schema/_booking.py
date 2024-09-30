#!/usr/bin/env python
import datetime
from enum import Enum

from pydantic import Field, computed_field

from ._base import BaseSchema


class ReservationStatusEnum(str, Enum):
    """Enum with reservation status."""

    unknown = "unknown"
    possible = "possible"
    not_possible = "not_possible"
    not_online = "not_online"


class OccupancyStatusEnum(str, Enum):
    """Enum with with occuptation status."""

    unknown = "unknown"
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
    free: int
    total: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def occupancy_percent(self) -> float:
        return (self.total - self.free) / self.total * 100 if self.total > 0 else 100

    @computed_field  # type: ignore[prop-decorator]
    @property
    def occupancy_steps(self) -> float:
        steps_fine = round(self.occupancy_percent / 10) * 10
        if self.occupancy_percent > 0 and self.occupancy_percent < 5:
            steps_fine = 10
        elif self.occupancy_percent < 100 and self.occupancy_percent > 95:
            steps_fine = 90
        return steps_fine

    @computed_field  # type: ignore[prop-decorator]
    @property
    def occupancy_status(self) -> OccupancyStatusEnum:
        if self.total == 0:
            return OccupancyStatusEnum.unknown
        if self.occupancy_percent == 100:
            return OccupancyStatusEnum.full
        elif self.occupancy_percent > 62:
            return OccupancyStatusEnum.high
        elif self.occupancy_percent > 37:
            return OccupancyStatusEnum.medium
        elif self.occupancy_percent > 0:
            return OccupancyStatusEnum.low
        return OccupancyStatusEnum.empty


class BookingSchema(BaseSchema):
    date: datetime.date
    reservation_status: ReservationStatusEnum = ReservationStatusEnum.unknown
    unattended: bool
    places: PlacesSchema
    link: str | None = None


class HutBookingsSchema(BaseSchema):
    source_id: int = Field(..., description="ID of the booking provider, e.g. alpsonline.org.")
    start_date: datetime.date
    days: int
    link: str | None = None
    bookings: list[BookingSchema]
