from __future__ import annotations
import math
import numpy as np
import pandas as pd
def compute_metrics(equity:pd.Series,trades:pd.DataFrame|None=None,periods_per_year:int=252)->dict:
 if equity is None or equity.empty:return {"total_return":np.nan,"annualized_return":np.nan,"volatility":np.nan,"sharpe":np.nan,"max_drawdown":np.nan,"calmar":np.nan,"trades":0,"turnover":0.,"time_in_market":0.,"commissions":0.,"slippage":0.}
 ret=equity.pct_change().dropna();total=float(equity.iloc[-1]/equity.iloc[0]-1);n=max(len(equity)-1,1);annual=float((equity.iloc[-1]/equity.iloc[0])**(periods_per_year/n)-1) if equity.iloc[-1]>0 and equity.iloc[0]>0 else np.nan;vol=float(ret.std(ddof=1)*math.sqrt(periods_per_year)) if len(ret)>1 else np.nan;sharpe=float(ret.mean()/ret.std(ddof=1)*math.sqrt(periods_per_year)) if len(ret)>1 and ret.std(ddof=1)>0 else np.nan;dd=equity/equity.cummax()-1;maxdd=float(abs(dd.min()));calmar=annual/maxdd if maxdd>0 and np.isfinite(annual) else np.nan;t=trades if trades is not None else pd.DataFrame()
 return {"total_return":total,"annualized_return":annual,"volatility":vol,"sharpe":sharpe,"max_drawdown":maxdd,"calmar":calmar,"trades":len(t),"turnover":float(t.notional_usd.sum()/equity.mean()) if not t.empty and "notional_usd" in t else 0.,"time_in_market":float(t.in_market.mean()) if not t.empty and "in_market" in t else 0.,"commissions":float(t.commission_usd.sum()) if not t.empty and "commission_usd" in t else 0.,"slippage":float(t.slippage_usd.sum()) if not t.empty and "slippage_usd" in t else 0.}
def monthly_returns(equity:pd.Series)->pd.DataFrame:
 return equity.resample("ME").last().pct_change().to_frame("return").dropna() if not equity.empty else pd.DataFrame()
