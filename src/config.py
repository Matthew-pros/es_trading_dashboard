from __future__ import annotations
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo
APP_NAME = "DRBL Matrix"
PORTFOLIO_CURRENCY = "USD"
UI_TIMEZONE = ZoneInfo("Europe/Prague")
EXCHANGE_TIMEZONE = ZoneInfo("America/New_York")
BASE_TICKERS = {"SPY":"SPY","QQQ":"QQQ","GLD":"GLD","IBIT":"IBIT"}
LEVERAGED_TICKERS = {"SPY":"UPRO","QQQ":"TQQQ","GLD":None,"IBIT":None}
@dataclass(frozen=True)
class CostConfig:
    profile:str="IBKR Pro Tiered – odhad"
    commission_per_share:float=0.0035
    minimum_per_order:float=0.35
    additional_fee_per_share:float=0.0
    slippage_bps_per_side:float=10.0
    fractional_shares:bool=True
    cash_interest_annual:float=0.0
    def __post_init__(self):
        if min(self.commission_per_share,self.minimum_per_order,self.additional_fee_per_share,self.slippage_bps_per_side)<0: raise ValueError("Náklady nemohou být záporné.")
        if self.cash_interest_annual<0: raise ValueError("Úrok hotovosti nemůže být záporný.")
@dataclass(frozen=True)
class StrategyConfig:
    initial_equity:float=100_000.0
    alm_cash_reserve:float=0.15
    alm_mid_drawdown:float=0.30
    alm_deep_drawdown:float=0.50
    alm_mid_fraction:float=0.15
    alm_deep_fraction:float=0.20
    matrix_target_fraction:float=0.85
    rotation_hysteresis:float=0.08
    adx_period:int=14
    breakout_entry_lookback:int=40
    breakout_exit_lookback:int=20
    regression_period:int=100
    rvol_short:int=20
    rvol_long:int=200
    ticker_mapping:dict=field(default_factory=lambda:dict(BASE_TICKERS))
    leveraged_mapping:dict=field(default_factory=lambda:dict(LEVERAGED_TICKERS))
    gld_leveraged_ticker:str|None=None
    def __post_init__(self):
        if self.initial_equity<=0: raise ValueError("Počáteční equity musí být kladná.")
        if not 0<=self.alm_cash_reserve<1: raise ValueError("Hotovostní rezerva musí být v intervalu [0, 1).")
        if not 0<self.matrix_target_fraction<=1: raise ValueError("Cílová alokace musí být v intervalu (0, 1].")
