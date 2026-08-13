"""Unit tests for the flight-director LLM seam: mock mode, the extra_body

kwarg shape (CHAT-08 regression gate), parse_reply's failure modes, and
call-failure handling.
"""

from __future__ import annotations

import pytest

from app.chat import llm
from app.chat.models import LLMError


class TestMockMode:
    """CHAT-06: LLM_MOCK=true must never reach litellm.acompletion."""

    async def test_mock_reply_returned_without_touching_stubbed_acompletion(
        self, mock_mode, stub_completion
    ):
        calls = stub_completion(RuntimeError("acompletion must not be called in mock mode"))

        fleet_context = {"remaining_kwh": 500.0, "roster": [], "active_missions": []}
        reply = await llm.generate_reply(fleet_context, [], "how is the fleet doing?")

        assert isinstance(reply, llm.FlightDirectorReply)
        assert calls == []


class TestExtraBodyShape:
    """CHAT-08 regression gate: response_format and provider must be nested

    inside extra_body, never as top-level kwargs — this is the exact defect
    the sibling-branch reference implementation has.
    """

    async def test_recorded_kwargs_carry_the_correct_shape(
        self, real_mode, monkeypatch, stub_completion
    ):
        monkeypatch.setenv("OPENROUTER_API_KEY", "dummy-test-key")
        valid_completion = '{"message": "fleet nominal", "missions": [], "roster_changes": []}'
        calls = stub_completion(valid_completion)

        fleet_context = {"remaining_kwh": 500.0}
        history = []
        reply = await llm.generate_reply(fleet_context, history, "status check")

        assert isinstance(reply, llm.FlightDirectorReply)
        assert reply.message == "fleet nominal"
        assert len(calls) == 1
        kwargs = calls[0]

        assert isinstance(kwargs["extra_body"], dict)
        assert kwargs["extra_body"]["response_format"] == {
            "type": "json_schema",
            "json_schema": llm.RESPONSE_SCHEMA,
        }
        assert kwargs["extra_body"]["provider"] == {"only": ["Cerebras"]}

        assert "response_format" not in kwargs
        assert "provider" not in kwargs

        assert kwargs["model"] == "openrouter/openai/gpt-oss-120b"
        assert kwargs["max_tokens"] == 800
        assert kwargs["temperature"] == 0.2

        assert kwargs["messages"] == llm.build_messages(fleet_context, history, "status check")

    async def test_history_and_new_message_ordering_preserved_in_recorded_call(
        self, real_mode, monkeypatch, stub_completion
    ):
        from app.chat.models import ChatMessage

        monkeypatch.setenv("OPENROUTER_API_KEY", "dummy-test-key")
        valid_completion = '{"message": "ok", "missions": [], "roster_changes": []}'
        calls = stub_completion(valid_completion)

        history = [
            ChatMessage(
                id="1",
                operator_id="default",
                role="user",
                content="hi",
                actions=None,
                created_at="t1",
            ),
            ChatMessage(
                id="2",
                operator_id="default",
                role="assistant",
                content="hello",
                actions=None,
                created_at="t2",
            ),
        ]
        fleet_context = {"remaining_kwh": 500.0}

        await llm.generate_reply(fleet_context, history, "new message")

        messages = calls[0]["messages"]
        assert messages[0] == {"role": "system", "content": llm.SYSTEM_PROMPT}
        assert messages[1]["role"] == "system"
        assert messages[2] == {"role": "user", "content": "hi"}
        assert messages[3] == {"role": "assistant", "content": "hello"}
        assert messages[4] == {"role": "user", "content": "new message"}


class TestParseReply:
    """Table-driven coverage of parse_reply's structural validation."""

    @pytest.mark.parametrize(
        "raw",
        [
            pytest.param("this is not json at all", id="prose"),
            pytest.param("```json\n{\"message\": \"hi\"}\n```", id="markdown-fenced"),
            pytest.param("[]", id="json-array"),
            pytest.param('{"missions": [], "roster_changes": []}', id="missing-message"),
            pytest.param(
                '{"message": "hi", "missions": [{"drone_id": "FALCON-01", '
                '"action": "hover", "zone": null, "distance_km": null}], '
                '"roster_changes": []}',
                id="invalid-action-enum",
            ),
            pytest.param(
                '{"message": "hi", "missions": [], "roster_changes": [], '
                '"unexpected_field": "schema drift"}',
                id="extra-top-level-field",
            ),
            pytest.param(
                '{"message": "hi", "missions": [{"drone_id": "FALCON-01", '
                '"action": "launch", "zone": "Riverside", "distance_km": 4.2, '
                '"priority": "high"}], "roster_changes": []}',
                id="extra-mission-action-field",
            ),
        ],
    )
    def test_malformed_completions_raise_llm_error(self, raw):
        with pytest.raises(LLMError):
            llm.parse_reply(raw)

    def test_valid_completion_parses_typed_actions(self):
        raw = (
            '{"message": "launching and recalling", '
            '"missions": [{"drone_id": "FALCON-01", "action": "launch", '
            '"zone": "Riverside", "distance_km": 4.2}], '
            '"roster_changes": [{"drone_id": "FALCON-11", "action": "add"}]}'
        )

        reply = llm.parse_reply(raw)

        assert reply.message == "launching and recalling"
        assert len(reply.missions) == 1
        assert isinstance(reply.missions[0], llm.MissionAction)
        assert reply.missions[0].drone_id == "FALCON-01"
        assert reply.missions[0].action == "launch"
        assert len(reply.roster_changes) == 1
        assert isinstance(reply.roster_changes[0], llm.RosterChange)
        assert reply.roster_changes[0].drone_id == "FALCON-11"


class TestCallFailure:
    """Transport-level failures and a missing API key both surface as LLMError."""

    async def test_transport_exception_becomes_llm_error(
        self, real_mode, monkeypatch, stub_completion
    ):
        monkeypatch.setenv("OPENROUTER_API_KEY", "dummy-test-key")
        stub_completion(RuntimeError("connection reset"))

        with pytest.raises(LLMError):
            await llm.generate_reply({"remaining_kwh": 500.0}, [], "status check")

    async def test_missing_api_key_raises_before_any_call(
        self, real_mode, monkeypatch, stub_completion
    ):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        calls = stub_completion('{"message": "should never be reached"}')

        with pytest.raises(LLMError):
            await llm.generate_reply({"remaining_kwh": 500.0}, [], "status check")

        assert calls == []
