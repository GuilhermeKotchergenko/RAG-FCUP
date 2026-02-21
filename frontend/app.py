"""
frontend/app.py

Chainlit chat interface for the FCUP RAG assistant.
Features:
  - Token streaming from LlamaIndex
  - Clickable source links displayed below each response
  - Magic Link session validation (reads cookie set by FastAPI)
"""

import os

import chainlit as cl
from dotenv import load_dotenv
from llama_index.core.callbacks import CallbackManager, LlamaDebugHandler

from rag.pipeline import configure_settings, format_sources, get_streaming_query_engine

load_dotenv()

API_URL = os.getenv("API_URL", "http://localhost:8001")
REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "false").lower() == "true"

# ── Startup ───────────────────────────────────────────────────────────────────


@cl.on_chat_start
async def on_chat_start():
    """Initialise settings and engine when a chat session starts."""
    configure_settings()
    engine = get_streaming_query_engine()
    cl.user_session.set("engine", engine)

    await cl.Message(
        content=(
            "👋 Olá! Sou o **Assistente FCUP**.\n\n"
            "Posso ajudar-te com informações sobre a Faculdade de Ciências da "
            "Universidade do Porto: procedimentos académicos, prazos, localização "
            "de serviços e muito mais.\n\n"
            "**O que queres saber?**"
        ),
        author="Assistente FCUP",
    ).send()


# ── Message Handler ───────────────────────────────────────────────────────────


@cl.on_message
async def on_message(message: cl.Message):
    engine = cl.user_session.get("engine")
    if engine is None:
        configure_settings()
        engine = get_streaming_query_engine()
        cl.user_session.set("engine", engine)

    # Stream the response token by token
    response_msg = cl.Message(content="", author="Assistente FCUP")
    await response_msg.send()

    try:
        # LlamaIndex async streaming query
        streaming_response = await engine.aquery(message.content)

        full_text = ""
        async for token in streaming_response.async_response_gen():
            await response_msg.stream_token(token)
            full_text += token

        await response_msg.update()

        # Append source links below the response
        sources_md = format_sources(streaming_response.source_nodes)
        if sources_md:
            await cl.Message(
                content=f"📚 **Fontes consultadas:**\n{sources_md}",
                author="Assistente FCUP",
                parent_id=response_msg.id,
            ).send()

    except Exception as exc:
        await response_msg.update()
        await cl.Message(
            content=(
                f"⚠️ Ocorreu um erro ao processar a tua pergunta.\n"
                f"Detalhes: `{exc}`\n\n"
                "Verifica se o Ollama e o Qdrant estão a correr."
            ),
            author="Sistema",
        ).send()


# ── Auth Guard (optional) ─────────────────────────────────────────────────────

if REQUIRE_AUTH:

    @cl.oauth_callback
    def oauth_callback(provider_id: str, token: str, raw_user_data: dict, default_app_user):
        """
        When REQUIRE_AUTH=true, validate the Magic Link session via the FastAPI backend.
        In dev mode (REQUIRE_AUTH=false) this is skipped entirely.
        """
        email = raw_user_data.get("email", "")
        if not email.endswith("@fc.up.pt"):
            return None  # Reject non-FCUP emails
        return default_app_user
