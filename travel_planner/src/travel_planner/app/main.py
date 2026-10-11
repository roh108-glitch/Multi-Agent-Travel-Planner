from pathlib import Path
from dotenv import load_dotenv
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(ROOT_DIR / "secrets.env", override=True)
from contextlib import asynccontextmanager
from fastapi import FastAPI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from ..agents.graph import build_graph
from .endpoints import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP LOGIC ---
    # 1. Open the async SQLite connection context
    async with AsyncSqliteSaver.from_conn_string("travel_planner.db") as checkpointer:
        # 2. Build the graph builder
        builder = await build_graph()
        
        # 3. Compile graph ONCE with the active checkpointer context
        compiled_graph = builder.compile(checkpointer=checkpointer)
        
        # 4. Attach compiled graph to FastAPI state so endpoints can access it
        app.state.graph = compiled_graph
        
        print("✅ LangGraph compiled with AsyncSqliteSaver successfully.")
        
        # Yield control to FastAPI app while it runs
        yield
        
    # --- SHUTDOWN LOGIC ---
    # When server stops, the async context closes connection automatically
    print("🛑 Checkpointer connection closed.")

app = FastAPI(title="Travel Planner", lifespan=lifespan)
app.include_router(router)