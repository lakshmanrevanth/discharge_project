"""Gradio UI for Host Orchestrator on :8083 (SSoT §5.8).

Run:
    uv run python -m host
    # or: uv run python -m host.app
"""

from __future__ import annotations

import asyncio
import uuid

import gradio as gr

from host.a2a_client import get_host_client
from host.orchestrator import run_case_pipeline, run_host_query
from shared.logger import get_logger
from shared.settings import get_service, listen_host

logger = get_logger("host_app")


def _run_async(coro):
    """Run an async coroutine from Gradio sync handlers."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Nested loop (rare) — use a fresh one via asyncio.run in a thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def discover_agents_ui() -> str:
    client = get_host_client()
    agents = _run_async(client.discover())
    rows = client.list_info()
    online = sum(1 for a in agents if not a.error)
    lines = [f"**Online:** {online}/{len(agents)}", ""]
    for row in rows:
        status = "✅" if row.get("status") == "ok" else "⛔"
        stream = " · streaming" if row.get("streaming") else ""
        lines.append(
            f"- {status} `{row.get('service_key')}` — **{row.get('name')}** "
            f"({row.get('url')}){stream}"
        )
        if row.get("error"):
            lines.append(f"  - _{row['error']}_")
    return "\n".join(lines)


def run_pipeline_ui(patient_id: str) -> str:
    pid = (patient_id or "").strip()
    if not pid:
        return "Enter a patient ID (e.g. P1019 or any P + digits)."
    return _run_async(run_case_pipeline(pid))


def chat_reply(message: str, history: list, session_id: str) -> tuple[list, str]:
    """Gradio chatbot turn → Google ADK Host."""
    history = list(history or [])
    if not (message or "").strip():
        return history, session_id
    if not session_id:
        session_id = uuid.uuid4().hex
    try:
        answer = _run_async(run_host_query(message.strip(), session_id=session_id))
    except Exception as exc:
        answer = f"Host error: {exc}\n\nTip: start A2A agents + MCP with `uv run python run.py`."
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": answer})
    return history, session_id


def build_ui() -> gr.Blocks:
    svc = get_service("host_orchestrator")
    title = svc.get("name", "Host Orchestrator")

    with gr.Blocks(title=title) as demo:
        gr.Markdown(
            f"""
# {title}
Google ADK · Gradio `:8083` · A2A client (streaming-capable)

Coordinates **Monitor → Extractor → Normalizer → Validator → Summary / RAG** over A2A.
HITL review lives on Streamlit `:8501` (separate UI — SSoT §7).
"""
        )

        session_state = gr.State("")

        with gr.Row():
            with gr.Column(scale=1):
                patient_id = gr.Textbox(
                    label="Patient ID",
                    placeholder="P1019 (any P + digits — not limited to the sample corpus)",
                )
                pipeline_btn = gr.Button("Run full case pipeline", variant="primary")
                pipeline_out = gr.Code(label="Pipeline log (JSON)", language="json", lines=18)
                pipeline_btn.click(fn=run_pipeline_ui, inputs=patient_id, outputs=pipeline_out)

                discover_btn = gr.Button("Discover A2A agents")
                agents_md = gr.Markdown("_Click Discover to probe AgentCards._")
                discover_btn.click(fn=discover_agents_ui, outputs=agents_md)

            with gr.Column(scale=2):
                chatbot = gr.Chatbot(label="Host chat (ADK)", height=480)
                msg = gr.Textbox(
                    label="Message",
                    placeholder=(
                        "e.g. List remote agents · Run pipeline for P1020 · "
                        "Ask RAG about meds for P1019"
                    ),
                )
                send_btn = gr.Button("Send", variant="primary")

                def _send(message, history, sid):
                    new_hist, new_sid = chat_reply(message, history, sid)
                    return new_hist, new_sid, ""

                send_btn.click(
                    fn=_send,
                    inputs=[msg, chatbot, session_state],
                    outputs=[chatbot, session_state, msg],
                )
                msg.submit(
                    fn=_send,
                    inputs=[msg, chatbot, session_state],
                    outputs=[chatbot, session_state, msg],
                )

        gr.Markdown(
            """
### Quick tips
- Pipeline needs Mock EHR `:8050`, Primary MCP `:8200`, Secondary MCP `:8201`, and the A2A agents.
- Summary streams only when the release gate allows (not High, not `discharge_blocked`).
- Use HITL `:8501` for elicitation, med edits, and approvals.
"""
        )

    return demo


def main() -> None:
    svc = get_service("host_orchestrator")
    host = listen_host(svc.get("host", "127.0.0.1"))
    port = int(svc.get("port", 8083))
    demo = build_ui()
    logger.info("Host Orchestrator Gradio starting on http://%s:%s", host, port)
    demo.queue().launch(
        server_name=host,
        server_port=port,
        show_error=True,
        share=False,
        theme=gr.themes.Soft(),
    )


if __name__ == "__main__":
    main()
