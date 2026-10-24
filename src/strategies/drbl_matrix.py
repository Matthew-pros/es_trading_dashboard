from __future__ import annotations
import pandas as pd
from ..config import StrategyConfig
from ..models import ModelName,PortfolioState,Recommendation,DataMode,Regime
from ..indicators import adx_wilder,breakout_factors,regression_factors,rvol,momentum_score
def monthly_rotation_score(prices:dict[str,pd.DataFrame])->dict[str,float]:
 out={}
 for t,f in prices.items():
  if f is not None and not f.empty and "Close" in f:
   v=momentum_score(f.Close).iloc[-1]
   if pd.notna(v):out[t]=float(v)
 return out
def choose_rotation(scores:dict[str,float],incumbent:str|None,hysteresis:float=.08)->str|None:
 scores={k:v for k,v in scores.items() if pd.notna(v)}
 if not scores:return None
 challenger=max(scores,key=lambda ticker: scores[ticker])
 if incumbent is None or incumbent not in scores:return challenger
 threshold=scores[incumbent]+abs(scores[incumbent])*hysteresis
 return challenger if challenger!=incumbent and scores[challenger]>threshold else incumbent
def _finite(v):
 try:
  x=float(v);return x if pd.notna(x) else None
 except (TypeError,ValueError):return None
def _latest(frame,asset,config):
 if frame is None or frame.empty:return {"available":False,"reason":"Data nejsou dostupná."}
 if asset in ("SPY","QQQ"):
  f=breakout_factors(frame,config.breakout_entry_lookback,config.breakout_exit_lookback);last=f.iloc[-1];entry=bool(last.entry);exit_=bool(last.exit);d={"entry_level":_finite(last.entry_level),"exit_level":_finite(last.exit_level)}
 else:
  f=regression_factors(frame.Close,config.regression_period);last=f.iloc[-1];entry=bool(last.entry);exit_=bool(last.exit);d={"slope":_finite(last.slope),"upper_band":_finite(last.upper_band)}
 adx=_finite(adx_wilder(frame,config.adx_period).iloc[-1]);rv=_finite(rvol(frame.Volume,config.rvol_short,config.rvol_long).iloc[-1]);available=adx is not None and rv is not None
 regime=Regime.C if exit_ else Regime.A if entry and available and adx>25 and rv>1.4 else Regime.B if entry else Regime.UNKNOWN
 d.update({"close":float(frame.Close.iloc[-1]),"entry":entry,"exit":exit_,"adx14":adx,"rvol":rv,"filters_available":available,"regime":regime.value,"available":True});return d
def generate_matrix_recommendation(prices:dict[str,pd.DataFrame],state:PortfolioState,config:StrategyConfig,source:str="Yahoo Finance",data_mode:DataMode=DataMode.HISTORICAL,gld_leveraged_ticker:str|None=None)->Recommendation:
 inds={a:_latest(prices.get(a),a,config) for a in ("SPY","QQQ","GLD","IBIT")}
 if len(state.positions)>1:return Recommendation(state.model,None,source,DataMode.STALE,False,None,"REVIEW",0,0,0,0,"Více současně držených aktiv: ruční kontrola.",indicators=inds,available=False)
 selected=state.selected_asset
 if selected is None and state.positions:
  held=next(iter(state.positions.values())).ticker;selected=next((a for a in ("SPY","QQQ","GLD","IBIT") if held in {config.ticker_mapping.get(a),config.leveraged_mapping.get(a),gld_leveraged_ticker}),None)
 if selected is None:selected=choose_rotation(monthly_rotation_score(prices),None,config.rotation_hysteresis)
 if selected is None:return Recommendation(state.model,None,source,DataMode.STALE,False,None,"UNAVAILABLE",0,0,0,0,"Pro měsíční rotaci nejsou validní skóre.",indicators=inds,available=False)
 info=inds.get(selected,{})
 if not info.get("available"):return Recommendation(state.model,None,source,DataMode.STALE,False,None,"UNAVAILABLE",0,0,0,0,f"Chybí validní data pro {selected}.",indicators=inds,available=False)
 ticker=config.ticker_mapping.get(selected,selected);reg=Regime(info["regime"]);reason=f"Aktivum {selected}; entry={info['entry']}, exit={info['exit']}, ADX={info['adx14']}, RVOL={info['rvol']}."
 if info["exit"]:ticker=None;target=0.;action="SELL_ALL" if state.positions else "HOLD_CASH"
 elif info["entry"]:
  if reg==Regime.A:
   if selected=="IBIT":ticker="IBIT"
   elif selected=="GLD":ticker=gld_leveraged_ticker or config.gld_leveraged_ticker
   else:ticker=config.leveraged_mapping.get(selected)
   if selected=="GLD" and not ticker:return Recommendation(state.model,None,source,data_mode,False,None,"CONFIGURATION_REQUIRED",0,0,0,0,"Pro režim A u GLD nastavte konkrétní pákový ticker; objednávka nebyla vytvořena.",reg,inds,False)
  target=state.equity_usd*config.matrix_target_fraction;action="BUY_OR_REBALANCE"
 else:return Recommendation(state.model,None,source,data_mode,False,None,"HOLD",0,0,0,0,"Entry ani exit není aktivní; zachovat současné pozice. "+reason,Regime.UNKNOWN,inds)
 current=sum(p.market_value_usd for p in state.positions.values() if ticker and p.ticker==ticker);delta=target-current
 if abs(delta)<.01:action="HOLD"
 return Recommendation(state.model,None,source,data_mode,False,ticker,action,target,delta,0,0,reason,reg,inds)
def process_monthly_rotation(prices:dict[str,pd.DataFrame],state:PortfolioState,config:StrategyConfig,rotation_date:str):
 scores=monthly_rotation_score(prices)
 if not scores:return state.selected_asset,False,scores
 month=pd.Timestamp(rotation_date).strftime("%Y-%m")
 if state.last_rotation_month==month:return state.selected_asset,False,scores
 choice=choose_rotation(scores,state.selected_asset,config.rotation_hysteresis);changed=choice is not None and choice!=state.selected_asset;state.last_rotation_month=month
 if choice is not None:state.selected_asset=choice
 return state.selected_asset,changed,scores
