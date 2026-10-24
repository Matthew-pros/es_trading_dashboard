# DRBL Matrix – česká investiční analýza

Streamlit aplikace oddělující tři modely: **ALM**, **DRBL Matrix** a **Combined**. Portfolio a návrhy pozic jsou v USD, UI pracuje s časovou zónou `Europe/Prague` a obchodní hodiny se počítají v `America/New_York`.

> Upozornění: jde o pravidlové analytické a simulační nástroje, nikoli investiční poradenství ani garanci výnosu. Výsledky závisí na kvalitě zdrojových dat, předpokladech nákladů, corporate actions a modelu exekuce. Tato verze nepodporuje automatické odesílání objednávek.

## Instalace a spuštění

Vyžaduje Python 3.11 nebo novější.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e '.[dev]'
streamlit run app.py
```

Windows PowerShell: `.venv\\Scripts\\Activate.ps1`. Aplikace stahuje historické denní OHLCV přes Yahoo Finance a nikdy tento zdroj neoznačuje jako live.

## Modely

- **ALM** začíná pouze v hotovosti, sleduje drawdown SPY/QQQ a navrhuje tranši 15 % equity při poklesu alespoň 30 % nebo 20 % při alespoň 50 %. Rezerva hotovosti je nejméně 15 %.
- **DRBL Matrix** obsahuje momentové skóre, rotaci, breakout/regresní faktory, Wilder ADX a relativní objem.
- **Combined** zahájí provozní fázi až po potvrzeném ALM fillu. Order preview sám o sobě stav nemění.

Momentum je počítáno dle definice `(Close[t-22]-Close[t-252])/Close[t-252]`, skóre jako momentum dělené anualizovanou sample volatilitou 60 denních výnosů. Hysterese rotace je definována jako `incumbent_score + abs(incumbent_score)*0.08`.

## Náklady a exekuce

Komise, minimum na pokyn, další poplatky a slippage v bps na stranu jsou nastavitelné. Výchozí 0,0035 USD/akcii, minimum 0,35 USD a 10 bps slippage jsou pouze modelové předpoklady, nikoli garantovaný ceník. Signál vzniká po denním Close a simulační exekuce se provádí nejdříve na Open následujícího dostupného baru. Cash interest je 0 %.

## IBKR

IBKR provider je read-only a vyžaduje volitelný `ib_async`, TWS/IB Gateway a market-data subscription. Konfigurace je v `.env.example`. Skutečná credentials ani `secrets.toml` nepatří do Git historie. Tato verze příkazy neodesílá; adaptér vrací pouze order preview.

## Omezení

- Chybějící indikátory nejsou doplňovány odhadem.
- Backtest je prototyp; před reálným použitím je nutný audit exekuce, corporate actions, historických tickerů, kalendáře, dividend a broker kontraktů.
- Pákový ticker pro GLD musí uživatel zvolit výslovně; IBIT se nepákuje.
- Cache, databáze, exporty a `.env` ignoruje `.gitignore`.

## Kontroly

```bash
pytest -q
ruff check src app.py tests
mypy src
```
