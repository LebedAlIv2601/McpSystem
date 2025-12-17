"""Weather forecast module using Open-Meteo Weather API."""

import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime


class WeatherAPIError(Exception):
    """Raised when weather API call fails."""
    pass


async def get_weather_forecast(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str
) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch weather forecast from Open-Meteo API.

    Args:
        latitude: Location latitude
        longitude: Location longitude
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        List of daily weather data dictionaries, or None if API fails
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "cloud_cover_mean",
            "relative_humidity_2m_mean",
            "wind_speed_10m_max"
        ],
        "timezone": "auto"
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if "daily" not in data:
                return None

            daily = data["daily"]
            dates = daily.get("time", [])
            temp_max = daily.get("temperature_2m_max", [])
            temp_min = daily.get("temperature_2m_min", [])
            precipitation = daily.get("precipitation_sum", [])
            cloud_cover = daily.get("cloud_cover_mean", [])
            humidity = daily.get("relative_humidity_2m_mean", [])
            wind_speed = daily.get("wind_speed_10m_max", [])

            forecast = []
            for i in range(len(dates)):
                forecast.append({
                    "date": dates[i],
                    "temperature_2m": {
                        "min": temp_min[i] if i < len(temp_min) else None,
                        "max": temp_max[i] if i < len(temp_max) else None,
                        "unit": "°C"
                    },
                    "precipitation": {
                        "total": precipitation[i] if i < len(precipitation) else None,
                        "unit": "mm"
                    },
                    "cloud_cover": {
                        "average": cloud_cover[i] if i < len(cloud_cover) else None,
                        "unit": "%"
                    },
                    "relative_humidity_2m": {
                        "average": humidity[i] if i < len(humidity) else None,
                        "unit": "%"
                    },
                    "wind_speed_10m": {
                        "max": wind_speed[i] if i < len(wind_speed) else None,
                        "unit": "km/h"
                    }
                })

            return forecast

    except (httpx.HTTPError, KeyError, ValueError):
        return None
