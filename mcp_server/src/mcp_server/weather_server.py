import asyncio
import time
from typing import List, Optional, Dict, Any
import httpx
from fastmcp import FastMCP

mcp = FastMCP("Weather")

GEOCODING_URL = "https://nominatim.openstreetmap.org/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

STATE_CAPITAL_MAP = {
    # 28 States
    "andhra pradesh": "Amaravati",
    "arunachal pradesh": "Itanagar",
    "assam": "Dispur",
    "bihar": "Patna",
    "chhattisgarh": "Raipur",
    "goa": "Panaji",
    "gujarat": "Gandhinagar",
    "haryana": "Chandigarh",
    "himachal pradesh": "Shimla",
    "jharkhand": "Ranchi",
    "karnataka": "Bengaluru",
    "kerala": "Thiruvananthapuram",
    "madhya pradesh": "Bhopal",
    "maharashtra": "Mumbai",
    "manipur": "Imphal",
    "meghalaya": "Shillong",
    "mizoram": "Aizawl",
    "nagaland": "Kohima",
    "odisha": "Bhubaneswar",
    "punjab": "Chandigarh",
    "rajasthan": "Jaipur",
    "sikkim": "Gangtok",
    "tamil nadu": "Chennai",
    "telangana": "Hyderabad",
    "tripura": "Agartala",
    "uttar pradesh": "Lucknow",
    "uttarakhand": "Dehradun",
    "west bengal": "Kolkata",
    
    # Key Union Territories
    "andaman and nicobar islands": "Port Blair",
    "chandigarh": "Chandigarh",
    "dadra and nagar haveli and daman and diu": "Daman",
    "delhi": "New Delhi",
    "jammu and kashmir": "Srinagar",
    "ladakh": "Leh",
    "lakshadweep": "Kavaratti",
    "puducherry": "Puducherry"
}

# --- Nominatim rate limiting ---
# Nominatim's usage policy caps requests at 1/second. Concurrent geocode calls
# (e.g. via asyncio.gather across multiple locations) can breach this, so we
# serialize and pace requests.
_NOMINATIM_LOCK = asyncio.Lock()
_last_nominatim_call = 0.0
_NOMINATIM_MIN_INTERVAL = 1.0  # seconds


async def _throttle_nominatim() -> None:
    """Ensures at most 1 Nominatim request per second from this process."""
    global _last_nominatim_call
    async with _NOMINATIM_LOCK:
        now = time.monotonic()
        wait = _NOMINATIM_MIN_INTERVAL - (now - _last_nominatim_call)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_nominatim_call = time.monotonic()


async def fetch_coordinates(
    client: httpx.AsyncClient, location_name: str
) -> Optional[Dict[str, Any]]:
    """Helper to fetch latitude and longitude for a given location string."""
    clean_name = location_name.strip()
    
    # 1. Check if the input is a known state name and map to its capital
    lookup_name = STATE_CAPITAL_MAP.get(clean_name.lower(), clean_name)
    headers = {
        "User-Agent": "UniqueTransportMCPToolsServer/1.0 (rohitskillman@gmail.com)",
        "Referer": "https://github.com/roh108-glitch"
    }
    params = {
        "q": lookup_name,
        "format": "json",
        "limit": 1
    }
    await _throttle_nominatim()
    response = await client.get(GEOCODING_URL, params=params, headers=headers)
    
    if response.status_code != 200:
        return None
        
    data = response.json()
    
    if not data or not isinstance(data, list):
        return None
        
    top_result = data[0]
    return {
        "name": top_result.get("display_name"),
        "latitude": float(top_result["lat"]),
        "longitude": float(top_result["lon"]),
    }


async def fetch_weather_for_single_location(
    client: httpx.AsyncClient, location_query: str
) -> Dict[str, Any]:
    """Helper to geocode a location and fetch its current weather & forecast."""
    geo_data = await fetch_coordinates(client, location_query)
    
    if not geo_data:
        return {
            "query": location_query,
            "status": "error",
            "message": f"Could not geocode location '{location_query}'."
        }

    weather_params = {
        "latitude": geo_data["latitude"],
        "longitude": geo_data["longitude"],
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "apparent_temperature",
            "precipitation",
            "weather_code",
            "wind_speed_10m"
        ],
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum"
        ],
        "timezone": "auto",
        "forecast_days": 3
    }

    response = await client.get(WEATHER_URL, params=weather_params)
    
    if response.status_code != 200:
        return {
            "query": location_query,
            "status": "error",
            "message": "Failed to fetch weather data from Open-Meteo."
        }

    weather_json = response.json()
    
    return {
        "query": location_query,
        "resolved_location": geo_data.get("name", location_query),
        "coordinates": {
            "latitude": geo_data["latitude"],
            "longitude": geo_data["longitude"]
        },
        "current_weather": weather_json.get("current", {}),
        "daily_forecast": weather_json.get("daily", {})
    }


@mcp.tool()
async def get_weather_info(
    location: Optional[str] = None,
    locations: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Fetches real-time weather details and a 3-day forecast using Open-Meteo.

    Accepts a single location name or a list of multiple locations.
    Geocodes input automatically (cities, states, tourist landmarks, countries).
    Suitable to use for general cities and well defined locations

    Args:
        location: Optional single location query string (e.g., 'Jaipur', 'Shimla, HP', 'Havelock Island').
        locations: Optional list of location queries for bulk execution (e.g., ['Delhi', 'Manali', 'Goa']).

    Returns:
        List of result dictionaries containing resolved coordinates, current temperature, 
        humidity, wind speed, precipitation, and 3-day min/max daily forecasts.
    """
    # 1. Parameter Normalization
    target_locations: List[str] = []
    
    if location:
        target_locations.append(location.strip())
    if locations:
        target_locations.extend([loc.strip() for loc in locations if loc.strip()])

    if not target_locations:
        raise ValueError("At least one location argument ('location' or 'locations') must be provided.")

    # 2. Async Client Execution using asyncio.gather for parallel fetching
    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks = [
            fetch_weather_for_single_location(client, loc) 
            for loc in target_locations
        ]
        results = await asyncio.gather(*tasks)

    return list(results)

# async def main():
#     result = await get_weather_info(location="jaipur")
#     print(result)
if __name__ == "__main__":
    # asyncio.run(main())
    mcp.run(transport="stdio")