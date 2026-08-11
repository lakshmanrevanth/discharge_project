"""RAG last-3 session history: pipeline gate + session_has_history helper."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from rag.generation_agent import refusal_text, session_has_history
from rag.pipeline import ask


def test_session_has_history_false_for_empty_and_missing():
    assert session_has_history(None) is False
    assert session_has_history("") is False
    with patch("rag.generation_agent._session_db") as mock_db:
        db = MagicMock()
        db.get_session.return_value = None
        mock_db.return_value = db
        assert session_has_history("no-such-session") is False


def test_session_has_history_true_when_runs_exist():
    with patch("rag.generation_agent._session_db") as mock_db:
        sess = MagicMock()
        sess.runs = [{"run_id": "1"}]
        db = MagicMock()
        db.get_session.return_value = sess
        mock_db.return_value = db
        assert session_has_history("sess-1") is True


def test_pipeline_uses_history_when_retrieval_useless():
    """Useless chunks + prior session → still call generation (no early refuse)."""

    async def _run():
        with (
            patch("rag.pipeline.check_prompt_injection", return_value=(True, "what did I ask?")),
            patch("rag.pipeline.run_indexing", new_callable=AsyncMock, return_value="indexed"),
            patch(
                "rag.pipeline.run_retrieval",
                new_callable=AsyncMock,
                return_value=[{"text": "unrelated", "score": 0.05, "keyword_score": 0.0}],
            ),
            patch("rag.pipeline.run_augmentation", new_callable=AsyncMock, side_effect=lambda q, c: c),
            patch("rag.pipeline._context_is_useful", return_value=False),
            patch("rag.pipeline.session_has_history", return_value=True),
            patch(
                "rag.pipeline.run_generation",
                new_callable=AsyncMock,
                return_value="You asked about medications.",
            ) as gen,
        ):
            out = await ask("P1021", "what did I ask?", session_id="sess-hist")
            gen.assert_awaited_once()
            assert out["refused"] is False
            assert out["answer"] == "You asked about medications."
            assert "answered_from_history" in out["notes"]

    asyncio.run(_run())


def test_pipeline_refuses_useless_retrieval_without_history():
    async def _run():
        refuse = refusal_text()
        with (
            patch("rag.pipeline.check_prompt_injection", return_value=(True, "world cup winner")),
            patch("rag.pipeline.run_indexing", new_callable=AsyncMock, return_value="indexed"),
            patch(
                "rag.pipeline.run_retrieval",
                new_callable=AsyncMock,
                return_value=[{"text": "x", "score": 0.05, "keyword_score": 0.0}],
            ),
            patch("rag.pipeline.run_augmentation", new_callable=AsyncMock, side_effect=lambda q, c: c),
            patch("rag.pipeline._context_is_useful", return_value=False),
            patch("rag.pipeline.session_has_history", return_value=False),
            patch("rag.pipeline.run_generation", new_callable=AsyncMock) as gen,
        ):
            out = await ask("P1021", "world cup winner", session_id="sess-new")
            gen.assert_not_awaited()
            assert out["refused"] is True
            assert out["answer"] == refuse
            assert "no_useful_context" in out["notes"]

    asyncio.run(_run())


def test_pipeline_history_miss_still_refuses():
    async def _run():
        refuse = refusal_text()
        with (
            patch("rag.pipeline.check_prompt_injection", return_value=(True, "weather in mysore")),
            patch("rag.pipeline.run_indexing", new_callable=AsyncMock, return_value="indexed"),
            patch(
                "rag.pipeline.run_retrieval",
                new_callable=AsyncMock,
                return_value=[{"text": "x", "score": 0.05, "keyword_score": 0.0}],
            ),
            patch("rag.pipeline.run_augmentation", new_callable=AsyncMock, side_effect=lambda q, c: c),
            patch("rag.pipeline._context_is_useful", return_value=False),
            patch("rag.pipeline.session_has_history", return_value=True),
            patch("rag.pipeline.run_generation", new_callable=AsyncMock, return_value=refuse),
        ):
            out = await ask("P1021", "weather in mysore", session_id="sess-hist")
            assert out["refused"] is True
            assert out["answer"] == refuse
            assert "history_miss" in out["notes"]

    asyncio.run(_run())


def test_run_generation_empty_chunks_still_aruns():
    """Empty chunks must still call Agent.arun so history can answer follow-ups."""

    async def _run():
        refuse = refusal_text()
        fake_response = MagicMock()
        fake_response.content = "You previously asked about the bill total."
        fake_response.messages = None

        fake_agent = MagicMock()
        fake_agent.arun = AsyncMock(return_value=fake_response)

        fake_mcp = MagicMock()
        fake_mcp.close = AsyncMock()

        with (
            patch(
                "rag.generation_agent.fetch_rag_answer_prompt",
                new_callable=AsyncMock,
                return_value="prompt",
            ),
            patch(
                "rag.generation_agent._connect_multi_mcp",
                new_callable=AsyncMock,
                return_value=fake_mcp,
            ),
            patch("rag.generation_agent.Agent", return_value=fake_agent),
            patch("rag.generation_agent._session_db", return_value=MagicMock()),
            patch("rag.generation_agent.get_agno_model", return_value=MagicMock()),
        ):
            from rag.generation_agent import run_generation

            answer = await run_generation(
                patient_id="P1021",
                question="what did I ask last?",
                chunks=[],
                session_id="sess-1",
            )
            fake_agent.arun.assert_awaited_once()
            assert answer != refuse
            assert "bill total" in answer

    asyncio.run(_run())
