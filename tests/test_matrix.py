from src.config import StrategyConfig
from src.models import ModelName, PortfolioState, Position
from src.strategies.drbl_matrix import generate_matrix_recommendation


def test_matrix_missing_data_not_available():
    state = PortfolioState(ModelName.DRBL_MATRIX, 100_000)
    rec = generate_matrix_recommendation({}, state, StrategyConfig())
    assert not rec.available


def test_more_than_one_holding_requires_review(sample_ohlcv):
    state = PortfolioState(
        ModelName.DRBL_MATRIX, 10_000,
        positions={"SPY": Position("SPY", 50_000, 500), "QQQ": Position("QQQ", 40_000, 300)},
    )
    rec = generate_matrix_recommendation(
        {"SPY": sample_ohlcv, "QQQ": sample_ohlcv, "GLD": sample_ohlcv, "IBIT": sample_ohlcv},
        state, StrategyConfig(),
    )
    assert rec.action == "REVIEW" and not rec.available

def test_regime_c_returns_held_ticker_for_exit(sample_ohlcv, monkeypatch):
    import src.strategies.drbl_matrix as strategy_module
    from src.models import Regime

    state = PortfolioState(
        ModelName.DRBL_MATRIX, 15_000,
        positions={"UPRO": Position("UPRO", 85_000, 200)},
        selected_asset="SPY",
    )
    prices = {"SPY": sample_ohlcv, "QQQ": sample_ohlcv, "GLD": sample_ohlcv, "IBIT": sample_ohlcv}
    monkeypatch.setattr(strategy_module, "_latest", lambda frame, asset, config: {
        "available": True, "entry": False, "exit": True, "adx14": 20.0, "rvol": 1.0, "regime": "C",
    })
    rec = generate_matrix_recommendation(prices, state, StrategyConfig())
    assert rec.action == "SELL_ALL"
    assert rec.ticker == "UPRO"
    assert rec.target_usd == 0
    assert rec.delta_usd < 0
