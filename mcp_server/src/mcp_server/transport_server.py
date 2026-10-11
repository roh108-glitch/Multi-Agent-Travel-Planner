from typing import Any, Dict
import httpx
from fastmcp import FastMCP
import asyncio  
import json
import time


mcp = FastMCP(name="Transport")
OSRM_BASE_URL = "https://router.project-osrm.org/route/v1/driving"

# --- Nominatim rate limiting ---
# Nominatim's usage policy caps requests at 1/second. Concurrent geocode calls
# (e.g. via asyncio.gather) can breach this, so we serialize and pace requests.
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


async def fetch_coordinates(loc1: str, loc2: str) -> dict:
    """
    Asynchronously fetches latitude and longitude for two location strings
    using HTTPX and the OpenStreetMap Nominatim API.
    """
    base_url = "https://nominatim.openstreetmap.org/search"
    
    # Custom headers are mandatory to comply with Nominatim's policy
    headers = {
        "User-Agent": "UniqueTransportMCPToolsServer/1.0 (rohitskillman@gmail.com)",
        "Referer": "https://github.com/roh108-glitch"
    }
    
    # Initialize the HTTPX AsyncClient
    async with httpx.AsyncClient(headers=headers, timeout=10.0,follow_redirects=True) as client:
        
        async def geocode(location_string: str):
            params = {
                "q": location_string,
                "format": "json",
                "limit": 1
            }
            
            try:
                await _throttle_nominatim()
                # HTTPX uses the exact same keyword arguments as requests/aiohttp
                response = await client.get(base_url, params=params)
                
                # Check for HTTP errors (4xx, 5xx)
                response.raise_for_status()
                
                data = response.json()
                
                if data:
                    return {
                        "address": data[0].get("display_name"),
                        "lat": float(data[0]["lat"]),
                        "lon": float(data[0]["lon"])
                    }
                return {"error": "Location not found"}
                
            except httpx.HTTPStatusError as e:
                return {"error": f"HTTP Error {e.response.status_code}"}
            except Exception as e:
                return {"error": f"Network exception: {str(e)}"}

        # Fire both geocode calls; internal throttle now paces the actual
        # Nominatim requests to stay within the 1/sec policy.
        results = await asyncio.gather(geocode(loc1), geocode(loc2))
        
        return {
            "location_1": results[0],
            "location_2": results[1]
        }
    
@mcp.tool()
async def get_user_current_location() -> Dict[str, Any]:
    """Retrieves the user's current geographic location based on their public IP address.

    Utilizes the free `ip-api.com` service to automatically determine the starting point
    for transport and travel queries when an explicit origin is not provided by the user.

    Returns:
        Dict[str, Any]: A dictionary containing location metadata if successful, or an error payload:
            - city (str): Name of the detected city (e.g., "Gurugram").
            - region (str): Name of the region/state (e.g., "Haryana").
            - country (str): Name of the country (e.g., "India").
            - lat (float): Approximate latitude coordinates.
            - lon (float): Approximate longitude coordinates.
            - error (str, optional): Descriptive error message if resolution fails.
    """
    ip_api_url = "http://ip-api.com/json/"
    custom_headers= {
        "User-Agent": "MCP-Transport-Agent/1.0"
    }

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(5.0), headers=custom_headers
        ) as client:
            response = await client.get(ip_api_url)
            response.raise_for_status()
            data = response.json()

            # IP-API returns status 'fail' for invalid/private IPs
            if data.get("status") == "fail":
                return {
                    "error": data.get(
                        "message", "Failed to resolve current IP address."
                    )
                }

            return {
                "city": data.get("city"),
                "region": data.get("regionName"),
                "country": data.get("country"),
                "lat": float(data.get("lat", 0.0)),
                "lon": float(data.get("lon", 0.0)),
            }

    except httpx.HTTPError as http_err:
        return {"error": f"HTTP network error during IP lookup: {str(http_err)}"}
    except Exception as err:
        return {"error": f"Unexpected error resolving location: {str(err)}"}


async def main() -> None:
    result = await get_user_current_location()
    print(json.dumps(result, indent=2))



@mcp.tool()
async def calculate_road_route(
    start_location: str,
    destination: str,
) -> Dict[str, Any]:
    """Calculates driving distance and travel time between two road locations.

    Args:
        start_location: Starting point city, address, or landmark (e.g.
          "Gurugram, Haryana").
        destination: Destination city, address, or landmark (e.g. "Bangalore,
          Karnataka").

    Returns:
        Dict containing road distance in kilometers and formatted travel time.
    """
    # 1. Fetch coordinates using helper
    coords_data = await fetch_coordinates(start_location, destination)

    loc1 = coords_data.get("location_1", {})
    loc2 = coords_data.get("location_2", {})

    if "error" in loc1:
        return {"error": loc1["error"]}
    if "error" in loc2:
        return {"error": loc2["error"]}

    start_lat, start_lon = loc1["lat"], loc1["lon"]
    dest_lat, dest_lon = loc2["lat"], loc2["lon"]

    # 2. Build OSRM request URL (OSRM expects: longitude,latitude)
    osrm_url = (
        f"{OSRM_BASE_URL}/{start_lon},{start_lat};{dest_lon},{dest_lat}"
    )

    try:
        async with httpx.AsyncClient(timeout=10.0,follow_redirects=True) as client:
            response = await client.get(
                osrm_url, params={"overview": "false", "steps": "false"}
            )
            response.raise_for_status()
            data = response.json()

        if data.get("code") != "Ok" or not data.get("routes"):
            return {"error": "No driving route found between the specified locations."}

        route = data["routes"][0]
        distance_km = round(route.get("distance", 0.0) / 1000.0, 2)
        duration_seconds = route.get("duration", 0.0)

        # Format travel duration
        total_minutes = int(round(duration_seconds / 60.0))
        hours, minutes = divmod(total_minutes, 60)
        duration_formatted = (
            f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
        )

        return {
            "start_location": start_location,
            "destination": destination,
            "distance_km": distance_km,
            "duration_formatted": duration_formatted,
        }

    except Exception as err:
        return {"error": f"Failed to compute route: {str(err)}"}

# async def main():
#     # Example usage of the calculate_road_route tool
#     result = await calculate_road_route(
#         start_location="Gurugram, Haryana",
#         destination="Bangalore, Karnataka"
#     )
#     print(json.dumps(result, indent=2))

if __name__ == "__main__":
    # asyncio.run(main())
    mcp.run(transport="stdio")