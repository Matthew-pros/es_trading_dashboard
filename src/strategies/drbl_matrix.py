from __future__ import annotations
import pandas as pd
from ..calendar import month_rotation_date
from ..config import StrategyConfig
from ..models import ModelName, PortfolioState, Recommendation, DataMode, Regime
from ..indicators import adx_wilder, breakout_factors, regression_factors, rvol, momentum_score


def monthly_rotation_score(prices: dict[str, pd.DataFrame]) -> dict[str, float]:
    """Score the four base ETFs with the documented 12–1 momentum/volatility formula."""
    out: dict[str, float] = {}
    for ticker in ("SPY", "QQQ", "GLD", "IBIT"):
        frame = prices.get(ticker)
        if frame is None or frame.empty or "Close" not in frame:
            continue
        score = momentum_score(frame["Close"]).iloc[-1]
        if pd.notna(score):
            out[ticker] = float(score)
    return out


def choose_rotation(scores: dict[str, float], incumbent: str | None, hysteresis: float = 0.08) -> str | None:
    scores = {key: value for key, value in scores.items() if pd.notna(value)}
    if not scores:
        return None
    challenger = max(scores, key=lambda ticker: scores[ticker])
    if incumbent is None or incumbent not in scores:
        return challenger
    threshold = scores[incumbent] + abs(scores[incumbent]) * hysteresis
    return challenger if challenger != incumbent and scores[challenger] > threshold else incumbent


def _finite(value: object) -> float | None:
    try:
        numeric = float(value)  # type: ignore[arg-type]
        return numeric if pd.notna(numeric) else None
    except (TypeError, ValueError):
        return None


def _latest(frame: pd.DataFrame | None, asset: str, config: StrategyConfig) -> dict:
    if frame is None or frame.empty:
        return {"available": False, "reason": "Data nejsou dostupná."}
    if asset in ("SPY", "QQQ"):
        factors = breakout_factors(frame, config.breakout_entry_lookback, config.breakout_exit_lookback)
        last = factors.iloc[-1]
        entry = bool(last["entry"])
        exit_signal = bool(last["exit"])
        extra = {"entry_level": _finite(last["entry_level"]), "exit_level": _finite(last["exit_level"])}
    else:
        factors = regression_factors(frame["Close"], config.regression_period)
        last = factors.iloc[-1]
        entry = bool(last["entry"])
        exit_signal = bool(last["exit"])
        extra = {"slope": _finite(last["slope"]), "upper_band": _finite(last["upper_band"])}
    adx = _finite(adx_wilder(frame, config.adx_period).iloc[-1])
    relative_volume = _finite(rvol(frame["Volume"], config.rvol_short, config.rvol_long).iloc[-1])
    filters_available = adx is not None and relative_volume is not None
    adx_for_regime = adx if adx is not None else float("-inf")
    rvol_for_regime = relative_volume if relative_volume is not None else float("-inf")
    regime = (
        Regime.C if exit_signal
        else Regime.A if entry and filters_available and adx_for_regime > 25 and rvol_for_regime > 1.4
        else Regime.B if entry
        else Regime.UNKNOWN
    )
    extra.update({
        "close": float(frame["Close"].iloc[-1]),
        "entry": entry,
        "exit": exit_signal,
        "adx14": adx,
        "rvol": relative_volume,
        "filters_available": filters_available,
        "regime": regime.value,
        "available": True,
    })
    return extra


def _base_asset_for_position(state: PortfolioState, config: StrategyConfig, gld_leveraged_ticker: str | None) -> str | None:
    if not state.positions:
        return state.selected_asset
    if len(state.positions) != 1:
        return None
    held_ticker = next(iter(state.positions.values())).ticker
    candidates = {
        base for base in ("SPY", "QQQ", "GLD", "IBIT")
        if held_ticker in {
            config.ticker_mapping.get(base),
            config.leveraged_mapping.get(base),
            gld_leveraged_ticker or config.gld_leveraged_ticker,
        }
    }
    return next(iter(candidates)) if len(candidates) == 1 else None


def generate_matrix_recommendation(
    prices: dict[str, pd.DataFrame],
    state: PortfolioState,
    config: StrategyConfig,
    source: str = "Yahoo Finance",
    data_mode: DataMode = DataMode.HISTORICAL,
    gld_leveraged_ticker: str | None = None,
) -> Recommendation:
    """Evaluate the daily signal for the currently selected asset; never rotate intramonth."""
    assets = ("SPY", "QQQ", "GLD", "IBIT")
    indicators = {asset: _latest(prices.get(asset), asset, config) for asset in assets}
    if len(state.positions) > 1:
        return Recommendation(
            state.model, None, source, DataMode.STALE, False, None, "REVIEW", 0, 0, 0, 0,
            "Více současně držených aktiv: ruční kontrola.", indicators=indicators, available=False,
        )

    selected = state.selected_asset or _base_asset_for_position(state, config, gld_leveraged_ticker)
    if selected is None:
        return Recommendation(
            state.model, None, source, data_mode, False, None, "ROTATION_REQUIRED", 0, 0, 0, 0,
            "Zatím není zvolené aktivum. Vyberte aktivum měsíční rotací; denní signál rotaci nespouští.",
            indicators=indicators, available=False,
        )
    info = indicators.get(selected, {})
    if not info.get("available"):
        return Recommendation(
            state.model, None, source, DataMode.STALE, False, None, "UNAVAILABLE", 0, 0, 0, 0,
            f"Chybí validní denní data pro {selected}.", indicators=indicators, available=False,
        )

    held = next(iter(state.positions.values()), None)
    held_ticker = held.ticker if held else None
    entry = bool(info["entry"])
    exit_signal = bool(info["exit"])
    regime = Regime(info["regime"])
    reason = (
        f"Aktivum {selected}; entry={entry}, exit={exit_signal}, "
        f"ADX={info['adx14']}, RVOL={info['rvol']}."
    )

    # Exit has priority over entry. The position ticker must be returned so the engine can close it.
    if exit_signal:
        target_ticker = held_ticker or config.ticker_mapping.get(selected, selected)
        current_value = held.market_value_usd if held else 0.0
        return Recommendation(
            state.model, None, source, data_mode, False, target_ticker,
            "SELL_ALL" if held else "HOLD_CASH", 0.0, -current_value, 0.0, 0.0,
            "Režim C: uzavřít spravovanou pozici a držet hotovost. " + reason,
            Regime.C, indicators,
        )

    if not entry:
        return Recommendation(
            state.model, None, source, data_mode, False, held_ticker, "HOLD", held.market_value_usd if held else 0.0,
            0.0, 0.0, 0.0, "Entry ani exit není aktivní; zachovat současnou pozici. " + reason,
            Regime.UNKNOWN, indicators,
        )

    if regime == Regime.A:
        target_ticker = (
            "IBIT" if selected == "IBIT"
            else (gld_leveraged_ticker or config.gld_leveraged_ticker) if selected == "GLD"
            else config.leveraged_mapping.get(selected)
        )
        if selected == "GLD" and not target_ticker:
            return Recommendation(
                state.model, None, source, data_mode, False, None, "CONFIGURATION_REQUIRED", 0, 0, 0, 0,
                "Pro režim A u GLD nastavte konkrétní ticker; objednávka nebyla vytvořena.",
                regime, indicators, False,
            )
        target_fraction = config.matrix_target_fraction
    else:
        target_ticker = config.ticker_mapping.get(selected, selected)
        target_fraction = config.matrix_target_fraction

    target_value = state.equity_usd * target_fraction
    current_value = held.market_value_usd if held and held.ticker == target_ticker else 0.0
    delta_value = target_value - current_value

    # A/B changes between base and leveraged ticker must explicitly close the old ticker first.
    if held and held.ticker != target_ticker:
        return Recommendation(
            state.model, None, source, data_mode, False, held.ticker, "ROTATE_POSITION", 0.0,
            -held.market_value_usd, 0.0, 0.0,
            f"Změna cílového tickeru {held.ticker} → {target_ticker}; nejprve uzavřít starou pozici. " + reason,
            regime, indicators,
        )
    action = "HOLD" if abs(delta_value) < 0.01 else "BUY_OR_REBALANCE"
    return Recommendation(
        state.model, None, source, data_mode, False, target_ticker, action,
        target_value, delta_value, 0.0, 0.0, reason, regime, indicators,
    )


def process_monthly_rotation(
    prices: dict[str, pd.DataFrame],
    state: PortfolioState,
    config: StrategyConfig,
    rotation_date: str,
) -> tuple[str | None, bool, dict[str, float]]:
    scores = monthly_rotation_score(prices)
    if not scores:
        # Missing scores do not mark the monthly rotation as completed.
        return state.selected_asset, False, scores
    scheduled_date = month_rotation_date(pd.Timestamp(rotation_date).year, pd.Timestamp(rotation_date).month)
    if scheduled_date is None or pd.Timestamp(rotation_date).date() < scheduled_date:
        return state.selected_asset, False, scores
    month = pd.Timestamp(rotation_date).strftime("%Y-%m")
    if state.last_rotation_month == month:
        return state.selected_asset, False, scores
    choice = choose_rotation(scores, state.selected_asset, config.rotation_hysteresis)
    changed = choice is not None and choice != state.selected_asset
    if choice is not None:
        state.selected_asset = choice
        state.last_rotation_month = month
    return state.selected_asset, changed, scores
