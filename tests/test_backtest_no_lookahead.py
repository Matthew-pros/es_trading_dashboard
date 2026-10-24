import pandas as pd
import pytest
from src.backtest.engine import run_backtest
from src.config import StrategyConfig, CostConfig
from src.models import ModelName

def test_backtest_requires_warmup(sample_ohlcv):
    with pytest.raises(ValueError,match="warm-up"):
        run_backtest({"SPY":sample_ohlcv.iloc[:150]},ModelName.ALM,StrategyConfig(),CostConfig())

def test_backtest_executes_after_signal_bar(sample_ohlcv):
    result=run_backtest({"SPY":sample_ohlcv,"QQQ":sample_ohlcv,"GLD":sample_ohlcv,"IBIT":sample_ohlcv,"UPRO":sample_ohlcv,"TQQQ":sample_ohlcv},ModelName.ALM,StrategyConfig(),CostConfig(),start=sample_ohlcv.index[260].date().isoformat())
    if not result.trades.empty:
        assert (pd.to_datetime(result.trades.execution_timestamp)>pd.to_datetime(result.trades.signal_timestamp)).all()
