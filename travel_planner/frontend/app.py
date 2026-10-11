"""
Travel Planner - Streamlit frontend
Location: <project-root>/frontend/app.py

Run from the project root, with the FastAPI backend already running:
    streamlit run frontend/app.py
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import requests
import streamlit as st

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
API_BASE_URL = os.getenv("TRAVEL_API_URL", "http://127.0.0.1:8000/tp").rstrip("/")
CHAT_TIMEOUT = 600   # the multi-agent graph can take minutes
QUICK_TIMEOUT = 20   # history, thread list, delete
MAX_TITLE_LEN = 45
# Fixed offset instead of zoneinfo: Windows often has no timezone database.
IST = timezone(timedelta(hours=5, minutes=30))

st.set_page_config(page_title="Travel Planner", page_icon="🧳", layout="wide")


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def new_thread_id() -> str:
    return str(uuid.uuid4())


def api(method: str, path: str, *, params=None, json_body=None, timeout=QUICK_TIMEOUT):
    """Call the backend. Always returns (ok, data) and never raises."""
    url = f"{API_BASE_URL}{path}"
    try:
        resp = requests.request(method, url, params=params, json=json_body, timeout=timeout)
    except requests.exceptions.ConnectionError:
        return False, f"Can't reach the backend at {API_BASE_URL}. Is the FastAPI server running?"
    except requests.exceptions.Timeout:
        return False, "The backend took too long to respond. Please try again."
    except requests.RequestException as exc:
        return False, f"Network error while contacting the backend: {exc}"

    try:
        data = resp.json()
    except ValueError:
        data = None

    if not resp.ok:
        detail = data.get("detail") if isinstance(data, dict) else None
        return False, f"Backend error ({resp.status_code}): {detail or resp.text[:300]}"

    return True, data


def to_text(content) -> str:
    """LLM content can be a string or a list of content blocks. Always return a string."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "\n".join(p for p in parts if p).strip()
    return str(content).strip()


def md(text: str) -> str:
    """Escape '$' so prices like '$50 to $100' don't render as LaTeX in Streamlit markdown."""
    return text.replace("$", r"\$")


def make_title(text) -> str:
    text = " ".join(str(text or "").split())
    if not text:
        return "Untitled trip"
    if len(text) > MAX_TITLE_LEN:
        return text[: MAX_TITLE_LEN - 1].rstrip() + "…"
    return text


def fmt_time(ts) -> str:
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST).strftime("%d %b %Y, %I:%M %p")


def normalize_history(data) -> list:
    # /chat_messages returns a list, but an empty thread comes back as {"thread_id": ..., "messages": []}
    if isinstance(data, dict):
        data = data.get("messages", [])
    if not isinstance(data, list):
        return []
    result = []
    for item in data:
        if isinstance(item, dict) and item.get("role") in ("user", "assistant"):
            text = to_text(item.get("content"))
            if text:
                result.append({"role": item["role"], "content": text})
    return result


def clean_threads(data) -> list:
    if not isinstance(data, list):
        return []
    return [t for t in data if isinstance(t, dict) and isinstance(t.get("thread_id"), str)]


# ----------------------------------------------------------------------------
# Data loading (cached in session_state, invalidated when things change)
# ----------------------------------------------------------------------------
def load_threads() -> None:
    if st.session_state.threads is not None:
        return
    ok, data = api("GET", "/threads")
    if ok and isinstance(data, list):
        st.session_state.threads = clean_threads(data)
        st.session_state.threads_error = None
    else:
        st.session_state.threads = []
        st.session_state.threads_error = data if not ok else "Unexpected response from /threads."


def load_history(thread_id: str):
    cached = st.session_state.history.get(thread_id)
    if cached is not None:
        return cached, None
    ok, data = api("GET", "/chat_messages", params={"thread_id": thread_id})
    if not ok:
        return [], data
    messages = normalize_history(data)
    st.session_state.history[thread_id] = messages
    return messages, None


def send_message(thread_id: str, text: str):
    ok, data = api(
        "POST", "/chat",
        json_body={"message": text, "thread_id": thread_id},
        timeout=CHAT_TIMEOUT,
    )
    if not ok:
        return False, data
    reply = to_text(data.get("response")) if isinstance(data, dict) else ""
    return True, reply or "_(The planner returned an empty response.)_"


# ----------------------------------------------------------------------------
# Callbacks (run before the script re-runs, so the UI is already updated)
# ----------------------------------------------------------------------------
def _open_thread(tid: str) -> None:
    st.session_state.current_thread_id = tid
    st.session_state.delete_error = None


def _new_chat() -> None:
    st.session_state.current_thread_id = new_thread_id()
    st.session_state.delete_error = None


def _refresh_threads() -> None:
    st.session_state.threads = None


def _delete_thread(tid: str) -> None:
    ok, data = api("DELETE", "/delete_chat", params={"thread_id": tid})
    if ok:
        st.session_state.history.pop(tid, None)
        st.session_state.threads = None
        st.session_state.current_thread_id = new_thread_id()   # open a fresh chat
        st.session_state.delete_error = None
    else:
        st.session_state.delete_error = data                   # keep the thread, show why


# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------
def render_sidebar() -> None:
    load_threads()
    threads = st.session_state.threads or []
    current = st.session_state.current_thread_id
    saved_ids = {t["thread_id"] for t in threads}

    with st.sidebar:
        st.title("🧳 Your trips")
        st.button("➕ New chat", on_click=_new_chat)

        st.divider()
        head, refresh = st.columns([4, 1])
        head.caption("Saved chats")
        refresh.button("⟳", help="Reload the list", on_click=_refresh_threads, key="refresh_threads")

        if st.session_state.threads_error:
            st.warning(f"Couldn't load saved chats. {st.session_state.threads_error}")

        if current not in saved_ids:
            st.markdown("**▸ New chat** _(saved once you send a message)_")

        if not threads and not st.session_state.threads_error:
            st.caption("No saved chats yet.")

        for t in threads:
            tid = t["thread_id"]
            st.button(
                make_title(t.get("title")),
                key=f"open_{tid}",
                type="primary" if tid == current else "secondary",
                on_click=_open_thread,
                args=(tid,),
                help=fmt_time(t.get("updated_at")) or None,
            )


def render_delete_button(tid: str) -> None:
    with st.popover("🗑️ Delete"):
        st.write("Delete this chat permanently? This can't be undone.")
        st.button(
            "Yes, delete",
            type="primary",
            key=f"confirm_delete_{tid}",
            on_click=_delete_thread,
            args=(tid,),
        )


def handle_prompt(tid: str, prompt: str) -> None:
    # Drop the cache first. If Streamlit interrupts this run mid-request,
    # the next run reloads the real history from the backend.
    prev = st.session_state.history.pop(tid, None)

    with st.chat_message("user"):
        st.markdown(md(prompt))

    with st.chat_message("assistant"):
        with st.spinner("Planning your trip... this can take a minute."):
            ok, reply = send_message(tid, prompt)
        if ok:
            st.markdown(md(reply))
        else:
            st.error(reply)

    if ok:
        if prev is not None:
            st.session_state.history[tid] = prev + [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": reply},
            ]
        st.session_state.threads = None   # the sidebar needs to show this chat
        st.rerun()


def render_main() -> None:
    tid = st.session_state.current_thread_id
    history, history_error = load_history(tid)

    title_col, action_col = st.columns([5, 1])
    with title_col:
        st.header("🧳 AI Travel Planner")
        st.caption(f"Chat ID: {tid[:8]}")
    with action_col:
        if history:   # only saved chats can be deleted
            render_delete_button(tid)

    if st.session_state.delete_error:
        st.error(st.session_state.delete_error)
        st.session_state.delete_error = None

    if history_error:
        st.error(f"Couldn't load this chat's messages. {history_error}")

    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(md(msg["content"]))

    if not history and not history_error:
        st.info("Tell me where you'd like to go, how many days, and your budget. Let's plan!")

    prompt = st.chat_input("e.g. 5 days in Kyoto in April, mid-range budget")
    if prompt and prompt.strip():
        handle_prompt(tid, prompt.strip())


def init_state() -> None:
    if "current_thread_id" not in st.session_state:
        st.session_state.current_thread_id = new_thread_id()   # every fresh visit starts a new chat
    st.session_state.setdefault("threads", None)
    st.session_state.setdefault("threads_error", None)
    st.session_state.setdefault("history", {})
    st.session_state.setdefault("delete_error", None)


def main() -> None:
    init_state()
    render_sidebar()
    render_main()


main()