from __future__ import annotations
from dataclasses import dataclass
import pandas as pd
from ..calendar import month_rotation_date
from ..config import CostConfig, StrategyConfig
from ..costs import estimate_costs
from ..models import ModelName, PortfolioState, Position
from ..indicators import normalize_ohlcv
from ..strategies.alm import generate_alm_recommendation
from ..strategies.drbl_matrix import generate_matrix_recommendation, process_monthly_rotation
from ..strategies.combined import generate_combined_recommendation
from .metrics import compute_metrics


@dataclass
class BacktestResult:
    model: ModelName
    equity: pd.Series
    trades: pd.DataFrame
    metrics: dict
    warnings: list[str]
    costs: dict

    def __post_init__(self):
        if self.equity is None:
            self.equity = pd.Series(dtype=float)


def run_backtest(
    data: dict[str, pd.DataFrame],
    model: ModelName,
    config: StrategyConfig,
    costs: CostConfig,
    start: str | None = None,
    end: str | None = None,
) -> BacktestResult:
    normalized = {key: normalize_ohlcv(frame) for key, frame in data.items() if frame is not None and not frame.empty}
    if not normalized:
        raise ValueError("Backtest nelze spustit: nejsou dostupná data.")
    primary = normalized.get("SPY")
    if primary is None or len(primary) < 253:
        raise ValueError("Nedostatečná historie pro warm-up momenta (vyžadováno alespoň 253 barů).")

    # Use full history for indicator warm-up and restrict only actionable signal dates.
    all_dates = primary.index
    if end:
        all_dates = all_dates[all_dates <= pd.Timestamp(end)]
    dates = all_dates.intersection(pd.DatetimeIndex(sorted(set.union(*(set(frame.index) for frame in normalized.values())))))
    if start:
        # Keep the warm-up bars in the rolling history but do not create trades before start.
        signal_start = pd.Timestamp(start)
    else:
        signal_start = dates[0]
    if len(dates) < 2:
        raise ValueError("Vybraný interval obsahuje méně než dva obchodní bary.")
    if signal_start > dates[-2]:
        raise ValueError("Vybraný interval nemá dostatek budoucích barů pro exekuci signálu.")

    state = PortfolioState(model, config.initial_equity)
    equity_rows: list[tuple[pd.Timestamp, float]] = []
    trade_rows: list[dict] = []
    warnings: list[str] = []

    for index, timestamp in enumerate(dates):
        # Mark positions to the close available at this timestamp.
        for ticker, position in list(state.positions.items()):
            frame = normalized.get(ticker)
            if frame is not None and timestamp in frame.index:
                position.market_value_usd = position.quantity * float(frame.loc[timestamp, "Close"])
        equity = state.equity_usd
        if timestamp >= signal_start:
            equity_rows.append((timestamp, equity))
        if index >= len(dates) - 1 or timestamp < signal_start:
            continue

        available = {
            ticker: frame.loc[:timestamp]
            for ticker, frame in normalized.items()
            if (frame.index <= timestamp).any()
        }

        # Rotation is a distinct monthly event; it is not re-run on every daily recommendation.
        if model in (ModelName.DRBL_MATRIX, ModelName.COMBINED):
            rotation_day = month_rotation_date(timestamp.year, timestamp.month)
            if rotation_day is not None and timestamp.date() >= rotation_day:
                if model == ModelName.DRBL_MATRIX or (state.alm_completed and state.alm_fill_confirmed):
                    try:
                        old_asset = state.selected_asset
                        selected, changed, scores = process_monthly_rotation(
                            {key: frame.loc[:timestamp] for key, frame in normalized.items() if key in ("SPY", "QQQ", "GLD", "IBIT")},
                            state,
                            config,
                            timestamp.date().isoformat(),
                        )
                        if not scores and state.last_rotation_month is None:
                            warnings.append(f"{timestamp.date()}: rotace odložena, momentum skóre nejsou dostupná.")
                        elif changed:
                            warnings.append(f"{timestamp.date()}: měsíční rotace {old_asset or '—'} → {selected}.")
                    except Exception as exc:
                        warnings.append(f"{timestamp.date()}: měsíční rotace přeskočena ({exc}).")

        try:
            if model == ModelName.ALM:
                rec = generate_alm_recommendation(available, state, config)
            elif model == ModelName.DRBL_MATRIX:
                rec = generate_matrix_recommendation(available, state, config)
            else:
                rec = generate_combined_recommendation(available, state, config)
        except Exception as exc:
            warnings.append(f"{timestamp}: signál přeskočen ({exc})")
            continue
        if not rec.available or not rec.ticker or abs(rec.delta_usd) < 0.01:
            continue

        next_timestamp = dates[index + 1]
        frame = normalized.get(rec.ticker)
        if frame is None or next_timestamp not in frame.index:
            continue
        raw_price = float(frame.loc[next_timestamp, "Open"])
        if raw_price <= 0:
            continue

        side = "BUY" if rec.delta_usd > 0 else "SELL"
        target = max(0.0, rec.target_usd)
        held = state.positions.get(rec.ticker)
        current_value = held.market_value_usd if held else 0.0
        delta = target - current_value
        quantity = abs(delta) / raw_price
        if not costs.fractional_shares:
            quantity = float(int(quantity))
        if quantity <= 0:
            continue

        estimate = estimate_costs(quantity, raw_price, side.lower(), costs)
        fill_price = estimate.fill_price
        notional = quantity * fill_price
        commission = estimate.commission_usd
        if side == "BUY":
            if notional + commission > state.cash_usd and fill_price > 0:
                quantity = max(0.0, (state.cash_usd - commission) / fill_price)
                if not costs.fractional_shares:
                    quantity = float(int(quantity))
                if quantity <= 0:
                    continue
                estimate = estimate_costs(quantity, raw_price, side.lower(), costs)
                fill_price = estimate.fill_price
                notional = quantity * fill_price
                commission = estimate.commission_usd
            state.cash_usd -= notional + commission
            previous_quantity = held.quantity if held else 0.0
            state.positions[rec.ticker] = Position(rec.ticker, notional, previous_quantity + quantity, fill_price)
        else:
            if held is None:
                continue
            quantity = min(quantity, held.quantity)
            notional = quantity * fill_price
            state.cash_usd += notional - commission
            remaining_quantity = held.quantity - quantity
            if remaining_quantity <= 1e-8:
                state.positions.pop(rec.ticker, None)
            else:
                held.quantity = remaining_quantity
                held.market_value_usd = remaining_quantity * fill_price

        trade_rows.append({
            "signal_timestamp": timestamp,
            "execution_timestamp": next_timestamp,
            "ticker": rec.ticker,
            "side": side,
            "quantity": quantity,
            "price": fill_price,
            "target_usd": target,
            "delta_usd": delta,
            "commission_usd": commission,
            "slippage_usd": estimate.slippage_usd,
            "other_fees_usd": estimate.other_fees_usd,
            "status": "SIMULATED_FILLED",
            "reason": rec.reason,
            "notional_usd": notional,
            "in_market": bool(state.positions),
        })
        if model == ModelName.COMBINED and not state.alm_completed and side == "BUY":
            state.alm_completed = True
            state.alm_fill_confirmed = True

    equity_series = pd.Series(dict(equity_rows), dtype=float).sort_index()
    trades = pd.DataFrame(trade_rows)
    if not trades.empty:
        trades["gross_notional_usd"] = trades["notional_usd"]
    costs_summary = {
        "commissions": float(trades["commission_usd"].sum()) if not trades.empty else 0.0,
        "slippage": float(trades["slippage_usd"].sum()) if not trades.empty else 0.0,
        "other_fees": float(trades["other_fees_usd"].sum()) if not trades.empty else 0.0,
    }
    return BacktestResult(model, equity_series, trades, compute_metrics(equity_series, trades), warnings, costs_summary)
