from __future__ import annotations
from .models import PortfolioState,Position
def mark_to_market(state:PortfolioState,prices:dict[str,float])->PortfolioState:
 for ticker,pos in list(state.positions.items()):
  if ticker in prices and prices[ticker]>0: pos.market_value_usd=pos.quantity*prices[ticker] if pos.quantity else pos.market_value_usd
  if pos.market_value_usd<=0:state.positions.pop(ticker,None)
 return state
def target_delta(state:PortfolioState,ticker:str,target_usd:float)->float:
 p=state.positions.get(ticker);return target_usd-(p.market_value_usd if p else 0.)
def apply_confirmed_fill(state:PortfolioState,ticker:str,target_usd:float,quantity:float,price:float,side:str,commission:float=0.):
 notional=quantity*price
 if side.upper()=="BUY":
  if notional+commission>state.cash_usd+1e-6:raise ValueError("Nedostatek hotovosti pro potvrzený nákup.")
  state.cash_usd-=notional+commission
 elif side.upper()=="SELL":state.cash_usd+=notional-commission
 else:raise ValueError("Neznámá strana obchodu.")
 ex=state.positions.get(ticker);newv=max(0.,target_usd)
 if newv<=.005:state.positions.pop(ticker,None)
 else:
  q=(ex.quantity if ex else 0.)+(quantity if side.upper()=="BUY" else -quantity);state.positions[ticker]=Position(ticker,newv,max(0.,q),price)
 if state.model.value=="Combined" and not state.alm_completed and side.upper()=="BUY" and target_usd>0:state.alm_completed=True;state.alm_fill_confirmed=True
