import pandas as pd
from src.calendar import month_rotation_date
from src.config import StrategyConfig
from src.models import ModelName, PortfolioState
from src.strategies.drbl_matrix import choose_rotation, generate_matrix_recommendation, process_monthly_rotation


def test_choose_rotation_initial_asset():
    assert choose_rotation({"SPY": 0.1, "QQQ": 0.2}, None) == "QQQ"


def test_rotation_hysteresis_positive():
    assert choose_rotation({"SPY": 1.0, "QQQ": 1.08}, "SPY") == "SPY"
    assert choose_rotation({"SPY": 1.0, "QQQ": 1.081}, "SPY") == "QQQ"


def test_rotation_hysteresis_negative_is_deterministic():
    assert choose_rotation({"SPY": -1.0, "QQQ": -0.95}, "SPY") == "SPY"
    assert choose_rotation({"SPY": -1.0, "QQQ": -0.91}, "SPY") == "QQQ"


def test_no_scores():
    assert choose_rotation({}, None) is None


def test_monthly_rotation_only_on_or_after_scheduled_date(sample_ohlcv):
    prices = {"SPY": sample_ohlcv, "QQQ": sample_ohlcv, "GLD": sample_ohlcv, "IBIT": sample_ohlcv}
    state = PortfolioState(ModelName.DRBL_MATRIX, 100_000)
    scheduled = month_rotation_date(sample_ohlcv.index[-1].year, sample_ohlcv.index[-1].month)
    if scheduled is not None:
        before = (pd.Timestamp(scheduled) - pd.Timedelta(days=1)).date().isoformat()
        _, changed, scores = process_monthly_rotation(prices, state, StrategyConfig(), before)
        assert not changed
        assert state.last_rotation_month is None
        after = pd.Timestamp(scheduled).date().isoformat()
        selected, _, scores = process_monthly_rotation(prices, state, StrategyConfig(), after)
        assert selected is not None
        assert state.last_rotation_month == pd.Timestamp(after).strftime("%Y-%m")


def test_daily_matrix_requires_selected_asset(sample_ohlcv):
    prices = {"SPY": sample_ohlcv, "QQQ": sample_ohlcv, "GLD": sample_ohlcv, "IBIT": sample_ohlcv}
    state = PortfolioState(ModelName.DRBL_MATRIX, 100_000)
    rec = generate_matrix_recommendation(prices, state, StrategyConfig())
    assert rec.action == "ROTATION_REQUIRED"
