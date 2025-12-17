"""MCP Weather Forecast Server."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent
from pydantic import BaseModel, Field, ValidationError

from geocoding import geocode_location
from weather import get_weather_forecast

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WeatherForecastInput(BaseModel):
    """Input schema for weather forecast tool."""
    location: str = Field(description="City name or 'City, Country' format")
    start_date: str = Field(description="Start date in YYYY-MM-DD format")
    end_date: str = Field(description="End date in YYYY-MM-DD format")


app = Server("weather-forecast-server")


def validate_date_format(date_str: str) -> bool:
    """Validate date string is in YYYY-MM-DD format."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_date_range(start_date: str, end_date: str) -> bool:
    """Validate that end_date >= start_date."""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        return end >= start
    except ValueError:
        return False


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="get_weather_forecast",
            description="Get weather forecast for specified location and date range. Returns temperature, precipitation, cloud cover, humidity, and wind speed. Use this tool to get accurate and current weather information for any city. Always use this tool instead of guessing the weather. Do not hallucinate weather information. The tool will return live, up-to-date data.",
            inputSchema=WeatherForecastInput.model_json_schema()
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls."""
    logger.info(f"Tool call received: {name} with arguments: {arguments}")

    if name != "get_weather_forecast":
        error_msg = f"Unknown tool: {name}. Only 'get_weather_forecast' is supported."
        logger.error(error_msg)
        return [TextContent(
            type="text",
            text=json.dumps({"error": error_msg})
        )]

    try:
        params = WeatherForecastInput(**arguments)
    except ValidationError as e:
        error_msg = f"Invalid parameters: {str(e)}"
        logger.error(error_msg)
        return [TextContent(
            type="text",
            text=json.dumps({"error": "Invalid parameters. Expected: location (string), start_date (YYYY-MM-DD), end_date (YYYY-MM-DD)"})
        )]

    if not validate_date_format(params.start_date) or not validate_date_format(params.end_date):
        error_msg = f"Invalid date format. Dates must be in YYYY-MM-DD format. Got: start_date={params.start_date}, end_date={params.end_date}"
        logger.error(error_msg)
        return [TextContent(
            type="text",
            text=json.dumps({"error": "Invalid date format. Please use YYYY-MM-DD format (e.g., 2025-12-17)"})
        )]

    if not validate_date_range(params.start_date, params.end_date):
        error_msg = f"Invalid date range: end_date ({params.end_date}) must be >= start_date ({params.start_date})"
        logger.error(error_msg)
        return [TextContent(
            type="text",
            text=json.dumps({"error": f"Invalid date range: end date ({params.end_date}) cannot be before start date ({params.start_date})"})
        )]

    logger.info(f"Geocoding location: {params.location}")
    geo_result = await geocode_location(params.location)
    if not geo_result:
        error_msg = f"Location not found: {params.location}"
        logger.error(error_msg)
        return [TextContent(
            type="text",
            text=json.dumps({"error": f"Location '{params.location}' not found. Please check the spelling or try a different format (e.g., 'City, Country')"})
        )]

    logger.info(f"Fetching weather forecast for {geo_result['name']} ({geo_result['latitude']}, {geo_result['longitude']}) from {params.start_date} to {params.end_date}")
    forecast_data = await get_weather_forecast(
        latitude=geo_result["latitude"],
        longitude=geo_result["longitude"],
        start_date=params.start_date,
        end_date=params.end_date
    )

    if not forecast_data:
        error_msg = f"Weather data not available for location: {geo_result['name']}, dates: {params.start_date} to {params.end_date}"
        logger.error(error_msg)
        return [TextContent(
            type="text",
            text=json.dumps({"error": "Weather forecast data is currently unavailable. Please try again later."})
        )]

    location_name = f"{geo_result['name']}, {geo_result['country']}" if geo_result['country'] else geo_result['name']

    result = {
        "location": location_name,
        "forecast": forecast_data
    }

    logger.info(f"Successfully returning weather forecast for {location_name}, {len(forecast_data)} days")

    return [TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


async def main():
    """Run the MCP server."""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
