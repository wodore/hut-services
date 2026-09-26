"""PlacesSchema extensions: free_tolerance and TotalFallback."""

from hut_services.core.schema import PlacesSchema, TotalFallback


def test_free_tolerance_default_zero() -> None:
    """Exact sources (the default) carry tolerance 0 -> point range."""
    p = PlacesSchema(free=7)
    assert p.free_tolerance == 0
    assert p.free_range == (7, 7)


def test_free_tolerance_range() -> None:
    """Estimated sources (e.g. people-binary probing) express ±uncertainty."""
    p = PlacesSchema(free=35, total=50, free_tolerance=5)
    assert p.free_range == (30, 40)


def test_free_range_clamped_at_zero() -> None:
    p = PlacesSchema(free=3, free_tolerance=5)
    assert p.free_range == (0, 8)
    assert p.free_range is not None and p.free_range[0] >= 0


def test_free_range_none_without_free() -> None:
    assert PlacesSchema(total=50).free_range is None
    assert PlacesSchema().free_range is None


def test_total_fallback_shape() -> None:
    """Per-season fallback totals, independent of occupancy computation."""
    tf = TotalFallback(standard=50, reduced=12)
    p = PlacesSchema(free=None, total=None, total_fallback=tf)
    assert p.total_fallback == tf
    assert p.total_fallback is not None and p.total_fallback.standard == 50
    assert p.total_fallback is not None and p.total_fallback.reduced == 12
    assert p.occupancy_percent is None  # fallback does not fake occupancy
