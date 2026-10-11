from .server import get_agent_tools
from langgraph.graph import END
from .chains import create_chains
from .state import AgentState
from langchain_core.messages import ToolMessage, AIMessage, HumanMessage
from langgraph.types import Command
from langgraph.prebuilt import ToolNode
from groq import BadRequestError

CHAINS = None
agent_tools_cache = {}

async def get_agent_chains():
    global CHAINS
    if CHAINS is None:
        CHAINS = await create_chains()
    return CHAINS

async def extract_agent_messages(messages):
    """Collects the trailing sequence of ToolMessages and the AIMessage

    that generated them from global state.
    """
    history = []

    # Iterate backwards through global state messages
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            history.append(msg)
        elif isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            history.append(msg)
        else:
            # Stop if we encounter any other message type
            break

    # Reverse back to maintain chronological order
    return list(reversed(history))

async def supervisor(state: AgentState):
    chains = await get_agent_chains()
    supervisor_chain = chains["supervisor"]
    
    filtered_messages = [
        msg for msg in state["messages"]
        if not isinstance(msg, ToolMessage) and not getattr(msg, "tool_calls", None)
    ]
    try:
        response = await supervisor_chain.ainvoke({"messages": filtered_messages})
    except BadRequestError:
        # Model failed to emit the required structured tool call — retry once
        # with an explicit reminder appended to the conversation.
        reminder = HumanMessage(
            content="(System reminder: you must always respond using the SupervisorResponse structured format.)"
        )
        response = await supervisor_chain.ainvoke({"messages": filtered_messages + [reminder]})
    
    content_text = response.response_to_user or ""
    target_goto = END if (not response.next or response.next == "END") else response.next
    
    # Only update state fields that actually changed
    state_updates = {
        "origin": response.origin or state.get("origin"),
        "destination": response.destination or state.get("destination"),
        "budget": response.budget or state.get("budget"),
        "task": response.task or state.get("task")
    }
    
    # Only append a new message if the supervisor wrote something to the user
    if content_text:
        state_updates["messages"] = [AIMessage(content=content_text, name="supervisor")]
        
    return Command(update=state_updates, goto=target_goto)



async def budget_expert(state:AgentState):
    chains = await get_agent_chains()
    messages = state.get("messages", [])
    filtered_messages = await extract_agent_messages(messages)
    budget_chain = chains["budget_expert"]
    task = state.get("task")
    response = await budget_chain.ainvoke({"agent_messages": filtered_messages, "task": task})
    response.name = "budget_expert"
    return {"messages" : [response]}

async def weather_expert(state:AgentState):
    chains = await get_agent_chains()
    messages = state.get("messages", [])
    weather_chain = chains["weather_expert"]
    task = state.get("task")
    filtered_messages = await extract_agent_messages(messages)
    response = await weather_chain.ainvoke({"agent_messages": filtered_messages, "task": task, "destination": state.get("destination") or "not provided"})
    response.name = "weather_expert"
    return {"messages" : [response]}


async def attractions_expert(state:AgentState):
    chains = await get_agent_chains()
    messages = state.get("messages", [])
    attractions_chain = chains["attractions_expert"]
    task = state.get("task")
    filtered_messages = await extract_agent_messages(messages)
    response = await attractions_chain.ainvoke({"agent_messages": filtered_messages, "task": task, "destination": state.get("destination") or "not provided"})
    response.name = "attractions_expert"
    return {"messages" : [response]}

async def accommodation_expert(state:AgentState):
    chains = await get_agent_chains()
    messages = state.get("messages", [])
    accommodation_chain = chains["accommodation_expert"]
    task = state.get("task")
    filtered_messages = await extract_agent_messages(messages)
    response = await accommodation_chain.ainvoke({"agent_messages": filtered_messages, "task": task, "destination": state.get("destination") or "not provided"})
    response.name = "accommodation_expert"
    return {"messages" : [response]}


async def transportation_expert(state:AgentState):
    chains = await get_agent_chains()
    messages = state.get("messages", [])
    transportation_chain = chains["transportation_expert"]
    task = state.get("task")
    filtered_messages = await extract_agent_messages(messages)
    response = await transportation_chain.ainvoke({"agent_messages": filtered_messages, "task": task, "origin": state.get("origin") or "not provided", "destination": state.get("destination") or "not provided"})
    response.name = "transportation_expert"
    return {"messages" : [response]}

async def get_all_tool_nodes():
    global agent_tools_cache

    # 1. Populate cache if empty
    if not agent_tools_cache:
        agent_tools_cache = await get_agent_tools()

    # 2. Construct ToolNodes using the populated cache
    return {
        "budget_tools_node": ToolNode(agent_tools_cache["budget_expert"]),
        "weather_tools_node": ToolNode(agent_tools_cache["weather_expert"]),
        "attractions_tools_node": ToolNode(
            agent_tools_cache["attractions_expert"]
        ),
        "accommodation_tools_node": ToolNode(
            agent_tools_cache["accommodation_expert"]
        ),
        "transportation_tools_node": ToolNode(
            agent_tools_cache["transportation_expert"]
        ),
    }