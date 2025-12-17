"""Geocoding module using Open-Meteo Geocoding API."""

import httpx
from typing import Optional


class GeocodingError(Exception):
    """Raised when geocoding fails."""
    pass


async def geocode_location(location: str) -> Optional[dict]:
    """
    Convert city name to coordinates using Open-Meteo Geocoding API.

    Args:
        location: City name or "City, Country" format

    Returns:
        Dictionary with latitude, longitude, and resolved name, or None if not found
    """
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {
        "name": location,
        "count": 1,
        "language": "en",
        "format": "json"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if "results" not in data or not data["results"]:
                return None

            result = data["results"][0]
            return {
                "latitude": result["latitude"],
                "longitude": result["longitude"],
                "name": result["name"],
                "country": result.get("country", ""),
                "admin1": result.get("admin1", "")
            }
    except (httpx.HTTPError, KeyError, ValueError):
        return None
