"""
Conversation handling backend for the Bible bot.

Each user's conversation history is stored in a separate JSON file at:
    assets/chat_{discord_user_id}.json

File format
-----------
{
  "user_id": "343889571060383744",
  "created_at": "2026-02-25T01:33:30",
  "updated_at": "2026-02-25T01:45:00",
  "messages": [
    {
      "role": "user",
      "content": "Tell me about the Book of John.",
      "timestamp": "2026-02-25T01:33:30"
    },
    {
      "role": "model",
      "content": "The Book of John is the fourth Gospel ...",
      "timestamp": "2026-02-25T01:33:31"
    }
  ]
}

Roles follow the Gemini convention: "user" for human turns, "model" for LLM turns.

Usage
-----
    from source.conversation import ConversationManager

    manager = ConversationManager()
    reply = await manager.chat(user_id="123456789", user_message="Hello!")
"""

import json
import os
import ssl
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional

from google import genai
from google.genai import types
from google.genai import errors as genai_errors

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

SYSTEM_PROMPT = (
    "You are a helpful, knowledgeable, and compassionate Bible assistant running on Discord. "
    "You answer questions about the Bible, Christian faith, theology, and related topics. "
    "Format your responses using Discord's markdown: **bold**, *italics*, __underline__, "
    "`inline code`, ```code blocks```, and > blockquotes for Scripture passages. "
    "Keep your answers concise, warm, and grounded in Scripture. "
    "If a question is unrelated to the Bible or Christianity, gently redirect "
    "the conversation back to those topics."
    "The max length of your response should be around 120 words. So try to be concise and efficient with your wording."
)

DEFAULT_MODEL  = "gemini-3-flash-preview"
FALLBACK_MODEL = "gemini-2.5-flash"      # used when primary is rate-limited
MAX_HISTORY_MESSAGES = 40  # cap stored turns (20 user + 20 model)


class RateLimitError(Exception):
    """Raised when all available Gemini models are exhausted / rate-limited."""


# ---------------------------------------------------------------------------
# Chat file helpers
# ---------------------------------------------------------------------------

def _chat_path(user_id: str) -> str:
    """Return the absolute path to a user's chat JSON file."""
    return os.path.join(ASSETS_DIR, f"chat_{user_id}.json")


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string (no microseconds)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def load_chat(user_id: str) -> Dict:
    """
    Load the conversation record for *user_id* from disk.

    Returns a fresh record dict if the file does not exist yet.
    """
    path = _chat_path(user_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[conversation] Error reading {path}: {e} — starting fresh")

    # Brand-new record
    return {
        "user_id": str(user_id),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "messages": [],
    }


def save_chat(record: Dict) -> None:
    """
    Persist a conversation record to disk.

    Enforces the MAX_HISTORY_MESSAGES cap before writing so the files
    never grow unbounded. The oldest messages are dropped first.
    """
    os.makedirs(ASSETS_DIR, exist_ok=True)
    record["updated_at"] = _now_iso()

    # Trim to cap (keep the most recent messages)
    messages: List[Dict] = record.get("messages", [])
    if len(messages) > MAX_HISTORY_MESSAGES:
        record["messages"] = messages[-MAX_HISTORY_MESSAGES:]

    path = _chat_path(record["user_id"])
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[conversation] Error saving {path}: {e}")


def clear_chat(user_id: str) -> None:
    """Delete the conversation history for *user_id* (resets context)."""
    path = _chat_path(user_id)
    if os.path.exists(path):
        try:
            os.remove(path)
            print(f"[conversation] Cleared chat history for user {user_id}")
        except Exception as e:
            print(f"[conversation] Error clearing {path}: {e}")


def get_message_count(user_id: str) -> int:
    """Return the number of stored messages for *user_id*."""
    record = load_chat(user_id)
    return len(record.get("messages", []))


def log_quote(
    user_id: str,
    text: str,
    reference: str,
    version: str,
    source: str = "quote",
) -> None:
    """
    Append a delivered Bible verse to the user's chat history.

    This does **not** call the LLM — it only persists context so the
    assistant knows which verses have been sent when the user asks.

    Parameters
    ----------
    user_id:
        Discord user snowflake (str).
    text:
        The verse body text.
    reference:
        Human-readable reference, e.g. ``"John 3:16"``.
    version:
        Bible version ID or abbreviation, e.g. ``"KJV"``.
    source:
        ``"daily"`` for the scheduled delivery, ``"quote"`` for /quote.
    """
    record = load_chat(user_id)
    messages: List[Dict] = record.setdefault("messages", [])

    content = (
        f"[Verse sent to user | source={source} | version={version}]\n"
        f"{reference}\n"
        f"{text}"
    )
    messages.append(
        {
            "role": "model",
            "content": content,
            "timestamp": _now_iso(),
            "event_type": "verse_delivery",
            "meta": {"reference": reference, "version": version, "source": source},
        }
    )
    save_chat(record)
    print(f"[conversation] Logged {source} verse for user {user_id}: {reference}")



# ---------------------------------------------------------------------------
# Gemini helpers
# ---------------------------------------------------------------------------

def _build_contents(messages: List[Dict]) -> List[types.Content]:
    """
    Convert our stored message list into the ``contents`` format
    expected by the Gemini SDK.
    """
    contents = []
    for msg in messages:
        role = msg.get("role", "user")          # "user" or "model"
        text = msg.get("content", "")
        contents.append(
            types.Content(
                role=role,
                parts=[types.Part(text=text)],
            )
        )
    return contents


# ---------------------------------------------------------------------------
# ConversationManager
# ---------------------------------------------------------------------------

class ConversationManager:
    """
    Manages per-user conversation state and Gemini API calls.

    All state is persisted to ``assets/chat_{user_id}.json`` so it
    survives bot restarts.
    """

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY environment variable is not set. "
                "Add it to your .env.local file."
            )
        self._client = genai.Client(api_key=api_key)
        self._model = model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def chat(self, user_id: str, user_message: str) -> str:
        """
        Send *user_message* to Gemini in the context of *user_id*'s
        conversation history, persist both turns, and return the reply.

        Parameters
        ----------
        user_id:
            The Discord user snowflake (as a str).
        user_message:
            The raw text the user sent.

        Returns
        -------
        str
            The model's reply text.
        """
        record = load_chat(user_id)
        messages: List[Dict] = record.setdefault("messages", [])

        # Append the new user turn
        messages.append(
            {"role": "user", "content": user_message, "timestamp": _now_iso()}
        )

        # Build Gemini request
        contents = _build_contents(messages)
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.7,
            max_output_tokens=1024,
        )

        reply_text: Optional[str] = None
        models_to_try = [self._model, FALLBACK_MODEL]

        _RETRYABLE = (ssl.SSLError, ConnectionResetError, ConnectionError, OSError)
        for model in models_to_try:
            for attempt in range(1, 4):  # up to 3 attempts per model
                try:
                    response = self._client.models.generate_content(
                        model=model,
                        contents=contents,
                        config=config,
                    )
                    reply_text = response.text or ""
                    if model != self._model:
                        print(f"[conversation] Used fallback model {model} for user {user_id}")
                    break  # success
                except _RETRYABLE as e:
                    print(
                        f"[conversation] Network error on {model} for user {user_id} "
                        f"(attempt {attempt}/3): {e}"
                    )
                    if attempt < 3:
                        time.sleep(2 * attempt)  # 2s, 4s back-off
                    else:
                        break  # give up on this model, try next
                except genai_errors.ClientError as e:
                    if e.code in (429, 503) or "quota" in str(e).lower() or "rate" in str(e).lower():
                        print(f"[conversation] Rate limit on {model} for user {user_id}: {e}")
                        break  # try next model
                    raise  # other client error — propagate
                except Exception as e:
                    print(f"[conversation] Unexpected error on {model} for user {user_id}: {e}")
                    raise
            if reply_text is not None:
                break  # a model succeeded

        if reply_text is None:
            raise RateLimitError(
                "All Gemini models are currently rate-limited or over quota."
            )

        # Append the model turn and persist
        messages.append(
            {"role": "model", "content": reply_text, "timestamp": _now_iso()}
        )
        save_chat(record)

        return reply_text

    def reset(self, user_id: str) -> None:
        """Wipe the stored history for *user_id* (fresh start)."""
        clear_chat(user_id)

    def history(self, user_id: str) -> List[Dict]:
        """Return the raw message list for *user_id* (read-only view)."""
        return load_chat(user_id).get("messages", [])
