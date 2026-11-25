"""Location rules shared by clubs, events and users."""
from fastapi import HTTPException

from .places import PLACES

MODES = ("onsite", "online", "hybrid")


def check_coords(lat, lng):
    if (lat is None) != (lng is None):
        raise HTTPException(422, "Provide both latitude and longitude, or neither")
    if lat is not None and not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise HTTPException(422, "Coordinates are out of range")


def resolve_location(mode: str | None, place: str | None, address: str | None, lat, lng, *, current: dict | None = None) -> dict:
    """Merge a partial update onto `current`, validate, and fill coordinates from the place when none were given.
    Online-only items have no physical location, so those fields are cleared."""
    cur = current or {}
    mode = mode or cur.get("location_mode") or "onsite"
    if mode not in MODES:
        raise HTTPException(422, f"location_mode must be one of {list(MODES)}")
    if mode == "online":
        return {"location_mode": "online", "place": None, "address": None, "latitude": None, "longitude": None}
    given_place = place
    place = place if place is not None else cur.get("place")
    if place == "":
        place = None
    if place is not None and place not in PLACES:
        raise HTTPException(422, "Unknown place. Choose one from the list.")
    address = (address if address is not None else cur.get("address")) or None
    if address and len(address) > 200:
        raise HTTPException(422, "Address is too long (max 200 characters)")
    check_coords(lat, lng)
    if lat is None:   # no coordinates supplied in this change
        if given_place is not None and place != cur.get("place") and place:
            lat, lng = PLACES[place]["lat"], PLACES[place]["lng"]          # moved to another place: follow it
        else:
            lat, lng = cur.get("latitude"), cur.get("longitude")
            if lat is None and place:
                lat, lng = PLACES[place]["lat"], PLACES[place]["lng"]
    return {"location_mode": mode, "place": place, "address": address, "latitude": lat, "longitude": lng}


def location_out(obj) -> dict:
    from .places import place_name
    return {"mode": getattr(obj, "location_mode", "onsite") or "onsite", "place": obj.place, "place_name": place_name(obj.place),
            "address": obj.address, "latitude": obj.latitude, "longitude": obj.longitude}
