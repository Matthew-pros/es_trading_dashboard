from __future__ import annotations
import math
import numpy as np
import pandas as pd
REQUIRED_OHLCV=("Open","High","Low","Close","Volume")
def normalize_ohlcv(data:pd.DataFrame)->pd.DataFrame:
 if data is None or data.empty:raise ValueError("Poskytovatel vrátil prázdná data.")
 df=data.copy()
 if isinstance(df.columns,pd.MultiIndex):df.columns=[str(c[0] if c[0] in REQUIRED_OHLCV else c[-1]) for c in df.columns]
 df.columns=[str(c).strip().title() for c in df.columns]
 missing=set(REQUIRED_OHLCV)-set(df.columns)
 if missing:raise ValueError("Chybí sloupce OHLCV: "+", ".join(sorted(missing)))
 idx=pd.to_datetime(df.index,errors="coerce"); valid=~idx.isna();df=df.loc[valid].copy();idx=idx[valid]
 if getattr(idx,"tz",None) is not None:idx=idx.tz_convert("America/New_York").tz_localize(None)
 df.index=idx;df=df[~df.index.duplicated(keep="last")].sort_index()
 for c in REQUIRED_OHLCV:df[c]=pd.to_numeric(df[c],errors="coerce")
 df=df.dropna(subset=["Open","High","Low","Close"]); positive=(df[list(REQUIRED_OHLCV[:4])]>0).all(axis=1); coherent=(df.High>=df[["Open","Close","Low"]].max(axis=1))&(df.Low<=df[["Open","Close","High"]].min(axis=1));df=df.loc[positive&coherent];df.loc[df.Volume<0,"Volume"]=np.nan
 return df
def rolling_drawdown(close:pd.Series)->pd.Series:
 peak=close.cummax();return (peak-close)/peak
def momentum_12_1(close:pd.Series)->pd.Series:return (close.shift(22)-close.shift(252))/close.shift(252)
def annualized_volatility(close:pd.Series,window:int=60)->pd.Series:return close.pct_change(fill_method=None).rolling(window,min_periods=window).std(ddof=1)*math.sqrt(252)
def momentum_score(close:pd.Series)->pd.Series:
 mom=momentum_12_1(close);vol=annualized_volatility(close);return (mom/vol).where(vol.notna()&(vol>0))
def breakout_factors(data:pd.DataFrame,entry_lookback:int=40,exit_lookback:int=20)->pd.DataFrame:
 df=data.copy();df["entry_level"]=df.High.shift(1).rolling(entry_lookback,min_periods=entry_lookback).max();df["exit_level"]=df.Low.shift(1).rolling(exit_lookback,min_periods=exit_lookback).min();df["entry"]=df.Close>=df.entry_level;df["exit"]=df.Close<=df.exit_level;df.loc[df.entry_level.isna(),"entry"]=False;df.loc[df.exit_level.isna(),"exit"]=False;return df
def regression_factors(close:pd.Series,period:int=100)->pd.DataFrame:
 slope=pd.Series(np.nan,index=close.index,dtype=float);upper=pd.Series(np.nan,index=close.index,dtype=float)
 for i in range(period-1,len(close)):
  values=close.iloc[i-period+1:i+1].to_numpy(dtype=float)
  if not np.isfinite(values).all():continue
  x=np.arange(period,dtype=float);slope.iloc[i]=np.polyfit(x,values,1)[0];upper.iloc[i]=values.mean()+2*values.std(ddof=0)
 return pd.DataFrame({"slope":slope,"upper_band":upper,"entry":(slope>0)&(close>upper),"exit":slope<0},index=close.index)
def rvol(volume:pd.Series,short:int=20,long:int=200)->pd.Series:
 num=volume.rolling(short,min_periods=short).mean();den=volume.rolling(long,min_periods=long).mean();return (num/den).where(den>0)
def adx_wilder(data:pd.DataFrame,period:int=14)->pd.Series:
 high=data.High.astype(float);low=data.Low.astype(float);close=data.Close.astype(float);prev=close.shift(1);tr=pd.concat([high-low,(high-prev).abs(),(low-prev).abs()],axis=1).max(axis=1);up=high.diff();down=-low.diff();pdm=pd.Series(np.where((up>down)&(up>0),up,0.),index=data.index);mdm=pd.Series(np.where((down>up)&(down>0),down,0.),index=data.index);tr.iloc[:1]=np.nan;pdm.iloc[:1]=np.nan;mdm.iloc[:1]=np.nan
 ts=pd.Series(np.nan,index=data.index);ps=ts.copy();ms=ts.copy()
 if len(data)<=period:return pd.Series(np.nan,index=data.index,name="ADX")
 ts.iloc[period]=tr.iloc[1:period+1].sum(min_count=period);ps.iloc[period]=pdm.iloc[1:period+1].sum(min_count=period);ms.iloc[period]=mdm.iloc[1:period+1].sum(min_count=period)
 for i in range(period+1,len(data)):ts.iloc[i]=ts.iloc[i-1]-ts.iloc[i-1]/period+tr.iloc[i];ps.iloc[i]=ps.iloc[i-1]-ps.iloc[i-1]/period+pdm.iloc[i];ms.iloc[i]=ms.iloc[i-1]-ms.iloc[i-1]/period+mdm.iloc[i]
 plus=100*ps/ts.replace(0,np.nan);minus=100*ms/ts.replace(0,np.nan);den=(plus+minus).replace(0,np.nan);dx=100*(plus-minus).abs()/den;adx=pd.Series(np.nan,index=data.index,dtype=float,name="ADX");first=2*period-1
 if len(data)>first:
  adx.iloc[first]=dx.iloc[period:first+1].mean()
  for i in range(first+1,len(data)):adx.iloc[i]=(adx.iloc[i-1]*(period-1)+dx.iloc[i])/period
 return adx
