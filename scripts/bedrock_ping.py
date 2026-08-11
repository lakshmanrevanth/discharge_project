"""Tiny LangGraph + Bedrock live check. Reads creds from .env — do not hardcode secrets.

Run:
  cd /Users/vasujindal/Desktop/cap_proj_v3
  uv run python scripts/bedrock_ping.py
"""

from __future__ import annotations

import os
from typing import TypedDict

from dotenv import load_dotenv
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

load_dotenv()  # loads .env in repo root


class State(TypedDict):
    reply: str


def _mask(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return value[:4] + "…" + value[-4:]


def call_bedrock(state: State) -> State:
    model_id = os.environ["BEDROCK_PRIMARY_MODEL_ID"]
    region = os.environ.get("AWS_REGION_NAME", "us-east-1")
    llm = ChatBedrockConverse(
        model=model_id,
        region_name=region,
        max_tokens=32,
        temperature=0,
    )
    msg = llm.invoke([HumanMessage(content="Reply with exactly one word: PONG")])
    content = msg.content
    if isinstance(content, list):
        content = "".join(
            str(p.get("text", p) if isinstance(p, dict) else p) for p in content
        )
    return {"reply": str(content).strip()}


def main() -> None:
    key = os.environ.get("AWS_ACCESS_KEY_ID", "")
    secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    model = os.environ.get("BEDROCK_PRIMARY_MODEL_ID", "")
    region = os.environ.get("AWS_REGION_NAME", "")

    print("AWS_ACCESS_KEY_ID     =", key)
    print("AWS_SECRET_ACCESS_KEY =", _mask(secret), f"(len={len(secret)})")
    print("AWS_REGION_NAME       =", region)
    print("BEDROCK_PRIMARY_MODEL =", model)
    print("---")

    graph = StateGraph(State)
    graph.add_node("bedrock", call_bedrock)
    graph.add_edge(START, "bedrock")
    graph.add_edge("bedrock", END)
    app = graph.compile()

    out = app.invoke({"reply": ""})
    print("LangGraph reply:", out["reply"])
    print("LIVE" if "PONG" in out["reply"].upper() else "UNEXPECTED — check Bedrock")


if __name__ == "__main__":
    main()
