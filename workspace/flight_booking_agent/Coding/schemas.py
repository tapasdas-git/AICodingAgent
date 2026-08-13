from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

SeatClass = Literal["economy", "premium_economy", "business", "first"]
BagPolicy = Literal["carry_on_only", "checked_bag_required", "one_checked_bag", "two_checked_bags", "any"]


class FlightQuery(BaseModel):
    origin: str = Field(min_length=3, max_length=64)
    destination: str = Field(min_length=3, max_length=64)
    departure_date: date | None = None
    return_date: date | None = None
    passengers: int = Field(default=1, ge=1, le=9)
    max_price: float | None = Field(default=None, gt=0)
    seat_preference: SeatClass = "economy"
    bag_policy: BagPolicy = "any"
    direct_only: bool = False

    @field_validator("origin", "destination")
    @classmethod
    def _normalize_airport(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not cleaned:
            raise ValueError("airport codes must not be empty")
        return cleaned

    @model_validator(mode="after")
    def _validate_dates(self) -> "FlightQuery":
        if self.return_date and self.departure_date and self.return_date < self.departure_date:
            raise ValueError("return_date must not precede departure_date")
        return self


class FlightOption(BaseModel):
    flight_id: str = Field(min_length=2)
    flight_number: str = Field(min_length=2)
    carrier: str = Field(min_length=2)
    origin: str = Field(min_length=3, max_length=64)
    destination: str = Field(min_length=3, max_length=64)
    departure_time: datetime
    arrival_time: datetime
    seat_class: SeatClass
    bag_policy: BagPolicy
    price_usd: float = Field(gt=0)
    available_seats: int = Field(ge=0)
    direct: bool = False

    @field_validator("origin", "destination")
    @classmethod
    def _normalize_airport(cls, value: str) -> str:
        return value.strip().upper()


class BookingConfirmation(BaseModel):
    confirmation_id: str = Field(min_length=3)
    request_id: str = Field(min_length=3)
    booking_reference: str = Field(min_length=3)
    flight_id: str = Field(min_length=2)
    passenger_name: str = Field(min_length=2)
    total_price_usd: float = Field(gt=0)
    status: Literal["confirmed"] = "confirmed"
    currency: Literal["USD"] = "USD"
    reserved_seats: int = Field(ge=1)
    issued_at: datetime
    notes: list[str] = Field(default_factory=list)
