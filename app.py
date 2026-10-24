from __future__ import annotations
from datetime import date, timedelta
import logging
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from src.config import APP_NAME, BASE_TICKERS, LEVERAGED_TICKERS, CostConfig, StrategyConfig
from src.data.yfinance_provider import YahooFinanceProvider
from src.models import ModelName, PortfolioState, Position, DataMode
from src.services.backtest_service import TICKERS, get_prices, run_model_backtest
from src.services.recommendation_service import recommend
from src.broker.ibkr_adapter import IBKROrderAdapter
from src.storage import Storage
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)
st.set_page_config(page_title=APP_NAME, page_icon="📈", layout="wide", initial_sidebar_state="expanded")
st.markdown("""<style>.block-container{max-width:1440px;padding-top:1.6rem}.drbl-card{padding:1.05rem 1.15rem;border:1px solid #e4e9ee;border-radius:14px;background:#fff}.muted{color:#667788;font-size:.88rem}.regime-a{color:#087f5b;font-weight:700}.regime-b{color:#b26a00;font-weight:700}.regime-c{color:#c92a2a;font-weight:700}</style>""", unsafe_allow_html=True)
st.title("📈 DRBL Matrix")
st.caption("Pravidlová analýza trhu · portfolio v USD · čas Europe/Prague")
st.warning("Model vytváří pravidlová doporučení a simulace, nikoli garanci výnosu. Objednávky se automaticky neposílají. Historické výsledky nejsou předpovědí budoucnosti.")
with st.sidebar:
    st.header("Nastavení relace")
    model_label = st.selectbox("Model", [m.value for m in ModelName], index=0)
    model = ModelName(model_label)
    section = st.radio("Sekce", ["Dashboard", "Denní doporučení", "Backtest", "Porovnání", "Nastavení"])
    initial_equity = st.number_input("Počáteční equity (USD)", min_value=100.0, value=100_000.0, step=5_000.0)
    start = st.date_input("Začátek historie", value=date.today() - timedelta(days=1500), max_value=date.today())
    end = st.date_input("Konec historie", value=date.today(), min_value=start, max_value=date.today())
    gld_lev = st.text_input("Pákový ticker GLD (povinný pro režim A)", value="").strip().upper() or None
    st.divider()
    slippage = st.select_slider("Slippage na stranu (bps)", options=[0, 5, 10, 25], value=10)
    commission = st.number_input("Komise za akcii (USD)", min_value=0.0, value=0.0035, format="%.4f")
    minimum = st.number_input("Minimum za pokyn (USD)", min_value=0.0, value=0.35, format="%.2f")
    fractional = st.checkbox("Povolit zlomkové kusy v simulaci", value=True)
    load_button = st.button("Načíst / obnovit historická data", type="primary", use_container_width=True)

strategy = StrategyConfig(initial_equity=initial_equity, gld_leveraged_ticker=gld_lev)
cost_config = CostConfig(commission_per_share=commission, minimum_per_order=minimum, slippage_bps_per_side=float(slippage), fractional_shares=fractional)
if "portfolio_states" not in st.session_state:
    st.session_state.portfolio_states = {m.value: PortfolioState(m, initial_equity) for m in ModelName}
if "prices" not in st.session_state:
    st.session_state.prices = {}
if "data_messages" not in st.session_state:
    st.session_state.data_messages = []
if load_button or not st.session_state.prices:
    with st.spinner("Načítám denní historická data přes Yahoo Finance…"):
        provider = YahooFinanceProvider()
        prices = {}
        msgs = []
        for ticker in TICKERS:
            try:
                result = provider.get_daily(ticker, start.isoformat(), (end + timedelta(days=1)).isoformat())
                prices[ticker] = result.bars
                msgs.append(f"{ticker}: {len(result.bars)} barů, poslední {result.last_timestamp}, HISTORICAL")
            except Exception as exc:
                log.warning("Data %s nejsou dostupná: %s", ticker, exc)
                msgs.append(f"{ticker}: nedostupné ({exc})")
        st.session_state.prices = prices
        st.session_state.data_messages = msgs
prices = st.session_state.prices
state = st.session_state.portfolio_states[model.value]
# UI changes affect only selected model's state.
if abs(state.cash_usd + sum(p.market_value_usd for p in state.positions.values()) - initial_equity) > 1e-6 and not state.positions:
    state.cash_usd = initial_equity

def get_recommendation(selected_model: ModelName):
    current_state = st.session_state.portfolio_states[selected_model.value]
    latest = max((f.index[-1].to_pydatetime() for f in prices.values() if not f.empty), default=None)
    return recommend(selected_model, prices, current_state, strategy, cost_config, latest_timestamp=latest, gld_leveraged_ticker=gld_lev)

def show_recommendation(rec):
    st.subheader("Doporučená změna")
    if not rec.available:
        st.error(f"Doporučení nedostupné: {rec.reason}")
        return
    if rec.action == "HOLD": st.info(rec.reason)
    elif rec.action in {"REVIEW", "CONFIGURATION_REQUIRED", "UNAVAILABLE"}: st.warning(rec.reason)
    else: st.write(rec.reason)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Akce", rec.action)
    c2.metric("Ticker", rec.ticker or "—")
    c3.metric("Cílová pozice", f"${rec.target_usd:,.2f}")
    c4.metric("Rozdíl vůči stávající", f"${rec.delta_usd:+,.2f}")
    st.caption(f"Zdroj: {rec.source} · režim dat: {rec.data_mode.value} · timestamp posledních dat: {rec.as_of} · {'PŘEDBĚŽNÉ' if rec.provisional else 'historické/finální bary'}")
    st.write(f"Odhad komise: **${rec.estimated_commission_usd:.2f}** · slippage: **${rec.estimated_slippage_usd:.2f}**")
    if rec.ticker:
        available_ticker = rec.ticker in prices
        px = float(prices[rec.ticker].Close.iloc[-1]) if available_ticker and not prices[rec.ticker].empty else None
        if px:
            adapter = IBKROrderAdapter(cost_config, fractional_allowed=fractional)
            current = sum(p.market_value_usd for p in state.positions.values() if p.ticker == rec.ticker)
            preview = adapter.preview_order(rec.ticker, rec.target_usd, current, px)
            st.write("**Order preview – pouze návrh, bez odeslání**")
            st.dataframe(pd.DataFrame([{"Ticker":preview.ticker,"Strana":preview.side,"Target USD":preview.target_usd,"Delta USD":preview.delta_usd,"Cena":preview.estimated_price,"Odhad kusů":preview.estimated_quantity,"Komise USD":preview.commission_usd,"Slippage USD":preview.slippage_usd,"Stav":preview.status}]),use_container_width=True,hide_index=True)
            if st.button("Uložit order preview", key=f"save-{model.value}"):
                try: Storage().save_order_preview(preview.__dict__); st.success("Návrh uložen do lokální SQLite databáze.")
                except Exception as exc: st.error(f"Návrh se nepodařilo uložit: {exc}")
        else: st.info("Pro odhad počtu kusů chybí historická cena konkrétního tickeru.")
    if rec.indicators:
        with st.expander("Indikátory a stav warm-upu"):
            st.json(rec.indicators)

if section == "Dashboard":
    st.subheader("Dashboard")
    rec = get_recommendation(model)
    equity = state.equity_usd
    cash_pct = state.cash_usd/equity*100 if equity else 0
    a,b,c,d = st.columns(4)
    a.metric("Equity", f"${equity:,.2f}")
    b.metric("Hotovost", f"${state.cash_usd:,.2f}", f"{cash_pct:.1f}% equity")
    c.metric("Aktivum", state.selected_asset or "—")
    d.metric("Režim", state.current_regime.value)
    st.write("**Model:**", model.value, "· **Stav ALM fillu:**", "potvrzen" if state.alm_fill_confirmed else "nepotvrzen")
    show_recommendation(rec)
    if prices and any(not x.empty for x in prices.values()):
        ticker = st.selectbox("Cenový graf", [x for x in ["SPY","QQQ","GLD","IBIT"] if x in prices and not prices[x].empty])
        frame=prices[ticker].tail(250); fig=go.Figure(go.Candlestick(x=frame.index,open=frame.Open,high=frame.High,low=frame.Low,close=frame.Close,name=ticker));fig.update_layout(height=450,xaxis_rangeslider_visible=False,margin=dict(l=10,r=10,t=20,b=10));st.plotly_chart(fig,use_container_width=True)
elif section == "Denní doporučení":
    st.subheader("Denní doporučení")
    rec = get_recommendation(model); show_recommendation(rec)
    rows=[]
    for ticker, frame in prices.items():
        if frame.empty: continue
        rows.append({"Ticker":ticker,"Poslední close":float(frame.Close.iloc[-1]),"Poslední timestamp":str(frame.index[-1]),"Počet barů":len(frame),"Zdroj":"Yahoo Finance","Typ":"HISTORICAL"})
    if rows: st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    st.caption("Provisional pre-close není zde aktivován: vyžaduje ověřený IBKR live stream a správný typ market-data feedu.")
elif section == "Backtest":
    st.subheader("Backtest")
    models_to_run = [model] if model != ModelName.COMBINED else [ModelName.ALM,ModelName.DRBL_MATRIX,ModelName.COMBINED]
    if st.button("Spustit backtest", type="primary"):
        if not prices: st.error("Nejsou dostupná data.")
        else:
            results={}
            with st.spinner("Simuluji obchody s exekucí nejdříve na Open dalšího baru…"):
                for m in models_to_run:
                    try: results[m.value] = run_model_backtest(prices,m,strategy,cost_config,start.isoformat(),end.isoformat())
                    except Exception as exc: log.exception("Backtest %s failed",m.value);st.error(f"{m.value}: {exc}")
            st.session_state.backtest_results=results
    results=st.session_state.get("backtest_results",{})
    for name,result in results.items():
        st.markdown(f"### {name}")
        met=result.metrics
        cols=st.columns(5);cols[0].metric("Celkový výnos",f"{met['total_return']:.2%}" if pd.notna(met['total_return']) else "n/a");cols[1].metric("Anualizovaný výnos",f"{met['annualized_return']:.2%}" if pd.notna(met['annualized_return']) else "n/a");cols[2].metric("Sharpe",f"{met['sharpe']:.2f}" if pd.notna(met['sharpe']) else "n/a");cols[3].metric("Max drawdown",f"{met['max_drawdown']:.2%}" if pd.notna(met['max_drawdown']) else "n/a");cols[4].metric("Počet obchodů",int(met['trades']))
        fig=go.Figure();fig.add_trace(go.Scatter(x=result.equity.index,y=result.equity.values,name="Equity",mode="lines"));fig.update_layout(height=340,xaxis_title="Datum",yaxis_title="USD",margin=dict(l=10,r=10,t=20,b=10));st.plotly_chart(fig,use_container_width=True)
        if not result.trades.empty:st.dataframe(result.trades,use_container_width=True,hide_index=True)
        st.write(f"Komise ${result.costs['commissions']:,.2f} · slippage ${result.costs['slippage']:,.2f} · další poplatky ${result.costs['other_fees']:,.2f}")
        if result.warnings: st.warning("\n".join(result.warnings[:10]))
elif section == "Porovnání":
    st.subheader("Porovnání modelů")
    if st.button("Porovnat všechny modely", type="primary"):
        results={}
        with st.spinner("Používám shodné vstupní období, kapitál a nákladové předpoklady…"):
            for m in ModelName:
                try:results[m.value]=run_model_backtest(prices,m,strategy,cost_config,start.isoformat(),end.isoformat())
                except Exception as exc:log.exception("Comparison failed");st.error(f"{m.value}: {exc}")
        st.session_state.comparison_results=results
    results=st.session_state.get("comparison_results",{})
    if results:
        table=[]
        fig=go.Figure()
        for name,result in results.items():
            table.append({"Model":name,"Výnos":result.metrics["total_return"],"Anualizovaný výnos":result.metrics["annualized_return"],"Volatilita":result.metrics["volatility"],"Sharpe":result.metrics["sharpe"],"Max drawdown":result.metrics["max_drawdown"],"Calmar":result.metrics["calmar"],"Obchody":result.metrics["trades"],"Komise USD":result.costs["commissions"],"Slippage USD":result.costs["slippage"]})
            fig.add_trace(go.Scatter(x=result.equity.index,y=result.equity.values,name=name,mode="lines"))
        st.dataframe(pd.DataFrame(table),use_container_width=True,hide_index=True);fig.update_layout(height=450,yaxis_title="Equity USD");st.plotly_chart(fig,use_container_width=True)
        st.info("Benchmark Buy & Hold SPY/QQQ a dividendově korigované výnosy musí být před produkčním použitím ověřeny samostatně; tento prototyp je nepředstírá jako vypočtené.")
else:
    st.subheader("Nastavení")
    st.write("**Datový provider:** Yahoo Finance – historické denní bary, nejde o live feed.")
    st.write("**Základní tickery:**", BASE_TICKERS)
    st.write("**Pákové tickery:**", {**LEVERAGED_TICKERS,"GLD":gld_lev})
    st.write("**Nákladový profil:**", cost_config.profile)
    st.write(f"Komise ${cost_config.commission_per_share:.4f}/akcii · minimum ${cost_config.minimum_per_order:.2f}/pokyn · slippage {cost_config.slippage_bps_per_side:.0f} bps/stranu · úrok hotovosti {cost_config.cash_interest_annual:.2%}.")
    st.write("**Časové zóny:** UI Europe/Prague; burza America/New_York.")
    st.write("**IBKR:** read-only konfigurace přes `.env`; adapter je order-preview-only. Odeslání příkazů je blokováno feature flagem `ENABLE_ORDER_SUBMISSION=false`.")
    st.write("**Režimy:** Paper/live nepřepíná aplikace automaticky. Ověřte předplatné dat a nastavení broker kontraktu ručně.")
    with st.expander("Stav načtených dat"):
        for line in st.session_state.data_messages: st.write("• "+line)
