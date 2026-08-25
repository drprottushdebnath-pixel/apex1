from __future__ import annotations

from brain.context import MarketContext, MarketContextBuilder, OrderBook, Trade
from brain.context import Candle


class LiveSnapshotContextAdapter:
    """Convert one live snapshot into the canonical market context."""

    def __init__(self, snapshot) -> None:
        self.snapshot = snapshot

    def build(
        self,
        calculation_time: float | None = None,
        as_of: float | None = None,
    ) -> MarketContext | None:
        state = self.snapshot.build(calculation_time=calculation_time)
        if state is None:
            return None

        data = self.snapshot.feed.data
        cutoff = data.last_event_time if as_of is None else float(as_of)
        quality, quality_reason = data.quality(now=calculation_time, thresholds=self.snapshot.feed.stale_thresholds)
        price_state = self.snapshot.feed.price_history.state(as_of=cutoff)
        if as_of is not None and price_state.price is None:
            return None
        if quality in {"OK", "DATA_VALID"} and data.open_interest is None:
            quality = "DATA_INCOMPLETE"
            quality_reason = "Open interest is unavailable"
        if quality in {"OK", "DATA_VALID"} and data.funding_rate is None:
            quality = "DATA_INCOMPLETE"
            quality_reason = "Funding is unavailable"
        order_book = None
        book_is_visible = data.orderbook_event_time is None or data.orderbook_event_time <= cutoff
        if book_is_visible and (data.bids or data.asks):
            try:
                order_book = OrderBook(
                    bids=tuple(data.snapshot_bids(50)),
                    asks=tuple(data.snapshot_asks(50)),
                )
            except ValueError:
                order_book = None

        trades = tuple(
            Trade(
                trade_id=str(item["id"]),
                event_time=float(item["timestamp"]) / 1000,
                price=float(item["price"]),
                quantity=float(item["quantity"]),
                side=str(item["side"]),
            )
            for item in data.trades
            if item.get("id") is not None
            and float(item["timestamp"]) / 1000 <= cutoff
        )
        candles = tuple(
            Candle(
                event_time=float(item["event_time"]),
                open=float(item["open"]),
                high=float(item["high"]),
                low=float(item["low"]),
                close=float(item["close"]),
                volume=float(item["volume"]),
            )
            for item in data.candles
            if item.get("confirmed", True)
            and float(item["event_time"]) <= cutoff
        )
        flow = state.order_flow
        if as_of is not None:
            from market.orderflow import OrderFlowEngine

            imbalance = order_book.imbalance if order_book else 0.0
            flow = vars(OrderFlowEngine().analyze(
                trades=[
                    {
                        "price": trade.price,
                        "quantity": trade.quantity,
                        "side": trade.side,
                    }
                    for trade in trades
                ],
                orderbook_imbalance=imbalance,
            ))
        oi_state = self.snapshot.feed.oi_history.state(as_of=cutoff)
        visible_funding = (
            data.funding_rate
            if data.funding_event_time is None or data.funding_event_time <= cutoff
            else None
        )
        if quality in {"OK", "DATA_VALID"}:
            if not book_is_visible:
                quality = "DATA_INCOMPLETE"
                quality_reason = "Order-book data is newer than the context cutoff"
            elif oi_state.open_interest is None:
                quality = "DATA_INCOMPLETE"
                quality_reason = "Open interest is unavailable at the context cutoff"
            elif visible_funding is None:
                quality = "DATA_INCOMPLETE"
                quality_reason = "Funding is unavailable at the context cutoff"
        visible_price = price_state.price if as_of is not None else state.price
        return (
            MarketContextBuilder(state.symbol, visible_price, state.timeframe)
            .set_exchange("BYBIT")
            .set_price(state.price, volume=data.volume)
            .set_price_change_pct(price_state.change_pct)
            .set_market_data(
                candles=candles,
                order_book=order_book,
                trades=trades,
                delta=flow.get("delta"),
                cvd=flow.get("cumulative_delta"),
                  open_interest=oi_state.open_interest if as_of is not None else data.open_interest,
                  oi_change=oi_state.change_pct if as_of is not None else data.oi_change_pct,
                  funding=visible_funding,
            )
            .set_event_times(
                  event_time=cutoff,
                received_time=data.last_update,
                calculation_time=calculation_time,
            )
            .add_metadata("candles_by_timeframe", {
                timeframe: tuple(
                    {
                        "event_time": float(item["event_time"]),
                        "open": float(item["open"]),
                        "high": float(item["high"]),
                        "low": float(item["low"]),
                        "close": float(item["close"]),
                        "volume": float(item["volume"]),
                    }
                    for item in items
                    if item.get("confirmed", True)
                      and float(item["event_time"]) <= cutoff
                )
                for timeframe, items in data.candles_by_timeframe.items()
            })
            .add_metadata("volume_24h", data.volume_24h)
            .add_metadata("volume_24h_event_time", data.volume_24h_event_time)
            .add_metadata("funding_event_time", data.funding_event_time)
            .add_metadata("oi_event_time", data.oi_event_time)
            .set_data_quality(quality, quality_reason)
            .build(allow_incomplete=True)
        )