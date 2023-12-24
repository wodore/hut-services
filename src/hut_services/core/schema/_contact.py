import logging
from collections import namedtuple
from typing import Sequence

import phonenumbers
from pydantic import Field

from ._base import BaseSchema
from .locale import TranslationSchema

logger = logging.getLogger(__name__)


PhoneMobile = namedtuple("PhoneMobile", ["phone", "mobile"])


class ContactSchema(BaseSchema):
    """Schema for a contact.

    Attributes:
        name: Contact name (persion or organization), can also be empty.
        email: E-mail address.
        phone: Phone number.
        mobile: Mobule phone number.
        function: Function, e.g. hut warden.
        url: Additional url for this contact (not the hut website).
        address: Address (street, city).
        note: Additional note/information.
        is_active: Contact is active.
        is_public: Show contact public.
    """

    name: str = Field("", max_length=70)
    email: str = Field("", max_length=70)
    phone: str = Field("", max_length=30)
    mobile: str = Field("", max_length=30)
    function: str = Field("", max_length=20)
    url: str = Field("", max_length=200)
    address: str = Field("", max_length=200)
    note: TranslationSchema = Field(default_factory=TranslationSchema)
    is_active: bool = True
    is_public: bool = False

    @classmethod
    def extract_phone_numbers(cls, numbers_string: str, region: str | None) -> list[str]:
        """Extracts phone numbers from a string and returns them formatted
        with international code.
        Uses the [`phonenumbers`](https://github.com/daviddrysdale/python-phonenumbers) package.

        Args:
            numbers_string: A string with phone numbers in it.
            region: Country code.

        Returns:
            A list with formatted phone numbers.
        """
        phones = []
        _matches = phonenumbers.PhoneNumberMatcher(numbers_string, region=region)
        if not _matches:
            logger.warning(f"Could not match phone CH number: '{numbers_string}'")
        phone_match: phonenumbers.PhoneNumberMatch
        for phone_match in _matches:
            phone_fmt = phonenumbers.format_number(phone_match.number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
            phones.append(phone_fmt)
        return phones

    @classmethod
    def number_to_phone_or_mobile(
        cls, numbers: str | Sequence[str], region: str | None, formatted: bool = False
    ) -> PhoneMobile:
        """Given a phone number it returns it eihter as `phone` or `mobile` number.
        Uses the [`phonenumbers`](https://github.com/daviddrysdale/python-phonenumbers) package.

        Args:
            numbers: List or string of phone numbers, they are extraced and the two assigned to phone and mobile.
            region: Country code.
            formatted: Phone list is alreaad formatted

        Returns:
            Tuple with `phone` and `mobile` number (`(phone, mobile)`).
        """
        numbers_fmt: Sequence[str] = []
        if formatted:
            numbers_fmt = [n.strip() for n in numbers.split(",")] if isinstance(numbers, str) else numbers
        else:
            if not isinstance(numbers, str):
                numbers = " and ".join(numbers)
            numbers_fmt = cls.extract_phone_numbers(numbers, region=region)

        mobiles: list[str] = []
        phones: list[str] = []
        for num in numbers_fmt:
            is_mobile = (
                phonenumbers.number_type(phonenumbers.parse(num, region=region)) == phonenumbers.PhoneNumberType.MOBILE
            )
            if is_mobile:
                mobiles.append(num)
            else:
                phones.append(num)
        mobile = mobiles[0] if mobiles else ""
        phone = phones[0] if phones else ""
        return PhoneMobile(phone=phone, mobile=mobile)
