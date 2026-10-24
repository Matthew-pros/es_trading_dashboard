import numpy as np
import pandas as pd
from src.config import StrategyConfig
from src.models import PortfolioState, ModelName
from src.strategies.alm import generate_alm_recommendation

def frame_from_close(close):
    idx=pd.bdate_range("2020-01-01",periods=len(close))
    return pd.DataFrame({"Open":close,"High":close*1.01,"Low":close*.99,"Close":close,"Volume":1_000_000},index=idx)

def test_alm_deepest_drawdown_and_tranche():
    spy=frame_from_close(np.r_[np.linspace(100,200,100),np.linspace(190,80,30)])
    qqq=frame_from_close(np.r_[np.linspace(100,200,100),np.linspace(190,90,30)])
    state=PortfolioState(ModelName.ALM,100_000)
    rec=generate_alm_recommendation({"SPY":spy,"QQQ":qqq},state,StrategyConfig(initial_equity=100_000))
    assert rec.ticker=="SPY"
    assert rec.target_usd==20_000

def test_alm_not_active_when_positions_exist(sample_ohlcv):
    from src.models import Position
    state=PortfolioState(ModelName.ALM,50_000,positions={"SPY":Position("SPY",50_000,400)})
    rec=generate_alm_recommendation({"SPY":sample_ohlcv,"QQQ":sample_ohlcv},state,StrategyConfig())
    assert not rec.available
    assert rec.action=="REVIEW"
