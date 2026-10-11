# graph.py
from langgraph.graph import START, StateGraph
from langgraph.prebuilt import tools_condition
from langgraph.checkpoint.memory import InMemorySaver
checkpointer = InMemorySaver()
from .nodes import (
    accommodation_expert,
    attractions_expert,
    budget_expert,
    supervisor,
    transportation_expert,
    weather_expert,
)
from .state import AgentState
from .nodes import get_all_tool_nodes


def create_subagent_tool_router(tool_node_name: str):
    """Creates a routing function for a subagent that directs execution to its

    dedicated tool node if a tool call was emitted, or routes back to the
    supervisor if a text response was produced.
    """

    def router(state: AgentState):
        # tools_condition returns "tools" if the last message has tool_calls, else END
        result = tools_condition(state)
        if result == "tools":
            return tool_node_name
        return "supervisor"

    return router


async def build_graph() -> StateGraph:
    """Asynchronously build the multi-agent travel planner graph.

    - Supervisor uses Command(goto=...) for dynamic routing. - Subagents return
    to Supervisor when finished, or route to their ToolNode when requesting
    tool calls.
    """
    # 1. Fetch pre-configured ToolNodes asynchronously (uses cached MCP tools)
    tool_nodes = await get_all_tool_nodes()

    builder = StateGraph(AgentState)

    # -------------------------------------------------------------------------
    # 2. Register Agent & Supervisor Nodes
    # -------------------------------------------------------------------------
    builder.add_node("supervisor", supervisor)
    builder.add_node("budget_expert", budget_expert)
    builder.add_node("weather_expert", weather_expert)
    builder.add_node("attractions_expert", attractions_expert)
    builder.add_node("accommodation_expert", accommodation_expert)
    builder.add_node("transportation_expert", transportation_expert)

    # -------------------------------------------------------------------------
    # 3. Register Subagent Tool Nodes
    # -------------------------------------------------------------------------
    builder.add_node("budget_tools_node", tool_nodes["budget_tools_node"])
    builder.add_node("weather_tools_node", tool_nodes["weather_tools_node"])
    builder.add_node(
        "attractions_tools_node", tool_nodes["attractions_tools_node"]
    )
    builder.add_node(
        "accommodation_tools_node", tool_nodes["accommodation_tools_node"]
    )
    builder.add_node(
        "transportation_tools_node", tool_nodes["transportation_tools_node"]
    )

    # -------------------------------------------------------------------------
    # 4. Define Entry Point
    # -------------------------------------------------------------------------
    builder.add_edge(START, "supervisor")

    # -------------------------------------------------------------------------
    # 5. Connect Subagents -> Tool Nodes / Supervisor (Conditional Edges)
    # -------------------------------------------------------------------------
    subagents = [
        ("budget_expert", "budget_tools_node"),
        ("weather_expert", "weather_tools_node"),
        ("attractions_expert", "attractions_tools_node"),
        ("accommodation_expert", "accommodation_tools_node"),
        ("transportation_expert", "transportation_tools_node"),
    ]

    for agent_name, tool_node_name in subagents:
        # Route to tool_node_name if tool called, else route back to supervisor
        builder.add_conditional_edges(
            agent_name,
            create_subagent_tool_router(tool_node_name),
            path_map={
                tool_node_name: tool_node_name,
                "supervisor": "supervisor",
            },
        )
        # Direct edge: Tool execution always returns back to its respective subagent
        builder.add_edge(tool_node_name, agent_name)

    # -------------------------------------------------------------------------
    # 6. Compile & Return Graph
    # -------------------------------------------------------------------------
    return builder

