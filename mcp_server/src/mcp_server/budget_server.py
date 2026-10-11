import aiosqlite
from typing import Optional, List, Dict, Any, Literal
from fastmcp import FastMCP
from pathlib import Path
import csv
import io

CURRENT_DIR = Path(__file__).parent
# Initialize FastMCP Server
mcp = FastMCP("Budget")

DB_PATH = CURRENT_DIR / "tourism_data" / "indian_tourism.db"


@mcp.tool()
async def query_Indian_budget(
    state_name: Optional[str] = None,
    city_name: Optional[str] = None,
    category: Optional[Literal["Budget", "Mid-Range", "Luxury"]] = None,
    min_cost: Optional[float] = None,
    max_cost: Optional[float] = None,
    limit: int = 5,
) -> str:
    """
    Queries daily estimated travel costs for Indian cities and tourist destinations.

    IMPORTANT: This tool ONLY covers locations within India (states, union territories, and Indian cities).
    It allows filtering by state, city, budget tier ('Budget', 'Mid-Range', 'Luxury'), and a cost range or specific budget.

    Args:
        state_name: Optional Indian state or UT name (e.g., 'Andaman and Nicobar Islands', 'Goa', 'Rajasthan').
        city_name: Optional city or island name (e.g., 'Havelock Island (Swaraj Dweep)', 'Jaipur').
        category: Optional travel style tier. Must be 'Budget', 'Mid-Range', or 'Luxury'.
        min_cost: Optional lower bound for daily cost filter in INR (₹). If searching for an exact cost, set min_cost = max_cost.
        max_cost: Optional upper bound for daily cost filter in INR (₹). If searching for an exact cost, set min_cost = max_cost.
        limit: Maximum number of rows to return to manage response size and token usage (default: 5).

    Returns:
        A CSV-formatted string containing matching records with columns:
        id,state_name,city_name,category,daily_estimated_cost
    """
    # 1. Validation: At least one search parameter must be provided
    if all(param is None for param in [state_name, city_name, category, min_cost, max_cost]):
        raise ValueError("At least one parameter (state_name, city_name, category, min_cost, or max_cost) must be provided.")

    # 2. Dynamic Query Builder
    query = "SELECT id, state_name, city_name, category, daily_estimated_cost FROM tourist_daily_costs WHERE 1=1"
    params: List[Any] = []

    if state_name:
        query += " AND LOWER(state_name) = LOWER(?)"
        params.append(state_name.strip())

    if city_name:
        query += " AND LOWER(city_name) LIKE LOWER(?)"
        params.append(f"%{city_name.strip()}%")

    if category:
        query += " AND LOWER(category) = LOWER(?)"
        params.append(category.strip())

    if min_cost is not None:
        query += " AND daily_estimated_cost >= ?"
        params.append(min_cost)

    if max_cost is not None:
        query += " AND daily_estimated_cost <= ?"
        params.append(max_cost)

    query += " ORDER BY state_name, city_name, daily_estimated_cost ASC LIMIT ?"
    params.append(limit)

    # 3. Asynchronous DB Execution and CSV Formatting
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        return "No matching records found."

    # Render directly to CSV string format using StringIO
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "state_name", "city_name", "category", "daily_estimated_cost"])
    writer.writerows(rows)

    return output.getvalue().strip()


if __name__ == "__main__":
    mcp.run(transport="stdio")
