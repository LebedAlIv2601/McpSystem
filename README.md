# Weather Forecast MCP Server

Local MCP server providing weather forecast data via Open-Meteo API.

## Features

- Single tool: `get_weather_forecast`
- Returns temperature, precipitation, cloud cover, humidity, and wind speed
- Supports city name or "City, Country" location format
- Stdio transport for local integration

## Requirements

- Python 3.14+
- Dependencies listed in `requirements.txt`

## Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

## Running the Server

```bash
python server.py
```

The server runs on stdio transport and communicates via standard input/output.

## Tool Specification

### `get_weather_forecast`

**Description:** Get weather forecast for specified location and date range.

**Input Parameters:**
- `location` (string, required): City name or "City, Country" format (e.g., "Moscow" or "Moscow, Russia")
- `start_date` (string, required): Start date in YYYY-MM-DD format
- `end_date` (string, required): End date in YYYY-MM-DD format

**Output:**
```json
{
  "location": "Moscow, Russia",
  "forecast": [
    {
      "date": "2025-12-17",
      "temperature_2m": {
        "min": -5,
        "max": 2,
        "unit": "°C"
      },
      "precipitation": {
        "total": 0.5,
        "unit": "mm"
      },
      "cloud_cover": {
        "average": 75,
        "unit": "%"
      },
      "relative_humidity_2m": {
        "average": 85,
        "unit": "%"
      },
      "wind_speed_10m": {
        "max": 15,
        "unit": "km/h"
      }
    }
  ]
}
```

**Error Response:**
```json
{
  "error": "No data, ask something other"
}
```

## Project Structure

```
.
├── server.py           # Main MCP server
├── geocoding.py        # Location geocoding module
├── weather.py          # Weather API module
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## Integration

This server is designed for integration with MCP clients (e.g., Telegram bots with OpenRouter models) running on the same machine via stdio transport.
