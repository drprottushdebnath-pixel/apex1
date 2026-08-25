from types import SimpleNamespace

import pytest

from brain.dashboard import create_app
from brain.decision import BrainDecision, DecisionLevels
from brain.risk import RiskResult


def result():
    context = SimpleNamespace(
        symbol="BTCUSDT", current_price=100, structure=None, mtf=None, liquidity=None,
        orderflow=None, aggression=None, absorption=None, value=None, oi=None,
        funding=0.001, effort=None, market_regime="TRENDING", setup=None, entry=None,
        fvg=None, order_blocks=None, observability=None, event_time=10,
    )
    return SimpleNamespace(context=context, decision=BrainDecision("WAIT", 0, DecisionLevels(), ["WAIT"], ["MISSING"]), risk=RiskResult(False, 0, 0, 0))


def test_dashboard_service_exposes_canonical_read_only_routes():
    app = create_app(lambda: result())
    assert app.get("/health")["read_only"] is True
    assert app.get("/snapshot")["symbol"] == "BTCUSDT"
    assert app.get("/decision")["decision"]["action"] == "WAIT"
    assert app.get("/risk")["risk"]["approved"] is False
    assert app.get("/observability")["observability"] is None


def test_dashboard_service_rejects_order_mutation_routes():
    app = create_app(lambda: result())
    with pytest.raises(PermissionError):
        app.get("/create_order")
    with pytest.raises(PermissionError):
        app.get("/cancel_order")