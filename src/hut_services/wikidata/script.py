# type: ignore  # noqa: PGH003
import urllib.parse

from icecream import ic
from wikidata.client import Client

## play with wikidata

# qid = "Q42157530"
qid = "Q887175"  # Bluemlisalp
width = 1000

client = Client()  # doctest: +SKIP
entity = client.get(qid, load=True)
ic(entity.description)
image_prop = client.get("P18")
image = entity[image_prop]
ic(entity.attributes)

ic(image.title)
title = urllib.parse.quote(image.title)
link = f"https://commons.wikimedia.org/w/index.php?title=Special:Redirect/file/{title}&width={width}"
ic(link)
ic(image.attributes)
# ic(image.image_resolution)
ic(image.attributes.get("canonicalurl"))
