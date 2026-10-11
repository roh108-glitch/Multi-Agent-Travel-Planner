import asyncio
from pathlib import Path
import sys
import uuid
from dotenv import load_dotenv
load_dotenv("secrets.env", override=True)
# 1. Add 'src' directory to Python search path
sys.path.append(str(Path.cwd() / "src"))

from langchain_core.messages import HumanMessage
from travel_planner.agents.graph import build_graph


# async def main():
#     print("🚀 Initializing MCP servers and building graph...")
#     # 1. Build and compile graph (fetches tools asynchronously)
#     graph = await build_graph()

#     # 2. Configure thread ID for MemorySaver checkpointing
#     config = {"configurable": {"thread_id": str(uuid.uuid4())}}

#     # 3. Define test user prompt
#     initial_state = {
#         "messages": [
#             HumanMessage(
#                 content="i want to plan a trip to delhi, for 3 days, what are some good places to see there? and what will be the total cost for 3 days?"
#             )
#         ]
#     }

#     print("⚡ Invoking travel planner graph...")
    
#     final_state = await graph.ainvoke(initial_state, config=config)

    

#     print("\n--- FINAL MESSAGE RESPONSE ---")
#     print(final_state["messages"][-1].content)


# if __name__ == "__main__":
#     asyncio.run(main())
async def main():
    print("🚀 Initializing MCP servers and building graph once...")
    # 1. Build the graph ONCE
    graph = await build_graph()

    # 2. Reuse the exact same thread_id across all turns[cite: 7]
    config = {"configurable": {"thread_id": str(uuid.uuid4())}, "recursion_limit":18}

    print("⚡ Interactive session started. Type 'exit' to quit.\n")

    # 3. Interactive turn-by-turn loop
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            break

        # Pass only the NEW message; LangGraph loads previous state via thread_id[cite: 7]
        initial_state = {"messages": [HumanMessage(content=user_input)]}
        
        # Execute turn using the compiled graph[cite: 7]
        final_state = await graph.ainvoke(initial_state, config=config)

        # Print the latest response from the graph[cite: 7]
        print(f"\nAgent: {final_state['messages'][-1].content}\n")

if __name__ == "__main__":
    asyncio.run(main())