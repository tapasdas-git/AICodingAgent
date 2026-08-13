from __future__ import annotations

import pytest

from workspace.flight_booking_agent.Coding.agents import AgentConfig, FakeGroqChatAdapter, create_flight_booking_engine
from workspace.flight_booking_agent.Coding.tools import MockReservationGateway


def test_invalid_model_output_is_rejected_before_any_side_effect() -> None:
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
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "book_flight",
                                        "arguments": '{"flight":{"flight_id":"AA100-SFO-JFK","flight_number":"AA100","carrier":"American Airlines","origin":"SFO","destination":"JFK","departure_time":"2026-09-01T08:00:00+00:00","arrival_time":"2026-09-01T16:15:00+00:00","seat_class":"economy","bag_policy":"one_checked_bag","price_usd":"invalid","available_seats":3,"direct":true},"request_id":"req-runtime","passenger_name":"Ada Lovelace","authorized":true}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    )
    engine = create_flight_booking_engine(AgentConfig(model="groq-mock", max_turns=2), adapter=adapter, reservation_gateway=gateway)

    result = engine.run("book me a flight", request_id="req-runtime", passenger_name="Ada Lovelace", authorized=True)

    assert result.status == "error"
    assert gateway.reservations_by_request_id == {}
    assert gateway.reservation_events == []


def test_config_validation_rejects_invalid_turn_budget() -> None:
    with pytest.raises(Exception):
        AgentConfig.model_validate({"model": "groq-mock", "max_turns": 0})
