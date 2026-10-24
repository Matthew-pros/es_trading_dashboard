from __future__ import annotations
import pandas as pd
from ..config import StrategyConfig
from ..models import ModelName,PortfolioState,Recommendation,DataMode
from ..indicators import rolling_drawdown
def generate_alm_recommendation(prices:dict[str,pd.DataFrame],state:PortfolioState,config:StrategyConfig,source:str="Yahoo Finance",data_mode:DataMode=DataMode.HISTORICAL)->Recommendation:
 if state.alm_completed:return Recommendation(state.model,None,source,data_mode,False,None,"HOLD",0,0,0,0,"ALM je již dokončen; žádný nový iniciační vstup.")
 if state.positions or state.cash_usd+1e-6<state.equity_usd-1e-6:return Recommendation(state.model,None,source,data_mode,False,None,"REVIEW",0,0,0,0,"ALM je aktivní pouze při 100% hotovosti a bez pozic.",available=False)
 eligible: list[tuple[str, float]] = []; ind: dict[str, float | None] = {}
 for ticker in ("SPY","QQQ"):
  frame=prices.get(ticker)
  if frame is None or frame.empty or "Close" not in frame:ind[ticker]=None;continue
  close=frame.Close.dropna()
  if close.empty or close.iloc[-1]<=0:ind[ticker]=None;continue
  dd_value = rolling_drawdown(close).iloc[-1]
  if pd.isna(dd_value):
   ind[ticker] = None
   continue
  dd = float(dd_value)
  ind[f"{ticker}_drawdown"] = dd
  ind[f"{ticker}_close"] = float(close.iloc[-1])
  if dd>=config.alm_deep_drawdown:eligible.append((ticker,config.alm_deep_fraction))
  elif dd>=config.alm_mid_drawdown:eligible.append((ticker,config.alm_mid_fraction))
 if not eligible:return Recommendation(state.model,None,source,data_mode,False,None,"HOLD",0,0,0,0,"SPY ani QQQ nedosáhly ALM drawdown prahu 30 %.",indicators=ind)
 ticker=max(eligible,key=lambda x: float(ind.get(f"{x[0]}_drawdown") or -1.0))[0];fraction=dict(eligible)[ticker];target=min(state.equity_usd*fraction,state.equity_usd*(1-config.alm_cash_reserve))
 return Recommendation(state.model,None,source,data_mode,False,ticker,"BUY",target,target,0,0,f"ALM tranše {fraction:.0%}; rezervována hotovost nejméně {config.alm_cash_reserve:.0%}.",indicators=ind)
