from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AggressionResult:
    direction: str
    score: float
    aggressive_volume: float
    delta: float
    trade_count: int
    intensity: float
    price_response: float | None
    event_time: float | None
    as_of: float | None
    data_quality: str

    def to_dict(self) -> dict[str, Any]:
        return vars(self).copy()


@dataclass(frozen=True)
class AbsorptionResult:
    detected: bool
    side: str
    strength: float
    aggressive_volume: float
    delta: float
    price_response: float | None
    effort_result: float | None
    event_time: float | None
    as_of: float | None
    data_quality: str

    def to_dict(self) -> dict[str, Any]:
        return vars(self).copy()


class _VisibleCandles:
    @staticmethod
    def filter(candles, as_of, symbol):
        visible = []
        for candle in candles:
            timestamp = candle.get("event_time", candle.get("timestamp"))
            if timestamp is None or candle.get("confirmed", True) is False:
                continue
            timestamp = float(timestamp)
            if as_of is not None and timestamp > as_of:
                continue
            if symbol is not None and candle.get("symbol") not in {None, symbol}:
                continue
            visible.append(candle)
        return sorted(visible, key=lambda item: float(item.get("event_time", item.get("timestamp"))))

    @staticmethod
    def response(candles):
        if len(candles) < 2:
            return None
        previous = float(candles[-2]["close"])
        current = float(candles[-1]["close"])
        if previous == 0:
            return None
        return (current - previous) / abs(previous)


class AggressionEngine:
    """Measure directional aggressive participation without opaque scoring."""

    def analyze(self, candles, orderflow=None, as_of=None, symbol=None) -> AggressionResult:
        visible = _VisibleCandles.filter(candles, as_of, symbol)
        flow = orderflow or {}
        if hasattr(flow, "to_dict"):
            flow = flow.to_dict()
        buy = float(flow.get("buy_volume", 0.0) or 0.0)
        sell = float(flow.get("sell_volume", 0.0) or 0.0)
        delta = float(flow.get("delta", buy - sell) or 0.0)
        total = buy + sell
        if total <= 0:
            return AggressionResult("NEUTRAL", 0.0, 0.0, delta, int(flow.get("trade_count", 0) or 0), 0.0, _VisibleCandles.response(visible), visible[-1].get("event_time") if visible else None, as_of, "DATA_INCOMPLETE")
        direction = "BULLISH" if delta > 0 else "BEARISH" if delta < 0 else "NEUTRAL"
        intensity = abs(delta) / total
        score = min(100.0, intensity * 100.0)
        return AggressionResult(direction, score, total, delta, int(flow.get("trade_count", 0) or 0), intensity, _VisibleCandles.response(visible), visible[-1].get("event_time") if visible else None, as_of, "DATA_VALID")


class AbsorptionEngine:
    """Detect high effort with limited price response across visible observations."""

    def __init__(self, effort_multiplier: float = 1.5, max_response_pct: float = 0.001):
        if effort_multiplier <= 1 or max_response_pct < 0:
            raise ValueError("Invalid absorption thresholds")
        self.effort_multiplier = effort_multiplier
        self.max_response_pct = max_response_pct

    def analyze(self, candles, orderflow=None, as_of=None, symbol=None) -> AbsorptionResult:
        visible = _VisibleCandles.filter(candles, as_of, symbol)
        flow = orderflow or {}
        if hasattr(flow, "to_dict"):
            flow = flow.to_dict()
        buy = float(flow.get("buy_volume", 0.0) or 0.0)
        sell = float(flow.get("sell_volume", 0.0) or 0.0)
        total = buy + sell
        delta = float(flow.get("delta", buy - sell) or 0.0)
        response = _VisibleCandles.response(visible)
        event_time = visible[-1].get("event_time") if visible else None
        if len(visible) < 2 or total <= 0 or response is None:
            return AbsorptionResult(False, "NONE", 0.0, total, delta, response, None, event_time, as_of, "DATA_INCOMPLETE")
        prior_volumes = [float(item.get("volume", 0.0) or 0.0) for item in visible[:-1]]
        baseline = sum(prior_volumes) / len(prior_volumes) if prior_volumes else 0.0
        effort_result = total / max(abs(response), 1e-12)
        high_effort = baseline <= 0 or total >= baseline * self.effort_multiplier
        detected = high_effort and abs(response) <= self.max_response_pct
        side = "BUY" if detected and delta > 0 else "SELL" if detected and delta < 0 else "NONE"
        strength = min(100.0, (total / max(baseline, total)) * 100.0) if detected else 0.0
        return AbsorptionResult(detected, side, strength, total, delta, response, effort_result, event_time, as_of, "DATA_VALID")
