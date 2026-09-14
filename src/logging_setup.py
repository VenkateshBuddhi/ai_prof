# src/logging_setup.py
"""Centralized logging configuration.

One place to configure log output so every layer reports failures consistently:

    [12:03:41] INFO     AgentGraph            : Using Groq model: openai/gpt-oss-120b
    [12:03:45] WARNING  MedplumClient         : Medplum patient lookup failed: ConnectTimeout
    [12:03:46] ERROR    AgentGraph            : Tool search_doctors raised: ConnectTimeout

Call `setup_logging()` once at each entry point (CLIs + worker). Level comes from
the `LOG_LEVEL` env var (default INFO); set `LOG_LEVEL=DEBUG` for full detail
including third-party libraries.

Our application loggers (their names, so you can tell layers apart at a glance):
    ConversationAgent · AgentGraph · AgentCapabilities · AgentExecutor
    MedplumClient · LiveKitWorker
Noisy third-party loggers (httpx, groq, langchain, …) are pinned to WARNING
unless LOG_LEVEL=DEBUG.
"""
import logging
import os
import sys

_THIRD_PARTY = [
    "httpx", "httpcore", "groq", "openai", "urllib3", "asyncio",
    "langchain", "langchain_core", "langchain_groq", "langgraph",
    "livekit", "livekit.agents",
]

_configured = False


def setup_logging(level: str | None = None) -> None:
    """Configure the root logger. Idempotent — safe to call from every entry point."""
    global _configured

    resolved = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()
    root = logging.getLogger()

    if _configured:
        root.setLevel(resolved)
        return

    from src.observability import CorrelationFilter

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        fmt="[%(asctime)s] %(levelname)-7s %(name)-18s [%(correlation_id)s] %(message)s",
        datefmt="%H:%M:%S",
    ))
    handler.addFilter(CorrelationFilter())  # injects correlation_id onto every record
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(resolved)

    # Keep libraries quiet unless we're explicitly debugging.
    third_party_level = logging.DEBUG if resolved == "DEBUG" else logging.WARNING
    for name in _THIRD_PARTY:
        logging.getLogger(name).setLevel(third_party_level)

    _configured = True
