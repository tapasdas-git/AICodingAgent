from __future__ import annotations

import pytest

from workspace.flight_booking_agent.Coding.agents import AgentConfig, BookingAgent, FakeGroqChatAdapter, PreferencePolicyAgent, SearchAgent, create_flight_booking_engine, parse_flight_request
from workspace.flight_booking_agent.Coding.tools import AuthorizationError, InventoryError, MockFlightSearchAPI, MockReservationGateway


def test_end_to_end_booking_is_idempotent_and_uses_canonical_record() -> None:
    search_api = MockFlightSearchAPI()
    gateway = MockReservationGateway()
    search_agent = SearchAgent(search_api)
    policy_agent = PreferencePolicyAgent()
    booking_agent = BookingAgent(gateway)

    query, options = search_agent.search_from_text("Find a direct economy flight from SFO to JFK under $500 with a checked bag")
    chosen = policy_agent.filter(query, options)[0]

    confirmation = booking_agent.book(chosen, request_id="req-1", passenger_name="Ada Lovelace", authorized=True)
    repeat = booking_agent.book(chosen, request_id="req-1", passenger_name="Ada Lovelace", authorized=True)

    assert confirmation == repeat
    assert confirmation.flight_id == "AA100-SFO-JFK"
    assert confirmation.total_price_usd == 420.0
    assert gateway.reservations_by_request_id["req-1"] == confirmation


def test_booking_requires_authorization() -> None:
    booking_agent = BookingAgent(MockReservationGateway())
    query = parse_flight_request("Find a direct economy flight from SFO to JFK under $500")
    flight = SearchAgent(MockFlightSearchAPI()).search(query)[0]

    with pytest.raises(AuthorizationError):
        booking_agent.book(flight, request_id="req-auth", passenger_name="Ada Lovelace", authorized=False)


def test_booking_fails_when_inventory_is_exhausted() -> None:
    gateway = MockReservationGateway()
    booking_agent = BookingAgent(gateway)
    flight = MockFlightSearchAPI().get_canonical_flight("WN400-SFO-LAX")

    booking_agent.book(flight, request_id="req-inventory-1", passenger_name="Ada Lovelace", authorized=True)

    with pytest.raises(InventoryError):
        booking_agent.book(flight, request_id="req-inventory-2", passenger_name="Grace Hopper", authorized=True)


def test_budget_failure_leaves_no_booking() -> None:
    search_agent = SearchAgent(MockFlightSearchAPI())
    policy_agent = PreferencePolicyAgent()
    gateway = MockReservationGateway()
    booking_agent = BookingAgent(gateway)

    query = parse_flight_request("Find a direct economy flight from SFO to JFK under $100 with a checked bag")
    options = search_agent.search(query)
    filtered = policy_agent.filter(query, options)

    assert filtered == []
    assert gateway.reservations_by_request_id == {}


def test_booking_tool_uses_trusted_run_context_for_identity_and_authorization() -> None:
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
                                        "arguments": '{"flight":{"flight_id":"AA100-SFO-JFK","flight_number":"AA100","carrier":"American Airlines","origin":"SFO","destination":"JFK","departure_time":"2026-09-01T08:00:00+00:00","arrival_time":"2026-09-01T16:15:00+00:00","seat_class":"economy","bag_policy":"one_checked_bag","price_usd":420.0,"available_seats":3,"direct":true},"request_id":"forged-request","passenger_name":"Mallory","authorized":true}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    )
    engine = create_flight_booking_engine(
        AgentConfig(model="groq-mock", max_turns=2),
        adapter=adapter,
        reservation_gateway=gateway,
    )

    result = engine.run("book me a flight", request_id="req-safe", passenger_name="Ada Lovelace", authorized=False)

    assert result.status == "error"
    assert "model-supplied request_id" in result.error
    assert gateway.reservations_by_request_id == {}
    assert gateway.reservation_events == []
