from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class FundingState:
    symbol: str
    event_time: float | None
    funding_rate: float | None
    stale: bool


class FundingHistory:
    """Chronological, duplicate-safe funding observations for live and replay."""

    def __init__(self, symbol: str, stale_after: float = 120.0) -> None:
        if not symbol:
            raise ValueError("symbol is required")
        if stale_after <= 0:
            raise ValueError("stale_after must be positive")
        self.symbol = symbol.upper()
        self.stale_after = stale_after
        self._observations: dict[float, float] = {}

    def ingest(self, event_time: float, funding_rate: float) -> FundingState:
        event_time = float(event_time)
        funding_rate = float(funding_rate)
        if event_time < 0 or not isfinite(event_time):
            raise ValueError("Funding event time must be finite and non-negative")
        if not isfinite(funding_rate):
            raise ValueError("Funding rate must be finite")
        self._observations.setdefault(event_time, funding_rate)
        return self.state(as_of=event_time)

    def state(self, as_of: float, stale_after: float | None = None) -> FundingState:
        as_of = float(as_of)
        visible = sorted(
            timestamp
            for timestamp in self._observations
            if timestamp <= as_of
        )
        if not visible:
            return FundingState(self.symbol, None, None, True)
        event_time = visible[-1]
        threshold = self.stale_after if stale_after is None else stale_after
        return FundingState(
            self.symbol,
            event_time,
            self._observations[event_time],
            as_of - event_time > threshold,
        )

    def latest(self) -> FundingState:
        if not self._observations:
            return FundingState(self.symbol, None, None, True)
        return self.state(max(self._observations))

    @property
    def observations(self) -> tuple[tuple[float, float], ...]:
        return tuple(sorted(self._observations.items()))
