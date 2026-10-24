from __future__ import annotations
from dataclasses import dataclass
from datetime import date
import pandas as pd
from ..config import CostConfig, StrategyConfig
from ..costs import estimate_costs
from ..models import ModelName, PortfolioState, Position, DataMode
from ..indicators import normalize_ohlcv
from ..strategies.alm import generate_alm_recommendation
from ..strategies.drbl_matrix import generate_matrix_recommendation
from ..strategies.combined import generate_combined_recommendation
from .metrics import compute_metrics
@dataclass
class BacktestResult:
    model:ModelName
    equity:pd.Series
    trades:pd.DataFrame
    metrics:dict
    warnings:list[str]
    costs:dict
    def __post_init__(self):
        if self.equity is None:self.equity=pd.Series(dtype=float)
def run_backtest(data:dict[str,pd.DataFrame],model:ModelName,config:StrategyConfig,costs:CostConfig,start:str|None=None,end:str|None=None)->BacktestResult:
    normalized={k:normalize_ohlcv(v) for k,v in data.items() if v is not None and not v.empty}
    if not normalized:raise ValueError("Backtest nelze spustit: nejsou dostupná data.")
    primary=normalized.get("SPY")
    if primary is None or len(primary)<253:raise ValueError("Nedostatečná historie pro warm-up momenta (vyžadováno alespoň 253 barů).")
    idx=primary.index
    if start:idx=idx[idx>=pd.Timestamp(start)]
    if end:idx=idx[idx<=pd.Timestamp(end)]
    idx=idx.intersection(pd.DatetimeIndex(sorted(set.union(*(set(f.index) for f in normalized.values())))))
    if len(idx)<2:raise ValueError("Vybraný interval obsahuje méně než dva obchodní bary.")
    state=PortfolioState(model,config.initial_equity);equity=[];rows=[];warnings=[]
    for i,ts in enumerate(idx):
        # Settle marked holdings at the current bar close before computing signal.
        for ticker,pos in list(state.positions.items()):
            frame=normalized.get(ticker)
            if frame is not None and ts in frame.index:pos.market_value_usd=pos.quantity*float(frame.loc[ts,"Close"])
        state.cash_usd=max(0.,state.cash_usd);eq=state.equity_usd;equity.append((ts,eq))
        # Signal after close is filled no earlier than the next observed bar's open.
        if i>=len(idx)-1:continue
        available={ticker:frame.loc[:ts] for ticker,frame in normalized.items() if ts in frame.index or (frame.index<=ts).any()}
        try:
            if model==ModelName.ALM:rec=generate_alm_recommendation(available,state,config)
            elif model==ModelName.DRBL_MATRIX:rec=generate_matrix_recommendation(available,state,config)
            else:rec=generate_combined_recommendation(available,state,config)
        except Exception as exc:
            warnings.append(f"{ts}: signál přeskočen ({exc})");continue
        if not rec.available or not rec.ticker or abs(rec.delta_usd)<0.01:continue
        next_ts=idx[i+1]
        frame=normalized.get(rec.ticker)
        if frame is None or next_ts not in frame.index:continue
        raw_price=float(frame.loc[next_ts,"Open"])
        if raw_price<=0:continue
        side="BUY" if rec.delta_usd>0 else "SELL";target=max(0.,rec.target_usd)
        held=state.positions.get(rec.ticker);current=held.market_value_usd if held else 0.;delta=target-current
        qty=abs(delta)/raw_price
        if not costs.fractional_shares:qty=float(int(qty))
        if qty<=0:continue
        est=estimate_costs(qty,raw_price,side.lower(),costs);price=est.fill_price;notional=qty*price;comm=est.commission_usd
        if side=="BUY":
            if notional+comm>state.cash_usd and price>0:
                qty=max(0.,(state.cash_usd-comm)/price)
                if not costs.fractional_shares:qty=float(int(qty))
                if qty<=0:continue
                est=estimate_costs(qty,raw_price,side.lower(),costs);price=est.fill_price;notional=qty*price;comm=est.commission_usd
            state.cash_usd-=notional+comm
            old=state.positions.get(rec.ticker);oldq=old.quantity if old else 0.;state.positions[rec.ticker]=Position(rec.ticker,notional,oldq+qty,price)
        else:
            if held is None:continue
            qty=min(qty,held.quantity);notional=qty*price;state.cash_usd+=notional-comm;newq=held.quantity-qty
            if newq<=1e-8:state.positions.pop(rec.ticker,None)
            else:held.quantity=newq;held.market_value_usd=newq*price
        rows.append({"signal_timestamp":ts,"execution_timestamp":next_ts,"ticker":rec.ticker,"side":side,"quantity":qty,"price":price,"target_usd":target,"delta_usd":delta,"commission_usd":comm,"slippage_usd":est.slippage_usd,"other_fees_usd":est.other_fees_usd,"status":"SIMULATED_FILLED","reason":rec.reason,"notional_usd":notional,"in_market":bool(state.positions)})
        if model==ModelName.COMBINED and not state.alm_completed and side=="BUY":state.alm_completed=True;state.alm_fill_confirmed=True
    eqs=pd.Series(dict(equity),dtype=float).sort_index();trades=pd.DataFrame(rows)
    if not trades.empty:trades["gross_notional_usd"]=trades.notional_usd
    return BacktestResult(model,eqs,trades,compute_metrics(eqs,trades),warnings,{"commissions":float(trades.commission_usd.sum()) if not trades.empty else 0.,"slippage":float(trades.slippage_usd.sum()) if not trades.empty else 0.,"other_fees":float(trades.other_fees_usd.sum()) if not trades.empty else 0.},)
