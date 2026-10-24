from __future__ import annotations
import os
from ..config import CostConfig
from ..costs import preview_quantity
from ..models import OrderPreview
from .interface import BrokerAdapter
class IBKROrderAdapter(BrokerAdapter):
 def __init__(self,cost_config:CostConfig,fractional_allowed:bool=True,exchange:str="SMART"):self.cost_config=cost_config;self.fractional_allowed=fractional_allowed;self.exchange=exchange
 def preview_order(self,ticker:str,target_usd:float,current_usd:float,price:float)->OrderPreview:
  if not ticker or price<=0 or target_usd<0 or current_usd<0:raise ValueError("Neplatný ticker, cena nebo pozice.")
  from dataclasses import replace
  cfg=replace(self.cost_config,fractional_shares=self.fractional_allowed);side,qty,delta,est=preview_quantity(target_usd,current_usd,price,cfg);return OrderPreview(ticker,side,target_usd,delta,price,qty,max(0.,-delta-est.commission_usd),est.commission_usd,est.slippage_usd,exchange=self.exchange)
 def submit_order(self,preview:OrderPreview,confirmed_by_user:bool=False)->str:
  if os.getenv("ENABLE_ORDER_SUBMISSION","false").lower()!="true":return "BLOCKED: ENABLE_ORDER_SUBMISSION=false."
  if not confirmed_by_user:return "BLOCKED: vyžaduje uživatelské potvrzení."
  return "NOT_IMPLEMENTED: tato verze podporuje pouze order preview."
