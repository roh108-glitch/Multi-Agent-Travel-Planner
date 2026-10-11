# app/functions.py
from fastapi import Request
from langgraph.graph.state import CompiledStateGraph
from .pydantic_models import ChatRequest
from langchain_core.messages import AIMessage, HumanMessage
 
def get_graph(request: Request) -> CompiledStateGraph:
    """Extracts the single pre-compiled graph from FastAPI app state."""
    return request.app.state.graph

async def process_chat(chat:ChatRequest, graph:CompiledStateGraph):
    config = {"configurable": {"thread_id": chat.thread_id}}
    input_data = {"messages": [("user", chat.message)]}
    
    # Run the graph asynchronously
    response = await graph.ainvoke(input_data, config=config)
    
    return {
        "thread_id": chat.thread_id,
        "response": response["messages"][-1].content
    }

async def fetch_chat_messages(thread_id:str, graph:CompiledStateGraph):
    config = {"configurable":{"thread_id":thread_id}}
    state_snapshot = await graph.aget_state(config)
    
    if not state_snapshot.values:
        return {"thread_id": thread_id, "messages": []}
    raw_messages = state_snapshot.values.get("messages", [])
    filtered_msgs = [msg for msg in raw_messages
        if isinstance(msg, HumanMessage)
        or (isinstance(msg, AIMessage) and msg.name == "supervisor")]
    return [
        {"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content}
        for m in filtered_msgs
    ]

async def delete_thread(thread_id: str, graph: CompiledStateGraph):
    # Pass thread_id directly as a string (NOT a config dict)
    await graph.checkpointer.adelete_thread(thread_id)
    
    return {"status": "success", "message": f"Thread {thread_id} purged."}

async def list_threads(graph: CompiledStateGraph):
    """One entry per saved thread (threads with at least one human message), newest first."""
    latest = {}  # alist yields newest checkpoints first, so the first hit per thread is its latest
    async for tup in graph.checkpointer.alist(None):
        tid = tup.config["configurable"]["thread_id"]
        if tid not in latest:
            latest[tid] = tup

    threads = []
    for tid, tup in latest.items():
        messages = (tup.checkpoint.get("channel_values") or {}).get("messages", [])
        first_user = next((str(m.content) for m in messages if isinstance(m, HumanMessage)), None)
        if not first_user:
            continue
        threads.append({
            "thread_id": tid,
            "title": first_user,
            "updated_at": tup.checkpoint.get("ts", ""),
        })

    threads.sort(key=lambda t: t["updated_at"] or "", reverse=True)
    return threads