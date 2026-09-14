# src/agent/chat.py
"""Terminal REPL to test the ConversationAgent end-to-end WITHOUT a phone call.

Run:
    uv run python -m src.agent.chat                 # anonymous caller
    uv run python -m src.agent.chat --phone +15550192834   # seeded patient (John Doe)
    uv run python -m src.agent.chat --show-tools    # print each tool call + result

Requires GROQ_API_KEY and MEDPLUM_CLIENT_ID/SECRET in .env. Type 'exit' or Ctrl-D to quit.
"""
import argparse
import asyncio
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(BASE_DIR, ".env")


def _load_env() -> None:
    """Lightweight .env loader (python-dotenv is unused across the project)."""
    if not os.path.exists(ENV_PATH):
        print("[warn] no .env found; expecting GROQ_API_KEY / MEDPLUM_* in the environment")
        return
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip("'").strip('"'))


async def _run(phone: str | None, show_tools: bool) -> None:
    # Import after env is loaded so module-level API keys pick up .env values.
    from src.agent.agent import ConversationAgent
    from src import observability

    agent = ConversationAgent()
    observability.start_call(agent.session.session_id, channel="text")
    greeting = await agent.start(phone_number=phone)
    print(f"\nAgent: {greeting}\n")

    loop = asyncio.get_event_loop()
    while True:
        try:
            user = (await loop.run_in_executor(None, input, "You: ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user.lower() in {"exit", "quit"}:
            break

        reply = await agent.send(user)

        if show_tools and agent.last_tool_calls:
            for call in agent.last_tool_calls:
                ok = call["result"].get("success")
                print(f"   [tool] {call['name']} -> success={ok}")

        print(f"\nAgent: {reply}\n")

    metrics = observability.pop_call(agent.session.session_id)
    if metrics:
        print(f"\nCall metrics: {metrics.summary()}")
    print(f"Session ended. state={agent.session.state.model_dump()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Text REPL for the healthcare scheduling agent")
    parser.add_argument("--phone", help="Look up an existing patient by phone (e.g. +15550192834)")
    parser.add_argument("--show-tools", action="store_true", help="Print each tool call + success")
    args = parser.parse_args()

    _load_env()
    from src.logging_setup import setup_logging
    setup_logging()
    asyncio.run(_run(args.phone, args.show_tools))


if __name__ == "__main__":
    main()
