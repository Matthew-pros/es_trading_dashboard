from __future__ import annotations
import pandas as pd
from ..config import StrategyConfig
from ..models import PortfolioState,Recommendation,ModelName,DataMode
from .alm import generate_alm_recommendation
from .drbl_matrix import generate_matrix_recommendation
def generate_combined_recommendation(prices:dict[str,pd.DataFrame],state:PortfolioState,config:StrategyConfig,source:str="Yahoo Finance",data_mode:DataMode=DataMode.HISTORICAL,gld_leveraged_ticker:str|None=None)->Recommendation:
 if not state.alm_completed or not state.alm_fill_confirmed:
  s=PortfolioState(ModelName.COMBINED,state.cash_usd,dict(state.positions),state.alm_completed,state.alm_fill_confirmed,state.selected_asset,state.current_regime,state.last_rotation_month);r=generate_alm_recommendation(prices,s,config,source,data_mode)
  return Recommendation(ModelName.COMBINED,r.as_of,r.source,r.data_mode,r.provisional,r.ticker,r.action,r.target_usd,r.delta_usd,r.estimated_commission_usd,r.estimated_slippage_usd,"Combined: čeká na potvrzený ALM fill. "+r.reason,r.regime,r.indicators,r.available)
 s=PortfolioState(ModelName.COMBINED,state.cash_usd,dict(state.positions),state.alm_completed,state.alm_fill_confirmed,state.selected_asset,state.current_regime,state.last_rotation_month);r=generate_matrix_recommendation(prices,s,config,source,data_mode,gld_leveraged_ticker)
 return Recommendation(ModelName.COMBINED,r.as_of,r.source,r.data_mode,r.provisional,r.ticker,r.action,r.target_usd,r.delta_usd,r.estimated_commission_usd,r.estimated_slippage_usd,"Combined – provozní fáze po potvrzeném ALM fillu. "+r.reason,r.regime,r.indicators,r.available)
