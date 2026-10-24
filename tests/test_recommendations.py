import pandas as pd
from src.config import CostConfig, StrategyConfig
from src.models import ModelName, PortfolioState
from src.services.recommendation_service import recommend

def test_recommendation_includes_source_and_historical_mode(sample_ohlcv):
    state=PortfolioState(ModelName.ALM,100_000)
    rec=recommend(ModelName.ALM,{"SPY":sample_ohlcv,"QQQ":sample_ohlcv},state,StrategyConfig(),CostConfig(),latest_timestamp=sample_ohlcv.index[-1].to_pydatetime())
    assert rec.source=="Yahoo Finance"
    assert rec.data_mode.value=="STALE"

def test_recommendation_costs_with_dataframe_price_source(sample_ohlcv, monkeypatch):
    from src.models import DataMode, Recommendation
    import src.services.recommendation_service as service

    state = PortfolioState(ModelName.ALM, 100_000)
    scripted = Recommendation(
        ModelName.ALM, None, "Yahoo Finance", DataMode.HISTORICAL, False,
        "SPY", "BUY", 10_000, 10_000, 0, 0, "test signal",
    )
    monkeypatch.setattr(service, "generate_alm_recommendation", lambda *args, **kwargs: scripted)
    rec = service.recommend(
        ModelName.ALM, {"SPY": sample_ohlcv}, state, StrategyConfig(), CostConfig(),
        latest_timestamp=sample_ohlcv.index[-1].to_pydatetime(),
    )
    assert rec.estimated_commission_usd > 0
