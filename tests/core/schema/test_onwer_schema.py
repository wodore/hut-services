from hut_services import OwnerSchema


def test_set_slug() -> None:
    o = OwnerSchema(name="Test Name")
    assert o.slug == "test-name"


def test_set_slug_special_name() -> None:
    o = OwnerSchema(name="Test Name ... #@")
    assert o.slug == "test-name"


def test_set_slug_with_long_name() -> None:
    o = OwnerSchema(name="Test Name so long that it cannot stop to give some shorter Slug.")
    assert o.slug == "test-name-so-long-that-it-cannot-stop-to-give-some"


def test_with_slug() -> None:
    o = OwnerSchema(slug="my-slug", name="Test Name")
    assert o.slug == "my-slug"
