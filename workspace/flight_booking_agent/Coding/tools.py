from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from .schemas import BookingConfirmation, FlightOption


def _dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


DEFAULT_CATALOG: tuple[FlightOption, ...] = (
    FlightOption(
        flight_id="AA100-SFO-JFK",
        flight_number="AA100",
        carrier="American Airlines",
        origin="SFO",
        destination="JFK",
        departure_time=_dt("2026-09-01T08:00:00+00:00"),
        arrival_time=_dt("2026-09-01T16:15:00+00:00"),
        seat_class="economy",
        bag_policy="one_checked_bag",
        price_usd=420.0,
        available_seats=3,
        direct=True,
    ),
    FlightOption(
        flight_id="UA200-SFO-JFK",
        flight_number="UA200",
        carrier="United Airlines",
        origin="SFO",
        destination="JFK",
        departure_time=_dt("2026-09-01T09:45:00+00:00"),
        arrival_time=_dt("2026-09-01T17:40:00+00:00"),
        seat_class="business",
        bag_policy="two_checked_bags",
        price_usd=980.0,
        available_seats=2,
        direct=True,
    ),
    FlightOption(
        flight_id="DL300-SFO-JFK",
        flight_number="DL300",
        carrier="Delta Air Lines",
        origin="SFO",
        destination="JFK",
        departure_time=_dt("2026-09-01T07:10:00+00:00"),
        arrival_time=_dt("2026-09-01T18:20:00+00:00"),
        seat_class="economy",
        bag_policy="carry_on_only",
        price_usd=260.0,
        available_seats=1,
        direct=False,
    ),
    FlightOption(
        flight_id="WN400-SFO-LAX",
        flight_number="WN400",
        carrier="Southwest Airlines",
        origin="SFO",
        destination="LAX",
        departure_time=_dt("2026-09-01T12:15:00+00:00"),
        arrival_time=_dt("2026-09-01T13:45:00+00:00"),
        seat_class="economy",
        bag_policy="one_checked_bag",
        price_usd=120.0,
        available_seats=1,
        direct=True,
    ),
)


class FlightSearchRequest(BaseModel):
    origin: str = Field(min_length=3, max_length=64)
    destination: str = Field(min_length=3, max_length=64)
    max_price: float | None = Field(default=None, gt=0)
    direct_only: bool = False


class InventoryError(RuntimeError):
    pass


class AuthorizationError(PermissionError):
    pass


class MockFlightSearchAPI:
    def __init__(self, catalog: Iterable[FlightOption] = DEFAULT_CATALOG):
        self._catalog = {flight.flight_id: flight.model_copy(deep=True) for flight in catalog}

    def get_canonical_flight(self, flight_id: str) -> FlightOption:
        try:
            return self._catalog[flight_id].model_copy(deep=True)
        except KeyError as exc:
            raise LookupError(f"unknown flight_id: {flight_id}") from exc

    def search(self, request: FlightSearchRequest) -> list[FlightOption]:
        results: list[FlightOption] = []
        for flight in self._catalog.values():
            if flight.origin != request.origin.upper() or flight.destination != request.destination.upper():
                continue
            if request.direct_only and not flight.direct:
                continue
            if request.max_price is not None and flight.price_usd > request.max_price:
                continue
            results.append(flight.model_copy(deep=True))
        results.sort(key=lambda option: (option.price_usd, not option.direct, option.departure_time))
        return results


class MockReservationGateway:
    def __init__(self, catalog: Iterable[FlightOption] = DEFAULT_CATALOG):
        self._catalog = {flight.flight_id: flight.model_copy(deep=True) for flight in catalog}
        self._inventory = {flight.flight_id: flight.available_seats for flight in catalog}
        self._reservations_by_request_id: dict[str, BookingConfirmation] = {}
        self._events: list[dict[str, Any]] = []

    @property
    def reservation_events(self) -> list[dict[str, Any]]:
        return list(self._events)

    @property
    def reservations_by_request_id(self) -> dict[str, BookingConfirmation]:
        return dict(self._reservations_by_request_id)

    def get_canonical_flight(self, flight_id: str) -> FlightOption:
        try:
            return self._catalog[flight_id].model_copy(deep=True)
        except KeyError as exc:
            raise LookupError(f"unknown flight_id: {flight_id}") from exc

    def reserve(
        self,
        *,
        request_id: str,
        passenger_name: str,
        flight_id: str,
        expected_price_usd: float,
        authorized: bool,
        reserved_seats: int = 1,
    ) -> BookingConfirmation:
        if not authorized:
            raise AuthorizationError("booking requires authorization")
        if reserved_seats < 1:
            raise ValueError("reserved_seats must be at least 1")

        existing = self._reservations_by_request_id.get(request_id)
        if existing is not None:
            if existing.flight_id != flight_id or existing.passenger_name != passenger_name:
                raise ValueError("idempotency key already used for a different booking")
            return existing

        canonical = self.get_canonical_flight(flight_id)
        if canonical.price_usd != expected_price_usd:
            raise ValueError("booking price does not match the canonical flight record")

        inventory = self._inventory.get(flight_id, 0)
        if inventory < reserved_seats:
            raise InventoryError("not enough inventory to reserve the requested seats")

        self._inventory[flight_id] = inventory - reserved_seats
        confirmation = BookingConfirmation(
            confirmation_id=f"cnf-{uuid4().hex[:10]}",
            request_id=request_id,
            booking_reference=f"BR-{uuid4().hex[:8].upper()}",
            flight_id=flight_id,
            passenger_name=passenger_name,
            total_price_usd=expected_price_usd * reserved_seats,
            reserved_seats=reserved_seats,
            issued_at=datetime.now(timezone.utc),
            notes=["reservation confirmed against canonical flight record"],
        )
        self._reservations_by_request_id[request_id] = confirmation
        self._events.append(
            {
                "type": "reserve",
                "request_id": request_id,
                "flight_id": flight_id,
                "reserved_seats": reserved_seats,
                "remaining_inventory": self._inventory[flight_id],
            }
        )
        return confirmation
