from __future__ import annotations

from workspace.flight_booking_agent.Coding.agents import PreferencePolicyAgent, SearchAgent, parse_flight_request
from workspace.flight_booking_agent.Coding.schemas import FlightOption
from workspace.flight_booking_agent.Coding.tools import MockFlightSearchAPI


def test_intent_parsing_extracts_route_budget_and_preferences() -> None:
    query = parse_flight_request("Find a non-stop business flight from SFO to JFK under $500 on 2026-09-01 with a checked bag")

    assert query.origin == "SFO"
    assert query.destination == "JFK"
    assert query.max_price == 500.0
    assert query.direct_only is True
    assert query.seat_preference == "business"
    assert query.bag_policy == "checked_bag_required"
    assert str(query.departure_date) == "2026-09-01"


def test_policy_filtering_applies_budget_seat_and_bag_rules() -> None:
    query = parse_flight_request("Find a direct economy flight from SFO to JFK under $500 with a checked bag")
    search_agent = SearchAgent(MockFlightSearchAPI())
    policy_agent = PreferencePolicyAgent()

    _, options = search_agent.search_from_text("Find a direct economy flight from SFO to JFK under $500 with a checked bag")
    filtered = policy_agent.filter(query, options)

    assert [option.flight_id for option in filtered] == ["AA100-SFO-JFK"]
    assert all(option.price_usd <= 500 for option in filtered)
    assert all(option.direct for option in filtered)
