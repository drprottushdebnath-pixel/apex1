from __future__ import annotations

from typing import Any


class ControlCenter:
    """Read-only dashboard/API projection of canonical APEX state."""

    def snapshot(self, pipeline_result, paper_position=None) -> dict[str, Any]:
        context = pipeline_result.context
        decision = pipeline_result.decision
        risk = pipeline_result.risk
        return {
            "symbol": context.symbol,
            "price": context.current_price,
            "structure": self._serialize(context.structure),
            "mtf": self._serialize(context.mtf),
            "liquidity": self._serialize(context.liquidity),
            "orderflow": self._serialize(context.orderflow),
            "aggression": self._serialize(context.aggression),
            "absorption": self._serialize(context.absorption),
            "value": self._serialize(context.value),
            "oi": self._serialize(context.oi),
            "funding": context.funding,
            "effort": self._serialize(context.effort),
            "regime": context.market_regime,
            "setup": self._serialize(context.setup),
            "entry": self._serialize(context.entry),
            "decision": decision.to_dict(),
            "risk": risk.to_dict(),
            "paper_position": self._serialize(paper_position),
            "reason_codes": list(decision.reasons) + list(decision.invalidation),
            "event_time": context.event_time,
        }

    @staticmethod
    def _serialize(value):
        if value is None:
            return None
        if hasattr(value, "to_dict"):
            return value.to_dict()
        if isinstance(value, dict):
            return dict(value)
        return vars(value)
