from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from .schemas import BookingConfirmation, FlightOption, FlightQuery
from .tools import (
    AuthorizationError,
    FlightSearchRequest,
    InventoryError,
    MockFlightSearchAPI,
    MockReservationGateway,
)

SEAT_RANK = {"economy": 0, "premium_economy": 1, "business": 2, "first": 3}
BAG_POLICY_RANK = {
    "carry_on_only": 0,
    "checked_bag_required": 1,
    "one_checked_bag": 1,
    "two_checked_bags": 2,
    "any": 0,
}


class AgentConfig(BaseModel):
    model: str = Field(min_length=1)
    max_turns: int = Field(default=4, ge=1, le=12)
    api_key_env_var: str = Field(default="GROQ_API_KEY", min_length=1)
    provider: Literal["groq"] = "groq"


class AgentRunResult(BaseModel):
    status: Literal["final", "error", "limit"]
    final_message: str | None = None
    error: str | None = None
    history: list[dict[str, Any]] = Field(default_factory=list)
    booking: BookingConfirmation | None = None


class ToolCallModel(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    arguments: dict[str, Any]


class SearchFlightsArgs(FlightQuery):
    pass


class ApplyPreferencesArgs(BaseModel):
    query: FlightQuery
    options: list[FlightOption]


class BookFlightArgs(BaseModel):
    flight: FlightOption
    request_id: str | None = Field(default=None, min_length=1)
    passenger_name: str | None = Field(default=None, min_length=1)
    authorized: bool | None = None


@dataclass(frozen=True)
class BookingContext:
    request_id: str
    passenger_name: str
    authorized: bool


class GroqChatAdapter(Protocol):
    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]],
        tool_choice: str,
    ) -> Any:
        ...


class GroqClientAdapter:
    def __init__(self, *, model: str, api_key: str | None = None, client: Any | None = None):
        self.model = model
        self._client = client
        self._api_key = api_key or os.environ.get("GROQ_API_KEY")

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from groq import Groq
        except ImportError as exc:
            raise RuntimeError("groq is not installed") from exc
        if not self._api_key:
            raise RuntimeError("GROQ_API_KEY is required for live Groq calls")
        self._client = Groq(api_key=self._api_key)
        return self._client

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]],
        tool_choice: str,
    ) -> Any:
        client = self._ensure_client()
        return client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
        )


class FakeGroqChatAdapter:
    def __init__(self, responses: Iterable[dict[str, Any]]):
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]],
        tool_choice: str,
    ) -> dict[str, Any]:
        self.calls.append({"messages": json.loads(json.dumps(messages)), "tools": tools, "tool_choice": tool_choice})
        if not self._responses:
            raise RuntimeError("no scripted response remaining")
        return self._responses.pop(0)


def parse_flight_request(text: str) -> FlightQuery:
    if not isinstance(text, str):
        raise TypeError("flight request text must be a string")
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("flight request text must not be empty")

    origin_destination = re.search(r"\bfrom\s+([A-Z]{3})\s+to\s+([A-Z]{3})\b", cleaned, re.IGNORECASE)
    if not origin_destination:
        raise ValueError("could not parse origin and destination")
    origin = origin_destination.group(1).upper()
    destination = origin_destination.group(2).upper()

    max_price_match = re.search(r"(?:under|below|less than)\s+\$?(\d+(?:\.\d+)?)", cleaned, re.IGNORECASE)
    max_price = float(max_price_match.group(1)) if max_price_match else None

    departure_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", cleaned)
    departure_date = date.fromisoformat(departure_match.group(1)) if departure_match else None

    direct_only = bool(re.search(r"\b(non[- ]?stop|direct)\b", cleaned, re.IGNORECASE))
    if re.search(r"\bbusiness\b", cleaned, re.IGNORECASE):
        seat_preference = "business"
    elif re.search(r"\bfirst\b", cleaned, re.IGNORECASE):
        seat_preference = "first"
    elif re.search(r"\bpremium\b", cleaned, re.IGNORECASE):
        seat_preference = "premium_economy"
    else:
        seat_preference = "economy"

    if re.search(r"\bchecked bag\b", cleaned, re.IGNORECASE):
        bag_policy = "checked_bag_required"
    elif re.search(r"\bcarry[- ]?on\b", cleaned, re.IGNORECASE):
        bag_policy = "carry_on_only"
    else:
        bag_policy = "any"

    return FlightQuery(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        max_price=max_price,
        direct_only=direct_only,
        seat_preference=seat_preference,
        bag_policy=bag_policy,
    )


class SearchAgent:
    def __init__(self, search_api: MockFlightSearchAPI):
        self._search_api = search_api

    def search(self, query: FlightQuery) -> list[FlightOption]:
        request = FlightSearchRequest(
            origin=query.origin,
            destination=query.destination,
            max_price=query.max_price,
            direct_only=query.direct_only,
        )
        return self._search_api.search(request)

    def search_from_text(self, request_text: str) -> tuple[FlightQuery, list[FlightOption]]:
        query = parse_flight_request(request_text)
        return query, self.search(query)


class PreferencePolicyAgent:
    def filter(self, query: FlightQuery, options: Iterable[FlightOption]) -> list[FlightOption]:
        ranked: list[FlightOption] = []
        min_seat_rank = SEAT_RANK[query.seat_preference]
        required_bag_rank = BAG_POLICY_RANK[query.bag_policy]
        for option in options:
            if query.max_price is not None and option.price_usd > query.max_price:
                continue
            if query.direct_only and not option.direct:
                continue
            if SEAT_RANK[option.seat_class] < min_seat_rank:
                continue
            if BAG_POLICY_RANK[option.bag_policy] < required_bag_rank:
                continue
            ranked.append(option)
        ranked.sort(key=lambda option: (option.price_usd, not option.direct, option.departure_time))
        return ranked


class BookingAgent:
    def __init__(self, reservation_gateway: MockReservationGateway):
        self._reservation_gateway = reservation_gateway

    def book(
        self,
        flight: FlightOption,
        *,
        request_id: str,
        passenger_name: str,
        authorized: bool,
    ) -> BookingConfirmation:
        canonical = self._reservation_gateway.get_canonical_flight(flight.flight_id)
        if canonical.price_usd != flight.price_usd:
            raise ValueError("selected flight does not match the canonical pricing")
        return self._reservation_gateway.reserve(
            request_id=request_id,
            passenger_name=passenger_name,
            flight_id=canonical.flight_id,
            expected_price_usd=canonical.price_usd,
            authorized=authorized,
        )


class ReActSupervisorOrchestrator:
    def __init__(
        self,
        *,
        config: AgentConfig,
        adapter: GroqChatAdapter,
        search_agent: SearchAgent,
        policy_agent: PreferencePolicyAgent,
        booking_agent: BookingAgent,
    ):
        self.config = config
        self.adapter = adapter
        self.search_agent = search_agent
        self.policy_agent = policy_agent
        self.booking_agent = booking_agent
        self.history: list[dict[str, Any]] = []

    def _tool_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_flights",
                    "description": "Search the mocked flight catalog.",
                    "parameters": SearchFlightsArgs.model_json_schema(),
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "apply_preferences",
                    "description": "Filter flight options against budget, seat, and bag rules.",
                    "parameters": ApplyPreferencesArgs.model_json_schema(),
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "book_flight",
                    "description": "Reserve a canonical flight after validation.",
                    "parameters": BookFlightArgs.model_json_schema(),
                },
            },
        ]

    def _extract_message(self, response: Any) -> dict[str, Any]:
        if isinstance(response, Mapping):
            choices = response.get("choices")
            if not choices:
                raise ValueError("missing choices in model response")
            message = choices[0].get("message")
            if not isinstance(message, Mapping):
                raise ValueError("missing assistant message in model response")
            return dict(message)
        choices = getattr(response, "choices", None)
        if not choices:
            raise ValueError("missing choices in model response")
        message = getattr(choices[0], "message", None)
        if message is None:
            raise ValueError("missing assistant message in model response")
        if isinstance(message, Mapping):
            return dict(message)
        return dict(message.__dict__)

    def _validate_tool_call_batch(self, tool_calls: list[dict[str, Any]]) -> list[ToolCallModel]:
        validated: list[ToolCallModel] = []
        for raw_call in tool_calls:
            function = raw_call.get("function") or {}
            name = function.get("name")
            if name not in {"search_flights", "apply_preferences", "book_flight"}:
                raise ValueError(f"tool {name!r} is not allowlisted")
            arguments_raw = function.get("arguments", "{}")
            if isinstance(arguments_raw, str):
                try:
                    arguments = json.loads(arguments_raw)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"tool {name!r} arguments are not valid JSON") from exc
            elif isinstance(arguments_raw, Mapping):
                arguments = dict(arguments_raw)
            else:
                raise ValueError(f"tool {name!r} arguments have unsupported type")
            validated.append(
                ToolCallModel(
                    id=str(raw_call.get("id") or raw_call.get("tool_call_id") or ""),
                    name=name,
                    arguments=arguments,
                )
            )
        if any(not call.id for call in validated):
            raise ValueError("tool calls must include ids")
        return validated

    def _execute_tool(self, call: ToolCallModel, *, booking_context: BookingContext | None = None) -> dict[str, Any]:
        if call.name == "search_flights":
            args = SearchFlightsArgs.model_validate(call.arguments)
            options = self.search_agent.search(args)
            return {"options": [option.model_dump(mode="json") for option in options]}
        if call.name == "apply_preferences":
            args = ApplyPreferencesArgs.model_validate(call.arguments)
            options = self.policy_agent.filter(args.query, args.options)
            return {"options": [option.model_dump(mode="json") for option in options]}
        if call.name == "book_flight":
            args = BookFlightArgs.model_validate(call.arguments)
            if booking_context is None:
                raise ValueError("booking context is required for booking")
            if args.request_id is not None and args.request_id != booking_context.request_id:
                raise ValueError("model-supplied request_id does not match trusted booking context")
            if args.passenger_name is not None and args.passenger_name != booking_context.passenger_name:
                raise ValueError("model-supplied passenger_name does not match trusted booking context")
            if args.authorized is not None and args.authorized != booking_context.authorized:
                raise ValueError("model-supplied authorization does not match trusted booking context")
            confirmation = self.booking_agent.book(
                args.flight,
                request_id=booking_context.request_id,
                passenger_name=booking_context.passenger_name,
                authorized=booking_context.authorized,
            )
            return {"confirmation": confirmation.model_dump(mode="json")}
        raise ValueError(f"unsupported tool {call.name}")

    def run(self, user_request: str, *, request_id: str, passenger_name: str, authorized: bool) -> AgentRunResult:
        if not isinstance(user_request, str) or not user_request.strip():
            raise ValueError("user_request must be a non-empty string")
        self.history = [{"role": "user", "content": user_request}]
        messages = list(self.history)
        booking_context = BookingContext(
            request_id=request_id,
            passenger_name=passenger_name,
            authorized=authorized,
        )
        for _ in range(self.config.max_turns):
            response = self.adapter.complete(messages, tools=self._tool_specs(), tool_choice="auto")
            assistant_message = self._extract_message(response)
            self.history.append(assistant_message)
            messages.append(assistant_message)
            tool_calls = assistant_message.get("tool_calls") or []
            if tool_calls:
                try:
                    validated_calls = self._validate_tool_call_batch(tool_calls)
                    for call in validated_calls:
                        payload = self._execute_tool(call, booking_context=booking_context)
                        tool_message = {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": json.dumps(payload, sort_keys=True),
                        }
                        self.history.append(tool_message)
                        messages.append(tool_message)
                except (ValidationError, ValueError, TypeError, InventoryError, AuthorizationError) as exc:
                    return AgentRunResult(status="error", error=str(exc), history=self.history)
                continue
            content = assistant_message.get("content")
            if content is None:
                return AgentRunResult(status="error", error="assistant response did not include content", history=self.history)
            if isinstance(content, str) and content.strip().startswith("{"):
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError as exc:
                    return AgentRunResult(status="error", error=str(exc), history=self.history)
                if parsed.get("status") != "final":
                    return AgentRunResult(status="error", error="final model output must declare status=final", history=self.history)
                return AgentRunResult(
                    status="final",
                    final_message=str(parsed.get("message", "")),
                    history=self.history,
                )
            return AgentRunResult(status="final", final_message=str(content), history=self.history)
        return AgentRunResult(status="limit", error="maximum tool-call turns reached", history=self.history)


def create_flight_booking_engine(
    config: AgentConfig | Mapping[str, Any] | None = None,
    *,
    adapter: GroqChatAdapter | None = None,
    search_api: MockFlightSearchAPI | None = None,
    reservation_gateway: MockReservationGateway | None = None,
) -> ReActSupervisorOrchestrator:
    parsed_config = config if isinstance(config, AgentConfig) else AgentConfig.model_validate(config or {"model": "groq-mock"})
    search_api = search_api or MockFlightSearchAPI()
    reservation_gateway = reservation_gateway or MockReservationGateway()
    adapter = adapter or GroqClientAdapter(model=parsed_config.model)
    return ReActSupervisorOrchestrator(
        config=parsed_config,
        adapter=adapter,
        search_agent=SearchAgent(search_api),
        policy_agent=PreferencePolicyAgent(),
        booking_agent=BookingAgent(reservation_gateway),
    )
