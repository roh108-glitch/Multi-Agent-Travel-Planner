from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
from ..app.config import settings
from .server import get_agent_tools
from .prompts import supervisor_prompt, budget_expert_prompt, accommodation_expert_prompt, attractions_expert_prompt, weather_expert_prompt, transportation_expert_prompt
from .state import SupervisorResponse
# llm = ChatOllama(model="qwen2.5:latest")
llm = ChatGroq(
    api_key=settings.GROQ_API_KEY,
    model="openai/gpt-oss-20b",
    temperature=0.5,
    max_retries=5,
)

async def create_chains()->dict[str,any]:
    agent_tools = await get_agent_tools()
    supervisor_llm = llm.with_structured_output(SupervisorResponse, method='json_schema')
    budget_llm = llm.bind_tools(agent_tools["budget_expert"])
    weather_llm = llm.bind_tools(agent_tools["weather_expert"])
    attractions_llm = llm.bind_tools(agent_tools["attractions_expert"])
    accommodation_llm = llm.bind_tools(agent_tools["accommodation_expert"])
    transportation_llm = llm.bind_tools(agent_tools["transportation_expert"])

    chains = {
        "supervisor": supervisor_prompt | supervisor_llm,
        "budget_expert": budget_expert_prompt | budget_llm,
        "weather_expert": weather_expert_prompt | weather_llm,
        "attractions_expert": attractions_expert_prompt | attractions_llm,
        "accommodation_expert": accommodation_expert_prompt | accommodation_llm,
        "transportation_expert": transportation_expert_prompt
        | transportation_llm,
    }

    return chains
