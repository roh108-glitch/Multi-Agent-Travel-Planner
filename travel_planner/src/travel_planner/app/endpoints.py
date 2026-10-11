from fastapi import Depends, APIRouter
from langgraph.graph.state import CompiledStateGraph
from .pydantic_models import ChatRequest
from .functions import get_graph, process_chat, fetch_chat_messages, delete_thread, list_threads

router = APIRouter(prefix="/tp")

@router.post("/chat")
async def chat_endpoint(chat_message:ChatRequest, graph:CompiledStateGraph = Depends(get_graph)):
    return await process_chat(chat_message,graph)

@router.get("/chat_messages")
async def fetch_chats(thread_id:str, graph:CompiledStateGraph = Depends(get_graph)):
    return await fetch_chat_messages(thread_id, graph)

@router.delete("/delete_chat")
async def delete_chat(thread_id:str, graph:CompiledStateGraph = Depends(get_graph)):
    return await delete_thread(thread_id, graph)

@router.get("/threads")
async def fetch_threads(graph: CompiledStateGraph = Depends(get_graph)):
    return await list_threads(graph)