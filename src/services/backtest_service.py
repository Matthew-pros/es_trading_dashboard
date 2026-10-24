from __future__ import annotations
from datetime import date,timedelta
from ..config import CostConfig,StrategyConfig
from ..data.yfinance_provider import YahooFinanceProvider
from ..backtest.engine import run_backtest
from ..models import ModelName
TICKERS=["SPY","QQQ","GLD","IBIT","UPRO","TQQQ"]
def get_prices(start:str,end:str|None=None,provider=None,tickers:list[str]|None=None):
    p=provider or YahooFinanceProvider();result={}
    for ticker in (tickers or TICKERS):
        try:result[ticker]=p.get_daily(ticker,start,end).bars
        except Exception:continue
    return result
def run_model_backtest(data,model:ModelName,config:StrategyConfig,costs:CostConfig,start=None,end=None):
    return run_backtest(data,model,config,costs,start,end)
