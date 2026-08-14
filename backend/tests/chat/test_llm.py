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


def _fleet_context(roster_ids: list[str], active_ids: list[str] | None = None) -> dict:
    """Minimal fleet_context in build_fleet_context's shape (see app/chat/context.py)."""
    active_ids = active_ids or []
    return {
        "remaining_kwh": 500.0,
        "roster": [{"drone_id": drone_id} for drone_id in roster_ids],
        "active_missions": [{"drone_id": drone_id} for drone_id in active_ids],
    }


class TestMockReplyDroneSelection:
    """The mock must dispatch the drone the operator named, not a positional one.

    Regression gate for the UAT defect where `mock_reply` keyword-matched
    "launch"/"recall" but always substituted idle[0]/active[0], silently
    dispatching a different drone than the message asked for.
    """

    def test_launch_uses_named_drone_not_first_idle(self):
        context = _fleet_context(["FALCON-01", "FALCON-02", "FALCON-03"])

        reply = llm.mock_reply(context, "Launch FALCON-03 to Riverside")

        assert [mission.drone_id for mission in reply.missions] == ["FALCON-03"]
        assert reply.missions[0].action == "launch"
        assert "FALCON-03" in reply.message

    def test_recall_uses_named_drone_not_first_active(self):
        context = _fleet_context(
            ["FALCON-01", "FALCON-02", "FALCON-03"], active_ids=["FALCON-01", "FALCON-03"]
        )

        reply = llm.mock_reply(context, "Recall FALCON-03")

        assert [mission.drone_id for mission in reply.missions] == ["FALCON-03"]
        assert reply.missions[0].action == "recall"

    def test_named_drone_matched_case_insensitively_returns_roster_casing(self):
        context = _fleet_context(["FALCON-01", "FALCON-02", "FALCON-05"])

        reply = llm.mock_reply(context, "launch falcon-05 please")

        assert reply.missions[0].drone_id == "FALCON-05"

    def test_longest_matching_id_wins_over_its_own_prefix(self):
        """FALCON-10 must not be read as FALCON-1 — the id-shape boundary."""
        context = _fleet_context(["FALCON-1", "FALCON-10"])

        reply = llm.mock_reply(context, "Launch FALCON-10 to Riverside")

        assert reply.missions[0].drone_id == "FALCON-10"

    def test_named_drone_is_honored_even_when_already_en_route(self):
        """Pass the operator's choice through so the service layer can reject it
        with an honest error, rather than silently substituting an idle drone."""
        context = _fleet_context(["FALCON-01", "FALCON-02"], active_ids=["FALCON-02"])

        reply = llm.mock_reply(context, "Launch FALCON-02 to Riverside")

        assert reply.missions[0].drone_id == "FALCON-02"

    def test_launch_without_a_named_drone_still_falls_back_to_first_idle(self):
        """The E2E spec sends "Launch a drone" and depends on this fallback."""
        context = _fleet_context(["FALCON-01", "FALCON-02"], active_ids=["FALCON-01"])

        reply = llm.mock_reply(context, "Launch a drone")

        assert reply.missions[0].drone_id == "FALCON-02"
        assert reply.missions[0].zone == "Riverside"
        assert reply.missions[0].distance_km == 4.0

    def test_recall_without_a_named_drone_still_falls_back_to_first_active(self):
        """The E2E spec sends "Recall the drone" and depends on this fallback."""
        context = _fleet_context(["FALCON-01", "FALCON-02"], active_ids=["FALCON-02", "FALCON-01"])

        reply = llm.mock_reply(context, "Recall the drone")

        assert reply.missions[0].drone_id == "FALCON-02"
        assert reply.missions[0].action == "recall"

    def test_named_drone_is_honored_on_recall_with_nothing_en_route(self):
        """The service layer answers "no active mission" — an error the operator
        can act on, rather than the silent no-op the positional version gave."""
        context = _fleet_context(["FALCON-01", "FALCON-03"])

        reply = llm.mock_reply(context, "Recall FALCON-03")

        assert reply.missions[0].drone_id == "FALCON-03"
        assert reply.missions[0].action == "recall"

    def test_recall_without_a_named_drone_and_nothing_en_route_takes_no_action(self):
        reply = llm.mock_reply(_fleet_context(["FALCON-01"]), "Recall the drone")

        assert reply.missions == []

    def test_naming_a_drone_without_a_keyword_takes_no_action(self):
        context = _fleet_context(["FALCON-01", "FALCON-03"])

        reply = llm.mock_reply(context, "How is FALCON-03 doing?")

        assert reply.missions == []
        assert reply.message.startswith("[mock]")

    def test_launch_with_an_empty_roster_takes_no_action(self):
        reply = llm.mock_reply(_fleet_context([]), "Launch a drone")

        assert reply.missions == []

    def test_mock_prefix_is_preserved_on_every_reply(self):
        """tests/specs/chat.spec.ts asserts on /^\\[mock\\]/ to prove the mocked
        path ran rather than a real, billable model call."""
        context = _fleet_context(["FALCON-01", "FALCON-02"], active_ids=["FALCON-02"])

        assert llm.mock_reply(context, "Launch FALCON-01 to Riverside").message.startswith("[mock]")
        assert llm.mock_reply(context, "Recall FALCON-02").message.startswith("[mock]")
        assert llm.mock_reply(context, "status?").message.startswith("[mock]")


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

    async def test_transport_exception_text_is_not_echoed_into_error_message(
        self, real_mode, monkeypatch, stub_completion
    ):
        """WR-04: the third-party library's own exception text must never
        flow unsanitized into the client-facing error."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "dummy-test-key")
        sentinel = "internal transport detail sentinel 8f3c2a"
        stub_completion(RuntimeError(sentinel))

        with pytest.raises(LLMError) as excinfo:
            await llm.generate_reply({"remaining_kwh": 500.0}, [], "status check")

        assert sentinel not in str(excinfo.value)

    async def test_missing_api_key_raises_before_any_call(
        self, real_mode, monkeypatch, stub_completion
    ):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        calls = stub_completion('{"message": "should never be reached"}')

        with pytest.raises(LLMError):
            await llm.generate_reply({"remaining_kwh": 500.0}, [], "status check")

        assert calls == []
