"""Tests for the BaseService.get_bookings signature contract."""

import datetime
import typing as t

import pytest

from hut_services.core.schema import (
    BookingSchema,
    HutBookingsSchema,
    HutSourceSchema,
    PlacesSchema,
    TotalFallback,
)
from hut_services.core.service import BaseService


class _StubSource(HutSourceSchema):
    """Minimal concrete source schema for a booking-service stub."""


class _StubService(BaseService[_StubSource]):
    """Records the ABC-named arguments (incl. total_fallback) for assertions."""

    last_call: dict[str, t.Any] | None = None

    def get_bookings(  # type: ignore[override]
        self,
        date=None,
        days=None,
        source_ids=None,
        lang="de",
        request_interval=None,
        total_fallback=None,
    ) -> dict[int | str, HutBookingsSchema]:
        _StubService.last_call = {"total_fallback": total_fallback}
        return {
            "1": HutBookingsSchema(
                source_id="1",
                start_date=datetime.date(2027, 7, 1),
                days=1,
                bookings=[
                    BookingSchema(
                        date=datetime.date(2027, 7, 1),
                        unattended=False,
                        places=PlacesSchema(free=1, total=2),
                    )
                ],
            )
        }


class TestGetBookingsTotalFallback:
    def test_base_raises_not_implemented(self) -> None:
        svc = BaseService[_StubSource]()
        with pytest.raises(NotImplementedError):
            svc.get_bookings()

    def test_param_accepted_positionally_typed(self) -> None:
        """The ABC signature carries a typed total_fallback parameter."""
        import inspect

        sig = inspect.signature(BaseService.get_bookings)
        assert "total_fallback" in sig.parameters
        assert sig.parameters["total_fallback"].default is None

    def test_single_fallback_passthrough(self) -> None:
        svc = _StubService()
        svc.get_bookings(total_fallback=TotalFallback(standard=42, reduced=10))
        assert _StubService.last_call is not None
        assert _StubService.last_call["total_fallback"] == TotalFallback(standard=42, reduced=10)

    def test_mapping_fallback_passthrough(self) -> None:
        svc = _StubService()
        mapping = {"123": TotalFallback(standard=30, reduced=None)}
        svc.get_bookings(total_fallback=mapping)
        assert _StubService.last_call is not None
        assert _StubService.last_call["total_fallback"] is mapping
