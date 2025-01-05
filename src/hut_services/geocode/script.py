# type: ignore  # noqa: PGH003
import httpx
from rich import print as rprint

request_url = (
    "https://nominatim.openstreetmap.org/search"  # ?q=Neue%20Regensburger%20H%C3%BCtte&polygon_geojson=0&format=jsonv2"
)

langs = ",".join(["ch", "de", "fr", "it", "at"])
params = {
    "amenity": "Neue Regensburger Huette",
    "format": "jsonv2",
    "limit": 1,
    "extratags": True,
    "countrycodes": langs,
    "accept-language": langs,
}

res = httpx.get(url=request_url, params=params).json()
if res:
    hut = res[0]
rprint(hut)
