from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
# Point directly to your mcp_server folder on your machine
MCP_ROOT = Path(r"C:\Users\ROHIT\Desktop\mcp_server")
MCP_DIR = MCP_ROOT / "src" / "mcp_server"

# Path to the virtual environment Python executable inside mcp_server
MCP_PYTHON = MCP_ROOT / ".venv" / "Scripts" / "python.exe"

# Point to project root (4 levels up from config.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
SECRETS_FILE = BASE_DIR / "secrets.env"




class Settings(BaseSettings):
    """Application configuration and environment variables."""
    
    # API Keys
    TAVILY_API_KEY: str 
    GROQ_API_KEY: str
    # Local MCP Server File Paths
    BUDGET_SERVER_PATH: str = str(MCP_DIR / "budget_server.py")
    ACCOMMODATION_SERVER_PATH: str = str(MCP_DIR / "accommodation_server.py")
    ATTRACTIONS_SERVER_PATH: str = str(MCP_DIR / "attraction_server.py")
    WEATHER_SERVER_PATH: str = str(MCP_DIR / "weather_server.py")
    TRANSPORT_SERVER_PATH: str = str(MCP_DIR / "transport_server.py")

    LANGSMITH_TRACING: str
    LANGSMITH_ENDPOINT: str
    LANGSMITH_API_KEY: str
    LANGSMITH_PROJECT: str

    MCP_PYTHON_PATH: str = str(MCP_PYTHON)

    model_config = SettingsConfigDict(
        env_file=str(SECRETS_FILE),  # Explicitly load secrets.env from root
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()