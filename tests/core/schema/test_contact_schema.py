from hut_services import ContactSchema


def test_detect_phone_numbers_list() -> None:
    mobile_in = "079 522 3665"
    mobile_exp = "+41 79 522 36 65"
    phone_in = "062 7263232"
    phone_exp = "+41 62 726 32 32"
    phone, mobile = ContactSchema.number_to_phone_or_mobile([mobile_in, phone_in], region="CH")
    assert phone, phone_exp
    assert mobile, mobile_exp


def test_detect_phone_numbers_str() -> None:
    mobile_in = "079 522 3665"
    mobile_exp = "+41 79 522 36 65"
    phone_in = "062 7263232"
    phone_exp = "+41 62 726 32 32"
    phone, mobile = ContactSchema.number_to_phone_or_mobile(f"some text {mobile_in} or call {phone_in}", region="CH")
    assert phone, phone_exp
    assert mobile, mobile_exp
