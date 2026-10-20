"""Location quality tiers: how precisely a location's coordinates place it.

A geocoder returns a point for an address and says how sure it is: on the roof, on the
parcel, somewhere on the street, the middle of the zip code, or the middle of the
county. Analysis on a zip-code centroid can put a house in the wrong flood zone, so every
point carries its tier.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tier:
    code: str          # stored in geo.feature.quality
    label: str
    typical_error_m: int


TIERS = [Tier("rooftop", "Rooftop", 10), Tier("parcel", "Parcel", 30),
         Tier("street", "Street", 150), Tier("zip", "Zip centroid", 3000),
         Tier("county", "County centroid", 25000)]
BY_CODE = {t.code: t for t in TIERS}

# Precision words geocoders commonly return, mapped to tiers.
_PRECISION = {
    "rooftop": "rooftop", "point": "rooftop", "address": "rooftop", "premise": "rooftop",
    "parcel": "parcel", "range_interpolated": "street", "interpolated": "street",
    "street": "street", "street_center": "street", "postcode": "zip", "zip": "zip",
    "postal_code": "zip", "county": "county", "region": "county",
}


def tier_for(precision: str) -> str:
    """The tier for a geocoder's precision word; unknown words count as the coarsest tier."""
    return _PRECISION.get(precision.strip().lower(), "county")
