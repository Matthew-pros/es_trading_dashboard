from __future__ import annotations
from datetime import datetime,timezone
from .backtest_service import get_prices
from ..config import CostConfig,StrategyConfig
from ..costs import estimate_costs
from ..models import DataMode,ModelName,PortfolioState,Recommendation
from ..strategies.alm import generate_alm_recommendation
from ..strategies.drbl_matrix import generate_matrix_recommendation
from ..strategies.combined import generate_combined_recommendation
def recommend(model:ModelName,prices:dict,state:PortfolioState,strategy:StrategyConfig,costs:CostConfig,latest_timestamp:datetime|None=None,gld_leveraged_ticker:str|None=None):
    source="Yahoo Finance";mode=DataMode.HISTORICAL
    if model==ModelName.ALM:rec=generate_alm_recommendation(prices,state,strategy,source,mode)
    elif model==ModelName.DRBL_MATRIX:rec=generate_matrix_recommendation(prices,state,strategy,source,mode,gld_leveraged_ticker)
    else:rec=generate_combined_recommendation(prices,state,strategy,source,mode,gld_leveraged_ticker)
    if latest_timestamp is not None:
        if latest_timestamp.tzinfo is None:latest_timestamp=latest_timestamp.replace(tzinfo=timezone.utc)
        age=(datetime.now(timezone.utc)-latest_timestamp.astimezone(timezone.utc)).total_seconds()/3600
        if age>72:mode=DataMode.STALE
    if rec.ticker and rec.delta_usd:
        f=prices.get(rec.ticker) or prices.get(next((k for k,v in strategy.ticker_mapping.items() if v==rec.ticker),""))
        price=float(f.Close.iloc[-1]) if f is not None and not f.empty else 0.
        if price>0:
            side="buy" if rec.delta_usd>0 else "sell";qty=abs(rec.delta_usd)/price
            if not costs.fractional_shares:qty=float(int(qty))
            cost=estimate_costs(qty,price,side,costs)
            from dataclasses import replace
            rec=replace(rec,estimated_commission_usd=cost.commission_usd,estimated_slippage_usd=cost.slippage_usd)
    from dataclasses import replace
    rec=replace(rec,as_of=latest_timestamp,data_mode=mode)
    return rec
