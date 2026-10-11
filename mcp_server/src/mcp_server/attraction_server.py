import asyncio
import time
from typing import List, Optional, Dict, Any
import httpx
from fastmcp import FastMCP
import logging
import logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("attractions_server")

mcp = FastMCP("Attractions")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Primary & Fallback Overpass Endpoints
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

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
    """Helper to geocode a location name into lat/lon using Nominatim."""
    clean_name = location_name.strip()
    lookup_name = STATE_CAPITAL_MAP.get(clean_name.lower(), clean_name)

    params = {
        "q": lookup_name,
        "format": "json",
        "limit": 1,
        "addressdetails": 1,
    }
    headers = {
            "User-Agent": "UniqueTransportMCPToolsServer/1.0 (roh108-glitch@users.noreply.github.com)",
            "Referer": "https://github.com/roh108-glitch"
        }
    try:
        await _throttle_nominatim()
        response = await client.get(NOMINATIM_URL, params=params, headers=headers)
        if response.status_code != 200:
            return None
        data = response.json()
        if not data:
            return None

        top_result = data[0]
        address = top_result.get("address", {})
        
        return {
            "name": top_result.get("name") or top_result.get("display_name", "").split(",")[0],
            "admin1": address.get("state", address.get("region", "")),
            "country": address.get("country", ""),
            "latitude": float(top_result["lat"]),
            "longitude": float(top_result["lon"]),
        }
    except Exception:
        return None


async def query_overpass_with_fallback(
    client: httpx.AsyncClient, overpass_query: str
) -> Optional[Dict[str, Any]]:
    """Tries primary Overpass API and falls back to mirrors if HTTP 406/504 occurs."""
    headers = {
    "User-Agent": "AttractionsServiceApp/1.0 (roh108-glitch@users.noreply.github.com)",
    "Referer": "https://github.com/roh108-glitch",
    "Content-Type": "text/plain; charset=utf-8",
}

    for url in OVERPASS_URLS:
        try:
            response = await client.post(url, content=overpass_query.encode("utf-8"), headers=headers, timeout=25.0)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"{url} -> {response.status_code}: {response.text[:300]}")
        except Exception as e:
            logger.warning(f"{url} -> {type(e).__name__}: {e}")
            continue
            
    return None


async def fetch_attractions_for_location(
    client: httpx.AsyncClient,
    location_query: str,
    radius_meters: int,
    limit: int,
) -> Dict[str, Any]:
    geo_data = await fetch_coordinates(client, location_query)

    if not geo_data:
        return {
            "query": location_query,
            "status": "error",
            "message": f"Could not geocode location '{location_query}'.",
        }

    lat = geo_data["latitude"]
    lon = geo_data["longitude"]

    overpass_query = f"""[out:json][timeout:25];
(
  nwr["tourism"~"attraction|museum|theme_park|zoo"](around:{radius_meters},{lat},{lon})["wikipedia"];
  nwr["historic"~"monument|castle|fort|ruins|archaeological_site"](around:{radius_meters},{lat},{lon})["wikipedia"];
  nwr["leisure"~"water_park|nature_reserve"](around:{radius_meters},{lat},{lon})["wikipedia"];
);
out center body;"""

    try:
        osm_data = await query_overpass_with_fallback(client, overpass_query)

        if not osm_data:
            return {
                "query": location_query,
                "status": "error",
                "message": "Overpass servers returned an error or were unreachable.",
            }

        elements = osm_data.get("elements", [])
        attractions = []
        seen_names = set()

        for el in elements:
            tags = el.get("tags", {})
            name = tags.get("name") or tags.get("name:en")

            if not name or name in seen_names:
                continue

            seen_names.add(name)

            category = (
                tags.get("tourism")
                or tags.get("historic")
                or tags.get("leisure")
                or "Point of Interest"
            )

            coords = el.get("center", {}) if "center" in el else {
                "lat": el.get("lat"),
                "lon": el.get("lon"),
            }

            attractions.append({
                "name": name,
                "category": category.replace("_", " ").title(),
                "coordinates": coords,
            })

            if len(attractions) >= limit:
                break

        resolved_loc = f"{geo_data['name']}, {geo_data.get('admin1', '')}, {geo_data.get('country', '')}".strip(", ")

        return {
            "query": location_query,
            "resolved_location": resolved_loc,
            "radius_km": radius_meters / 1000,
            "total_found": len(attractions),
            "attractions": attractions,
        }

    except Exception as e:
        return {
            "query": location_query,
            "status": "error",
            "message": f"Failed to fetch attractions: {str(e)}",
        }


@mcp.tool()
async def get_tourist_attractions(
    location: Optional[str] = None,
    locations: Optional[List[str]] = None,
    radius_km: int = 25,
    limit_per_location: int = 30,
) -> List[Dict[str, Any]]:
    """
    Fetches tourist spots, historical monuments, parks, and key points of interest around a location using OpenStreetMap.

    Accepts a single location name or a list of multiple locations.
    Automatically geocodes locations (cities, towns, landmarks, or states).

    Args:
        location: Optional single location query string (e.g., 'Jaipur', 'Shimla', 'Manali').
        locations: Optional list of location queries for batch processing (e.g., ['Agra', 'Udaipur']).
        radius_km: Search radius around the location center in kilometers (default: 25 km).
        limit_per_location: Maximum number of distinct attractions to return per location (default: 30).

    Returns:
        List of result dictionaries containing resolved location, category, name and exact coordinates for each attraction.
    """
    target_locations: List[str] = []

    if location:
        target_locations.append(location.strip())
    if locations:
        target_locations.extend([loc.strip() for loc in locations if loc.strip()])

    if not target_locations:
        raise ValueError("At least one location argument must be provided.")

    radius_meters = int(radius_km * 1000)

    async with httpx.AsyncClient(timeout=35.0) as client:
        tasks = [
            fetch_attractions_for_location(
                client, loc, radius_meters, limit_per_location
            )
            for loc in target_locations
        ]
        results = await asyncio.gather(*tasks)

    return list(results)


# async def main():
#     result = await get_tourist_attractions(location="Delhi")
#     print(result)

if __name__ == "__main__":
    mcp.run(transport="stdio")
    # asyncio.run(main())