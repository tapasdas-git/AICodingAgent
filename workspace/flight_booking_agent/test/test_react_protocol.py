from __future__ import annotations

from workspace.flight_booking_agent.Coding.agents import AgentConfig, FakeGroqChatAdapter, create_flight_booking_engine
from workspace.flight_booking_agent.Coding.tools import MockReservationGateway


def _tool_call(call_id: str, name: str, arguments: str) -> dict[str, object]:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


def test_react_history_records_assistant_and_tool_messages() -> None:
    adapter = FakeGroqChatAdapter(
        [
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                _tool_call("call-1", "search_flights", '{"origin":"SFO","destination":"JFK","passengers":1,"seat_preference":"economy","bag_policy":"any","direct_only":true}'),
                                _tool_call("call-2", "search_flights", '{"origin":"SFO","destination":"LAX","passengers":1,"seat_preference":"economy","bag_policy":"any","direct_only":true}'),
                            ],
                        }
                    }
                ]
            },
            {"choices": [{"message": {"role": "assistant", "content": "{\"status\":\"final\",\"message\":\"done\"}"}}]},
        ]
    )
    engine = create_flight_booking_engine(
        AgentConfig(model="groq-mock", max_turns=3),
        adapter=adapter,
        reservation_gateway=MockReservationGateway(),
    )

    result = engine.run("book me a flight", request_id="req-react", passenger_name="Ada Lovelace", authorized=True)

    assert result.status == "final"
    assert [message["role"] for message in result.history] == ["user", "assistant", "tool", "tool", "assistant"]
    assert result.history[1]["tool_calls"][0]["id"] == "call-1"
    assert result.history[2]["tool_call_id"] == "call-1"
    assert result.history[3]["tool_call_id"] == "call-2"
    assert len(adapter.calls) == 2
    assert adapter.calls[0]["tool_choice"] == "auto"


def test_invalid_or_mixed_tool_call_batch_is_rejected_without_side_effects() -> None:
    gateway = MockReservationGateway()
    adapter = FakeGroqChatAdapter(
        [
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                _tool_call("call-1", "search_flights", '{"origin":"SFO","destination":"JFK","passengers":1,"seat_preference":"economy","bag_policy":"any","direct_only":true}'),
                                _tool_call("call-2", "delete_inventory", '{"flight_id":"AA100-SFO-JFK"}'),
                            ],
                        }
                    }
                ]
            }
        ]
    )
    engine = create_flight_booking_engine(
        {"model": "groq-mock", "max_turns": 2},
        adapter=adapter,
        reservation_gateway=gateway,
    )

    result = engine.run("book me a flight", request_id="req-invalid", passenger_name="Ada Lovelace", authorized=True)

    assert result.status == "error"
    assert gateway.reservations_by_request_id == {}
    assert gateway.reservation_events == []


def test_loop_termination_returns_limit_when_model_never_finishes() -> None:
    adapter = FakeGroqChatAdapter(
        [
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [_tool_call("call-1", "search_flights", '{"origin":"SFO","destination":"JFK","passengers":1,"seat_preference":"economy","bag_policy":"any","direct_only":true}')],
                        }
                    }
                ]
            },
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [_tool_call("call-2", "search_flights", '{"origin":"SFO","destination":"JFK","passengers":1,"seat_preference":"economy","bag_policy":"any","direct_only":true}')],
                        }
                    }
                ]
            },
        ]
    )
    engine = create_flight_booking_engine(
        AgentConfig(model="groq-mock", max_turns=2),
        adapter=adapter,
    )

    result = engine.run("book me a flight", request_id="req-limit", passenger_name="Ada Lovelace", authorized=True)

    assert result.status == "limit"
