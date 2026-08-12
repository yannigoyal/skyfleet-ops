"""Tests for structured-output parsing, prompt assembly, and mock mode."""

from __future__ import annotations

import json

import pytest

from app.chat import llm
from app.chat.models import ChatMessage


def _context(remaining: float = 500.0, roster=None, active=None) -> dict:
    return {
        "energy_budget_kwh": 500.0,
        "remaining_kwh": remaining,
        "active_mission_count": len(active or []),
        "active_missions": active or [],
        "roster": roster or [],
        "average_battery_pct": 90.0,
    }


class TestParseReply:
    def test_parses_message_and_actions(self):
        raw = json.dumps(
            {
                "message": "Dispatching.",
                "missions": [
                    {
                        "drone_id": "FALCON-03",
                        "action": "launch",
                        "zone": "Riverside",
                        "distance_km": 4.2,
                    }
                ],
                "roster_changes": [{"drone_id": "FALCON-11", "action": "add"}],
            }
        )
        reply = llm.parse_reply(raw)
        assert reply.message == "Dispatching."
        assert reply.missions[0].drone_id == "FALCON-03"
        assert reply.missions[0].distance_km == 4.2
        assert reply.roster_changes[0].action == "add"

    def test_missing_arrays_default_to_empty(self):
        reply = llm.parse_reply('{"message": "All nominal."}')
        assert reply.missions == []
        assert reply.roster_changes == []

    def test_null_arrays_default_to_empty(self):
        reply = llm.parse_reply('{"message": "hi", "missions": null, "roster_changes": null}')
        assert reply.missions == []

    def test_invalid_json_raises(self):
        with pytest.raises(llm.LLMError):
            llm.parse_reply("not json at all")

    def test_non_object_payload_raises(self):
        with pytest.raises(llm.LLMError):
            llm.parse_reply('["message"]')

    def test_missing_message_raises(self):
        with pytest.raises(llm.LLMError):
            llm.parse_reply('{"missions": []}')

    def test_invalid_action_value_raises(self):
        raw = json.dumps({"message": "x", "missions": [{"drone_id": "A", "action": "explode"}]})
        with pytest.raises(llm.LLMError):
            llm.parse_reply(raw)


class TestBuildMessages:
    def test_includes_system_prompt_context_history_and_user_turn(self):
        history = [
            ChatMessage(
                id="1",
                operator_id="default",
                role="user",
                content="status?",
                actions=None,
                created_at="2026-01-01T00:00:00+00:00",
            )
        ]
        messages = llm.build_messages(_context(), history, "launch one")
        assert messages[0]["content"] == llm.SYSTEM_PROMPT
        assert "remaining_kwh" in messages[1]["content"]
        assert messages[2] == {"role": "user", "content": "status?"}
        assert messages[-1] == {"role": "user", "content": "launch one"}


class TestMockMode:
    def test_mock_mode_enabled_reads_env(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "TRUE")
        assert llm.mock_mode_enabled() is True
        monkeypatch.setenv("LLM_MOCK", "false")
        assert llm.mock_mode_enabled() is False
        monkeypatch.delenv("LLM_MOCK")
        assert llm.mock_mode_enabled() is False

    def test_plain_message_returns_summary_without_actions(self):
        reply = llm.mock_reply(_context(roster=[{"drone_id": "FALCON-01"}]), "how are we doing?")
        assert reply.missions == []
        assert "1 drones on roster" in reply.message

    def test_launch_keyword_proposes_first_idle_drone(self):
        context = _context(roster=[{"drone_id": "FALCON-01"}, {"drone_id": "FALCON-02"}])
        reply = llm.mock_reply(context, "Launch a delivery please")
        assert len(reply.missions) == 1
        assert reply.missions[0].drone_id == "FALCON-01"
        assert reply.missions[0].zone == "Riverside"
        assert reply.missions[0].distance_km == 4.0

    def test_launch_skips_drones_already_en_route(self):
        context = _context(
            roster=[{"drone_id": "FALCON-01"}, {"drone_id": "FALCON-02"}],
            active=[{"drone_id": "FALCON-01"}],
        )
        reply = llm.mock_reply(context, "launch")
        assert reply.missions[0].drone_id == "FALCON-02"

    def test_recall_keyword_recalls_first_active_mission(self):
        context = _context(active=[{"drone_id": "FALCON-05"}])
        reply = llm.mock_reply(context, "Recall it")
        assert reply.missions[0].action == "recall"
        assert reply.missions[0].drone_id == "FALCON-05"

    def test_is_deterministic(self):
        context = _context(roster=[{"drone_id": "FALCON-01"}])
        assert llm.mock_reply(context, "launch") == llm.mock_reply(context, "launch")

    async def test_generate_reply_uses_mock_without_network(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "true")
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        reply = await llm.generate_reply(_context(), [], "status")
        assert reply.message.startswith("[mock]")


class TestGenerateReply:
    async def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "false")
        monkeypatch.setenv("OPENROUTER_API_KEY", "")
        with pytest.raises(llm.LLMError, match="OPENROUTER_API_KEY"):
            await llm.generate_reply(_context(), [], "status")

    async def test_calls_litellm_and_parses_content(self, monkeypatch, stub_completion):
        monkeypatch.setenv("LLM_MOCK", "false")
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        calls = stub_completion(json.dumps({"message": "Fleet nominal."}))

        reply = await llm.generate_reply(_context(), [], "status")

        assert reply.message == "Fleet nominal."
        assert calls[0]["model"] == llm.MODEL
        assert calls[0]["extra_body"] == {"provider": {"only": ["cerebras"]}}
        assert calls[0]["response_format"]["type"] == "json_schema"

    async def test_transport_failure_becomes_llm_error(self, monkeypatch, stub_completion):
        monkeypatch.setenv("LLM_MOCK", "false")
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        stub_completion(RuntimeError("connection reset"))
        with pytest.raises(llm.LLMError, match="connection reset"):
            await llm.generate_reply(_context(), [], "status")

    async def test_malformed_model_output_becomes_llm_error(self, monkeypatch, stub_completion):
        monkeypatch.setenv("LLM_MOCK", "false")
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        stub_completion("sorry, I can't do that")
        with pytest.raises(llm.LLMError):
            await llm.generate_reply(_context(), [], "status")
