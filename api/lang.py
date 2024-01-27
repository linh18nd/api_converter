# SPDX-FileCopyrightText: 2023 James R. Barlow
# SPDX-License-Identifier: MPL-2.0


from typing import NamedTuple


class ISOCodeData(NamedTuple):
    """Data for a single ISO 639 code."""
    alt: str
    alpha_2: str
    english: str
    french: str


ISO_639_3 = {
    'eng': ISOCodeData('enm', 'en', 'English', 'anglais'),
    'vie': ISOCodeData('', 'vi', 'Vietnamese', 'vietnamien'),
}


def iso_639_2_from_3(iso3: str) -> str:
    """Convert ISO 639-3 code to ISO 639-2 code."""
    if iso3 in ISO_639_3:
        return ISO_639_3[iso3].alpha_2
    else:
        return ""
