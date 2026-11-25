"""Built-in gazetteer for Bangladesh: 64 district headquarters plus common Dhaka areas.
Coordinates are approximate city centres (good to a few km), enough to rank clubs and events by distance
without any paid geocoding service. Organizers can add exact coordinates on top of a place."""
from math import asin, cos, radians, sin, sqrt

_D = [  # (division, name, lat, lng)
    ("Dhaka", "Dhaka", 23.8103, 90.4125), ("Dhaka", "Gazipur", 23.9999, 90.4203), ("Dhaka", "Narayanganj", 23.6238, 90.5000),
    ("Dhaka", "Narsingdi", 23.9322, 90.7151), ("Dhaka", "Munshiganj", 23.5422, 90.5305), ("Dhaka", "Manikganj", 23.8617, 90.0003),
    ("Dhaka", "Tangail", 24.2513, 89.9167), ("Dhaka", "Kishoreganj", 24.4449, 90.7766), ("Dhaka", "Faridpur", 23.6070, 89.8429),
    ("Dhaka", "Gopalganj", 23.0050, 89.8266), ("Dhaka", "Madaripur", 23.1641, 90.1896), ("Dhaka", "Rajbari", 23.7574, 89.6445),
    ("Dhaka", "Shariatpur", 23.2423, 90.4348),
    ("Chattogram", "Chattogram", 22.3569, 91.7832), ("Chattogram", "Cox's Bazar", 21.4272, 92.0058), ("Chattogram", "Cumilla", 23.4607, 91.1809),
    ("Chattogram", "Brahmanbaria", 23.9571, 91.1119), ("Chattogram", "Chandpur", 23.2513, 90.8518), ("Chattogram", "Lakshmipur", 22.9425, 90.8412),
    ("Chattogram", "Noakhali", 22.8696, 91.0995), ("Chattogram", "Feni", 23.0159, 91.3976), ("Chattogram", "Khagrachhari", 23.1193, 91.9847),
    ("Chattogram", "Rangamati", 22.7324, 92.2985), ("Chattogram", "Bandarban", 22.1953, 92.2184),
    ("Rajshahi", "Rajshahi", 24.3745, 88.6042), ("Rajshahi", "Bogura", 24.8465, 89.3773), ("Rajshahi", "Pabna", 24.0064, 89.2372),
    ("Rajshahi", "Sirajganj", 24.4534, 89.7006), ("Rajshahi", "Natore", 24.4206, 89.0000), ("Rajshahi", "Naogaon", 24.7936, 88.9318),
    ("Rajshahi", "Chapainawabganj", 24.5965, 88.2775), ("Rajshahi", "Joypurhat", 25.0947, 89.0945),
    ("Khulna", "Khulna", 22.8456, 89.5403), ("Khulna", "Jashore", 23.1664, 89.2081), ("Khulna", "Satkhira", 22.7185, 89.0705),
    ("Khulna", "Bagerhat", 22.6602, 89.7895), ("Khulna", "Narail", 23.1725, 89.5126), ("Khulna", "Magura", 23.4855, 89.4198),
    ("Khulna", "Jhenaidah", 23.5448, 89.1539), ("Khulna", "Chuadanga", 23.6401, 88.8418), ("Khulna", "Kushtia", 23.9013, 89.1205),
    ("Khulna", "Meherpur", 23.7622, 88.6318),
    ("Barishal", "Barishal", 22.7010, 90.3535), ("Barishal", "Bhola", 22.6859, 90.6482), ("Barishal", "Patuakhali", 22.3596, 90.3299),
    ("Barishal", "Pirojpur", 22.5841, 89.9720), ("Barishal", "Jhalokathi", 22.6406, 90.1987), ("Barishal", "Barguna", 22.1591, 90.1126),
    ("Sylhet", "Sylhet", 24.8949, 91.8687), ("Sylhet", "Moulvibazar", 24.4829, 91.7774), ("Sylhet", "Habiganj", 24.3745, 91.4155),
    ("Sylhet", "Sunamganj", 25.0658, 91.4073),
    ("Rangpur", "Rangpur", 25.7439, 89.2752), ("Rangpur", "Dinajpur", 25.6279, 88.6332), ("Rangpur", "Kurigram", 25.8054, 89.6361),
    ("Rangpur", "Gaibandha", 25.3297, 89.5430), ("Rangpur", "Lalmonirhat", 25.9923, 89.2847), ("Rangpur", "Nilphamari", 25.9318, 88.8560),
    ("Rangpur", "Panchagarh", 26.3411, 88.5542), ("Rangpur", "Thakurgaon", 26.0337, 88.4616),
    ("Mymensingh", "Mymensingh", 24.7471, 90.4203), ("Mymensingh", "Jamalpur", 24.9375, 89.9372), ("Mymensingh", "Netrokona", 24.8103, 90.7289),
    ("Mymensingh", "Sherpur", 25.0204, 90.0153),
]
_DHAKA_AREAS = [  # (name, lat, lng): neighbourhoods inside Dhaka city
    ("Dhanmondi", 23.7461, 90.3742), ("Gulshan", 23.7925, 90.4078), ("Banani", 23.7937, 90.4066), ("Uttara", 23.8759, 90.3795),
    ("Mirpur", 23.8223, 90.3654), ("Mohammadpur", 23.7662, 90.3589), ("Motijheel", 23.7330, 90.4172), ("Bashundhara R/A", 23.8187, 90.4526),
    ("Farmgate", 23.7561, 90.3872), ("Tejgaon", 23.7639, 90.3925), ("Shahbag", 23.7389, 90.3958), ("Old Dhaka", 23.7104, 90.4074),
    ("Badda", 23.7806, 90.4261), ("Khilgaon", 23.7510, 90.4350), ("Jatrabari", 23.7104, 90.4350), ("Savar", 23.8583, 90.2667),
]


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-").replace("--", "-")


PLACES: dict[str, dict] = {}
for _div, _name, _lat, _lng in _D:
    PLACES[_slug(_name)] = {"id": _slug(_name), "name": _name, "division": _div, "lat": _lat, "lng": _lng}
for _name, _lat, _lng in _DHAKA_AREAS:
    PLACES[_slug(_name)] = {"id": _slug(_name), "name": f"{_name}, Dhaka", "division": "Dhaka", "lat": _lat, "lng": _lng}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = radians(lat1), radians(lat2)
    a = sin((p2 - p1) / 2) ** 2 + cos(p1) * cos(p2) * sin(radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * asin(sqrt(a))


def place_name(place_id: str | None) -> str | None:
    p = PLACES.get(place_id or "")
    return p["name"] if p else None
