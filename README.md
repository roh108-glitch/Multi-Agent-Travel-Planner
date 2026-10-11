# Multi-Agent AI Travel Planner

An AI-powered travel planner where a **supervisor agent** coordinates five **specialist agents** (budget, weather, attractions, accommodation, and transport). Each specialist gets live data from its own **MCP (Model Context Protocol) server**, and the supervisor combines their answers into one travel plan.

Ask something like *"Plan a 3-day trip to Jaipur from Delhi with a budget of 20000 INR"* and the system works out costs, weather, sights, hotels, and travel routes for you.

## Features

- **Multi-agent orchestration** with a supervisor that decides which specialist to call next and when to finish
- **Five MCP tool servers**, each running as its own process and exposing tools to the agents
- **Live data sources:** weather forecasts, OpenStreetMap attractions, road routes, hotel listings
- **Budget estimates** from a local SQLite database covering all Indian states and union territories
- **Web search fallback** through Tavily when a primary tool has no answer
- **Persistent chat threads** saved in SQLite, so past trips can be reopened
- **Streamlit chat interface** with a sidebar of saved trips

---

## Architecture

```
Streamlit frontend  ──HTTP──▶  FastAPI backend (LangGraph workflow)
                                    │
                                    ├── Supervisor (structured output decides routing)
                                    │
                                    ├── budget_expert ────▶ budget MCP server ──▶ SQLite
                                    ├── weather_expert ───▶ weather MCP server ──▶ Open-Meteo
                                    ├── attractions_expert ▶ attractions MCP ───▶ OpenStreetMap
                                    ├── accommodation_expert ▶ accommodation MCP ▶ Booking.com (Playwright)
                                    └── transportation_expert ▶ transport MCP ──▶ OSRM / Nominatim
                                    │
                                    └── Tavily web search (fallback for every specialist)
```

The supervisor delegates one task at a time to a specialist. Each specialist calls its tools in a loop and returns to the supervisor, which either asks a follow-up question or writes the final plan.

---

## Tech Stack

| Area | Technologies |
|---|---|
| Agents and orchestration | LangChain, LangGraph |
| LLMs | Groq (`gpt-oss-20b`), Google Gemini via `langchain-google-genai` |
| Tool protocol | MCP (Model Context Protocol), FastMCP, `langchain-mcp-adapters` |
| Backend | FastAPI, Uvicorn, SQLAlchemy, Alembic |
| Frontend | Streamlit |
| Storage | SQLite (chat checkpoints via `langgraph-checkpoint-sqlite`, tourism costs via `aiosqlite`) |
| Browser automation | Playwright (with stealth tweaks) |
| External APIs | Tavily, Open-Meteo, OpenStreetMap (Nominatim and Overpass), OSRM, LangSmith (tracing) |
| Tooling | uv, Python 3.12 |

---

## Project Structure

```
multi-agent-travel-planner/
├── travel_planner/          # Agents, LangGraph workflow, FastAPI backend, Streamlit frontend
│   ├── frontend/
│   │   └── app.py           # Streamlit chat UI
│   └── src/travel_planner/
│       ├── agents/          # Supervisor and specialist nodes, prompts, graph, state
│       └── app/             # FastAPI endpoints, config, chat functions
├── mcp_server/              # MCP tool servers
│   └── src/mcp_server/
│       ├── budget_server.py
│       ├── weather_server.py
│       ├── attraction_server.py
│       ├── accommodation_server.py
│       ├── transport_server.py
│       └── tourism_data/    # SQLite database of Indian travel costs
├── Dockerfile
├── .dockerignore
└── README.md
```

---

## How It Works

1. You send a message to the Streamlit chat.
2. The FastAPI backend passes it to the LangGraph workflow, with the chat thread ID so the conversation is remembered.
3. The supervisor reads the conversation and extracts the origin, destination, and budget. If something important is missing (such as dates for hotel searches), it asks you.
4. The supervisor sends one self-contained task to a specialist.
5. The specialist calls its MCP tools, falls back to Tavily when needed, and returns its findings.
6. The supervisor repeats steps 4 and 5 until every part of your request is answered, then writes a single combined plan.

---

## Running Locally

### Prerequisites
- Python 3.12
- [uv](https://docs.astral.sh/uv/) package manager
- API keys for Groq, Google Gemini, Tavily, and (optional) LangSmith

### 1. Clone the repository
```bash
git clone https://github.com/roh108-glitch/multi-agent-travel-planner.git
cd multi-agent-travel-planner
```

### 2. Add your API keys
In the `travel_planner` folder, copy `secrets.env.example` to `secrets.env` and fill in your keys:

```env
TAVILY_API_KEY=your_key
GROQ_API_KEY=your_key
GOOGLE_API_KEY=your_key
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=your_key
LANGSMITH_PROJECT=your_project
```

> **[CHECK]** Make sure `secrets.env.example` lists every key your code reads, including `GOOGLE_API_KEY`.

### 3. Install dependencies
```bash
cd travel_planner
uv sync

cd ../mcp_server
uv sync
uv run playwright install chromium
```

### 4. Start the backend
```bash
cd travel_planner/src
uv run uvicorn travel_planner.app.main:app --reload
```

### 5. Start the frontend
In a second terminal:
```bash
cd travel_planner
uv run streamlit run frontend/app.py
```

Open http://localhost:8501 in your browser.

---



## Known Limitations

- **Booking.com scraping** is unreliable. Cloud IPs are often blocked, so the accommodation agent relies on Tavily in those cases.
- **Free-tier LLM limits** (Groq tokens per minute) can make long conversations fail. Starting a new chat helps.
- **Live location lookup** (`get_user_current_location`) reports the server's location, not the user's, when deployed.
- **Chat history** is stored in a local SQLite file, so it resets on hosts without persistent storage.

---

## Future Improvements

- Flight search through a dedicated API
- Itinerary export as PDF or calendar file
- Day-by-day itinerary view in the UI
- Automated tests for each agent and MCP tool

---

## Author

**Rohit** · [GitHub: roh108-glitch](https://github.com/roh108-glitch)

---

