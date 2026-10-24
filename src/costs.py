from __future__ import annotations
from dataclasses import dataclass
from .config import CostConfig
@dataclass(frozen=True)
class CostEstimate:
 commission_usd:float; slippage_usd:float; other_fees_usd:float; fill_price:float
def estimate_costs(quantity:float,price:float,side:str,config:CostConfig)->CostEstimate:
 if quantity<0 or price<=0: raise ValueError("Množství musí být nezáporné a cena kladná.")
 if side.lower() not in {"buy","sell"}: raise ValueError("Strana musí být buy nebo sell.")
 if quantity==0:return CostEstimate(0,0,0,price)
 commission=max(config.minimum_per_order,quantity*config.commission_per_share); other=quantity*config.additional_fee_per_share; slip_factor=config.slippage_bps_per_side/10000; slip=quantity*price*slip_factor; fill=price*(1+slip_factor if side.lower()=="buy" else 1-slip_factor)
 return CostEstimate(commission,slip,other,fill)
def preview_quantity(target_usd:float,current_usd:float,price:float,config:CostConfig):
 delta=target_usd-current_usd; side="buy" if delta>0.005 else "sell" if delta<-.005 else "hold"; qty=abs(delta)/price if price>0 else 0
 if not config.fractional_shares: qty=float(int(qty))
 est=estimate_costs(qty,price,side if side!="hold" else "buy",config);return side.upper(),qty,delta,est
