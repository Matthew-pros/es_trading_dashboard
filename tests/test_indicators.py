import numpy as np
import pandas as pd
import pytest
from src.indicators import adx_wilder,annualized_volatility,breakout_factors,momentum_12_1,momentum_score,normalize_ohlcv,regression_factors,rvol

def test_momentum_formula_12_1():
    close=pd.Series(np.arange(1,301,dtype=float))
    got=momentum_12_1(close).iloc[-1]
    assert got==pytest.approx((close.iloc[-23]-close.iloc[-253])/close.iloc[-253])

def test_volatility_uses_sample_std():
    close=pd.Series(np.exp(np.cumsum(np.random.default_rng(8).normal(0,.01,100))))
    expected=close.pct_change(fill_method=None).iloc[-60:].std(ddof=1)*np.sqrt(252)
    assert annualized_volatility(close).iloc[-1]==pytest.approx(expected)

def test_rotation_score_missing_when_vol_zero():
    assert pd.isna(momentum_score(pd.Series([100.]*300)).iloc[-1])

def test_breakout_excludes_current_bar(sample_ohlcv):
    f=sample_ohlcv.copy();res=breakout_factors(f,40,20)
    idx=f.index[100]
    assert res.loc[idx,"entry_level"]==pytest.approx(f.High.iloc[60:100].max())
    f.loc[idx,"High"]*=10
    assert breakout_factors(f,40,20).loc[idx,"entry_level"]==pytest.approx(res.loc[idx,"entry_level"])

def test_regression_band_uses_population_std():
    close=pd.Series(np.linspace(10,20,120))
    frame=regression_factors(close,100)
    expected=close.iloc[-100:].mean()+2*close.iloc[-100:].std(ddof=0)
    assert frame.upper_band.iloc[-1]==pytest.approx(expected)

def test_adx_wilder_has_warmup():
    f=pd.DataFrame({"High":np.arange(1.,100.),"Low":np.arange(.5,99.5),"Close":np.arange(.75,99.75)})
    adx=adx_wilder(f,14)
    assert adx.iloc[:26].isna().all()
    assert pd.notna(adx.iloc[27])

def test_rvol_requires_full_windows():
    vol=pd.Series(np.ones(199))
    assert pd.isna(rvol(vol).iloc[-1])

def test_normalize_rejects_bad_prices(sample_ohlcv):
    f=sample_ohlcv.copy();f.iloc[5,f.columns.get_loc("Close")]=-1
    cleaned=normalize_ohlcv(f)
    assert f.index[5] not in cleaned.index
