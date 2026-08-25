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
            "fvg": self._serialize(getattr(context, "fvg", None)),
            "order_blocks": self._serialize(getattr(context, "order_blocks", None)),
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
            "observability": self._serialize(getattr(context, "observability", None)),
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


class DashboardService:
    """Read-only API facade backed by one canonical pipeline result provider."""

    _routes = {
        "/market": "snapshot",
        "/snapshot": "snapshot",
        "/decision": "decision",
        "/risk": "risk",
        "/paper-position": "paper_position",
        "/observability": "observability",
    }

    def __init__(self, result_provider, paper_position_provider=None) -> None:
        self.result_provider = result_provider
        self.paper_position_provider = paper_position_provider
        self.control_center = ControlCenter()

    def get(self, path: str) -> dict[str, Any]:
        if path == "/health":
            return {"status": "ok", "read_only": True}
        if path not in self._routes:
            if path.rstrip("/") in {"/create_order", "/place_order", "/submit_order", "/cancel_order", "/orders"}:
                raise PermissionError("Live order endpoints are disabled")
            raise KeyError(path)
        result = self.result_provider()
        if result is None:
            return {"status": "unavailable"}
        snapshot = self.control_center.snapshot(result, self.paper_position_provider() if self.paper_position_provider else None)
        key = self._routes[path]
        return snapshot if key == "snapshot" else {key: snapshot[key]}


def create_app(result_provider, paper_position_provider=None) -> DashboardService:
    """Create the dependency-free read-only control-center service."""
    return DashboardService(result_provider, paper_position_provider)
