class OSMCoordinatesError(Exception):
    def __init__(self, osm_id: int | str, name: str = ""):
        message = f"OSM coordinates missing for id {osm_id} (name: '{name}')"
        super().__init__(message)
