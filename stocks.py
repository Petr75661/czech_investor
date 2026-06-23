import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import yfinance as yf
import json
import os
from datetime import datetime, timedelta, date
import time
import threading
import math
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter
import requests
from bs4 import BeautifulSoup
import sys
import numpy as np
import multiprocessing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
import webbrowser
import base64
import urllib.parse
import pdfplumber
import io
import concurrent.futures
from yahooquery import Ticker as YQTicker
import csv

# ==============================================================================
# KONFIGURACE A DATABÁZE APLIKACE
# ==============================================================================

PORTFOLIO_FILE = "portfolio_ledger.json"

# Konstanty pro optimalizaci poplatků (IBKR Tiered Minimums)
IBKR_MIN_FEE_USD = 0.35
IBKR_MIN_FEE_GBP = 1.00
DEFAULT_FEE_PERCENT = 0.5

# Výchozí cílové váhy (TARGETS)
# Reprezentují ideální rozložení kapitálu. Tyto hodnoty jsou v paměti přepsány,
# pokud má uživatel uložené vlastní váhy v JSON souboru.
# Výchozí cílové váhy (TARGETS)
TARGETS = {
    "LGEN.L": 0.06,     # Legal & General - High Yield
    "ULVR.L": 0.035,    # Unilever - Defensive Staples
    "TRIG.L": 0.08,     # Renewables Infrastructure - Income
    "JNJ":    0.04,     # Johnson & Johnson - Core Healthcare
    "NEE":    0.04,     # NextEra - Green Utility Growth
    "PEP":    0.042,    # PepsiCo - Resilient Staples
    "CAT":    0.025,    # Industrial/Cyclical Growth
    "TT":     0.025,    # Trane Technologies - Industrials
    "ETN":    0.024,    # Eaton Corporation - Industrials
    "AAPL":   0.05,     # Technology/Quality Growth
    "O":      0.042,    # Realty Income
    "ABBV":   0.053,    # Farmaceutický gigant
    "MAIN":   0.039,    # BDC
    "HTGC":   0.035,    # BDC
    "ARCC":   0.039,    # BDC
    "TRIN":   0.039,    # Trinity Capital - BDC
    "FDUS":   0.039,    # Fidus Investment - BDC
    "OHI":    0.035,    # Zdravotnický REIT
    "SBRA":   0.035,    # Sabra Health Care - REIT
    "AVGO":   0.073,    # Broadcom
    "MU":     0.025,    # Micron Technology
    "MRK":    0.04,     # Merck - biotechnologie
    "LLY":    0.06,     # Eli Lilly
    "PWR":    0.025     # Quanta - power utility
}

# Měny jednotlivých titulů pro správný výpočet FX (převodů měn)
CURRENCIES = {
    "LGEN.L": "GBP", "ULVR.L": "GBP", "TRIG.L": "GBP", 
    "JNJ": "USD", "NEE": "USD", "PEP": "USD", "CAT": "USD", "AAPL": "USD",
    "O": "USD", "ABBV": "USD", "MAIN": "USD", "HTGC": "USD", "ARCC": "USD", 
    "OHI": "USD", "AVGO": "USD", "MRK": "USD", "LLY": "USD", "PWR": "USD",
    "TT": "USD", "ETN": "USD", "MU": "USD", "FDUS": "USD", "TRIN": "USD", "SBRA": "USD"
}

# Pravidla pro hodnocení "zdraví" portfolia (použito v Editoru akcií)
# --- KONFIGURACE ZDRAVÍ PORTFOLIA ---
LIMITS = {
    "MAX_SINGLE_WEIGHT": 0.15,   
    "MAX_SECTOR_WEIGHT": 0.35,   
    "MAX_RATE_SENSITIVE_WEIGHT": 0.30, # Max podíl firem citlivých na sazby (REIT, BDC, Utility)
    "MIN_POSITIONS": 8,
    "MAX_POSITIONS": 40,
    "MIN_GROWTH_RATIO": 0.25,     
    "MIN_YIELD_RATIO": 0.40
}

# Etické a rizikové štítky pro filtrování akcií v Editoru
TAGS = {
    "CASINO": "Kasina a Hazard",
    "FOSSIL": "Fosilní paliva",
    "WEAPONS": "Zbraně a Obrana",
    "TOBACCO": "Tabákový průmysl",
    "AI_BUBBLE": "AI Bubble Risk"
}

# Master databáze (Universe) dostupných akcií
# Pokud JSON soubor neexistuje, aplikace zkopíruje data z této šablony.
DEFAULT_STOCK_DB = {
    # -- TECHNOLOGIE & RŮST --
    "AAPL":   {"name": "Apple Inc.", "sector": "Technology", "tags":[], "yield": 0.5, "growth": 35.0},
    "MSFT":   {"name": "Microsoft Corp.", "sector": "Technology", "tags": ["AI_BUBBLE"], "yield": 0.7, "growth": 45.0},
    "AVGO":   {"name": "Broadcom Inc.", "sector": "Technology", "tags": ["AI_BUBBLE"], "yield": 1.4, "growth": 110.0},
    "TXN":    {"name": "Texas Instruments", "sector": "Technology", "tags":[], "yield": 2.8, "growth": 15.0},
    "NVDA":   {"name": "NVIDIA Corp.", "sector": "Technology", "tags": ["AI_BUBBLE"], "yield": 0.03, "growth": 250.0},
    "GOOGL":  {"name": "Alphabet Inc.", "sector": "Technology", "tags": ["AI_BUBBLE"], "yield": 0.0, "growth": 40.0},
    "TT":     {"name": "Trane Technologies plc", "sector": "Industrial", "tags": [], "yield": 0.86, "growth": 64.0},
    "ETN":    {"name": "Eaton Corporation", "sector": "Industrial", "tags": [], "yield": 1.04, "growth": 31.3},
    "MU":     {"name": "Micron Technology", "sector": "Technology", "tags": ["AI_BUBBLE"], "yield": 0.11, "growth": 374.7},
    
    # -- ZDRAVOTNICTVÍ --
    "JNJ":    {"name": "Johnson & Johnson", "sector": "Healthcare", "tags":[], "yield": 3.0, "growth": -5.0},
    "ABBV":   {"name": "AbbVie Inc.", "sector": "Healthcare", "tags":[], "yield": 3.6, "growth": 25.0},
    "PFE":    {"name": "Pfizer Inc.", "sector": "Healthcare", "tags":[], "yield": 6.0, "growth": -35.0},
    "MRK":    {"name": "Merck & Co.", "sector": "Healthcare", "tags":[], "yield": 2.5, "growth": 20.0},
    "LLY":    {"name": "Eli Lilly and Co.", "sector": "Healthcare", "tags":[], "yield": 0.6, "growth": 85.0},

    # -- SPOTŘEBNÍ ZBOŽÍ (DEFENZIVA) --
    "PEP":    {"name": "PepsiCo, Inc.", "sector": "Consumer Defensive", "tags":[], "yield": 3.1, "growth": -2.0},
    "KO":     {"name": "Coca-Cola Co.", "sector": "Consumer Defensive", "tags":[], "yield": 3.2, "growth": 5.0},
    "PG":     {"name": "Procter & Gamble", "sector": "Consumer Defensive", "tags":[], "yield": 2.4, "growth": 12.0},
    "ULVR.L": {"name": "Unilever PLC", "sector": "Consumer Defensive", "tags":[], "yield": 3.8, "growth": 8.0},
    "BATS.L": {"name": "British American Tobacco", "sector": "Consumer Defensive", "tags": ["TOBACCO"], "yield": 9.5, "growth": -10.0},
    "MO":     {"name": "Altria Group", "sector": "Consumer Defensive", "tags": ["TOBACCO"], "yield": 9.2, "growth": 5.0},

    # -- FINANCE & BDC (VÝNOS) --
    "MAIN":   {"name": "Main Street Capital", "sector": "Financial", "tags":[], "yield": 6.2, "growth": 18.0},
    "HTGC":   {"name": "Hercules Capital", "sector": "Financial", "tags":[], "yield": 10.5, "growth": 12.0},
    "ARCC":   {"name": "Ares Capital Corporation", "sector": "Financial", "tags":[], "yield": 10.41, "growth": 10.2651},
    "LGEN.L": {"name": "Legal & General", "sector": "Financial", "tags":[], "yield": 8.5, "growth": -5.0},
    "MNG.L":  {"name": "M&G PLC", "sector": "Financial", "tags":[], "yield": 9.5, "growth": 2.0},
    "JPM":    {"name": "JPMorgan Chase", "sector": "Financial", "tags":[], "yield": 2.3, "growth": 45.0},
    "FDUS":   {"name": "Fidus Investment", "sector": "Financial", "tags": [], "yield": 11.69, "growth": 17.3},
    "TRIN":   {"name": "Trinity Capital", "sector": "Financial", "tags": [], "yield": 12.1, "growth": 53.2},

    # -- REALITY (REITs) --
    "O":      {"name": "Realty Income", "sector": "Real Estate", "tags":[], "yield": 5.5, "growth": -12.0},
    "OHI":    {"name": "Omega Healthcare", "sector": "Real Estate", "tags":[], "yield": 8.5, "growth": 10.0},
    "VICI":   {"name": "VICI Properties", "sector": "Real Estate", "tags": ["CASINO"], "yield": 5.8, "growth": 5.0},
    "WPC":    {"name": "W. P. Carey", "sector": "Real Estate", "tags":[], "yield": 6.2, "growth": -15.0},
    "SBRA":   {"name": "Sabra Health Care REIT", "sector": "Real Estate", "tags": [], "yield": 6.04, "growth": 57.9},

    # -- PRŮMYSL & INFRASTRUKTURA --
    "CAT":    {"name": "Caterpillar Inc.", "sector": "Industrial", "tags":[], "yield": 1.6, "growth": 60.0},
    "LMT":    {"name": "Lockheed Martin", "sector": "Industrial", "tags": ["WEAPONS"], "yield": 2.8, "growth": 10.0},
    "MMM":    {"name": "3M Company", "sector": "Industrial", "tags":[], "yield": 6.5, "growth": -20.0},
    "TRIG.L": {"name": "Renewables Infra", "sector": "Utilities", "tags":[], "yield": 7.5, "growth": -25.0},
    "NEE":    {"name": "NextEra Energy", "sector": "Utilities", "tags":[], "yield": 3.5, "growth": -15.0},
    "PWR":    {"name": "Quanta Services", "sector": "Industrial", "tags":[], "yield": 0.2, "growth": 45.0},

    # -- ENERGIE (FOSILNÍ) --
    "CVX":    {"name": "Chevron Corp.", "sector": "Energy", "tags": ["FOSSIL"], "yield": 4.1, "growth": -5.0},
    "XOM":    {"name": "Exxon Mobil", "sector": "Energy", "tags": ["FOSSIL"], "yield": 3.2, "growth": 10.0},
    "SHEL.L": {"name": "Shell PLC", "sector": "Energy", "tags": ["FOSSIL"], "yield": 4.0, "growth": 15.0},

    # -- ETF SEKTOR (UCITS VARIANTY PRO ČESKÉHO INVESTORA) --
    "VUSA.L": {"name": "Vanguard S&P 500 (Dist)", "sector": "ETF", "tags": [], "yield": 1.2, "growth": 30.0, "etf_type": "Dist", "currency": "USD", "country": "UK"},
    "CSPX.L": {"name": "iShares Core S&P 500 (Acc)", "sector": "ETF", "tags": [], "yield": 0.0, "growth": 31.0, "etf_type": "Acc", "currency": "USD", "country": "UK"},
    "VWRL.L": {"name": "Vanguard All-World (Dist)", "sector": "ETF", "tags": [], "yield": 1.6, "growth": 20.0, "etf_type": "Dist", "currency": "USD", "country": "UK"},
    "VWRA.L": {"name": "Vanguard All-World (Acc)", "sector": "ETF", "tags": [], "yield": 0.0, "growth": 21.0, "etf_type": "Acc", "currency": "USD", "country": "UK"},
    "VHYL.L": {"name": "Vanguard High Div (Dist)", "sector": "ETF", "tags": [], "yield": 3.5, "growth": 12.0, "etf_type": "Dist", "currency": "USD", "country": "UK"},
    "EQQQ.L": {"name": "iShares NASDAQ 100 (Dist)", "sector": "ETF", "tags": [], "yield": 0.5, "growth": 55.0, "etf_type": "Dist", "currency": "USD", "country": "UK"},
    "CNDX.L": {"name": "iShares NASDAQ 100 (Acc)", "sector": "ETF", "tags": [], "yield": 0.0, "growth": 56.0, "etf_type": "Acc", "currency": "USD", "country": "UK"},
    "IWDP.L": {"name": "iShares Global REITs (Dist)", "sector": "ETF", "tags": [], "yield": 3.8, "growth": 2.0, "etf_type": "Dist", "currency": "USD", "country": "UK"},
}
# Sektory, které trpí při růstu sazeb (REITs, Utilities)
# Rozšiřitelný seznam, který aplikace použije pro Stress Test
RATE_HARMED_TICKERS = {
    "O", "VICI", "WPC", "AMT", "PLD", "CCI", "SPG", "PSA", "DLR", "EQIX", "WELL", "VTR", "AVB", "INVH", "OHI", "SBRA",
    "NEE", "TRIG.L", "PWR", "DUK", "SO", "NG.L", "SSE.L"
}

# Sektory, které z růstu sazeb těží (BDCs s plovoucími sazbami)
# Rozšiřitelný seznam, který aplikace použije pro Stress Test
RATE_BENEFITED_TICKERS = {
    "MAIN", "HTGC", "ARCC", "OBDC", "BXSL", "CSWC", "GBDC", "FSK", "TSLX", "TRIN", "FDUS", "PSEC", "OCSL", "GSBD"
}

# Parametry pro Monte Carlo tuning portfolia
MIN_W = 0.024
MAX_W = 0.08
EPS = 0.001
ENFORCEMENT_W = 0.5  # Důraz na trefení čísla na slideru
STABILITY_W = 0.5    # Důraz na minimální změnu existujících vah
MC_NO = 200000       # Počet simulovaných portfolií (musí být větší než 20000)
MC_NO_IMPR = 500000  # Počet simulovaných portfolií při vylepšování
MAX_DIV_SHARE = 0.23 # Maximální tolerovaný podíl jedné akcii v celkovém úhrnu dividend
DIV_YIELD_DROP = 0.5 # Očekávaný poměr změny dividend u akcií, které vyplácejí více než 90% zisku
DIV_WARN_FRACTION = 0.03 # Od jakého podílu jednoho zdroje dividend se zobrazí varování
HHI_PENALTY = 2.0    # míra penalizace koncentrace portfolia při optimalizaci (multiplikátor Herfindahl-Hirschmanova indexu)

# --- KONSTANTA PRO DYNAMICKÝ POSUV VAH (DRIFTING TARGETS) ---
ALPHA_DRIFT = 0.5 # 0.5 = 50% váha na původní cíl, 50% váha na aktuální tržní realitu

# --- KONSTANTY PRO DYNAMICKOU BRZDU A DANĚ ---
DEFAULT_TAX_RATE = 0.15               # Výchozí srážková daň z dividend a zisků (15 %)
DYN_TARGET_MIN_WEIGHT_FRACTION = 0.25 # Mantinel (Soft-Floor): váha akcie nesmí klesnout pod 50 % původního cíle
DYN_BRAKE_MAX_K = 5000.0              # Max hodnota k-faktoru v iteraci (horní mez)
DYN_BRAKE_ITERATIONS = 60             # Počet iterací algoritmu Water-Filling
GLIDE_PATH_RAMP_START = 0.5           # Procento splnění cíle, od kterého brzda začne polevovat (50 %)
DYN_YIELD_TOLERANCE = 0.004           # Aditivní rezerva proti matematickému extrému
EWMA_HALF_LIFE_DAYS = 45.0            # Poločas rozpadu v dnech pro vyhlazování odhadů růstu akcií

# --- Další konstanty
EPSILON_WEIGHT = 1e-6  # minimální váha, která už je považovaná za nulovou

# ==============================================================================
# TŘÍDA PRO ROBUSTNÍ STAHOVÁNÍ FINANČNÍCH DAT
# ==============================================================================
class RobustDataFetcher:
    """Nástroj pro paralelní stahování dat ze 2 nezávislých Yahoo API bez nutnosti API klíčů a registrací."""
    
    _yf_lock = threading.Lock() 

    def __init__(self):
        pass

    def fetch_history(self, tickers, start=None, end=None, period="5y", interval="1d", auto_adjust=True):
        if isinstance(tickers, str): tickers = tickers.split()
        tickers = list(set(tickers)) 

        # Sjednocení času pro přesné nalepení dat ze dvou různých API endpointů
        if not start and period:
            now = datetime.now()
            if period == "5y": start_dt = now - timedelta(days=5*365)
            elif period == "1y": start_dt = now - timedelta(days=365)
            else: start_dt = now - timedelta(days=10)
            
            start = start_dt.strftime('%Y-%m-%d')
            end = now.strftime('%Y-%m-%d')
            period = None 

        missing_tickers = tickers.copy()
        collected_data = {} 
        
        # --- ZDROJ 1: yfinance (Primární vrstva) ---
        if missing_tickers:
            try:
                with self._yf_lock:
                    df_yf = yf.download(missing_tickers, start=start, end=end, interval=interval,
                                     progress=False, auto_adjust=auto_adjust, actions=False, threads=False)

                if df_yf is not None and not df_yf.empty:
                    df_yf.index = pd.to_datetime(df_yf.index).tz_localize(None).normalize()
                    
                    actual_close_col = 'Adj Close' if auto_adjust and 'Adj Close' in df_yf else 'Close'

                    if isinstance(df_yf.columns, pd.MultiIndex):
                        if actual_close_col in df_yf:
                            close_df = df_yf[actual_close_col]
                            for t in missing_tickers.copy():
                                if t in close_df.columns:
                                    valid_data = close_df[t].dropna()
                                    if not valid_data.empty:
                                        t_data = {'Close': valid_data}
                                        if not auto_adjust and 'Adj Close' in df_yf and t in df_yf['Adj Close']:
                                            t_data['Adj Close'] = df_yf['Adj Close'][t].dropna()
                                        elif not auto_adjust:
                                            t_data['Adj Close'] = valid_data
                                            
                                        collected_data[t] = pd.DataFrame(t_data)
                                        missing_tickers.remove(t)
                    else:
                        if actual_close_col in df_yf.columns:
                            if len(missing_tickers) == 1:
                                t = missing_tickers[0]
                                valid_data = df_yf[actual_close_col].dropna()
                                if not valid_data.empty:
                                    t_data = {'Close': valid_data}
                                    if not auto_adjust and 'Adj Close' in df_yf.columns:
                                        t_data['Adj Close'] = df_yf['Adj Close'].dropna()
                                    elif not auto_adjust:
                                        t_data['Adj Close'] = valid_data
                                        
                                    collected_data[t] = pd.DataFrame(t_data)
                                    missing_tickers.remove(t)
            except Exception as e:
                print(f"[!] yfinance částečně selhalo: {e}")

        # --- ZDROJ 2: yahooquery (Sekundární vrstva - zachraňuje výpadky yfinance) ---
        if missing_tickers:
            print(f"[!] Zachraňuji chybějící data přes yahooquery pro: {missing_tickers}")
            try:
                # Ochranný zámek proti Race Condition a vypnutí interního asyncio
                with self._yf_lock:
                    yq_ticker = YQTicker(missing_tickers, asynchronous=False)
                    df_yq = yq_ticker.history(start=start, end=end, interval=interval)

                if isinstance(df_yq, pd.DataFrame) and not df_yq.empty:
                    df_yq = df_yq.reset_index()
                    date_col = 'date' if 'date' in df_yq.columns else df_yq.columns[1]
                    target_col = 'adjclose' if auto_adjust and 'adjclose' in df_yq.columns else 'close'

                    for t in missing_tickers.copy():
                        t_df = df_yq[df_yq['symbol'] == t]
                        if not t_df.empty:
                            t_df = t_df.set_index(date_col)
                            t_df.index = pd.to_datetime(t_df.index).tz_localize(None).normalize()
                            
                            t_data = {'Close': t_df[target_col]}
                            if not auto_adjust and 'adjclose' in t_df.columns:
                                t_data['Adj Close'] = t_df['adjclose']
                            elif not auto_adjust:
                                t_data['Adj Close'] = t_df['close']
                                
                            collected_data[t] = pd.DataFrame(t_data)
                            missing_tickers.remove(t)
            except Exception as e:
                print(f"[!] yahooquery částečně selhalo: {e}")

        # --- FINÁLNÍ SESTAVENÍ (Slepení dat) ---
        if not collected_data:
            return pd.DataFrame()
            
        if len(tickers) == 1:
            return collected_data.get(tickers[0], pd.DataFrame())
        else:
            close_dict, adj_dict = {}, {}
            for t in tickers:
                if t in collected_data:
                    df = collected_data[t]
                    close_dict[t] = df['Close']
                    if 'Adj Close' in df: adj_dict[t] = df['Adj Close']
            
            close_df = pd.DataFrame(close_dict)
            close_df.columns = pd.MultiIndex.from_product([['Close'], close_df.columns])
            
            if adj_dict:
                adj_df = pd.DataFrame(adj_dict)
                adj_df.columns = pd.MultiIndex.from_product([['Adj Close'], adj_df.columns])
                return pd.concat([close_df, adj_df], axis=1)
            
            return close_df

    def fetch_dividends(self, ticker):
        # ZDROJ 1: yfinance (pod zámkem _yf_lock) [1]
        try:
            with self._yf_lock:
                tick = yf.Ticker(ticker)
                divs = tick.dividends
            if divs is not None and not divs.empty:
                divs.index = pd.to_datetime(divs.index).tz_localize(None).normalize()
                return divs
        except: pass

        # ZDROJ 2: yahooquery (také pod zámkem _yf_lock)
        try:
            with self._yf_lock:
                yq_t = YQTicker(ticker, asynchronous=False) 
                div_df = yq_t.dividend_history()
            if isinstance(div_df, pd.DataFrame) and not div_df.empty and 'amount' in div_df.columns:
                div_df = div_df.reset_index()
                div_series = pd.Series(div_df['amount'].values, index=pd.to_datetime(div_df['date']))
                div_series.index = div_series.index.tz_localize(None).normalize()
                return div_series
        except: pass

        return pd.Series(dtype=float)

# ==============================================================================
# JÁDRO PRO MULTIPROCESSING (MONTE CARLO)
# ==============================================================================

def _worker_simulation_task(n_sims, active_indices, fixed_weights, target_sum, 
                            min_w, max_w, eps, stock_divs, stock_growths, sim_returns_values,
                            safe_divs, upsides, cov_matrix):
    """
    Paralelizovaná funkce pro Monte Carlo simulaci portfolií.
    Využívá Rejection Sampling k vygenerování validních vah a numpy matice k rychlému
    výpočtu rizik (drawdown) a výnosů. Běží odděleně na každém jádře CPU.
    """
    n_assets = len(active_indices)
    valid_w_list =[]
    
    # 1. Edge-case: Ošetření pro 1 akcii nebo matematicky znemožněné rozmezí
    if min_w >= max_w or n_assets == 0:
        w_act = np.full((n_sims, max(1, n_assets)), min_w)
        sums = np.sum(w_act, axis=1, keepdims=True)
        sums[sums == 0] = 1.0
        valid_w_matrix = w_act / sums * target_sum
    else:
        # 2. Hybridní generátor: Mix průzkumu (rohy) a diverzifikace (střed)
        # alpha=1.0 prozkoumává extrémy (dobré pro maximalizaci dividend)
        # alpha=5.0 nutí matici ke koncentraci vah doprostřed (dobré pro diverzifikaci)
        sims_half = n_sims // 2
        x_explore = np.random.dirichlet(np.full(n_assets, 1.0), sims_half)
        x_center = np.random.dirichlet(np.full(n_assets, 5.0), n_sims - sims_half)
        
        x = np.vstack([x_explore, x_center]) * target_sum
        
        # Fáze "Soft-Projection" (Přesná matematická projekce na hranice).
        # Hledáme posun lambda tak, aby součet po zaříznutí (clip) dal přesně target_sum.
        # Toto elegantně řeší problém "4.2 %" - zachovává Dirichletovo hladké rozložení, 
        # ale hodnoty mimo limity se zaříznou naprosto ostře bez nechtěného posunu.
        lambda_shift = np.zeros((n_sims, 1))
        
        for _ in range(25): # 25 iterací spolehlivě zaručí absolutní konvergenci
            w_clipped = np.clip(x + lambda_shift, min_w, max_w)
            diffs = target_sum - np.sum(w_clipped, axis=1, keepdims=True)
            # Rychlý a bezpečný gradientní krok
            lambda_shift += diffs / n_assets
            
        # Finální oříznutí s aplikovaným posunem
        w_act = np.clip(x + lambda_shift, min_w, max_w)
        
        # Pojistná filtrace proti nepřesnostem ve Float operacích
        final_sums = np.sum(w_act, axis=1)
        mask = (np.abs(final_sums - target_sum) <= eps)
        valid_w_matrix = w_act[mask]

    # 3. Zabalení vygenerovaných bloků zpět do kompletního pole vah (včetně fixovaných akcií)
    for gw in valid_w_matrix:
        full = fixed_weights.copy()
        full[active_indices] = gw
        valid_w_list.append(full)
        
    # Pokud z nějakého důvodu nastal absolutní fail (nemožné limity), ochrana pádu aplikace
    if not valid_w_list: return np.array([]), np.array([])
    weights_chunk = np.array(valid_w_list)
    
    # Maticové operace pro extrémní rychlost výpočtu metrik
    port_yields = np.dot(weights_chunk, stock_divs)
    div_income_czk = port_yields * 100000 
    
    port_period_rets = np.dot(sim_returns_values, weights_chunk.T)
    cum_returns = (1 + port_period_rets).cumprod(axis=0)
    
    # Skutečný celkový růst (Total Return) s reinvesticí dividend za celou periodu
    port_growths = (cum_returns[-1, :] - 1.0) * 100
    
    running_max = np.maximum.accumulate(cum_returns, axis=0)
    drawdowns = (cum_returns - running_max) / running_max
    max_dds = np.min(drawdowns, axis=0) * 100 
    
    # --- VÝPOČET PŘEDPOVĚDÍ DO BUDOUCNA ---
    fut_div_czk = np.dot(weights_chunk, safe_divs) * 100000
    fut_growths = np.dot(weights_chunk, upsides) # Desetinné číslo
    
    # Rychlý výpočet Volatility celého batche portfolií naráz
    batch_var = np.sum((weights_chunk @ cov_matrix) * weights_chunk, axis=1)
    batch_vol = np.sqrt(batch_var)
    
    # Výpočet 95% krizového propadu (Stress Test)
    # V krizi se optimistický růst nerealizuje, proto jsme 'fut_growths' odstranili.
    fut_crisis_drop = -1.645 * batch_vol * 100
    fut_crisis_drop = np.minimum(fut_crisis_drop, 0.0) # Zarovnáme na nulu, propad nesmí být kladný
    
    metrics_chunk = np.column_stack((div_income_czk, max_dds, port_growths, fut_div_czk, fut_crisis_drop, fut_growths * 100, batch_vol * 100))
    return weights_chunk, metrics_chunk


# ==============================================================================
# HLAVNÍ TŘÍDA APLIKACE (GUI A LOGIKA)
# ==============================================================================

class CzechInvestorApp:
    def __init__(self, root):
        """Inicializace hlavního okna, načtení dat a vykreslení uživatelského rozhraní."""
        self.root = root
        
        current_year = datetime.now().year
        self.root.title("Czech Investor: Tax & Portfolio Manager")
        self.root.geometry("1500x960")  
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self._slider_job = None      
        self.pie_tooltip = None      
        self.editor_window = None    
        
        # --- Globální styling aplikace (Fonty a vzhled) ---
        style = ttk.Style()
        default_font = ('Arial', 12)
        bold_font = ('Arial', 12, 'bold')
        
        style.configure('.', font=default_font)
        style.configure('TNotebook.Tab', font=bold_font, padding=[12, 6])
        style.configure('Treeview', font=default_font, rowheight=30)
        style.configure('Treeview.Heading', font=bold_font)
        style.configure('TButton', font=bold_font)
        
        # Načtení dat a aktualizace kurzů
        self.ledger, self.sales_history, self.uniform_rates = self.load_data()
        assert round(sum(TARGETS.values()), 4) == 1.0, f"Součet vah je {sum(TARGETS.values())}, musí být 1.0!"
        self.check_and_update_uniform_rates()
        
        # Sestavení UI
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        self.setup_planner_tab()  
        self.setup_sell_tab()
        self.setup_dividend_tab() 
        self.setup_dashboard_tab()
        self.setup_tuner_tab()    
        self.setup_donation_tab()

        # --- RYCHLÝ OFFLINE ODHAD PRO OKAMŽITÉ POUŽITÍ V TOOLTIPU ---
        # Pokud hodnoty nebyly načteny ze souboru, spočítáme nouzový odhad z nákupů
        if getattr(self, 'last_portfolio_value_czk', 0.0) == 0.0:
            temp_val = 0.0
            db_temp = getattr(self, 'stock_db_from_json', DEFAULT_STOCK_DB)
            for t, lots in self.ledger.items():
                p_factor = 0.01 if t.endswith('.L') else 1.0
                for lot in lots:
                    try:
                        temp_val += float(lot['qty']) * float(lot['price_at_buy']) * p_factor * float(lot.get('fx_rate', 23.0))
                    except:
                        pass
            self.last_portfolio_value_czk = temp_val
            
            temp_yield_sum = 0.0
            for t in TARGETS.keys():
                w = TARGETS.get(t, 0.0)
                dy = db_temp.get(t, {}).get('yield', 0.0) / 100.0
                temp_yield_sum += w * dy
            self.last_nominal_yield = temp_yield_sum if temp_yield_sum > 0 else 0.04
        
        # Zámek a příznak pro asynchronní preload worker na pozadí
        self._preload_thread_lock = threading.Lock()
        self.tuner_preloading = False
        
        self.root.after(2000, self.start_incremental_refresh)
        
        # Okamžité spuštění stahování fundamentů na pozadí, aby uživatel nečekal u nákupů
        def _safe_start_preload():
            with self._preload_thread_lock:
                if not self.tuner_preloading and not getattr(self, 'tuner_data_loaded', False):
                    self.tuner_preloading = True
                    threading.Thread(target=self._async_preload_worker, daemon=True).start()
                    
        self.root.after(500, _safe_start_preload)

    def on_close(self):
        self.root.destroy()
        os._exit(0)

    # --------------------------------------------------------------------------
    # PRÁCE S DATY A ÚLOŽIŠTĚM
    # --------------------------------------------------------------------------

    def load_data(self):
        global TARGETS
        if os.path.exists(PORTFOLIO_FILE):
            try:
                with open(PORTFOLIO_FILE, "r") as f:
                    data = json.load(f)
                    
                    saved_targets = data.get("targets", {})
                    if saved_targets:
                        TARGETS.clear()
                        TARGETS.update({k: float(v) for k, v in saved_targets.items()})

                    self.ethical_filters = data.get("ethical_filters", {k: True for k in TAGS})
                    
                    if "stock_db" in data:
                        self.stock_db_from_json = data["stock_db"]
                        # Načtení měn pro VŠECHNY evidované akcie, i ty minulé
                        for t, meta in self.stock_db_from_json.items():
                            if "currency" in meta and t not in CURRENCIES:
                                CURRENCIES[t] = meta["currency"]

                    ledger = data.get("holdings", {})
                    for t in TARGETS.keys():
                        if t not in ledger: ledger[t] =[]

                    # Automatická oprava řazení u již existujících dat v JSONu.
                    # Garantuje striktní FIFO chronologii hned po spuštění aplikace.
                    for t in ledger:
                        ledger[t].sort(key=lambda x: x.get("date", "1970-01-01"))

                    history = data.get("sales_history",[])
                    rates = data.get("uniform_rates", {})
                    
                    # Načtení custom limitů (s fallbackem na globální konstanty)
                    self.custom_min_w = float(data.get("min_w", MIN_W))
                    self.custom_max_w = float(data.get("max_w", MAX_W))
                    self.real_dividends = data.get("real_dividends",[])
                    
                    # Načtení uložených hodnot z minulé relace pro okamžitý start (použito v tooltipu)
                    self.last_portfolio_value_czk = float(data.get("last_portfolio_value_czk", 0.0))
                    self.last_nominal_yield = float(data.get("last_nominal_yield", 0.04))
                    
                    # Načtení nastavení optimalizace poplatků
                    self.fee_percent = float(data.get("fee_percent", 0.5))
                    self.optimize_fees_enabled = data.get("optimize_fees_enabled", True)
                    
                    # Načtení nastavení řazení v Editoru (výchozí "metrics")
                    self.editor_sort_mode = data.get("editor_sort_mode", "metrics")
                    
                    # Načtení datumu poslední aktualizace hodnoty růstu akcií
                    self.last_growth_update = data.get("last_growth_update", None)
                    
                    # Načtení nastavení metody výpočtu rebalancování
                    self.drifting_targets_enabled = data.get("drifting_targets_enabled", False)
                    
                    # Načtení nastavení dynamického cílování portfolia
                    self.dyn_targets_enabled = data.get("dyn_targets_enabled", False)
                    self.dyn_yield_cap = float(data.get("dyn_yield_cap", 3.0))
                    self.dyn_abs_div = float(data.get("dyn_abs_div", 500000))

                    return ledger, history, rates
            except Exception as e: 
                print(f"Varování při načítání JSON: {e}")
        
        self.ethical_filters = {k: True for k in TAGS}
        self.custom_min_w = MIN_W
        self.custom_max_w = MAX_W
        self.dyn_targets_enabled = False
        self.dyn_yield_cap = 3.0
        self.dyn_abs_div = 500000
        self.drifting_targets_enabled = False
        return {t:[] for t in TARGETS},[], {}

    def save_data(self):
        data = {
            "targets": TARGETS,  
            "holdings": self.ledger, 
            "sales_history": self.sales_history, 
            "uniform_rates": self.uniform_rates,
            "stock_db": getattr(self, 'stock_db_from_json', DEFAULT_STOCK_DB),
            "ethical_filters": getattr(self, 'ethical_filters', {k: True for k in TAGS}),
            "min_w": getattr(self, 'custom_min_w', MIN_W),
            "max_w": getattr(self, 'custom_max_w', MAX_W),
            "real_dividends": getattr(self, 'real_dividends',[]),
            "fee_percent": getattr(self, 'fee_percent', 0.5),
            "optimize_fees_enabled": getattr(self, 'optimize_fees_enabled', True),
            "editor_sort_mode": getattr(self, 'editor_sort_mode', 'metrics'),
            "last_growth_update": getattr(self, 'last_growth_update', None),
            "drifting_targets_enabled": getattr(self, 'drifting_targets_enabled', False),
            "dyn_targets_enabled": getattr(self, 'dyn_targets_enabled', False),
            "dyn_yield_cap": getattr(self, 'dyn_yield_cap', 3.0),
            "dyn_abs_div": getattr(self, 'dyn_abs_div', 500000),
            # hodnoty pro okamžitý start bez načítání (použito v tooltipu):
            "last_portfolio_value_czk": getattr(self, 'last_portfolio_value_czk', 0.0),
            "last_nominal_yield": getattr(self, 'last_nominal_yield', 0.04)
        }
        with open(PORTFOLIO_FILE, "w") as f: json.dump(data, f, indent=4)

    def check_and_update_uniform_rates(self):
        current_year = datetime.now().year
        last_year = str(current_year - 1)
        if last_year in self.uniform_rates: return
        threading.Thread(target=self._fetch_rates_from_gfr_pdf, args=(current_year,), daemon=True).start()

    def _fetch_rates_from_gfr_pdf(self, current_year):
        # Převod na int, aby fungovala matematika (year - 1)
        current_year_int = int(current_year)
        # Hledáme kurzy za PŘEDCHOZÍ rok (GFŘ 2026 řeší rok 2025)
        last_year = current_year_int - 1
        source_year = last_year + 1 
        
        base_url = f"https://financnisprava.gov.cz/cs/dane/legislativa-a-metodika/pokyny-d/cleneni-podle-dani/dane-z-prijmu/{source_year}"
        
        try:
            resp = requests.get(base_url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            pdf_url = None
            # Procházíme teasery na webu
            for teaser in soup.find_all(class_="b-teaser"):
                text_content = teaser.find(class_="b-teaser__text").get_text()
                # Hledáme cílový text (seznam jednotných kurzů)
                if "jednotných kurzů" in text_content and str(last_year) in text_content:
                    link = teaser.find('a', class_='btn--ghost')
                    if link and link.get('href'):
                        pdf_url = "https://financnisprava.gov.cz" + link.get('href')
                        break
            
            if not pdf_url:
                print(f"Nepodařilo se najít odkaz na PDF pro rok {last_year}")
                return False

            pdf_response = requests.get(pdf_url, timeout=15)
            with pdfplumber.open(io.BytesIO(pdf_response.content)) as pdf:
                # GFŘ pokyny mají tabulku zpravidla na 2. straně
                if len(pdf.pages) < 2: return False
                page = pdf.pages[1] 
                table = page.extract_table()
                
                if not table: return False
                
                usd_found, gbp_found = False, False
                for row in table:
                    # Řádek: [Země, Měna, Množství, Kód, Průměr]
                    # row[3] je kód, row[4] je průměr
                    if len(row) >= 5:
                        code = row[3]
                        val_raw = row[4]
                        
                        if code == "USD":
                            self.uniform_rates.setdefault(str(last_year), {})["USD"] = float(val_raw.replace(',', '.'))
                            usd_found = True
                        elif code == "GBP":
                            self.uniform_rates.setdefault(str(last_year), {})["GBP"] = float(val_raw.replace(',', '.'))
                            gbp_found = True
                
                if usd_found and gbp_found:
                    self.save_data()
                    return True
                
        except Exception as e:
            print(f"Chyba při extrakci z FS PDF: {e}")
        return False

    def get_fx_rates(self):
        # Vytvoření mezipaměti při prvním spuštění
        if not hasattr(self, '_fx_cache_time'): 
            self._fx_cache_time = 0
            self._fx_cache_data = {"USD": 23.5, "GBP": 29.5}
            
        # Cache je platná 1 hodinu (3600 vteřin)
        # Zabrání to zasekávání UI, když uživatel rychle "odentrovává" řádky
        if time.time() - self._fx_cache_time < 3600:
            return self._fx_cache_data
            
        try:
            df = self._safe_yf_download("USDCZK=X GBPCZK=X", period="5d")
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex) and 'Close' in df.columns.get_level_values(0):
                    vals = df['Close'].ffill().iloc[-1]
                elif 'Close' in df.columns:
                    vals = df['Close'].ffill().iloc[-1]
                else:
                    vals = df.ffill().iloc[-1]
                
                usd = float(vals.get('USDCZK=X', 23.5)) if 'USDCZK=X' in vals else 23.5
                gbp = float(vals.get('GBPCZK=X', 29.5)) if 'GBPCZK=X' in vals else 29.5
                
                # Uložení do mezipaměti
                self._fx_cache_data = {"USD": usd, "GBP": gbp}
                self._fx_cache_time = time.time()
                
                return self._fx_cache_data
        except Exception as e: 
            print(f"FX Warning: {e}")
            
        return self._fx_cache_data

    def fetch_sell_price(self):
        """Spustí stahování aktuální ceny ve vedlejším vlákně, aby UI nezamrzlo."""
        ticker = self.sell_ticker.get().strip().upper()
        if not ticker: return
        
        # Nastavení zpožděného loading overlaye (animace vyjede až pokud stahování trvá > 500 ms)
        if getattr(self, 'sell_price_loading_timer', None):
            self.root.after_cancel(self.sell_price_loading_timer)
            
        self.sell_price_loading_timer = self.root.after(500, lambda: self.show_loading(self.sell_loading_state, f"Stahuji cenu pro {ticker}..."))
        
        def work():
            try:
                # Použijeme náš robustní downloader
                df = self._safe_yf_download(ticker, period="5d")
                
                if df.empty or 'Close' not in df:
                    raise ValueError(f"Servery neposkytly cenu pro {ticker}.")
                
                # Získání Close dat
                close_col = df['Close']
                
                # yfinance může vrátit DataFrame (u více tickerů) nebo Series (u jednoho).
                if isinstance(close_col, pd.DataFrame):
                    p_val = close_col[ticker].ffill().iloc[-1]
                else:
                    p_val = close_col.ffill().iloc[-1]

                # Ošetření nečíselných hodnot (NaN)
                if pd.isna(p_val):
                    raise ValueError("Cena je momentálně nedostupná (NaN).")

                # Úprava pro britské pence (.L)
                if ticker.endswith(".L"): 
                    p_val = float(p_val) / 100.0
                
                # Bezpečný zápis do UI přes hlavní vlákno
                self.root.after(0, lambda p=p_val: self._update_sell_price_ui(p))
                
            except Exception as e:
                err_msg = str(e)
                print(f"Error fetching price: {err_msg}")
                self.root.after(0, lambda m=err_msg: messagebox.showerror("Chyba stahování", m))
            finally:
                # Garantované zrušení časovače a skrytí animace (provedeno v hlavním vlákně)
                self.root.after(0, self._cleanup_sell_price_loading)

        threading.Thread(target=work, daemon=True).start()

    def _cleanup_sell_price_loading(self):
        """Bezpečně zruší časovač a skryje animaci po dokončení stahování jedné ceny."""
        if getattr(self, 'sell_price_loading_timer', None):
            self.root.after_cancel(self.sell_price_loading_timer)
            self.sell_price_loading_timer = None
        self.hide_loading(self.sell_loading_state)

    def _update_sell_price_ui(self, price):
        """Pomocná metoda pro bezpečný zápis ceny do políčka (voláno z after)."""
        self.sell_price_entry.delete(0, tk.END)
        # alternativní zobrazení ceny s desetinnou čárkou
        #self.sell_price_entry.insert(0, f"{float(price):.2f}".replace('.', ','))
        # alternativní zobrazení ceny s desetinnou tečkou
        self.sell_price_entry.insert(0, f"{float(price):.2f}")

    def _safe_yf_download(self, tickers, period="5y", interval="1d", max_retries=2, auto_adjust=True, start=None, end=None):
        """Volá robustní stahovač se záložním zdrojem a ochranou relace."""
        if not hasattr(self, 'data_fetcher'):
            self.data_fetcher = RobustDataFetcher()

        for i in range(max_retries):
            df = self.data_fetcher.fetch_history(tickers, start=start, end=end, period=period, interval=interval, auto_adjust=auto_adjust)
            if not df.empty:
                return df
            time.sleep(0.5)
        return pd.DataFrame()

    def _safe_get_dividends(self, ticker, max_retries=2):
        """Stahuje dividendy s fallbackem a ochranou mezipaměti."""
        if not hasattr(self, '_div_cache'): self._div_cache = {}

        # Z cache čteme pouze v případě, že obsahuje validní (ne-prázdná) data
        if ticker in self._div_cache and not self._div_cache[ticker].empty:
            return self._div_cache[ticker]

        for i in range(max_retries):
            divs = self.data_fetcher.fetch_dividends(ticker)
            if not divs.empty:
                self._div_cache[ticker] = divs
                return divs
            time.sleep(0.5)

        # Neukládáme prázdnou řadu natrvalo do cache, pokud šlo o dočasné selhání,
        # abychom neotrávili mezipaměť a dovolili úspěšný pokus při příštím volání.
        return pd.Series(dtype=float)

    def _safe_get_fundamentals(self, ticker, max_retries=3):
        """
        Stahuje fundamentální data pro budoucí predikci (P/E, Výplatní poměr, Cílové ceny analytiků).
        Využívá yfinance s robustním záchranným fallbackem na yahooquery při chybě 401 Invalid Crumb.
        Celá síťová komunikace je synchronizována přes sdílený zámek RobustDataFetcher._yf_lock.
        """
        if not hasattr(self, '_fund_cache'):
            self._fund_cache = {}
            
        if ticker in self._fund_cache:
            return self._fund_cache[ticker]
            
        # Pokus č. 1: yfinance (řízený zámkem _yf_lock)
        for i in range(max_retries):
            try:
                time.sleep(0.3)
                # Synchronizace síťového požadavku přes sdílený třídní zámek
                with RobustDataFetcher._yf_lock:
                    info = yf.Ticker(ticker).info
                
                if info and isinstance(info, dict):
                    data = {
                        "pe_ratio": info.get('forwardPE') or info.get('trailingPE'),
                        "eps": info.get('forwardEps') or info.get('trailingEps'),
                        "beta": info.get('beta'),
                        "recommendation": info.get('recommendationKey'),
                        "payout_ratio": info.get('payoutRatio') or 0.0,
                        "target_price": info.get('targetMeanPrice'),
                        "current_price": info.get('currentPrice') or info.get('previousClose')
                    }
                    self._fund_cache[ticker] = data
                    return data
            except Exception as e:
                print(f"[!] yfinance .info selhalo pro {ticker} ({e}). Zkouším znovu...")
                time.sleep(0.5 + i)
                
        # Pokus č. 2: Záchranný fallback přes yahooquery (také pod zámkem _yf_lock)
        print(f"[!] Používám yahooquery jako záchranný zdroj pro fundamenty {ticker}")
        try:
            with RobustDataFetcher._yf_lock:
                yq_t = YQTicker(ticker, asynchronous=False)
                summary_detail = yq_t.summary_detail.get(ticker, {}) if hasattr(yq_t, 'summary_detail') else {}
                financial_data = yq_t.financial_data.get(ticker, {}) if hasattr(yq_t, 'financial_data') else {}
                key_statistics = yq_t.key_statistics.get(ticker, {}) if hasattr(yq_t, 'key_statistics') else {}
            
            if isinstance(summary_detail, dict) and isinstance(financial_data, dict):
                pe_ratio = summary_detail.get('forwardPE') or summary_detail.get('trailingPE')
                eps = key_statistics.get('trailingEps') or key_statistics.get('forwardEps') if isinstance(key_statistics, dict) else None
                beta = summary_detail.get('beta')
                recommendation = financial_data.get('recommendationKey')
                payout_ratio = summary_detail.get('payoutRatio') or 0.0
                target_price = financial_data.get('targetMeanPrice')
                current_price = summary_detail.get('currentPrice') or summary_detail.get('previousClose')
                
                data = {
                    "pe_ratio": pe_ratio,
                    "eps": eps,
                    "beta": beta,
                    "recommendation": recommendation,
                    "payout_ratio": payout_ratio,
                    "target_price": target_price,
                    "current_price": current_price
                }
                self._fund_cache[ticker] = data
                return data
        except Exception as e:
            print(f"[!] Selhal i záchranný zdroj yahooquery pro {ticker}: {e}")

        # Úplný nouzový fallback (neutrální hodnoty)
        data = {
            "pe_ratio": None, 
            "eps": None, 
            "beta": None, 
            "recommendation": None, 
            "payout_ratio": 0.0, 
            "target_price": None, 
            "current_price": None
        }
        self._fund_cache[ticker] = data
        return data


    # --------------------------------------------------------------------------
    # VIZUÁLNÍ OVERLAY A ANIMACE NAČÍTÁNÍ
    # --------------------------------------------------------------------------

    def _create_loading_card(self, parent_frame):
        bg_color = "#E0E0E0" 
        card = tk.Frame(parent_frame, bg=bg_color, relief=tk.RAISED, borderwidth=4)
        card_content = tk.Frame(card, bg=bg_color)
        card_content.place(relx=0.5, rely=0.5, anchor="center")
        
        canvas_gears = tk.Canvas(card_content, width=240, height=140, bg=bg_color, highlightthickness=0)
        canvas_gears.pack(pady=(0, 20))
        
        lbl_text = tk.Label(card_content, text="Probíhá výpočet...", font=("Arial", 18, "bold"), bg=bg_color, fg="#333")
        lbl_text.pack(pady=10)
        progress = ttk.Progressbar(card_content, orient="horizontal", length=350, mode="indeterminate")
        progress.pack(pady=10)
        
        return {"card": card, "canvas": canvas_gears, "label": lbl_text, "progress": progress, "angle": 0.0, "is_loading": False, "job": None}

    def _get_gear_coords(self, cx, cy, radius, teeth, angle_offset):
        coords =[]
        segment = math.pi / (teeth * 2)
        for i in range(teeth * 4):
            tooth_idx = i // 4
            if i % 4 == 0:
                angle = angle_offset + tooth_idx * (math.pi * 2 / teeth) - segment * 0.8
                r = radius * 0.75
            elif i % 4 == 1:
                angle = angle_offset + tooth_idx * (math.pi * 2 / teeth) - segment * 0.3
                r = radius
            elif i % 4 == 2:
                angle = angle_offset + tooth_idx * (math.pi * 2 / teeth) + segment * 0.3
                r = radius
            else:
                angle = angle_offset + tooth_idx * (math.pi * 2 / teeth) + segment * 0.8
                r = radius * 0.75

            coords.append(cx + r * math.cos(angle))
            coords.append(cy + r * math.sin(angle))
        return coords

    def _animate_gears(self, state_dict):
        if not state_dict["is_loading"]: return
        state_dict["angle"] += 0.08
        canvas = state_dict["canvas"]
        canvas.delete("gear")

        cx1, cy1, r1, teeth = 70, 70, 55, 8
        coords1 = self._get_gear_coords(cx1, cy1, r1, teeth, state_dict["angle"])
        canvas.create_polygon(coords1, fill="#1565C0", outline="#0D47A1", width=2, tags="gear")
        canvas.create_oval(cx1-15, cy1-15, cx1+15, cy1+15, fill="#E0E0E0", outline="#0D47A1", width=3, tags="gear")

        cx2, cy2, r2 = 170, 70, 55
        coords2 = self._get_gear_coords(cx2, cy2, r2, teeth, -state_dict["angle"] + (math.pi / teeth))
        canvas.create_polygon(coords2, fill="#F57F17", outline="#F9A825", width=2, tags="gear")
        canvas.create_oval(cx2-15, cy2-15, cx2+15, cy2+15, fill="#E0E0E0", outline="#F9A825", width=3, tags="gear")

        state_dict["job"] = self.root.after(40, lambda: self._animate_gears(state_dict))

    def show_loading(self, state_dict, message="Pracuji..."):
        if state_dict["is_loading"]: return
        state_dict["label"].config(text=message)
        state_dict["card"].place(relx=0.5, rely=0.5, anchor="center", width=550, height=350)
        state_dict["card"].lift()
        state_dict["is_loading"] = True
        state_dict["progress"].start(10)
        self._animate_gears(state_dict)
        self.root.update_idletasks()

    def hide_loading(self, state_dict):
        state_dict["is_loading"] = False
        state_dict["progress"].stop()
        state_dict["card"].place_forget()
        if state_dict["job"]:
            self.root.after_cancel(state_dict["job"])
            state_dict["job"] = None

    def _set_tuner_controls_state(self, state):
        """Zapíná/vypíná ovládací prvky na kartě Tuning během výpočtu."""
        if hasattr(self, 'btn_change_stocks') and self.btn_change_stocks.winfo_exists():
            self.btn_change_stocks.config(state=state)
        if hasattr(self, 'btn_init_tuner') and self.btn_init_tuner.winfo_exists():
            self.btn_init_tuner.config(state=state)
        if hasattr(self, 'btn_auto_tune') and self.btn_auto_tune.winfo_exists():
            self.btn_auto_tune.config(state=state)
        if hasattr(self, 'btn_apply_weights') and self.btn_apply_weights.winfo_exists():
            self.btn_apply_weights.config(state=state)
        if hasattr(self, 'tuner_checkboxes'):
            for cb in self.tuner_checkboxes:
                if cb.winfo_exists(): cb.config(state=state)
        
        # Slidery vypínáme vždy. Zapínají se pak nezávisle pouze při úspěšné simulaci.
        if state == tk.DISABLED and hasattr(self, 'sliders'):
            for s in self.sliders.values():
                if s.winfo_exists(): s.config(state=tk.DISABLED)

    def run_tuner_with_loading(self, target_func, msg):
        """Spustí funkci na pozadí s vizuální indikací a uzamkne UI Tuneru."""
        if self.tuner_loading_state["is_loading"]: return
        
        # Zrušení jakéhokoliv plánovaného výpočtu ze sliderů, aby nekolidoval se simulací
        if getattr(self, '_slider_job', None):
            self.root.after_cancel(self._slider_job)
            self._slider_job = None

        # Validace limitů z textových polí na hlavním vlákně před spuštěním
        if hasattr(self, '_validate_and_get_limits'):
            self._validate_and_get_limits()
            
        self.show_loading(self.tuner_loading_state, msg)
        self._set_tuner_controls_state(tk.DISABLED) # Okamžité vizuální zablokování UI
        
        # Obalovací funkce (Wrapper), která garantuje odemčení UI i při pádu kódu (výpadku dat atd.)
        def wrapped_func():
            try:
                target_func()
            finally:
                self.root.after(0, lambda: self._set_tuner_controls_state(tk.NORMAL))
                
        threading.Thread(target=lambda: self._thread_task(wrapped_func, self.tuner_loading_state), daemon=True).start()

    def run_dash_with_loading(self, target_func, msg):
        """Spustí funkci na pozadí s vizuální indikací a uzamkne UI Statistik."""
        if self.dash_loading_state["is_loading"]: return
        
        self.show_loading(self.dash_loading_state, msg)
        self._set_dash_controls_state(tk.DISABLED) # Vizuální zablokování tlačítek
        
        # Obalovací funkce garantující odemčení UI i při selhání stahování
        def wrapped_func():
            try:
                target_func()
            finally:
                self.root.after(0, lambda: self._set_dash_controls_state(tk.NORMAL))
                
        threading.Thread(target=lambda: self._thread_task(wrapped_func, self.dash_loading_state), daemon=True).start()

    def _thread_task(self, target_func, state_dict):
        try: target_func()
        finally: self.root.after(0, lambda: self.hide_loading(state_dict))


    # --------------------------------------------------------------------------
    # TAB 1: PLÁNOVAČ NÁKUPŮ (NÁKUP)
    # --------------------------------------------------------------------------

    def setup_planner_tab(self):
        main_frame = tk.Frame(self.notebook, bg="#f0f2f5")
        self.notebook.add(main_frame, text="Nákup")
        
        # --- 1. VYTVOŘENÍ A ROZMÍSTĚNÍ HLAVNÍCH RÁMEČKŮ ---
        # Trik pro responzivitu: Zabíráme místo odspodu nahoru. Tím garantujeme, 
        # že spodní tlačítka nikdy nezmizí při zmenšení okna a smrskne se jen tabulka.
        
        # Spodní rámeček se seznamem k uložení.
        # Nastavujeme expand=True. Při zvětšení okna si tak vezme 
        # veškeré přebytečné místo právě tato tabulka. Skvělé pro CSV import!
        final_frame = tk.LabelFrame(main_frame, text="3. Seznam realizovaných obchodů (Připraveno k zápisu)", bg="#f0f2f5", padx=10, pady=5, font=("Arial", 12, "bold"))
        final_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Prostřední formulář. Pevná výška (expand=False), zůstává zakotven dole.
        edit_frame = tk.LabelFrame(main_frame, text="2. Skutečná realizace (Zadejte dle výpisu brokera)", bg="#E3F2FD", padx=10, pady=10, font=("Arial", 12, "bold"))
        edit_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)

        # Horní rámeček (Kalkulátor).
        # Nastavujeme expand=False. Rámeček tak vyroste přesně na výšku
        # stromu (např. 16 řádků) a zastaví se. Zabrání se ošklivému prázdnému místu.
        calc_frame = tk.LabelFrame(main_frame, text="1. Teoretický návrh (Kalkulátor)", bg="#f0f2f5", padx=10, pady=5, font=("Arial", 12, "bold"))
        calc_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=False, padx=10, pady=5)

        # --- 2. OBSAH RÁMEČKU 1 (Kalkulátor) ---
        top_bar = tk.Frame(calc_frame, bg="#f0f2f5")
        top_bar.pack(side=tk.TOP, pady=5, anchor="w")
        
        tk.Label(top_bar, text="Investice (Kč):", font=("Arial", 12), bg="#f0f2f5").pack(side=tk.LEFT, padx=5)
        self.cash_entry = tk.Entry(top_bar, font=("Arial", 12), width=12)
        self.cash_entry.pack(side=tk.LEFT, padx=5)
        self.cash_entry.insert(0, "70000")
        
        self.btn_calc_buys = tk.Button(top_bar, text="Spočítat návrh", command=self.start_calculate_buys, 
                  bg="#2E7D32", fg="white", font=("Arial", 12, "bold"))
        self.btn_calc_buys.pack(side=tk.LEFT, padx=20)
        
        # --- Ovládací prvky pro optimalizaci poplatků ---
        self.opt_fee_var = tk.BooleanVar(value=getattr(self, 'optimize_fees_enabled', True))
        self.opt_fee_checkbox = tk.Checkbutton(top_bar, text="Optimalizovat poplatky pro typ účtu IBKR Pro Tiered", variable=self.opt_fee_var, 
                       font=("Arial", 12), bg="#f0f2f5", 
                       command=self._on_fee_opt_change)
        self.opt_fee_checkbox.pack(side=tk.LEFT, padx=(20, 5))
        
        tk.Label(top_bar, text="Max poplatek:", font=("Arial", 12), bg="#f0f2f5").pack(side=tk.LEFT)
        self.fee_entry = tk.Entry(top_bar, font=("Arial", 12), width=5, justify="center")
        self.fee_entry.pack(side=tk.LEFT, padx=5)
        self.fee_entry.insert(0, str(getattr(self, 'fee_percent', DEFAULT_FEE_PERCENT)).replace('.', ','))
        
        # Automatický přepočet i při stisku Enter uvnitř políčka pro procenta
        self.fee_entry.bind("<Return>", self._on_fee_opt_change)

        tk.Label(top_bar, text="%", font=("Arial", 12), bg="#f0f2f5").pack(side=tk.LEFT)

        # --- Checkbox pro Dynamický posuv vah (Drifting Targets) ---
        self.drift_var = tk.BooleanVar(value=getattr(self, 'drifting_targets_enabled', False))
        self.cb_drift = tk.Checkbutton(top_bar, text="Dynamický posuv vah (nechat vítěze růst)", 
                                       variable=self.drift_var, font=("Arial", 12), bg="#f0f2f5",
                                       command=self._on_drift_opt_change)
        self.cb_drift.pack(side=tk.LEFT, padx=(30, 5))

        # Tooltip pro Drifting Targets
        tt_drift = ("Pokud je zapnuto, aplikace dovolí růstovým akciím přesáhnout nastavené váhy.\n"
                    "Cílové váhy se dynamicky posouvají (driftují) směrem k aktuální tržní realitě.\n"
                    "Díky tomu algoritmus neodstřihne rychle rostoucí akcie od nových investic,\n"
                    "aniž byste ztratili výhodu automatického rebalancování propadlíků.")
        self.cb_drift.bind("<Enter>", lambda e: self._show_tooltip(tt_drift))
        self.cb_drift.bind("<Leave>", lambda e: self._hide_tooltip())

        # Rámeček pro Dynamické řízení portfolia
        dyn_frame = tk.Frame(calc_frame, bg="#E3F2FD", padx=5, pady=5, relief=tk.RIDGE, borderwidth=1)
        dyn_frame.pack(side=tk.TOP, fill=tk.X, pady=(5, 5))
        
        self.dyn_opt_var = tk.BooleanVar(value=getattr(self, 'dyn_targets_enabled', False))
        self.cb_dyn_opt = tk.Checkbutton(dyn_frame, text="Dynamicky řídit dividendový výnos (dividendová brzda)", 
                                         variable=self.dyn_opt_var, font=("Arial", 12, "bold"), bg="#E3F2FD",
                                         command=self._on_dyn_opt_change)
        self.cb_dyn_opt.pack(side=tk.LEFT, padx=5)
        
        # Tooltip pro hlavní Checkbox
        tt_main = ("Pokud je zapnuto, aplikace automaticky tlumí nákupy akcií s vysokou dividendou v případě,\n"
                   "že je portfolio v kumulativní části životního cyklu. Veškeré ušetřené peníze přesměruje do růstových akcií.\n"
                   "Po dosažení cílového pasivního příjmu už nákup dividendých akcií není limitován (portfolio prioritizuje rentu).")
        self.cb_dyn_opt.bind("<Enter>", lambda e: self._show_tooltip(tt_main))
        self.cb_dyn_opt.bind("<Leave>", lambda e: self._hide_tooltip())

        tk.Label(dyn_frame, text=" |  Max. yield (strop pro růst):", font=("Arial", 11), bg="#E3F2FD").pack(side=tk.LEFT)
        
        self.dyn_floor_slider = tk.Scale(dyn_frame, from_=0.0, to=10.0, resolution=0.1, orient=tk.HORIZONTAL, 
                                         length=150, bg="#E3F2FD", font=("Arial", 12))
        self.dyn_floor_slider.set(getattr(self, 'dyn_yield_cap', 3.0))
        self.dyn_floor_slider.pack(side=tk.LEFT, padx=5)
        # Připojení eventu na uvolnění tlačítka myši (netrhá to aplikaci při tažení)
        self.dyn_floor_slider.bind("<ButtonRelease-1>", self._on_dyn_opt_change)

        # Dynamický výpočet maxima slideru podle aktuálních vah
        # Používáme last_nominal_yield (načteno z JSONu jako poslední známá přesná hodnota), 
        # nikoliv statická data z databáze, aby to ihned po startu sedělo se simulací.
        nom_yield = getattr(self, 'last_nominal_yield', 0.04)
        max_slider = round(nom_yield * 100, 2)
        if max_slider < 0.5: max_slider = 5.0 # Fallback pro úplně prázdné portfolio
        self.dyn_floor_slider.config(to=max_slider)

        tk.Label(dyn_frame, text="%", font=("Arial", 11), bg="#E3F2FD").pack(side=tk.LEFT)
        
        # Tooltip pro Slider
        tt_slider = ("Maximální povolený dividendový výnos portfolia.\n"
                     "Pokud vaše aktuální cílové váhy generují vyšší procento dividend než tento limit, aplikace před nákupem utlumí\n"
                     "požadavky na nákup dividendových akcií a přesměruje volné peníze do růstových titulů.\n"
                     "Tím vás ve fázi budování majetku (a zvláště v krizi) ochrání před uvíznutím v pomalých titulech.\n"
                     "Po dosažení cílového pasivního příjmu už nákup dividendých akcií není limitován (portfolio prioritizuje rentu).")
        self.dyn_floor_slider.bind("<Enter>", lambda e: self._show_tooltip(tt_slider))
        self.dyn_floor_slider.bind("<Leave>", lambda e: self._hide_tooltip())

        tk.Label(dyn_frame, text="  |  Cílový pasivní příjem:", font=("Arial", 12), bg="#E3F2FD").pack(side=tk.LEFT, padx=(10, 0))
        
        self.dyn_abs_entry = tk.Entry(dyn_frame, font=("Arial", 12), width=10, justify="right")
        self.dyn_abs_entry.insert(0, str(int(getattr(self, 'dyn_abs_div', 300000))))
        self.dyn_abs_entry.pack(side=tk.LEFT, padx=5)
        self.dyn_abs_entry.bind("<Return>", self._on_dyn_opt_change)
        tk.Label(dyn_frame, text="Kč / rok", font=("Arial", 12), bg="#E3F2FD").pack(side=tk.LEFT)
        
        # Dynamický tooltip pro Absolutní cíl (s predikcí času a analýzou historie)
        self.dyn_abs_entry.bind("<Enter>", lambda e: self._show_tooltip(self.get_dyn_abs_tooltip_text()))
        self.dyn_abs_entry.bind("<Leave>", lambda e: self._hide_tooltip())

        # Počáteční nastavení stavu (zešednutí) podle zaškrtávacího políčka
        initial_state = tk.NORMAL if getattr(self, 'dyn_targets_enabled', False) else tk.DISABLED
        self.dyn_floor_slider.config(state=initial_state)
        self.dyn_abs_entry.config(state=initial_state)

        tree_container = tk.Frame(calc_frame, bg="#f0f2f5")
        tree_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=5)

        # LEVÝ PANEL (Checkboxy pro vyřazení akcií)
        self.buy_cb_frame = tk.LabelFrame(tree_container, text="Koupit", bg="#f0f2f5", font=("Arial", 12, "bold"))
        self.buy_cb_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))

        self.buy_cb_canvas = tk.Canvas(self.buy_cb_frame, bg="#f0f2f5", width=90, highlightthickness=0)
        cb_scroll = ttk.Scrollbar(self.buy_cb_frame, orient="vertical", command=self.buy_cb_canvas.yview)
        self.buy_cb_inner_frame = tk.Frame(self.buy_cb_canvas, bg="#f0f2f5")

        self.buy_cb_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cb_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.buy_cb_canvas.configure(yscrollcommand=cb_scroll.set)
        self.buy_cb_canvas.create_window((0,0), window=self.buy_cb_inner_frame, anchor="nw")
        self.buy_cb_inner_frame.bind("<Configure>", lambda e: self.buy_cb_canvas.configure(scrollregion=self.buy_cb_canvas.bbox("all")))
        
        # Posouvání kolečkem myši u checkboxů
        self.buy_cb_canvas.bind("<Enter>", lambda e: self.buy_cb_canvas.bind_all("<MouseWheel>", lambda ev: self.buy_cb_canvas.yview_scroll(int(-1*(ev.delta/120)), "units")))
        self.buy_cb_canvas.bind("<Leave>", lambda e: self.buy_cb_canvas.unbind_all("<MouseWheel>"))

        self.buy_active_vars = {}
        self._build_buy_checkboxes()

        # PRAVÝ PANEL (Samotná tabulka nákupů)
        tree_right_frame = tk.Frame(tree_container, bg="#f0f2f5")
        tree_right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tree_scroll = ttk.Scrollbar(tree_right_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        rows_needed = len(TARGETS)
        tree_height = min(rows_needed, 20)

        self.buy_tree = ttk.Treeview(tree_right_frame, columns=("Ticker", "Cíl %", "Cena trh [USD/GBP]", "FX", "CZK (Návrh)", "Hodnota [USD/GBP]", "Ks (Návrh)"), 
                                     show="headings", height=tree_height, yscrollcommand=tree_scroll.set)
        
        for c, w in {"Ticker":90, "Cíl %":70, "Cena trh [USD/GBP]":90, "FX":70, "CZK (Návrh)":120, "Hodnota [USD/GBP]":120, "Ks (Návrh)":120}.items():
            self.buy_tree.heading(c, text=c)
            self.buy_tree.column(c, width=w, anchor="center")
        
        self.buy_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.buy_tree.yview)
        self.buy_tree.bind("<<TreeviewSelect>>", self.fill_entry_from_proposal)
        
        # Sledování myši pro zobrazení tooltipu nadbytku
        self.buy_tree.bind("<Motion>", self._on_buy_tree_hover)
        self.buy_tree.bind("<Leave>", lambda e: self._hide_tooltip())
        self._buy_excess_data = {}
        self._last_hovered_buy_item = None
        
        # --- 3. OBSAH RÁMEČKU 2 (Skutečná realizace) ---
        tk.Label(edit_frame, text="Ticker:", bg="#E3F2FD", font=("Arial", 12)).grid(row=0, column=0, padx=5)
        self.real_ticker = tk.Entry(edit_frame, width=10, font=("Arial", 12))
        self.real_ticker.grid(row=1, column=0, padx=5)

        tk.Label(edit_frame, text="Datum:", bg="#E3F2FD", font=("Arial", 12)).grid(row=0, column=1, padx=5)
        self.real_date = tk.Entry(edit_frame, width=12, font=("Arial", 12))
        self.real_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.real_date.grid(row=1, column=1, padx=5)

        tk.Label(edit_frame, text="Skutečné množství (Ks):", bg="#E3F2FD", font=("Arial", 12)).grid(row=0, column=2, padx=5)
        self.real_qty = tk.Entry(edit_frame, width=12, font=("Arial", 12))
        self.real_qty.grid(row=1, column=2, padx=5)

        tk.Label(edit_frame, text="Nákupní cena [USD/GBP]:", bg="#E3F2FD", font=("Arial", 12)).grid(row=0, column=3, padx=5)
        self.real_price = tk.Entry(edit_frame, width=12, font=("Arial", 12))
        self.real_price.grid(row=1, column=3, padx=5)

        tk.Button(edit_frame, text="↓ Přidat do seznamu k uložení", command=self.add_manual_entry, bg="#1565C0", fg="white", font=("Arial", 12, "bold")).grid(row=1, column=4, padx=20)
        tk.Label(edit_frame, text="(Klikni nahoře na řádek pro rychlé vyplnění)", bg="#E3F2FD", fg="grey", font=("Arial", 11)).grid(row=0, column=4)

        tk.Button(edit_frame, text="📥 Import nákupů\nIBKR (.csv)", command=self.import_ibkr_csv, bg="#FF9800", fg="black", font=("Arial", 12, "bold")).grid(row=0, column=5, rowspan=2, padx=(10, 5), sticky="nsew")

        # --- 4. OBSAH RÁMEČKU 3 (Staging / Připraveno k zápisu) ---
        btn_bar = tk.Frame(final_frame, bg="#f0f2f5")
        btn_bar.pack(side=tk.BOTTOM, pady=10)
        tk.Button(btn_bar, text="💾 Uložit všechny nákupy ze seznamu do portfolia", command=self.commit_staging_to_ledger, 
                  font=("Arial", 14, "bold"), bg="#C62828", fg="white", padx=20).pack()

        staging_container = tk.Frame(final_frame, bg="#f0f2f5")
        staging_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        staging_scroll = ttk.Scrollbar(staging_container, orient="vertical")
        staging_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Výšku (height) jsem zvednul na 5, aby tabulka vypadala lépe už při spuštění,
        # ale díky expand=True výše na 'final_frame' si po maximalizaci okna vezme spoustu místa navíc.
        self.staging_tree = ttk.Treeview(staging_container, columns=("Ticker", "Datum", "Množství", "Cena", "Akce"), 
                                         show="headings", height=5, yscrollcommand=staging_scroll.set)
        
        staging_scroll.config(command=self.staging_tree.yview)

        for c in ("Ticker", "Datum", "Množství", "Cena"):
            self.staging_tree.heading(c, text=c)
            self.staging_tree.column(c, anchor="center")
        self.staging_tree.heading("Akce", text="Smazat")
        self.staging_tree.column("Akce", width=80, anchor="center")
        
        self.staging_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.staging_tree.bind("<Double-1>", self.delete_staging_row)
                  
        self.planner_loading_state = self._create_loading_card(main_frame)

    def _build_buy_checkboxes(self):
        """Vygeneruje checkboxy pro povolení/zakázání nákupu jednotlivých akcií."""
        if not hasattr(self, 'buy_cb_inner_frame'): return
        
        # Vyčistit staré checkboxy (při změně portfolia)
        for widget in self.buy_cb_inner_frame.winfo_children():
            widget.destroy()
            
        # Aktualizovat proměnné pro nové akcie
        for t in TARGETS.keys():
            if t not in self.buy_active_vars:
                self.buy_active_vars[t] = tk.BooleanVar(value=True)
                
        # Vytvořit UI
        for t in sorted(TARGETS.keys()):
            if TARGETS[t] <= 1e-6: continue
            cb = tk.Checkbutton(self.buy_cb_inner_frame, text=t, variable=self.buy_active_vars[t], 
                                bg="#f0f2f5", font=("Arial", 11), command=self._on_buy_cb_change)
            cb.pack(anchor="w", padx=2, pady=1)

    def _on_buy_cb_change(self):
        """Přepočítá nákup, pokud uživatel odškrtne akcii."""
        if hasattr(self, 'buy_tree') and self.buy_tree.get_children() and self.btn_calc_buys['state'] == tk.NORMAL:
            self.start_calculate_buys()

    def _on_fee_opt_change(self, event=None):
        """Spustí automatický přepočet nákupů při změně nastavení poplatků."""
        # 1. Uložíme aktuální stav do paměti
        try:
            self.fee_percent = float(self.fee_entry.get().replace(',', '.'))
        except ValueError:
            self.fee_percent = DEFAULT_FEE_PERCENT
        self.optimize_fees_enabled = self.opt_fee_var.get()
        
        # 2. Uložíme do JSONu
        self.save_data()
        
        # 3. Spustíme přepočet
        if self.buy_tree.get_children() and self.btn_calc_buys['state'] == tk.NORMAL:
            self.start_calculate_buys()

    def _on_dyn_opt_change(self, event=None):
        """Uloží nastavení dynamických cílů, upraví UI a spustí přepočet."""
        # 1. Přečtení aktuálního stavu Checkboxu
        is_enabled = self.dyn_opt_var.get()
        
        # 2. Okamžitá změna stavu UI (zešednutí / odblokování)
        new_state = tk.NORMAL if is_enabled else tk.DISABLED
        if hasattr(self, 'dyn_floor_slider'):
            self.dyn_floor_slider.config(state=new_state)
        if hasattr(self, 'dyn_abs_entry'):
            self.dyn_abs_entry.config(state=new_state)

        # 3. Uložení hodnot
        try:
            self.dyn_abs_div = float(self.dyn_abs_entry.get().replace(' ', '').replace(',', '.'))
            if self.dyn_abs_div < 0.0: self.dyn_abs_div = 0.0
        except ValueError:
            self.dyn_abs_div = 500000.0
            
        self.dyn_yield_cap = float(self.dyn_floor_slider.get())
        self.dyn_targets_enabled = is_enabled
        
        self.save_data()
        
        # 4. Pokud je funkce zapnuta a zrovna je aktivní návrh, automaticky ho přepočítáme
        # (při vypnutí funkce ho také přepočítáme, aby se vrátil na nominální váhy)
        if hasattr(self, 'buy_tree') and self.buy_tree.get_children() and self.btn_calc_buys['state'] == tk.NORMAL:
            self.start_calculate_buys()

    def _on_drift_opt_change(self, event=None):
        """Uloží nastavení dynamického posuvu vah a spustí přepočet."""
        self.drifting_targets_enabled = self.drift_var.get()
        self.save_data()
        
        if hasattr(self, 'buy_tree') and self.buy_tree.get_children() and self.btn_calc_buys['state'] == tk.NORMAL:
            self.start_calculate_buys()

    def _apply_dynamic_dividend_brake(self, nom_weights, yields_array, growths_array, projected_total_val, abs_target_gross_czk, yield_cap):
        """
        Centrální metoda pro aplikaci dividendové brzdy na původní váhy.
        Využívá "Toxický yield" (zohledňuje růst akcií) a Soft-Floor mantinely.
        """
        nom_portfolio_yield = np.sum(nom_weights * yields_array)
        
        # 1. Fáze životního cyklu (Glide-Path)
        achievable_gross_div = nom_portfolio_yield * projected_total_val
        progress = achievable_gross_div / abs_target_gross_czk if abs_target_gross_czk > 0 else 1.0
        
        if progress >= 1.0:
            target_yield_limit = nom_portfolio_yield + 1.0 
        elif progress <= GLIDE_PATH_RAMP_START:
            target_yield_limit = yield_cap
        else:
            ramp_position = (progress - GLIDE_PATH_RAMP_START) / (1.0 - GLIDE_PATH_RAMP_START)
            alpha = ramp_position ** 3
            target_yield_limit = yield_cap + alpha * (nom_portfolio_yield - yield_cap)
            
        # Matematicky správný výpočet nejnižšího dosažitelného yieldu (abychom zabránili útesovému efektu)
        min_allowed_weights = nom_weights * DYN_TARGET_MIN_WEIGHT_FRACTION
        rem_weight = 1.0 - np.sum(min_allowed_weights)
        lowest_yield_available = np.min(yields_array[nom_weights > 0.0001]) if np.any(nom_weights > 0.0001) else 0.0
        
        true_min_portfolio_yield = np.sum(min_allowed_weights * yields_array) + (rem_weight * lowest_yield_available)
        safe_target_yield = max(target_yield_limit, true_min_portfolio_yield + DYN_YIELD_TOLERANCE)
        
        # 2. Exponenciální brzda s toxickým yieldem a ochrannými mantinely
        if nom_portfolio_yield > safe_target_yield:
            low, high = 0.0, DYN_BRAKE_MAX_K
            best_w = nom_weights.copy()
            
            # Zvýšení štítu: Za každé 1 % růstu odpustíme 0.75 % dividendy. 
            # (TRIG s ~30% růstem tak s přehledem smaže svůj 8% yield a nebude brzděn vůbec).
            growth_credit = np.maximum(0, growths_array) * 0.75
            toxic_yield = np.maximum(0, yields_array - growth_credit)
            
            # Matematická nutnost: Nejnižší toxický yield posuneme na nulu.
            # Tím zajistíme, že nejlepší růstová akcie nebude nikdy brzděna (exp(0) = 1.0),
            # nespadne na 50% mantinel a algoritmus se nezacyklí (tzv. bounce-back efekt).
            active_mask = nom_weights > EPSILON_WEIGHT
            if np.any(active_mask):
                toxic_yield[active_mask] -= np.min(toxic_yield[active_mask])
            
            # Načtení uživatelského maxima z UI (ochrana proti přetečení vah)
            max_limit = getattr(self, 'custom_max_w', MAX_W)
            
            for _ in range(DYN_BRAKE_ITERATIONS):
                k = (low + high) / 2.0
                decay_factors = np.exp(-k * toxic_yield)
                w_raw = nom_weights * decay_factors
                
                # Zajištění, že nespadneme pod podlahu
                w_raw = np.maximum(w_raw, min_allowed_weights)
                
                if np.sum(w_raw) < 1e-10:
                    high = k
                    continue
                    
                # ---------------------------------------------------------
                # MATEMATICKÁ PROJEKCE S DODRŽENÍM MAXIMÁLNÍCH LIMITŮ
                # ---------------------------------------------------------
                # Uvolněný kapitál přeléváme do růstových akcií. Musíme ale zaručit,
                # že žádná akcie (např. TRIG) nepřeteče přes uživatelsky nastavený limit.
                w_norm = w_raw / np.sum(w_raw)
                lambda_shift = 0.0
                for _ in range(20):
                    w_clipped = np.clip(w_norm + lambda_shift, min_allowed_weights, max_limit)
                    diff = 1.0 - np.sum(w_clipped)
                    if abs(diff) < 1e-7:
                        break
                    lambda_shift += diff / len(nom_weights)
                    
                w_norm = np.clip(w_norm + lambda_shift, min_allowed_weights, max_limit)
                # ---------------------------------------------------------
                
                simulated_yield = np.sum(w_norm * yields_array)
                
                if simulated_yield > safe_target_yield:
                    low = k
                    best_w = w_norm # Záchrana hraničního optima, pokud mantinel blokuje dosažení cíle
                else:
                    high = k
                    best_w = w_norm
                    
            best_w[best_w < 0.00001] = 0.0 
            if np.sum(best_w) > 0:
                best_w = best_w / np.sum(best_w)
            else:
                best_w = nom_weights
            return best_w
            
        return nom_weights.copy()

    def _apply_drifting_targets(self, current_targets, current_holdings_val, total_portfolio_val):
        """
        Upraví cílové váhy tak, aby částečně driftovaly směrem k aktuální realitě.
        Zabraňuje tomu, aby water-filling algoritmus přestal kupovat rychle rostoucí akcie.
        Zároveň garantuje, že žádná z vah nepřeteče přes uživatelský MAX limit.
        """
        dynamic_targets = {}
        
        for t, target in current_targets.items():
            curr_val = current_holdings_val.get(t, 0.0)
            curr_weight = curr_val / total_portfolio_val if total_portfolio_val > 0 else 0.0
            
            # Ochrana: Pokud uživatel nastavil cíl na 0, natvrdo ho vynulujeme.
            if target <= 1e-6:
                dynamic_targets[t] = 0.0
            else:
                # Výpočet driftujícího cíle
                dynamic_targets[t] = (target * ALPHA_DRIFT) + (curr_weight * (1.0 - ALPHA_DRIFT))
                
        # Načtení uživatelského maxima z UI (karta Tuning Portfolia)
        max_limit = getattr(self, 'custom_max_w', MAX_W)
        
        # Extrakce aktivních tickerů pro matematickou projekci
        active_tickers = [t for t, w in dynamic_targets.items() if w > 1e-6]
        if not active_tickers:
            return current_targets.copy()
            
        w_raw = np.array([dynamic_targets[t] for t in active_tickers])
        w_norm = w_raw / np.sum(w_raw)
        
        # Ochrana před matematicky neřešitelným stavem (uživatel nastavil příliš nízký strop)
        if max_limit * len(active_tickers) < 1.0:
            max_limit = 1.0 / len(active_tickers)
            
        # ---------------------------------------------------------
        # MATEMATICKÁ PROJEKCE S DODRŽENÍM MAXIMÁLNÍHO LIMITU
        # ---------------------------------------------------------
        # Přetečená váha z nadhodnocených akcií se odřízne a 
        # rovnoměrně se rozprostře mezi ostatní aktivní akcie.
        lambda_shift = 0.0
        for _ in range(25):
            w_clipped = np.clip(w_norm + lambda_shift, 0.0, max_limit)
            diff = 1.0 - np.sum(w_clipped)
            if abs(diff) < 1e-7:
                break
            lambda_shift += diff / len(w_raw)
            
        w_norm = np.clip(w_norm + lambda_shift, 0.0, max_limit)
        
        # Zápis upravených a oříznutých vah zpět do slovníku
        for i, t in enumerate(active_tickers):
            dynamic_targets[t] = float(w_norm[i])
            
        return dynamic_targets

    def start_calculate_buys(self):
        """Příprava před výpočtem - zamkne tlačítka a vyčistí tabulku v hlavním vlákně."""
        self.btn_calc_buys.config(state=tk.DISABLED)
        
        # Zamknutí prvků pro optimalizaci poplatků a posuvu vah
        if hasattr(self, 'opt_fee_checkbox'): self.opt_fee_checkbox.config(state=tk.DISABLED)
        if hasattr(self, 'fee_entry'): self.fee_entry.config(state=tk.DISABLED)
        if hasattr(self, 'cb_drift'): self.cb_drift.config(state=tk.DISABLED)
        if hasattr(self, 'buy_cb_inner_frame'):
            for cb in self.buy_cb_inner_frame.winfo_children():
                cb.config(state=tk.DISABLED)
        
        for i in self.buy_tree.get_children(): self.buy_tree.delete(i)
        
        # Nastavení časovače pro zobrazení animace ozubených kol (pokud to trvá déle než 2 vteřiny)
        self.planner_loading_timer = self.root.after(2000, lambda: self.show_loading(self.planner_loading_state, "Stahuji data, prosím, čekejte..."))
        
        threading.Thread(target=self.calculate_buys, daemon=True).start()

    def calculate_buys(self):
        try:
            wait_loops = 0
            # Aplikace čeká na dokončení stahování fundamentů z preloaderu na pozadí (max 180 vteřin, zde v desetinách)
            while not getattr(self, 'tuner_data_loaded', False) and wait_loops < 1800:
                time.sleep(0.1)
                wait_loops += 1

            try: 
                invest = float(self.cash_entry.get().replace(',', '.'))
            except ValueError:
                self.root.after(0, lambda: messagebox.showerror("Chyba", "Zadejte platnou částku k investici."))
                return

            fx = self.get_fx_rates()
            all_tickers = list(TARGETS.keys())
            
            try: 
                # Použití robustního stahovače místo obyčejného yf.download pro větší stabilitu
                raw_data = self._safe_yf_download(all_tickers, period="5d")
                if raw_data.empty or 'Close' not in raw_data:
                    raise ValueError("Nelze získat aktuální ceny akcií z Yahoo Finance.")
                
                close_data = raw_data['Close']
                if isinstance(close_data, pd.DataFrame):
                    prices_data = close_data.ffill().iloc[-1]
                else:
                    prices_data = pd.Series({all_tickers[0]: close_data.ffill().iloc[-1]})
            except Exception as e:
                self.root.after(0, lambda err=e: messagebox.showerror("Chyba", f"Chyba stahování dat: {err}"))
                return

            # --- ŘEŠENÍ PRO ČERSTVÁ IPO A CHYBĚJÍCÍ CENY ---
            prices_dict = {}
            for t in all_tickers:
                try:
                    p = float(prices_data.get(t, 0.0))
                    if pd.isna(p) or p <= 0:
                        raise ValueError("Chybí cena v historii")
                    prices_dict[t] = p
                except Exception:
                    # Fallback: Yfinance v history() často nemá dnešní IPO, 
                    # ale v info (fundamenty) se dá zjistit 'currentPrice'
                    fund = self._safe_get_fundamentals(t)
                    p = float(fund.get('current_price') or 0.0)
                    prices_dict[t] = p if not pd.isna(p) else 0.0

            current_holdings_val = {}
            total_current_portfolio_val = 0.0

            for t in all_tickers:
                qty_held = sum(item['qty'] for item in self.ledger.get(t,[]))
                price = prices_dict.get(t, 0.0)
                
                cur = CURRENCIES.get(t, "USD")
                fx_rate = fx.get(cur, 1.0)
                
                if t.endswith(".L"): price /= 100.0
                
                if price > 0:
                    val_czk = qty_held * price * fx_rate
                    current_holdings_val[t] = val_czk
                    total_current_portfolio_val += val_czk
                else:
                    current_holdings_val[t] = 0.0

           # Skutečná hodnota portfolia po zainvestování vložené částky (potřebné pro dynamický cíl)
            projected_total_val = total_current_portfolio_val + invest

            # --- ZÍSKÁNÍ PŘESNÝCH DAT (Společné pro dynamickou brzdu i pro uložení do paměti) ---
            nom_weights = np.array([TARGETS[t] for t in TARGETS.keys()])
            yields_list = []
            growths_list = []
            db = getattr(self, 'stock_db_from_json', DEFAULT_STOCK_DB)
            
            for t in TARGETS.keys():
                if getattr(self, 'tuner_data_loaded', False) and hasattr(self, 'ordered_tickers') and t in self.ordered_tickers:
                    idx = self.ordered_tickers.index(t)
                    # Použijeme stejná precizní data jako Tuner
                    yields_list.append(self.tuner_stock_divs[idx])
                    growths_list.append(self.tuner_upsides[idx])
                else:
                    # Fallback na databázi, pokud by náhodou preloader selhal
                    meta = db.get(t, {})
                    yields_list.append(meta.get("yield", 0.0) / 100.0)
                    growths_list.append(meta.get("growth", 0.0) / 100.0)

            yields_array = np.array(yields_list)
            growths_array = np.array(growths_list)
            nom_portfolio_yield = np.sum(nom_weights * yields_array)

            # DYNAMICKÉ ŘÍZENÍ DIVIDENDOVÉHO VÝNOSU (EXPONENCIÁLNÍ BRZDA)
            effective_targets = TARGETS.copy()
            if getattr(self, 'dyn_targets_enabled', False) and projected_total_val > 0:
                try:
                    # 1. Zjištění limitů z UI (čte přímo aktuální text v políčku, i bez stisku Enter)
                    yield_cap = float(self.dyn_floor_slider.get()) / 100.0
                    try:
                        abs_target_net_czk = float(self.dyn_abs_entry.get().replace(' ', '').replace(',', '.'))
                        if abs_target_net_czk < 0.0: abs_target_net_czk = 0.0
                    except ValueError:
                        abs_target_net_czk = getattr(self, 'dyn_abs_div', 500000.0)
                        
                    # Přepočet požadované čisté částky na hrubou (zohlednění srážkové daně)
                    abs_target_gross_czk = abs_target_net_czk / (1 - DEFAULT_TAX_RATE)
                    
                    # Okamžitá aktualizace slideru z hlavního vlákna (nepřepisuje vaši pozici, jen posouvá limit)
                    max_slider_val = round(nom_portfolio_yield * 100, 2)
                    if max_slider_val < 0.5: max_slider_val = 5.0
                    self.root.after(0, lambda v=max_slider_val: self.dyn_floor_slider.config(to=v))
                    
                    # 4. VÝPOČET DYNAMICKÉ BRZDY PŘES CENTRALIZOVANOU METODU
                    best_w = self._apply_dynamic_dividend_brake(
                        nom_weights=nom_weights,
                        yields_array=yields_array,
                        growths_array=growths_array,  # Předání pole růstů
                        projected_total_val=projected_total_val,
                        abs_target_gross_czk=abs_target_gross_czk,
                        yield_cap=yield_cap
                    )
                    
                    # Propsání nových upravených vah do dočasného slovníku
                    for i, t in enumerate(TARGETS.keys()):
                        effective_targets[t] = float(best_w[i])
                        
                except Exception as e:
                    print(f"[!] Chyba dynamického cílování: {e}")

            # DYNAMICKÝ POSUV VAH (DRIFTING TARGETS)
            if getattr(self, 'drifting_targets_enabled', False) and total_current_portfolio_val > 0:
                effective_targets = self._apply_drifting_targets(
                    current_targets=effective_targets,
                    current_holdings_val=current_holdings_val,
                    total_portfolio_val=total_current_portfolio_val
                )

            # VYŘAZENÍ AKCIÍ ODŠKRTNUTÝCH UŽIVATELEM
            if not hasattr(self, 'buy_active_vars'):
                self.buy_active_vars = {t: tk.BooleanVar(value=True) for t in TARGETS.keys()}
                
            for t in list(effective_targets.keys()):
                if t in self.buy_active_vars and not self.buy_active_vars[t].get():
                    effective_targets[t] = 0.0 # Vynulujeme cíl, nedostane z investice nic
                    
            # Důležité: Váhy musíme znovu normalizovat na 100 %, 
            # jinak by "Virtual Total" ve waterfillingu zanechal část peněz nevyužitou!
            sum_eff = sum(effective_targets.values())
            if sum_eff > 0:
                for t in effective_targets:
                    effective_targets[t] /= sum_eff
            else:
                self.root.after(0, lambda: messagebox.showwarning("Chyba", "Všechny akcie byly odškrtnuty. Není co nakoupit."))
                return

            # OPTIMALIZACE POPLATKŮ
            valid_targets = [w for w in effective_targets.values() if w > 0]
            min_target = min(valid_targets) if valid_targets else 1.0
            
            # 1. Získání limitů pro poplatky z UI
            optimize_fees = self.opt_fee_var.get()
            try:
                max_fee_pct = float(self.fee_entry.get().replace(',', '.')) / 100.0
            except ValueError:
                max_fee_pct = 0.005 # Fallback 0.5%
            
            # Výpočet minimální investice (MTS - Minimum Trade Size) pro každý ticker
            mts_czk = {}
            for t in all_tickers:
                cur = self.get_currency_for_ticker(t)
                fx_rate = fx.get(cur, 1.0)
                if cur == "GBP":
                    mts_czk[t] = (IBKR_MIN_FEE_GBP / max_fee_pct) * fx_rate
                else:
                    mts_czk[t] = (IBKR_MIN_FEE_USD / max_fee_pct) * fx_rate
            
            banned_from_buy = set()
            final_allocations_czk = {t: 0.0 for t in all_tickers}
            
            # 2. Iterativní Water Filling (až N-krát vyloučí nejmenší nevalidní nákup)
            for _ in range(len(all_tickers) + 1):
                low = 0.0
                high = (total_current_portfolio_val + invest) / min_target 
                virtual_total = 0.0
                
                # Binární hledání
                for _ in range(50):
                    mid = (low + high) / 2.0
                    required_cash = 0.0
                    for t, target in effective_targets.items():
                        if t in banned_from_buy: continue # Tuto akcii už nenakupujeme
                        ideal_val = mid * target
                        curr_val = current_holdings_val.get(t, 0.0)
                        if ideal_val > curr_val:
                            required_cash += (ideal_val - curr_val)
                            
                    if required_cash > invest: high = mid
                    else: low = mid; virtual_total = mid
                
                # Zjištění alokací z nalezeného virtual_total
                temp_allocs = {}
                for t, target in effective_targets.items():
                    if t in banned_from_buy:
                        temp_allocs[t] = 0.0
                    else:
                        ideal_val = virtual_total * target
                        curr_val = current_holdings_val.get(t, 0.0)
                        temp_allocs[t] = max(0.0, ideal_val - curr_val)
                        
                if not optimize_fees:
                    final_allocations_czk = temp_allocs
                    break
                    
                # 3. Kontrola limitů poplatků (hledáme nejhoršího hříšníka)
                violation_found = False
                worst_violation_t = None
                worst_violation_score = -float('inf')
                
                for t, alloc in temp_allocs.items():
                    # Prevence "falešných poplatkových penalizací" u nadvážených nebo nulových pozic.
                    # Zjistíme cenu v CZK pro výpočet minimálního smysluplného nákupu (0.001 ks)
                    cur = self.get_currency_for_ticker(t)
                    price = prices_dict.get(t, 0.0)
                    if price <= 0: continue
                    fx_rate = fx.get(cur, 1.0)
                    if t.endswith(".L"): price /= 100.0
                    price_in_czk = price * fx_rate
                    
                    # Nákup považujeme za matematicky reálný pouze tehdy, pokud by vedl k pořízení alespoň 0.001 ks
                    min_meaningful_alloc = price_in_czk * 0.001
                    
                    # Poplatkovou penalizaci uplatníme pouze pro reálné nákupy (větší než 0.001 ks a zároveň pod limitem MTS)
                    if min_meaningful_alloc < alloc < mts_czk[t]:
                        violation_found = True
                        
                        # Počítáme absolutní chybějící částku (shortfall).
                        shortfall = mts_czk[t] - alloc
                        
                        if shortfall > worst_violation_score:
                            worst_violation_score = shortfall
                            worst_violation_t = t
                            
                # Pokud existuje porušení, vyloučíme "nejslabší článek" a jedeme další kolo.
                if violation_found:
                    banned_from_buy.add(worst_violation_t)
                else:
                    final_allocations_czk = temp_allocs
                    break

            # Skutečná hodnota portfolia po zainvestování vložené částky
            projected_total_val = total_current_portfolio_val + invest

            # --- ULOŽENÍ PARAMETRŮ PRO DYNAMICKOU PREDIKCI (ŽIVÝ DYNAMICKÝ YIELD) ---
            # Zde už jen elegantně převezmeme přesně vypočítaný výnos portfolia z bloku výše
            self.last_nominal_yield = nom_portfolio_yield if nom_portfolio_yield > 0 else 0.04
            self.last_portfolio_value_czk = total_current_portfolio_val

            raw_rows_data = []
            info_data_temp = {} 
            
            # 4. Formátování řádků pro UI
            for t, target in effective_targets.items():
                if target <= EPSILON_WEIGHT: continue
                
                try:
                    cur = self.get_currency_for_ticker(t)
                    price = prices_dict.get(t, 0.0)
                    if price <= 0:
                        print(f"[!] Akcie {t} přeskočena - nebyla nalezena tržní cena.")
                        continue
                    fx_rate = fx.get(cur, 1.0)
                    if t.endswith(".L"): price /= 100.0
                    price_in_czk = price * fx_rate

                    czk_alloc = final_allocations_czk.get(t, 0.0)
                    qty = czk_alloc / price_in_czk if price_in_czk > 0 else 0.0

                    if qty < 0.001:
                        qty = 0.0
                        czk_alloc = 0.0
                        
                        curr_val = current_holdings_val.get(t, 0.0)
                        true_ideal_val = projected_total_val * target
                        excess_czk = curr_val - true_ideal_val
                        
                        # Přiřazení správného důvodu pro Tooltip (Poplatky vs. Běžný nadbytek)
                        if t in banned_from_buy:
                            info_data_temp[t] = {"type": "fee", "min_req": mts_czk[t], "currency": cur}
                        elif excess_czk > 50 and price_in_czk > 0:
                            excess_qty = excess_czk / price_in_czk
                            info_data_temp[t] = {"type": "excess", "qty": excess_qty, "czk": excess_czk}
                        else:
                            continue # akcie, u kterých bychom kupovali méně než 0,001 kusů, ignorujeme

                    qty_rounded = round(qty, 3)
                    orig_val = qty_rounded * price
                    
                    # Formátování cílové váhy - pokud je zapnutý posuv, ukážeme i původní cíl v závorce
                    if getattr(self, 'drifting_targets_enabled', False):
                        orig_target = TARGETS.get(t, target)
                        target_str = f"{target:.1%} ({orig_target:.1%})".replace('.', ',')
                    else:
                        target_str = f"{target:.1%}".replace('.', ',')
                    
                    row_tuple = (
                        t, 
                        target_str, 
                        f"{price:.2f}".replace('.', ','), 
                        f"{fx_rate:.1f}".replace('.', ','), 
                        f"{czk_alloc:.0f}",
                        f"{orig_val:.2f}".replace('.', ','), 
                        f"» {str(qty_rounded).replace('.', ',')} «"
                    )
                    
                    # Uložíme i s číselnou alokací, abychom podle ní mohli řadit
                    raw_rows_data.append((czk_alloc, row_tuple))
                except Exception as e: print(f"Skipping {t}: {e}")

            # 5. Seřazení: Primárně od největšího nákupu po nejmenší, sekundárně abecedně
            # Použijeme trik s mínusem u alokace (-x[0]), abychom pro tickery (x[1][0]) zachovali klasické A-Z řazení.
            raw_rows_data.sort(key=lambda x: (-x[0], x[1][0]))
            rows_to_insert = [r[1] for r in raw_rows_data]

            # Bezpečný zápis do UI z hlavního vlákna (bezpečné pro Tkinter)
            self.root.after(0, lambda r=rows_to_insert, i=info_data_temp: self._populate_buy_tree(r, i))

        finally:
            # Garantované odemčení a skrytí loading animace (provedeno v hlavním vlákně)
            self.root.after(0, self._cleanup_planner_loading)

    def _cleanup_planner_loading(self):
        """Bezpečně zruší časovač a skryje animaci po dokončení výpočtu."""
        if getattr(self, 'planner_loading_timer', None):
            self.root.after_cancel(self.planner_loading_timer)
            self.planner_loading_timer = None
        self.hide_loading(self.planner_loading_state)
        self.btn_calc_buys.config(state=tk.NORMAL)
        
        # Odemknutí prvků pro optimalizaci poplatků a posuvu vah
        if hasattr(self, 'opt_fee_checkbox'): self.opt_fee_checkbox.config(state=tk.NORMAL)
        if hasattr(self, 'fee_entry'): self.fee_entry.config(state=tk.NORMAL)
        if hasattr(self, 'cb_drift'): self.cb_drift.config(state=tk.NORMAL)
        if hasattr(self, 'buy_cb_inner_frame'):
            for cb in self.buy_cb_inner_frame.winfo_children():
                cb.config(state=tk.NORMAL)

    def _populate_buy_tree(self, rows, info_data=None):
        """Pomocná metoda pro bezpečné vypsání dat do tabulky v UI vlákně."""
        # Uložení doplňujících informací (pro Tooltipy)
        if info_data is not None:
            self._buy_info_data = info_data
        else:
            self._buy_info_data = {}
            
        for row in rows:
            self.buy_tree.insert("", "end", values=row)

    def fill_entry_from_proposal(self, event):
        """Přenese hodnoty z vybraného návrhu nákupu do formuláře."""
        selection = self.buy_tree.selection()
        if not selection: return
        vals = self.buy_tree.item(selection[0])['values']
        self.real_ticker.delete(0, tk.END)
        self.real_ticker.insert(0, vals[0])
        
        # Očištění o vizuální znaky (» a «) a převod čárky zpět na TEČKU pro brokera
        clean_qty = str(vals[6]).replace('»', '').replace('«', '').replace(',', '.').strip()
        self.real_qty.delete(0, tk.END)
        self.real_qty.insert(0, clean_qty) 
        
        # alternativní možnost: Převod čárky na tečku i u ceny, ať je to pro kopírování do brokera konzistentní
        clean_price = str(vals[2]).replace(',', '.').strip()
        # alternativní možnost: cena je s tečkou
        #clean_price = str(vals[2]).strip()
        self.real_price.delete(0, tk.END)
        self.real_price.insert(0, clean_price)

    def _on_buy_tree_hover(self, event):
        """Zobrazí tooltip s dodatečnými informacemi (nadbytek nebo poplatky)."""
        item = self.buy_tree.identify_row(event.y)
        if not item:
            self._last_hovered_buy_item = None
            self._hide_tooltip()
            return
            
        if item == getattr(self, '_last_hovered_buy_item', None): return
        self._last_hovered_buy_item = item
        
        values = self.buy_tree.item(item, "values")
        if not values:
            self._hide_tooltip()
            return
            
        ticker = str(values[0])
        
        if hasattr(self, '_buy_info_data') and ticker in self._buy_info_data:
            info = self._buy_info_data[ticker]
            
            if info["type"] == "fee":
                min_req = f"{info['min_req']:,.0f} Kč".replace(',', ' ')
                cur = info['currency']
                fee_val = IBKR_MIN_FEE_GBP if cur == "GBP" else IBKR_MIN_FEE_USD
                msg = f"{ticker}\n⚠️ Nákup zrušen kvůli poplatkům:\nAkcie je sice podvážená, ale aby\npoplatek ({fee_val} {cur}) nepřesáhl váš limit,\nmuseli byste nakoupit alespoň za {min_req}.\nPeníze byly přesunuty na další akcie."
                self._show_tooltip(msg)
            elif info["type"] == "excess" and info['czk'] > 1000 :
                excess_str = f"{info['qty']:.3f}".replace('.', ',')
                czk_str = f"{info['czk']:,.0f} Kč".replace(',', ' ')
                msg = f"{ticker}\nℹ️ Nadbytek v portfoliu:\nDržíte o {excess_str} ks více,\nnež odpovídá cílové váze\n(Hodnota nadbytku: {czk_str})."
                self._show_tooltip(msg)
                
        else:
            self._hide_tooltip()

    def add_manual_entry(self):
        t = self.real_ticker.get().strip()
        d = self.real_date.get().strip()
        q = self.real_qty.get().strip()
        p = self.real_price.get().strip()

        if not t or not q or not p:
            messagebox.showwarning("Chyba", "Vyplňte Ticker, Množství a Cenu.")
            return

        try:
            entered_qty = float(q.replace(",", "."))
            float(p.replace(",", "."))
            datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Chyba", "Neplatný formát čísel nebo data (RRRR-MM-DD).")
            return

        # 1. Zjištění původního návrhu z horní tabulky
        suggested_qty = 0.0
        for item in self.buy_tree.get_children():
            row_vals = self.buy_tree.item(item)['values']
            if str(row_vals[0]) == t:
                sq_str = str(row_vals[6]).replace('»', '').replace('«', '').replace(',', '.').strip()
                try: suggested_qty = float(sq_str)
                except: pass
                break
                
        # 2. Zjištění množství, které už je připraveno ve spodní tabulce ke schválení
        staged_qty = 0.0
        for item in self.staging_tree.get_children():
            row_vals = self.staging_tree.item(item)['values']
            if str(row_vals[0]) == t:
                staged_str = str(row_vals[2]).replace(',', '.').strip()
                try: staged_qty += float(staged_str)
                except: pass

        # 3. Výpočet reálného zbytku (Návrh - To co už čeká - To co zadávám teď)
        remaining = suggested_qty - staged_qty - entered_qty

        # Do čekací tabulky vkládáme vizuálně s čárkou
        self.staging_tree.insert("", "end", values=(t, d, q.replace('.', ','), p.replace('.', ','), "❌"))
        
        # Přepsání políčka pro případný další frakční nákup (s tečkou pro IBKR)
        self.real_qty.delete(0, tk.END)
        if remaining > 0.001:
            self.real_qty.insert(0, str(round(remaining, 3)))

    def import_ibkr_csv(self):
        filepath = filedialog.askopenfilename(
            title="Vyberte CSV výpis (Activity Statement) z Interactive Brokers",
            filetypes=(("CSV Soubory", "*.csv"), ("Všechny soubory", "*.*"))
        )
        if not filepath:
            return
            
        def safe_float(val):
            """Pomocná funkce pro bezpečný převod US formátu (IBKR)."""
            try:
                return float(str(val).replace(',', '').replace(' ', ''))
            except ValueError:
                return 0.0
            
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                reader = csv.reader(f)
                rows = list(reader)
                
            header_row = None
            for row in rows:
                if len(row) > 1 and row[0] == 'Trades' and row[1] == 'Header':
                    header_row = row
                    break
                    
            if not header_row:
                messagebox.showerror("Neznámý formát CSV", "Vybraný soubor zřejmě není podporovaný výpis z IBKR.\n\nAplikace aktuálně podporuje výhradně standardní 'Activity Statement' od brokera Interactive Brokers (v anglickém jazyce).")
                return
            
            try:
                idx_desc = header_row.index('DataDiscriminator')
                idx_asset = header_row.index('Asset Category')
                idx_sym = header_row.index('Symbol')
                idx_date = header_row.index('Date/Time')
                idx_qty = header_row.index('Quantity')
                idx_price = header_row.index('T. Price')
            except ValueError as e:
                messagebox.showerror("Chybný formát sloupců", f"Ve výpisu chybí očekávané sloupce (např. T. Price, Symbol, Date/Time).\nDetail: {e}")
                return

            known_symbols = list(TARGETS.keys()) + list(getattr(self, 'stock_db_from_json', DEFAULT_STOCK_DB).keys())
            
            def map_sym(s):
                if s in known_symbols: return s
                if s + ".L" in known_symbols: return s + ".L"
                if s + ".UK" in known_symbols: return s + ".UK"
                # Oprava pro IBKR - někdy k britským akciím přidá malé 'l' (např. LGENl -> LGEN.L)
                if s.endswith('l') and s[:-1] + ".L" in known_symbols: return s[:-1] + ".L"
                return s

            # --- EXTRAKCE DATA VYGENEROVÁNÍ REPORTU ---
            report_date = None
            for row in rows:
                if len(row) > 3 and row[0] == 'Statement' and row[1] == 'Data':
                    # Priorita 1: WhenGenerated (přesný čas snapshotu)
                    if row[2] == 'WhenGenerated':
                        date_part = row[3].split(',')[0].strip()
                        try:
                            report_date = datetime.strptime(date_part, "%Y-%m-%d").date()
                            break
                        except: pass
                    
                    # Priorita 2: Period (pokud WhenGenerated chybí, vezmeme konec období)
                    if row[2] == 'Period':
                        try:
                            # Formát: "January 1, 2026 - March 13, 2026"
                            period_str = row[3]
                            if '-' in period_str:
                                end_date_str = period_str.split('-')[1].strip()
                                # IBKR formát v Period: "March 13, 2026"
                                report_date = datetime.strptime(end_date_str, "%B %d, %Y").date()
                                break
                        except: pass
            
            # Pokud se datum nepodařilo najít, audit nebude validní
            if not report_date:
                messagebox.showwarning("Audit nelze provést", 
                    "V CSV výpisu chybí metadata o datu (WhenGenerated nebo Period).\n\n"
                    "Nákupy budou naimportovány, ale hloubková kontrola (Audit) "
                    "otevřených pozic bude přeskočena, protože aplikace neví, "
                    "k jakému dni má stav Ledgeru porovnat.")

            # --- KROK 1: Agregace nákupů a prodejů z CSV ---
            csv_aggregated_buys = {}
            csv_aggregated_sales = {}
            for row in rows:
                if len(row) > idx_price and row[0] == 'Trades' and row[1] == 'Data':
                    if row[idx_desc] == 'Order' and row[idx_asset] == 'Stocks':
                        qty_raw = safe_float(row[idx_qty])
                        price = safe_float(row[idx_price])
                        sym = map_sym(row[idx_sym])
                        date_str = row[idx_date].split(',')[0].strip()
                        try:
                            parsed_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
                        except ValueError:
                            parsed_date = date_str 
                        
                        key = (sym, parsed_date)
                        
                        # Kladné množství = Nákup
                        if qty_raw > 0: 
                            if key not in csv_aggregated_buys:
                                csv_aggregated_buys[key] = {'qty': 0.0, 'total_value': 0.0}
                            csv_aggregated_buys[key]['qty'] += qty_raw
                            csv_aggregated_buys[key]['total_value'] += qty_raw * price
                            
                        # Záporné množství = Prodej
                        elif qty_raw < 0:
                            abs_qty = abs(qty_raw)
                            if key not in csv_aggregated_sales:
                                csv_aggregated_sales[key] = {'qty': 0.0, 'total_value': 0.0}
                            csv_aggregated_sales[key]['qty'] += abs_qty
                            csv_aggregated_sales[key]['total_value'] += abs_qty * price

            # --- KROK 2A: Agregace existujících nákupů (Ledger + Staging + Prodeje) ---
            existing_aggregated_buys = {}
            for t, lots in self.ledger.items():
                for lot in lots:
                    d = lot.get("date")
                    q = safe_float(lot.get("qty", 0))
                    key = (t, d)
                    existing_aggregated_buys[key] = existing_aggregated_buys.get(key, 0.0) + q
                    
            for item in self.staging_tree.get_children():
                vals = self.staging_tree.item(item)['values']
                t = str(vals[0])
                d = str(vals[1])
                q = safe_float(str(vals[2]).replace(',', '.'))
                key = (t, d)
                existing_aggregated_buys[key] = existing_aggregated_buys.get(key, 0.0) + q

            for sale in self.sales_history:
                t = sale.get("ticker")
                d = sale.get("buy_date")
                q = safe_float(sale.get("qty", 0))
                key = (t, d)
                existing_aggregated_buys[key] = existing_aggregated_buys.get(key, 0.0) + q

            # --- KROK 2B: Agregace existujících prodejů (Sales History) ---
            existing_aggregated_sales = {}
            for sale in self.sales_history:
                t = sale.get("ticker")
                d = sale.get("sell_date")
                q = safe_float(sale.get("qty", 0))
                key = (t, d)
                existing_aggregated_sales[key] = existing_aggregated_sales.get(key, 0.0) + q

            # --- KROK 3A: Vložení chybějících nákupů do Staging fronty ---
            added_buys_count = 0
            for (t, d), data in csv_aggregated_buys.items():
                csv_qty = data['qty']
                csv_val = data['total_value']
                exist_qty = existing_aggregated_buys.get((t, d), 0.0)
                missing_qty = csv_qty - exist_qty
                
                if missing_qty > 0.0001:
                    avg_price = csv_val / csv_qty if csv_qty > 0 else 0.0
                    q_str = str(round(missing_qty, 4)).replace('.', ',')
                    p_str = str(round(avg_price, 4)).replace('.', ',')
                    self.staging_tree.insert("", "end", values=(t, d, q_str, p_str, "❌"))
                    added_buys_count += 1

            # --- KROK 3B: Automatické zpracování chybějících prodejů (metodou FIFO) ---
            missing_sales_to_execute =[]
            for (t, d), data in csv_aggregated_sales.items():
                csv_qty = data['qty']
                csv_val = data['total_value']
                exist_qty = existing_aggregated_sales.get((t, d), 0.0)
                missing_qty = csv_qty - exist_qty

                if missing_qty > 0.0001:
                    avg_price = csv_val / csv_qty if csv_qty > 0 else 0.0
                    missing_sales_to_execute.append({
                        'ticker': t,
                        'sell_date': d,
                        'qty': missing_qty,
                        'sell_price': avg_price
                    })

            added_sales_count = 0
            failed_sales =[]
            
            if missing_sales_to_execute:
                # Seřadíme chybějící prodeje chronologicky, aby FIFO fungovalo správně
                missing_sales_to_execute.sort(key=lambda x: x['sell_date'])
                
                for sale in missing_sales_to_execute:
                    t = sale['ticker']
                    rem_qty = sale['qty']
                    s_date = sale['sell_date']
                    s_price = sale['sell_price']

                    # Kontrola, zda máme v Ledgeru dostatek akcií k prodeji
                    current_held_qty = sum(safe_float(l['qty']) for l in self.ledger.get(t,[]))
                    if current_held_qty < rem_qty - 0.0001:
                        failed_sales.append(f"{t} ({rem_qty:g} ks)".replace('.', ','))
                        continue

                    # Seřazení Ledgeru před prodejem (pojistka pro přesné FIFO)
                    if t in self.ledger:
                        self.ledger[t].sort(key=lambda x: x.get("date", "1970-01-01"))

                    # Exekuce prodeje a přesun do sales_history
                    while rem_qty > 0.0001 and self.ledger.get(t):
                        lot = self.ledger[t][0]
                        lot_qty = safe_float(lot['qty'])
                        sold = min(lot_qty, rem_qty)

                        rem_qty -= sold
                        lot['qty'] = lot_qty - sold

                        self.sales_history.append({
                            "ticker": t,
                            "currency": self.get_currency_for_ticker(t),
                            "buy_date": lot['date'],
                            "sell_date": s_date,
                            "qty": sold,
                            "buy_price": safe_float(lot.get('price_at_buy', 0)),
                            "sell_price": s_price
                        })

                        # Pokud jsme lot celý vyprodali, odstraníme ho z Ledgeru
                        if lot['qty'] < 0.0001:
                            self.ledger[t].pop(0)

                    added_sales_count += 1
                
                # Pokud prošel aspoň jeden prodej, ihned uložíme změny a updatneme UI
                if added_sales_count > 0:
                    self.save_data()
                    self.update_lots_view()

            # --- KROK 3C: ZPRACOVÁNÍ SKUTEČNÝCH DIVIDEND A DANÍ Z CSV ---
            parsed_dividends = {}
            for row in rows:
                if len(row) > 5 and row[0] == 'Dividends' and row[1] == 'Data' and not row[2].startswith('Total'):
                    desc = row[4]
                    # Ignorovat úroky z hotovosti
                    if "Credit Interest" in desc or "Interest" in desc:
                        continue

                    currency = row[2]
                    date_str = row[3]
                    amount = safe_float(row[5])
                    
                    # Extrakce tickeru (např. "JNJ(US4781601046) Cash Dividend..." -> "JNJ")
                    raw_ticker = desc.split('(')[0].split(' ')[0].strip()
                    sym = map_sym(raw_ticker)
                    
                    key = (sym, date_str)
                    if key not in parsed_dividends:
                        parsed_dividends[key] = {'gross': 0.0, 'tax': 0.0, 'currency': currency}
                    parsed_dividends[key]['gross'] += amount

                elif len(row) > 5 and row[0] == 'Withholding Tax' and row[1] == 'Data' and not row[2].startswith('Total'):
                    desc = row[4]
                    # Ignorovat srážkovou daň z úroků na hotovosti
                    if "Credit Interest" in desc or "Interest" in desc or desc.startswith("Withholding @"):
                        continue

                    currency = row[2]
                    date_str = row[3]
                    amount = safe_float(row[5])
                    
                    raw_ticker = desc.split('(')[0].split(' ')[0].strip()
                    sym = map_sym(raw_ticker)
                    
                    key = (sym, date_str)
                    if key not in parsed_dividends:
                        parsed_dividends[key] = {'gross': 0.0, 'tax': 0.0, 'currency': currency}
                    # Daně jsou v CSV záporné, vezmeme absolutní hodnotu
                    parsed_dividends[key]['tax'] += abs(amount)

            # Příprava paměti a deduplikace zjištěných dividend
            if not hasattr(self, 'real_dividends'):
                self.real_dividends =[]
                
            added_divs = 0
            for (sym, date_str), data in parsed_dividends.items():
                # Zkontrolujeme, jestli přesně tuto výplatu v JSONu už nemáme
                exists = any(d['ticker'] == sym and d['date'] == date_str for d in self.real_dividends)
                if not exists:
                    self.real_dividends.append({
                        "ticker": sym,
                        "date": date_str,
                        "gross": data['gross'],
                        "tax": data['tax'],
                        "currency": data['currency']
                    })
                    added_divs += 1
            
            # Pokud jsme našli nové dividendy, rovnou je chronologicky seřadíme a zapíšeme do JSONu
            if added_divs > 0:
                self.real_dividends.sort(key=lambda x: x['date'])
                self.save_data()

            # =================================================================
            # KROK 3D: ZPĚTNÉ DOPLNĚNÍ PŘESNÝCH FX KURZŮ A POPLATKŮ Z CSV
            # =================================================================
            exact_fx = {'USD': {}, 'GBP': {}}
            exact_fees_buys = {}
            exact_fees_sales = {}
            idx_fee = header_row.index('Comm/Fee') if 'Comm/Fee' in header_row else -1

            # Bezpečné stažení aktuálních kurzů pro případ chybějících dat
            current_fx = self.get_fx_rates()

            for row in rows:
                # 1. Extrakce přesných FX kurzů vteřinu po vteřině (z Forex sekce)
                if len(row) > idx_price and row[0] == 'Trades' and row[1] == 'Data' and row[idx_asset] == 'Forex':
                    sym = row[idx_sym]
                    date_str = row[idx_date].split(',')[0].strip()
                    try: parsed_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
                    except: parsed_date = date_str
                    
                    price = safe_float(row[idx_price])
                    # Striktní shoda, aby se nám do USD nepletl měnový pár GBP.USD
                    if sym == 'USD.CZK': exact_fx['USD'][parsed_date] = price
                    elif sym == 'GBP.CZK': exact_fx['GBP'][parsed_date] = price

                # 2. Extrakce poplatků za jednotlivé akcie
                elif idx_fee != -1 and len(row) > max(idx_price, idx_fee) and row[0] == 'Trades' and row[1] == 'Data' and row[idx_asset] == 'Stocks':
                    sym = map_sym(row[idx_sym])
                    date_str = row[idx_date].split(',')[0].strip()
                    try: parsed_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
                    except: parsed_date = date_str
                    
                    qty_raw = safe_float(row[idx_qty])
                    # Broker uvádí poplatky do mínusu, bereme absolutní hodnotu
                    fee_val = abs(safe_float(row[idx_fee]))
                    
                    key = (sym, parsed_date)
                    if qty_raw > 0: exact_fees_buys[key] = exact_fees_buys.get(key, 0.0) + fee_val
                    elif qty_raw < 0: exact_fees_sales[key] = exact_fees_sales.get(key, 0.0) + fee_val

            # 3. Zpětné propsání do aktuálního Ledgeru
            for t, lots in self.ledger.items():
                curr = self.get_currency_for_ticker(t)
                for lot in lots:
                    d = lot['date']
                    key = (t, d)
                    
                    # Update FX
                    if d in exact_fx[curr]: 
                        lot['fx_rate'] = exact_fx[curr][d]
                    elif lot.get('fx_rate', 23.0) < 15.0:
                        lot['fx_rate'] = current_fx.get(curr, 23.0)
                    
                    # Update Poplatků (poměrné rozdělení, pokud byl lot rozdělen FIFO)
                    if key in exact_fees_buys:
                        total_csv_qty = csv_aggregated_buys.get(key, {}).get('qty', lot['qty'])
                        ratio = lot['qty'] / total_csv_qty if total_csv_qty > 0 else 1.0
                        lot['fee'] = exact_fees_buys[key] * ratio

            # 4. Zpětné propsání do historie prodejů (Sales History)
            for sale in self.sales_history:
                t = sale['ticker']
                curr = sale.get('currency', 'USD')
                b_date = sale['buy_date']
                s_date = sale['sell_date']
                
                # Update FX
                if b_date in exact_fx[curr]: 
                    sale['buy_fx_rate'] = exact_fx[curr][b_date]
                elif sale.get('buy_fx_rate', 23.0) < 15.0: 
                    sale['buy_fx_rate'] = current_fx.get(curr, 23.0)
                    
                if s_date in exact_fx[curr]: 
                    sale['sell_fx_rate'] = exact_fx[curr][s_date]
                elif sale.get('sell_fx_rate', 23.0) < 15.0: 
                    sale['sell_fx_rate'] = current_fx.get(curr, 23.0)
                
                # Update Poplatků
                b_key = (t, b_date)
                if b_key in exact_fees_buys:
                    total_buy_qty = csv_aggregated_buys.get(b_key, {}).get('qty', sale['qty'])
                    ratio = sale['qty'] / total_buy_qty if total_buy_qty > 0 else 1.0
                    sale['buy_fee'] = exact_fees_buys[b_key] * ratio
                    
                s_key = (t, s_date)
                if s_key in exact_fees_sales:
                    total_sell_qty = csv_aggregated_sales.get(s_key, {}).get('qty', sale['qty'])
                    ratio = sale['qty'] / total_sell_qty if total_sell_qty > 0 else 1.0
                    sale['sell_fee'] = exact_fees_sales[s_key] * ratio
                    
            self.save_data() # Uložení do JSONu

            # =================================================================
            # KROK 4: HLOUBKOVÝ AUDIT (Spustí se pouze, pokud známe datum reportu)
            # =================================================================
            audit_errors = []
            audit_performed = False

            if report_date:
                audit_performed = True

                # A) Načtení finálních pozic akcií přímo ze Statementu IBKR
                ibkr_positions = {}
                for row in rows:
                    # Očekáváme řádek: Open Positions,Data,Summary,Stocks,GBP,LGEN,2701.251,...
                    if len(row) > 6 and row[0] == 'Open Positions' and row[1] == 'Data' and row[2] == 'Summary' and row[3] == 'Stocks':
                        sym = map_sym(row[5])
                        qty = safe_float(row[6])
                        ibkr_positions[sym] = ibkr_positions.get(sym, 0.0) + qty

                app_positions = {}
                
                # 1. Započtení aktuálně držených (zbytkových) nákupů v Ledgeru
                for t, lots in self.ledger.items():
                    for lot in lots:
                        try:
                            lot_d = datetime.strptime(lot["date"], "%Y-%m-%d").date()
                            if lot_d <= report_date:
                                app_positions[t] = app_positions.get(t, 0.0) + safe_float(lot.get("qty", 0))
                        except: pass
                
                # 2. Započtení nákupů právě přidaných do fronty (Staging)
                for item in self.staging_tree.get_children():
                    vals = self.staging_tree.item(item)['values']
                    t = str(vals[0])
                    try:
                        st_d = datetime.strptime(str(vals[1]), "%Y-%m-%d").date()
                        if st_d <= report_date:
                            app_positions[t] = app_positions.get(t, 0.0) + safe_float(str(vals[2]).replace(',', '.'))
                    except: pass

                # 3. Započtení akcií, které jsme K DATU REPORTU vlastnili, ale prodali je AŽ POTÉ.
                # (Protože metoda FIFO tyto akcie z Ledgeru fyzicky odečítá, musíme je
                # pro zpětnou kontrolu přičíst zpět, abychom zrekonstruovali tehdejší stav.)
                for sale in self.sales_history:
                    try:
                        buy_d = datetime.strptime(sale["buy_date"], "%Y-%m-%d").date()
                        sell_d = datetime.strptime(sale["sell_date"], "%Y-%m-%d").date()
                        
                        # Podmínka: Akcie už byla nakoupena, ale ještě nebyla prodána
                        if buy_d <= report_date and sell_d > report_date:
                            t = sale["ticker"]
                            app_positions[t] = app_positions.get(t, 0.0) + safe_float(sale.get("qty", 0))
                    except: pass

                # C) Porovnání a detekce chyb
                # Projdeme všechny tickery, které se objevily buď v CSV nebo v naší evidenci
                all_audited_tickers = set(list(ibkr_positions.keys()) + list(app_positions.keys()))
                
                for t in all_audited_tickers:
                    ib_qty = ibkr_positions.get(t, 0.0)
                    app_qty = app_positions.get(t, 0.0)
                    
                    # Pokud je rozdíl větší než drobná zaokrouhlovací odchylka (0.001 ks)
                    if abs(ib_qty - app_qty) > 0.001:
                        diff = app_qty - ib_qty
                        # Přidána tečka do formátovacího předpisu (+,.3f)
                        # Výsledek vyrobí formát: +1,234.567 -> následně replace změní na +1 234,567
                        # Čísla naformátujeme individuálně, abychom nepoškodili tečku v názvu tickeru (t)
                        aq_s = f"{app_qty:,.3f}".replace(',', ' ').replace('.', ',')
                        iq_s = f"{ib_qty:,.3f}".replace(',', ' ').replace('.', ',')
                        df_s = f"{diff:+,.3f}".replace(',', ' ').replace('.', ',')
                        
                        # Složíme finální řádek, kde t zůstane v původním formátu
                        err_line = f"• {t}: V evidenci máte {aq_s}, broker hlásí {iq_s} (rozdíl {df_s} ks)"
                        audit_errors.append(err_line)

            # --- FINÁLNÍ ZOBRAZENÍ VÝSLEDKŮ UŽIVATELI ---
            import_msg = ""
            if added_buys_count > 0 or added_sales_count > 0 or added_divs > 0 or failed_sales:
                import_msg = "Nalezeno a zpracováno:\n"
                if added_buys_count > 0:
                    import_msg += f"• {added_buys_count} nových nákupů (čekají dole na potvrzení)\n"
                if added_sales_count > 0:
                    import_msg += f"• {added_sales_count} nových prodejů (automaticky zapsáno pomocí FIFO)\n"
                if added_divs > 0:
                    import_msg += f"• {added_divs} záznamů o dividendách a daních (automaticky uloženo)\n"
                
                # Zobrazení případného varování u prodejů
                if failed_sales:
                    import_msg += "\n❌ Následující prodeje nešlo zpracovat (nemáte evidován dostatek akcií):\n"
                    for fs in failed_sales:
                        import_msg += f"   - {fs}\n"
                    import_msg += "-> Zapište nejprve nákupy z čekací fronty a zopakujte import.\n"
            else:
                import_msg = "Ve výpisu nebyly nalezeny žádné nové nákupy, prodeje ani dividendy k importu."

            if not audit_performed:
                messagebox.showinfo("Výsledek importu", import_msg + "\n\n(Audit pozic nebyl proveden kvůli chybějícímu datu v CSV.)")
            elif audit_errors:
                audit_msg = ("\n\n⚠️ UPOZORNĚNÍ - AUDIT POZIC NAŠEL NESROVNALOSTI:\n"
                             f"Váš stav k {report_date.strftime('%d.%m.%Y')} neodpovídá brokerovi:\n\n" + 
                             "\n".join(audit_errors))
                messagebox.showwarning("Výsledek importu a auditu", import_msg + audit_msg)
            else:
                success_msg = f"\n\n✅ AUDIT POŘÁDKU: Vaše evidence k {report_date.strftime('%d.%m.%Y')} přesně odpovídá brokerovi."
                messagebox.showinfo("Výsledek importu", import_msg + success_msg)

            # Jakmile uživatel odklikne výsledek importu, okamžitě zrestartujeme grafy statistik, aby obsahovaly nově přidané poplatky
            self.start_incremental_refresh()

        except Exception as e:
            messagebox.showerror("Chyba při čtení", f"Při zpracování CSV souboru došlo k nečekané chybě.\n\nDetail: {e}")
            
    def delete_staging_row(self, event):
        item = self.staging_tree.selection()
        if item: self.staging_tree.delete(item)

    def commit_staging_to_ledger(self):
        rows = self.staging_tree.get_children()
        if not rows:
            messagebox.showinfo("Info", "Žádné položky k uložení.")
            return

        count = 0
        fx_rates = self.get_fx_rates() # Získání aktuálních kurzů pro ruční nákupy
        
        for item in rows:
            vals = self.staging_tree.item(item)['values']
            ticker = vals[0]
            date_str = vals[1]
            qty = float(str(vals[2]).replace(",", "."))
            price = str(vals[3]).replace(",", ".") 

            if ticker not in self.ledger: self.ledger[ticker] = []
            
            # Uložení FX kurzu v době nákupu a prázdného poplatku (bude upraveno z CSV)
            curr = self.get_currency_for_ticker(ticker)
            fx_val = fx_rates.get(curr, 23.0)
            
            self.ledger[ticker].append({
                "date": date_str, 
                "qty": qty, 
                "price_at_buy": price,
                "fx_rate": fx_val,
                "fee": 0.0  # Poplatek v původní měně (např. USD)
            })
            count += 1

        # Před uložením musíme celý ledger pro každý ticker znovu seřadit podle data,
        # protože nově importované nákupy mohly být do seznamu připojeny mimo chronologické pořadí.
        for t in self.ledger:
            self.ledger[t].sort(key=lambda x: x.get("date", "1970-01-01"))

        self.save_data()
        for item in rows: self.staging_tree.delete(item)
            
        self.update_lots_view()
        threading.Thread(target=self.refresh_dividends, daemon=True).start()
        messagebox.showinfo("Úspěch", f"Úspěšně zapsáno {count} obchodů do portfolia.")

    def analyze_historical_data(self):
        """
        Robustní statistický modul. Analyzuje historii nákupů v JSON ledgeru pro odhad 
        středního měsíčního vkladu, trendu jeho růstu a kombinuje pětiletou historii 
        portfolia s konsenzem analytiků pro odhad budoucího ročního zhodnocení.
        """

        # --- 1. ODHAD PRAVIDELNÉHO MĚSÍČNÍHO VKLADU A JEHO TRENDU ---
        median_deposit = None
        deposit_growth = 0.03 # Výchozí konzervativní odhad růstu vkladů / inflace (3 %)
        
        all_purchases = []
        
        # 1. Zahrnutí aktuálně držených akcií (Ledger)
        for ticker, lots in self.ledger.items():
            p_factor = 0.01 if ticker.endswith('.L') else 1.0
            for lot in lots:
                try:
                    dt = pd.to_datetime(lot['date'])
                    qty = float(lot['qty'])
                    price = float(lot['price_at_buy'])
                    fx_rate = float(lot.get('fx_rate', 23.0))
                    czk_val = qty * price * p_factor * fx_rate
                    all_purchases.append({'date': dt, 'czk': czk_val})
                except:
                    pass

        # 2. Zahrnutí nákupů u akcií, které už byly prodány.
        # Při prodeji (FIFO) se nákupní loty z Ledgeru fyzicky mažou. Pokud bychom je zde 
        # nedohledali v historii prodejů, po masivním odprodeji by si appka myslela, 
        # že jste v minulosti peníze vůbec nevkládali a predikce by se zhroutila.
        for sale in self.sales_history:
            ticker = sale.get('ticker', '')
            p_factor = 0.01 if ticker.endswith('.L') else 1.0
            try:
                # Použijeme buy_date a buy_price, protože zkoumáme vaše vklady, nikoliv výdělky z prodeje
                dt = pd.to_datetime(sale['buy_date'])
                qty = float(sale['qty'])
                price = float(sale['buy_price'])
                
                # U prodaných akcií máme chytře uložen původní buy_fx_rate
                fx_rate = float(sale.get('buy_fx_rate', 23.0))
                czk_val = qty * price * p_factor * fx_rate
                all_purchases.append({'date': dt, 'czk': czk_val})
            except:
                pass

        # Pokud v ledgeru existují obchody, provedeme očištění dat
        if all_purchases:
            df = pd.DataFrame(all_purchases)
            df['year_month'] = df['date'].dt.to_period('M')
            monthly_sums = df.groupby('year_month')['czk'].sum()
            
            # Statisticky významné množství dat definujeme jako alespoň 6 měsíců historie
            if len(monthly_sums) >= 6:
                # Rekonstrukce kompletní měsíční osy od prvního do posledního nákupu (vč. prázdných měsíců)
                full_range = pd.period_range(start=monthly_sums.index.min(), end=monthly_sums.index.max(), freq='M')
                monthly_sums = monthly_sums.reindex(full_range, fill_value=0.0)
                
                # IQR Filtrace: Odstraníme měsíce s nulou a vyřadíme extrémní ojedinělé obří vklady (outliery)
                active_months = monthly_sums[monthly_sums > 100] 
                if len(active_months) >= 4:
                    q1 = active_months.quantile(0.25)
                    q3 = active_months.quantile(0.75)
                    iqr = q3 - q1
                    upper_bound = q3 + 1.5 * iqr
                    
                    filtered_sums = monthly_sums[monthly_sums <= upper_bound]
                    
                    # Robustní střední hodnota pravidelného vkladu (medián z očištěných aktivních měsíců)
                    valid_active = filtered_sums[filtered_sums > 100]
                    if not valid_active.empty:
                        median_deposit = float(valid_active.median())
                    
                    # Odhad růstového trendu vkladů pomocí lineární regrese nad očištěnými daty
                    if len(filtered_sums) >= 6:
                        x = np.arange(len(filtered_sums))
                        y = filtered_sums.values
                        slope, intercept = np.polyfit(x, y, 1)
                        
                        if median_deposit and median_deposit > 0:
                            monthly_growth_rate = slope / median_deposit
                            annual_growth_rate = (1 + monthly_growth_rate) ** 12 - 1
                            # Bezpečné dlouhodobé ohraničení (tempo růstu vkladů omezíme na 0 % až 10 % p.a.)
                            deposit_growth = float(np.clip(annual_growth_rate, 0.0, 0.10))

        # FALLBACK: Pokud nemáme dostatek dat, použijeme aktuální hodnotu z textového pole kalkulátoru
        if median_deposit is None or median_deposit < 500:
            try:
                median_deposit = float(self.cash_entry.get().replace(',', '.'))
            except:
                median_deposit = 20000.0 # Absolutní nouzový vklad v Kč

        # --- 2. ODHAD BUDOUCÍHO RŮSTU PORTFOLIA (CAGR + ANALYTICI) ---
        portfolio_growth = 0.075 # Výchozí konzervativní odhad (7.5 % p.a.)
        
        # Pokud máme v paměti stažená historická a fundamentální data z karty Tuner
        if getattr(self, 'tuner_data_loaded', False) and hasattr(self, 'tuner_stock_growths'):
            hist_cagrs = []
            weights = []
            
            for i, t in enumerate(self.ordered_tickers):
                w = TARGETS.get(t, 0.0)
                weights.append(w)
                
                # Zjištění 5letého zhodnocení akcie ze stažených dat
                start_to_end_ratio = self.tuner_stock_growths[i]
                if start_to_end_ratio > 0:
                    growth_mult_5y = 1.0 / start_to_end_ratio
                    cagr = (growth_mult_5y ** 0.2) - 1.0 # Přepočet na roční CAGR
                else:
                    cagr = 0.06 # fallback 6%
                hist_cagrs.append(cagr)
                
            weights = np.array(weights)
            if np.sum(weights) > 0:
                weights = weights / np.sum(weights)
                
                # Vážený průměr historie a vážený průměr 1y odhadů analytiků (upsides)
                weighted_hist_cagr = np.sum(weights * np.array(hist_cagrs))
                weighted_analyst_cagr = np.sum(weights * self.tuner_upsides)
                
                # Kombinace: 80 % dáváme reálné pětileté historii, 20 % dáváme konsenzu analytiků
                calculated_growth = 0.8 * weighted_hist_cagr + 0.2 * weighted_analyst_cagr
                # Bezpečné zastropování celého portfolia pro reálné dlouhodobé plánování (4 % až 30 % p.a.)
                portfolio_growth = float(np.clip(calculated_growth, 0.04, 0.30))
        else:
            # Data nejsou načtena. Pokud ještě neběží stahování na pozadí, bezpečně ho nastartujeme pod zámkem
            if hasattr(self, '_preload_thread_lock'):
                with self._preload_thread_lock:
                    if not self.tuner_preloading:
                        self.tuner_preloading = True
                        threading.Thread(target=self._async_preload_worker, daemon=True).start()


        return {
            "monthly_deposit": median_deposit,
            "deposit_growth": deposit_growth,
            "portfolio_growth": portfolio_growth
        }

    def _async_preload_worker(self):
        """
        Asynchronní worker běžící na pozadí. Tiše stáhne 5letou historii,
        dynamicky spočítá dividendové výnosy z historie dividend a uloží
        analytické cíle pro všechny aktivní akcie do paměti.
        Využije se pro rychlou aktualizaci tooltipu na záložce nákupů
        (odhad času dosažení cílového pasivního příjmu)
        """
        try:
            tickers = list(TARGETS.keys())
            if not tickers:
                return

            # 1. Stažení pětiletých dat pro akcie a index S&P 500
            all_to_download = tickers + ["SPY"]
            downloaded = self._safe_yf_download(all_to_download, period="5y")
            
            if downloaded.empty or 'Close' not in downloaded:
                return
                
            full_raw_data = downloaded['Close'].replace(0.0, np.nan)
            data = full_raw_data[tickers].ffill().bfill()
            
            # Výpočet start/end poměrů pro CAGR
            rel_start_prices = (data.iloc[0] / data.iloc[-1])
            ordered_tickers = rel_start_prices.index.tolist()
            tuner_stock_growths = rel_start_prices.values
            
            # 2. Dynamický výpočet dividendových výnosů (stejně jako v hlavním tuneru)
            div_yields = {}
            today_date = datetime.now().date()
            current_year = today_date.year
            end_of_year = date(current_year, 12, 31)

            for t in ordered_tickers:
                meta = getattr(self, 'stock_db_from_json', DEFAULT_STOCK_DB).get(t, {})
                if meta.get("sector") == "ETF" and meta.get("etf_type") == "Acc":
                    div_yields[t] = 0.0
                    continue

                dy = (meta.get("yield", 0.0) / 100.0) # Výchozí statický yield
                try:
                    hist_divs = self._safe_get_dividends(t)
                    if not hist_divs.empty:
                        divs_current = hist_divs[hist_divs.index.year == current_year]
                        divs_last = hist_divs[hist_divs.index.year == current_year - 1]
                        
                        total_div_local = sum(divs_current)
                        confirmed_months = [d.date().month for d in divs_current.index]
                        for d_date, amount in divs_last.items():
                            try:
                                proj_date = d_date.date().replace(year=current_year)
                            except:
                                proj_date = d_date.date() + timedelta(days=365)
                            
                            if proj_date.month not in confirmed_months:
                                total_div_local += amount
                        
                        curr_price = float(data[t].iloc[-1])
                        if curr_price > 0:
                            calc_dy = total_div_local / curr_price
                            if 0 < calc_dy <= 0.25:
                                dy = calc_dy
                except Exception as ex:
                    print(f"[!] Výpočet živého dividendového výnosu selhal pro {t}: {ex}")
                div_yields[t] = dy
            
            # 3. Stažení fundamentů a výpočet zdaněných/bezpečných dividend
            upsides = []
            safe_divs = []
            tuner_fundamentals = {}
            
            # --- VÝPOČET ČASOVÉHO KROKU PRO EWMA FILTR ---
            now = datetime.now()
            last_update_str = getattr(self, 'last_growth_update', None)
            if last_update_str:
                try:
                    last_update_date = datetime.fromisoformat(last_update_str)
                    delta_days = (now - last_update_date).total_seconds() / 86400.0
                except:
                    delta_days = 1.0
            else:
                delta_days = 1.0 # Výchozí krok pro iniciální start filtru
                
            delta_days = max(0.0, min(delta_days, 365.0)) # Ochrana před nesmyslnými časovými skoky
            # Výpočet exponenciálního tlumícího faktoru závislého na čase (poločas = EWMA_HALF_LIFE_DAYS)
            decay_factor = math.exp(-delta_days * (math.log(2) / EWMA_HALF_LIFE_DAYS))
            
            for t in ordered_tickers:
                fund = self._safe_get_fundamentals(t)
                sector = getattr(self, 'stock_db_from_json', DEFAULT_STOCK_DB).get(t, {}).get("sector", "Unknown")
                
                raw_yield = div_yields.get(t, 0.0)
                payout = fund['payout_ratio']
                
                # Výpočet bezpečné dividendy s ohledem na srážkovou daň a payout ratio
                safe_yield, payout, limit = self._evaluate_dividend_safety(sector, raw_yield, payout)
                safe_divs.append(safe_yield)
                
                tuner_fundamentals[t] = {
                    "payout_ratio": payout,
                    "raw_yield": raw_yield,
                    "safe_yield": safe_yield,
                    "limit": limit,
                    "pe_ratio": fund.get('pe_ratio'),
                    "eps": fund.get('eps'),
                    "beta": fund.get('beta'),
                    "recommendation": fund.get('recommendation')
                }
                
                # 1. Výpočet aktuálního živého růstu (více se opíráme o 5Y historii CAGR, méně o volatilní odhady)
                idx = ordered_tickers.index(t)
                hist_growth_ratio = 1.0 / tuner_stock_growths[idx] if tuner_stock_growths[idx] > 0 else 1.0
                cagr_5y = (hist_growth_ratio ** (1/5.0)) - 1.0 if hist_growth_ratio > 0 else 0.0
                
                tp = fund['target_price']
                cp = fund['current_price']
                analyst_ups = (tp / cp) - 1.0 if (tp and cp and cp > 0) else cagr_5y
                
                if analyst_ups < 0 and cagr_5y > 0.15:
                    live_ups = cagr_5y * 0.8 
                elif analyst_ups < 0 and cagr_5y > 0.05:
                    live_ups = max(analyst_ups * 0.2 + cagr_5y * 0.8, 0.0) 
                else:
                    live_ups = (analyst_ups * 0.3) + (cagr_5y * 0.7)

                # 2. APLIKACE ČASOVĚ ZÁVISLÉHO EWMA FILTRU
                now = datetime.now()
                last_update_str = getattr(self, 'last_growth_update', None)
                if last_update_str:
                    try:
                        delta_days = max(0.0, min((now - datetime.fromisoformat(last_update_str)).total_seconds() / 86400.0, 365.0))
                    except: delta_days = 1.0
                else: delta_days = 1.0
                decay_factor = math.exp(-delta_days * (math.log(2) / EWMA_HALF_LIFE_DAYS))

                db_meta = getattr(self, 'stock_db_from_json', {}).get(t, {})
                if "growth" in db_meta and last_update_str is not None:
                    saved_growth = db_meta["growth"] / 100.0
                    smoothed_ups = (saved_growth * decay_factor) + (live_ups * (1.0 - decay_factor))
                else:
                    smoothed_ups = live_ups
                    
                upsides.append(smoothed_ups)
                
            # 4. Bezpečné uložení výsledků do instance pro ostatní části aplikace
            self.ordered_tickers = ordered_tickers
            self.tuner_stock_growths = tuner_stock_growths
            self.tuner_stock_divs = np.array([div_yields.get(t, 0.03) for t in ordered_tickers])
            self.tuner_upsides = np.array(upsides)
            self.tuner_safe_divs = np.array(safe_divs)
            self.tuner_fundamentals = tuner_fundamentals
            
            # --- ULOŽENÍ ČERSTVÝCH DAT DO JSON DATABÁZE ---
            self.last_growth_update = datetime.now().isoformat()
            if hasattr(self, 'stock_db_from_json'):
                for i, t in enumerate(ordered_tickers):
                    if t in self.stock_db_from_json:
                        if self.stock_db_from_json[t].get("sector") == "ETF" and self.stock_db_from_json[t].get("etf_type") == "Acc":
                            self.stock_db_from_json[t]['yield'] = 0.0
                        else:
                            self.stock_db_from_json[t]['yield'] = round(float(div_yields.get(t, 0.0)) * 100.0, 4)
                        self.stock_db_from_json[t]['growth'] = round(float(upsides[i]) * 100.0, 4)
                self.save_data()
            
            # --- JEDNORÁZOVÁ AKTUALIZACE PRO DYNAMICKÝ TOOLTIP ---
            # 1. Výpočet aktuálního nominálního výnosu z čerstvě stažených cen
            temp_yield_sum = 0.0
            for t in TARGETS.keys():
                w = TARGETS.get(t, 0.0)
                dy = div_yields.get(t, 0.0)
                temp_yield_sum += w * dy
            self.last_nominal_yield = temp_yield_sum if temp_yield_sum > 0 else 0.04

            # --- DYNAMICKÁ AKTUALIZACE SLIDERU NA ZÁLOŽCE NÁKUP (ihned po stažení živých dat) ---
            if hasattr(self, 'dyn_floor_slider'):
                max_slider_val = round(self.last_nominal_yield * 100, 2)
                if max_slider_val < 0.5: max_slider_val = 5.0
                # Musíme volat přes .after(0), abychom bezpečně sáhli na UI z pracovního vlákna
                self.root.after(0, lambda v=max_slider_val: self.dyn_floor_slider.config(to=v))

            # 2. Výpočet aktuální hodnoty portfolia v CZK
            fx_rates = self.get_fx_rates()
            temp_portfolio_val = 0.0
            for t in tickers:
                qty_now = sum(l['qty'] for l in self.ledger.get(t, []))
                if qty_now > 0:
                    try:
                        price = float(data[t].iloc[-1])
                        if t.endswith(".L"): 
                            price /= 100.0
                        curr = self.get_currency_for_ticker(t)
                        temp_portfolio_val += qty_now * price * fx_rates.get(curr, 23.0)
                    except:
                        pass
            self.last_portfolio_value_czk = temp_portfolio_val
            
            # Označení, že data jsou kompletně připravena
            self.tuner_data_loaded = True 
            
        except Exception as e:
            print(f"[!] Chyba asynchronního načítání dat: {e}")
            
        finally:
            # Vždy bezpečně uvolníme příznak stahování pod zámkem, aby se dalo v budoucnu spustit znovu
            if hasattr(self, '_preload_thread_lock'):
                with self._preload_thread_lock:
                    self.tuner_preloading = False
            else:
                self.tuner_preloading = False

    def estimate_years_to_target(self, current_val, target_val, monthly_deposit, portfolio_growth, deposit_growth):
        """Vypočítá odhadovaný čas v letech do dosažení cílové hodnoty portfolia."""
        if current_val >= target_val:
            return 0.0
        if monthly_deposit <= 0 and current_val <= 0:
            return float('inf')
            
        val = current_val
        dep = monthly_deposit
        months = 0
        
        # Maximální limit 50 let pro zamezení případného zacyklení
        while val < target_val and months < 600:
            # Měsíční složené úročení portfolia + měsíční vklad
            val = val * (1 + portfolio_growth / 12) + dep
            
            # Každý rok navýšíme pravidelný vklad o vypočtené tempo růstu (inflaci/trend)
            if months % 12 == 0 and months > 0:
                dep *= (1 + deposit_growth)
            months += 1
            
        return months / 12.0

    def get_dyn_abs_tooltip_text(self):
        """Generuje dynamický text tooltipu pro cílový pasivní příjem s predikcí."""
        try:
            # Načtení zadané čisté renty z UI
            abs_target_net_czk = float(self.dyn_abs_entry.get().replace(' ', '').replace(',', '.'))
        except:
            abs_target_net_czk = getattr(self, 'dyn_abs_div', 500000.0)
            
        # Přepočet na hrubou rentu (před 15% srážkovou daní v ČR)
        abs_target_gross_czk = abs_target_net_czk / (1 - DEFAULT_TAX_RATE) 
        
        # Spuštění statistické analýzy
        stats = self.analyze_historical_data()
        
        # Načtení aktuální hodnoty portfolia
        curr_val_czk = getattr(self, 'last_portfolio_value_czk', 0.0)
        # Pokud je hodnota nula (čerstvý start), zrekonstruujeme ji aspoň z nákupních nákladů v ledgeru
        if curr_val_czk == 0.0:
            for t, lots in self.ledger.items():
                p_factor = 0.01 if t.endswith('.L') else 1.0
                for lot in lots:
                    try:
                        curr_val_czk += float(lot['qty']) * float(lot['price_at_buy']) * p_factor * float(lot.get('fx_rate', 23.0))
                    except:
                        pass
                        
        nom_yield = getattr(self, 'last_nominal_yield', 0.04) 
        
        # Výpočet cílové hodnoty portfolia, abychom při daném výnosu bezpečně vygenerovali rentu
        target_val_czk = abs_target_gross_czk / nom_yield if nom_yield > 0 else 0.0

        # Výpočet aktuálního procenta splnění cílové hodnoty
        achieved_pct = (curr_val_czk / target_val_czk * 100) if target_val_czk > 0 else 0.0
        
        # Výpočet predikce
        years = self.estimate_years_to_target(
            current_val=curr_val_czk,
            target_val=target_val_czk,
            monthly_deposit=stats["monthly_deposit"],
            portfolio_growth=stats["portfolio_growth"],
            deposit_growth=stats["deposit_growth"]
        )
        
        # Formátování výstupu pro českého uživatele (tisíce oddělené mezerou, desetiny čárkou)
        target_net_str = f"{abs_target_net_czk:,.0f}".replace(',', ' ')
        target_gross_str = f"{abs_target_gross_czk:,.0f}".replace(',', ' ')
        target_val_str = f"{target_val_czk:,.0f}".replace(',', ' ')
        curr_val_str = f"{curr_val_czk:,.0f}".replace(',', ' ')
        monthly_dep_str = f"{stats['monthly_deposit']:,.0f}".replace(',', ' ')

        # Převedení desetinných teček na české čárky
        achieved_pct_str = f"{achieved_pct:.1f}".replace('.', ',')
        nom_yield_str = f"{nom_yield*100:.1f}".replace('.', ',')
        dep_growth_str = f"{stats['deposit_growth']*100:.1f}".replace('.', ',')
        port_growth_str = f"{stats['portfolio_growth']*100:.1f}".replace('.', ',')
        
        if years == 0.0:
            pred_str = "Dosaženo! 🎉 Vaše portfolio již tento cíl splňuje."
        elif years == float('inf'):
            pred_str = "Nelze spočítat (chybí vklady)."
        elif years < 1.0:
            months = round(years * 12)
            pred_str = f"Odhadovaný čas: cca {months} měsíců"
        else:
            years_cz = f"{years:.1f}".replace('.', ',')
            pred_str = f"Odhadovaný čas: {years_cz} let"
            
        tooltip_text = (
            f"🎯 Predikce dosažení cílové roční dividendové renty\n"
            f"───────────────────────────────────\n"
            f"• Požadovaná čistá renta: {target_net_str} / rok\n"
            f"• Cílová hodnota portfolia: {target_val_str} (při yieldu {nom_yield_str} %)\n"
            f"• Současná hodnota portfolia: {curr_val_str} ({achieved_pct_str} % z cíle)\n"
            f"• Analyzovaný pravidelný vklad: {monthly_dep_str} / měsíc\n"
            f"• Růst vkladů p.a.: {stats['deposit_growth']*100:.1f} % (inflace / trend)\n"
            f"• Očekávané zhodnocení akcií: {stats['portfolio_growth']*100:.1f} % p.a. (historie + analytici)\n"
            f"───────────────────────────────────\n"
            f"📈 {pred_str}"
        )
        return tooltip_text

    # --------------------------------------------------------------------------
    # TAB 2: SPRÁVA POZIC A PRODEJŮ (PRODEJ & LEDGER)
    # --------------------------------------------------------------------------

    def setup_sell_tab(self):
        frame = tk.Frame(self.notebook, bg="#fff")
        self.notebook.add(frame, text="Prodej & Ledger")

        # --- HORNÍ PANEL: Kalkulátory a Ruční editace ---
        top_panel = tk.Frame(frame, bg="#fff")
        top_panel.pack(fill=tk.X, padx=10, pady=5)

        # 1. Kalkulátor výběru hotovosti
        calc_frame = tk.LabelFrame(top_panel, text="1. Návrh prodeje pro výběr hotovosti", padx=10, pady=10, font=("Arial", 12, "bold"), bg="#E8F5E9")
        calc_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        tk.Label(calc_frame, text="Částka k výběru (Kč):", font=("Arial", 12), bg="#E8F5E9").grid(row=0, column=0, padx=5)
        self.withdraw_entry = tk.Entry(calc_frame, width=12, font=("Arial", 12))
        self.withdraw_entry.grid(row=0, column=1, padx=5)
        self.withdraw_entry.insert(0, "50000")

        self.btn_calc_sale = tk.Button(calc_frame, text="Spočítat návrh", command=self.start_calculate_withdrawal, bg="#2E7D32", fg="white", font=("Arial", 12, "bold"))
        self.btn_calc_sale.grid(row=0, column=2, padx=10)

        # 2. NOVÝ: Kalkulátor pro rebalancování portfolia (zohledňuje nastavení brzdy)
        rebal_frame = tk.LabelFrame(top_panel, text="2. Návrh prodeje pro rebalancování", padx=10, pady=10, font=("Arial", 12, "bold"), bg="#FFF3E0")
        rebal_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        tk.Label(rebal_frame, text="Srovná nadbytečné pozice s cílem.", font=("Arial", 12), bg="#FFF3E0").grid(row=0, column=0, padx=5)
        self.btn_calc_rebal = tk.Button(rebal_frame, text="Spočítat rebalancování", command=self.start_calculate_rebalancing, bg="#E65100", fg="white", font=("Arial", 12, "bold"))
        self.btn_calc_rebal.grid(row=0, column=1, padx=10)

        # 3. Ruční zadání / Úprava ceny (přejmenováno z 2 na 3)
        manual_frame = tk.LabelFrame(top_panel, text="3. Ruční zadání / Úprava ceny", padx=10, pady=10, font=("Arial", 12, "bold"), bg="#E3F2FD")
        manual_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(manual_frame, text="Ticker:", font=("Arial", 12), bg="#E3F2FD").grid(row=0, column=0)
        self.sell_ticker = ttk.Combobox(manual_frame, values=list(TARGETS.keys()), width=8, font=("Arial", 12))
        self.sell_ticker.grid(row=0, column=1, padx=5)

        tk.Label(manual_frame, text="Kusy:", font=("Arial", 12), bg="#E3F2FD").grid(row=0, column=2)
        self.sell_qty = tk.Entry(manual_frame, width=8, font=("Arial", 12))
        self.sell_qty.grid(row=0, column=3, padx=5)

        tk.Label(manual_frame, text="Cena:", font=("Arial", 12), bg="#E3F2FD").grid(row=0, column=4)
        self.sell_price_entry = tk.Entry(manual_frame, width=8, font=("Arial", 12))
        self.sell_price_entry.grid(row=0, column=5, padx=5)
        
        self.sell_price_entry.bind("<Return>", self._on_sell_price_enter)

        tk.Button(manual_frame, text="Stáhnout", command=self.fetch_sell_price, font=("Arial", 12)).grid(row=0, column=6, padx=5)
        tk.Button(manual_frame, text="↓ Přidat / Upravit", command=self.add_to_sell_staging, bg="#1565C0", fg="white", font=("Arial", 12, "bold")).grid(row=0, column=7, padx=5)
        tk.Label(manual_frame, text="(Klikni na řádek v seznamu níže pro rychlou úpravu)", bg="#E3F2FD", fg="grey", font=("Arial", 10)).grid(row=1, column=0, columnspan=8, pady=(5,0))

        # --- STŘEDNÍ PANEL: Tabulka k prodeji (Staging) ---
        # expand=True pro tuto tabulku, takže zabere dostupné místo
        staging_frame = tk.LabelFrame(frame, text="3. Seznam připravených prodejů", padx=10, pady=5, font=("Arial", 12, "bold"), bg="#fff")
        staging_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Červené tlačítko zabalíme úplně dolů
        btn_bar = tk.Frame(staging_frame, bg="#fff")
        btn_bar.pack(side=tk.BOTTOM, pady=10)
        tk.Button(btn_bar, text="💾 Uložit všechny prodeje ze seznamu do portfolia (FIFO)", command=self.execute_sale, font=("Arial", 14, "bold"), bg="#C62828", fg="white", padx=20).pack()

        # Kontejner pro strom a posuvník (Odděluje posuvník od červeného tlačítka)
        tree_container = tk.Frame(staging_frame, bg="#fff")
        tree_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        staging_scroll = ttk.Scrollbar(tree_container, orient="vertical")
        staging_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.sell_staging_tree = ttk.Treeview(tree_container, columns=("Ticker", "Množství", "Cena [USD/GBP]", "Odhad [CZK]", "Smazat"), show="headings", height=8, yscrollcommand=staging_scroll.set)
        for c, w in {"Ticker": 100, "Množství": 150, "Cena [USD/GBP]": 150, "Odhad [CZK]": 150, "Smazat": 100}.items():
            self.sell_staging_tree.heading(c, text=c)
            self.sell_staging_tree.column(c, width=w, anchor="center")

        self.sell_staging_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        staging_scroll.config(command=self.sell_staging_tree.yview)

        # Propojení tabulky s akcemi
        self.sell_staging_tree.bind("<<TreeviewSelect>>", self.fill_entry_from_sell_staging)
        self.sell_staging_tree.bind("<Double-1>", self.delete_sell_staging_row)
        # Mazání klávesou Delete
        self.sell_staging_tree.bind("<Delete>", self.delete_sell_staging_row)

        # --- SPODNÍ PANEL: Ledger (Aktuální stav) ---
        # expand=False (neporoste při maximalizaci okna)
        ledger_frame = tk.LabelFrame(frame, text="4. Aktuální stav portfolia (ledger)", padx=10, pady=5, font=("Arial", 12, "bold"), bg="#fff")
        ledger_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=5)

        top_ledger_bar = tk.Frame(ledger_frame, bg="#fff")
        top_ledger_bar.pack(fill=tk.X)
        tk.Button(top_ledger_bar, text="↻ Aktualizovat seznam", command=self.update_lots_view, font=("Arial", 12)).pack(side=tk.RIGHT, pady=5)

        tree_scroll = ttk.Scrollbar(ledger_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.lots_tree = ttk.Treeview(ledger_frame, columns=("Ticker", "Datum", "Množství", "Nákupní cena[GBP/USD]", "Daň"), show="headings", height=6, yscrollcommand=tree_scroll.set)
        for c in ("Ticker", "Datum", "Množství", "Nákupní cena[GBP/USD]", "Daň"):
            self.lots_tree.heading(c, text=c)
            self.lots_tree.column(c, anchor="center")

        self.lots_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.lots_tree.yview)

        self.update_lots_view()
        
        self.sell_loading_state = self._create_loading_card(frame)

    def update_lots_view(self):
        self.lots_tree.delete(*self.lots_tree.get_children())
        now = datetime.now()
        try:
            three_years_ago = now.replace(year=now.year - 3)
        except ValueError:
            three_years_ago = now.replace(year=now.year - 3, day=28)
        
        for t in TARGETS.keys():
            lots = self.ledger.get(t,[])
            if not lots:
                self.lots_tree.insert("", "end", values=(t, "Žádné nákupy", "0", "-", "-"))
                continue
                
            for lot in lots:
                try:
                    s = "OSVOBOZENO" if datetime.strptime(lot['date'], "%Y-%m-%d") <= three_years_ago else "ZDANITELNÉ"
                    qty_str = str(round(lot['qty'], 3)).replace('.', ',')
                    price_str = str(lot.get('price_at_buy', 'N/A')).replace('.', ',')
                    self.lots_tree.insert("", "end", values=(t, lot['date'], qty_str, price_str, s))
                except: pass

    # ---------------------------------------------------------
    # NOVÉ FUNKCE PRO VÝPOČET A REALIZACI PRODEJŮ
    # ---------------------------------------------------------
    
    def start_calculate_withdrawal(self):
        self.btn_calc_sale.config(state=tk.DISABLED)
        for i in self.sell_staging_tree.get_children(): self.sell_staging_tree.delete(i)
        
        self.sell_loading_timer = self.root.after(1000, lambda: self.show_loading(self.sell_loading_state, "Počítám optimální prodej..."))
        threading.Thread(target=self.calculate_withdrawal, daemon=True).start()

    def start_calculate_rebalancing(self):
        """Spustí výpočet rebalančních prodejů ve vedlejším vlákně a dočasně zablokuje UI."""
        self.btn_calc_rebal.config(state=tk.DISABLED)
        # Vyčištění tabulky stagingu před novým návrhem
        for i in self.sell_staging_tree.get_children(): 
            self.sell_staging_tree.delete(i)
        
        # Nastavení časovače pro zobrazení loading ozubených kol
        self.sell_loading_timer = self.root.after(1000, lambda: self.show_loading(self.sell_loading_state, "Počítám rebalancování z živých dat..."))
        
        threading.Thread(target=self.calculate_rebalancing, daemon=True).start()

    def calculate_rebalancing(self):
        """
        Matematické jádro rebalancování. 
        Stáhne živé kurzy a dividendy, zohlední případnou dividendovou brzdu,
        vyhledá všechny nadhodnocené pozice a navrhne jejich prodej.
        """
        try:
            wait_loops = 0
            # Aplikace čeká na dokončení stahování fundamentů z preloaderu na pozadí (max 180 vteřin, zde v desetinách)
            while not getattr(self, 'tuner_data_loaded', False) and wait_loops < 1800:
                time.sleep(0.1)
                wait_loops += 1

            fx = self.get_fx_rates()
            all_tickers = list(TARGETS.keys())
            
            # 1. Stažení aktuálních tržních cen z Yahoo
            try:
                raw_data = self._safe_yf_download(all_tickers, period="5d")
                if raw_data.empty or 'Close' not in raw_data:
                    raise ValueError("Nepodařilo se stáhnout aktuální ceny z Yahoo Finance.")
                
                close_data = raw_data['Close']
                if isinstance(close_data, pd.DataFrame):
                    prices_data = close_data.ffill().iloc[-1]
                else:
                    prices_data = pd.Series({all_tickers[0]: close_data.ffill().iloc[-1]})
            except Exception as e:
                self.root.after(0, lambda err=e: messagebox.showerror("Chyba rebalancování", f"Chyba stahování dat: {err}"))
                return

            # --- ŘEŠENÍ PRO ČERSTVÁ IPO A CHYBĚJÍCÍ CENY ---
            prices_dict = {}
            for t in all_tickers:
                try:
                    p = float(prices_data.get(t, 0.0))
                    if pd.isna(p) or p <= 0:
                        raise ValueError("Chybí cena v historii")
                    prices_dict[t] = p
                except Exception:
                    fund = self._safe_get_fundamentals(t)
                    p = float(fund.get('current_price') or 0.0)
                    prices_dict[t] = p if not pd.isna(p) else 0.0

            # Výpočet aktuální tržní hodnoty každé pozice a celku
            current_holdings_val = {}
            total_current_portfolio_val = 0.0

            for t in all_tickers:
                qty_held = sum(item['qty'] for item in self.ledger.get(t, []))
                price = prices_dict.get(t, 0.0)
                cur = self.get_currency_for_ticker(t)
                fx_rate = fx.get(cur, 23.0)
                
                if t.endswith(".L"): price /= 100.0
                
                if price > 0:
                    val_czk = qty_held * price * fx_rate
                    current_holdings_val[t] = val_czk
                    total_current_portfolio_val += val_czk
                else:
                    current_holdings_val[t] = 0.0

            # --- ZÍSKÁNÍ PŘESNÝCH DAT (Společné pro dynamickou brzdu) ---
            nom_weights = np.array([TARGETS[t] for t in TARGETS.keys()])
            yields_list = []
            growths_list = []
            db = getattr(self, 'stock_db_from_json', DEFAULT_STOCK_DB)
            
            for t in TARGETS.keys():
                if getattr(self, 'tuner_data_loaded', False) and hasattr(self, 'ordered_tickers') and t in self.ordered_tickers:
                    idx = self.ordered_tickers.index(t)
                    yields_list.append(self.tuner_stock_divs[idx])
                    growths_list.append(self.tuner_upsides[idx])
                else:
                    meta = db.get(t, {})
                    yields_list.append(meta.get("yield", 0.0) / 100.0)
                    growths_list.append(meta.get("growth", 0.0) / 100.0)

            yields_array = np.array(yields_list)
            growths_array = np.array(growths_list)
            nom_portfolio_yield = np.sum(nom_weights * yields_array)

            # 2. Výpočet cílů se zohledněním dividendové brzdy (Glide-Path)
            effective_targets = TARGETS.copy()
            if getattr(self, 'dyn_targets_enabled', False) and total_current_portfolio_val > 0:
                try:
                    yield_cap = float(self.dyn_floor_slider.get()) / 100.0
                    try:
                        abs_target_net_czk = float(self.dyn_abs_entry.get().replace(' ', '').replace(',', '.'))
                        if abs_target_net_czk < 0.0: abs_target_net_czk = 0.0
                    except ValueError:
                        abs_target_net_czk = getattr(self, 'dyn_abs_div', 500000.0)
                        
                    abs_target_gross_czk = abs_target_net_czk / (1 - DEFAULT_TAX_RATE)
                    
                    # APLIKACE DYNAMICKÉ BRZDY PŘES CENTRALIZOVANOU METODU
                    best_w = self._apply_dynamic_dividend_brake(
                        nom_weights=nom_weights,
                        yields_array=yields_array,
                        growths_array=growths_array,  # Předání pole růstů
                        projected_total_val=total_current_portfolio_val,
                        abs_target_gross_czk=abs_target_gross_czk,
                        yield_cap=yield_cap
                    )
                    
                    for i, t in enumerate(TARGETS.keys()):
                        effective_targets[t] = float(best_w[i])
                        
                except Exception as e:
                    print(f"[!] Chyba rebalančního cílování: {e}")

            # DYNAMICKÝ POSUV VAH (DRIFTING TARGETS)
            if getattr(self, 'drifting_targets_enabled', False) and total_current_portfolio_val > 0:
                effective_targets = self._apply_drifting_targets(
                    current_targets=effective_targets,
                    current_holdings_val=current_holdings_val,
                    total_portfolio_val=total_current_portfolio_val
                )

            # 3. Identifikace nadhodnocených pozic
            rows_to_insert = []
            total_raised_czk = 0.0

            for t, target in effective_targets.items():
                ideal_val = total_current_portfolio_val * target
                curr_val = current_holdings_val.get(t, 0.0)

                # Porovnáme realitu s cílem (zavedeme toleranci 100 Kč kvůli drobným zaokrouhlením)
                if curr_val > ideal_val + 100.0:
                    excess_czk = curr_val - ideal_val
                    try:
                        price = prices_dict.get(t, 0.0)
                        if price <= 0: continue
                        cur = self.get_currency_for_ticker(t)
                        fx_rate = fx.get(cur, 23.0)
                        
                        price_factor = 100.0 if t.endswith(".L") else 1.0
                        calc_price = price / price_factor 

                        sell_qty = excess_czk / (calc_price * fx_rate) if calc_price > 0 else 0.0

                        # Bezpečnostní pojistka: neprodáváme víc, než máme v Ledgeru
                        held_qty = sum(item['qty'] for item in self.ledger.get(t, []))
                        if sell_qty > held_qty:
                            sell_qty = held_qty
                        
                        sell_czk = sell_qty * calc_price * fx_rate

                        if sell_qty > 0.001:
                            total_raised_czk += sell_czk
                            rows_to_insert.append((
                                t,
                                f"{sell_qty:.3f}".replace('.', ','), 
                                f"{calc_price:.2f}".replace('.', ','),
                                f"{sell_czk:.0f}",
                                "❌"
                            ))
                    except Exception as e:
                        print(f"Chyba výpočtu odprodeje u {t}: {e}")

            # 4. Aktualizace grafického rozhraní z hlavního vlákna
            self.root.after(0, lambda: self._populate_rebal_staging(rows_to_insert, total_raised_czk))

        finally:
            self.root.after(0, self._cleanup_rebal_loading)

    def _populate_rebal_staging(self, rows, total_raised_czk):
        """Zapíše navržené prodeje do staging tabulky a předvyplní investiční pole na kartě nákupů."""
        for row in rows:
            self.sell_staging_tree.insert("", "end", values=row)
            
        # PŘEDVYPLNĚNÍ KARTY NÁKUPŮ:
        # Částka, kterou odprodejem získáme, se ihned zaokrouhlená vloží do pole investic.
        if hasattr(self, 'cash_entry'):
            self.cash_entry.delete(0, tk.END)
            self.cash_entry.insert(0, f"{total_raised_czk:.0f}")
            
        if rows:
            total_raised_czk_space = f"{total_raised_czk:,.0f}".replace(',', ' ')
            messagebox.showinfo(
                "Návrh rebalancování", 
                f"Výpočet úspěšně dokončen!\n\n"
                f"• Navrženo snížení u {len(rows)} nadhodnocených pozic.\n"
                f"• Celkový odhadovaný výnos k reinvestování: {total_raised_czk_space} Kč.\n\n"
                f"Tato částka byla automaticky předvyplněna do pole 'Investice (Kč)' "
                f"na kartě Nákup. Po schválení těchto prodejů stačí přejít tam a jedním kliknutím "
                f"spočítat optimální rebalanční nákup.", parent=self.root
            )
        else:
            messagebox.showinfo(
                "Návrh rebalancování", 
                "Vaše portfolio je dokonale vyvážené (žádná pozice nepřesahuje své cílové zastoupení).\n\n"
                "Není třeba nic odprodávat.", parent=self.root
            )

    def _cleanup_rebal_loading(self):
        """Uvolní časovač, skryje ozubená kola a odblokuje rebalanční tlačítko."""
        if getattr(self, 'sell_loading_timer', None):
            self.root.after_cancel(self.sell_loading_timer)
            self.sell_loading_timer = None
        self.hide_loading(self.sell_loading_state)
        self.btn_calc_rebal.config(state=tk.NORMAL)

    def calculate_withdrawal(self):
        try:
            try:
                target_cash = float(self.withdraw_entry.get().replace(',', '.'))
            except ValueError:
                self.root.after(0, lambda: messagebox.showerror("Chyba", "Zadejte platnou částku k výběru."))
                return

            fx = self.get_fx_rates()
            all_tickers = list(TARGETS.keys())

            try:
                if not hasattr(self, 'data_fetcher'):
                    self.data_fetcher = RobustDataFetcher()
                raw_data = self.data_fetcher.fetch_history(all_tickers, period="5d")
                if raw_data.empty or 'Close' not in raw_data:
                    raise ValueError("Nelze získat aktuální ceny akcií pro výpočet.")

                close_data = raw_data['Close']
                if isinstance(close_data, pd.DataFrame):
                    prices_data = close_data.ffill().iloc[-1]
                else:
                    prices_data = pd.Series({all_tickers[0]: close_data.ffill().iloc[-1]})
            except Exception as e:
                self.root.after(0, lambda err=e: messagebox.showerror("Chyba", f"Chyba stahování dat: {err}"))
                return

            prices_dict = {}
            for t in all_tickers:
                try:
                    p = float(prices_data.get(t, 0.0))
                    if pd.isna(p) or p <= 0:
                        raise ValueError
                    prices_dict[t] = p
                except Exception:
                    fund = self._safe_get_fundamentals(t)
                    p = float(fund.get('current_price') or 0.0)
                    prices_dict[t] = p if not pd.isna(p) else 0.0

            current_holdings_val = {}
            total_current_portfolio_val = 0.0

            for t in all_tickers:
                qty_held = sum(item['qty'] for item in self.ledger.get(t,[]))
                price = prices_dict.get(t, 0.0)
                cur = self.get_currency_for_ticker(t)
                fx_rate = fx.get(cur, 23.0)
                
                if t.endswith(".L"): price /= 100.0
                
                if price > 0:
                    val_czk = qty_held * price * fx_rate
                    current_holdings_val[t] = val_czk
                    total_current_portfolio_val += val_czk
                else:
                    current_holdings_val[t] = 0.0

            # --- DYNAMICKÝ POSUV VAH (DRIFTING TARGETS) ---
            effective_targets = TARGETS.copy()
            if getattr(self, 'drifting_targets_enabled', False) and total_current_portfolio_val > 0:
                effective_targets = self._apply_drifting_targets(
                    current_targets=effective_targets,
                    current_holdings_val=current_holdings_val,
                    total_portfolio_val=total_current_portfolio_val
                )

            if target_cash > total_current_portfolio_val:
                self.root.after(0, lambda: messagebox.showerror("Chyba", "Požadovaná částka přesahuje aktuální hodnotu celého portfolia!"))
                return

            valid_targets =[w for w in effective_targets.values() if w > 0]
            min_target = min(valid_targets) if valid_targets else 1.0

            low = 0.0
            high = total_current_portfolio_val / min_target if min_target > 0 else total_current_portfolio_val * 2
            virtual_total = 0.0

            for _ in range(50):
                mid = (low + high) / 2.0
                cash_raised = 0.0
                for t, target in effective_targets.items():
                    ideal_val = mid * target
                    curr_val = current_holdings_val.get(t, 0.0)
                    if curr_val > ideal_val:
                        cash_raised += (curr_val - ideal_val)

                if cash_raised > target_cash:
                    low = mid
                else:
                    high = mid
                    virtual_total = mid

            rows_to_insert =[]
            for t, target in effective_targets.items():
                ideal_val = virtual_total * target
                curr_val = current_holdings_val.get(t, 0.0)

                if curr_val > ideal_val:
                    sell_czk = curr_val - ideal_val
                    try:
                        price = prices_dict.get(t, 0.0)
                        if price <= 0: continue
                        cur = self.get_currency_for_ticker(t)
                        fx_rate = fx.get(cur, 23.0)
                        
                        price_factor = 100.0 if t.endswith(".L") else 1.0
                        calc_price = price / price_factor # CENA V GBP/USD

                        sell_qty = sell_czk / (calc_price * fx_rate) if calc_price > 0 else 0.0

                        held_qty = sum(item['qty'] for item in self.ledger.get(t,[]))
                        if sell_qty > held_qty:
                            sell_qty = held_qty
                            sell_czk = sell_qty * calc_price * fx_rate

                        if sell_qty > 0.001:
                            rows_to_insert.append((
                                t,
                                f"{sell_qty:.3f}".replace('.', ','), 
                                f"{calc_price:.2f}".replace('.', ','),
                                f"{sell_czk:.0f}",
                                "❌"
                            ))
                    except Exception as e:
                        print(f"Přeskakuji odprodej u {t}: {e}")

            self.root.after(0, lambda: self._populate_sell_staging(rows_to_insert))

        finally:
            self.root.after(0, self._cleanup_sell_loading)

    def _cleanup_sell_loading(self):
        if getattr(self, 'sell_loading_timer', None):
            self.root.after_cancel(self.sell_loading_timer)
            self.sell_loading_timer = None
        self.hide_loading(self.sell_loading_state)
        self.btn_calc_sale.config(state=tk.NORMAL)

    def _populate_sell_staging(self, rows):
        for row in rows:
            self.sell_staging_tree.insert("", "end", values=row)

    def _on_sell_price_enter(self, event):
        """Uloží upravenou cenu a automaticky načte další řádek ze seznamu."""
        ticker_to_find = self.sell_ticker.get().strip().upper()
        
        self.add_to_sell_staging()
        
        children = self.sell_staging_tree.get_children()
        current_idx = -1
        
        for i, child in enumerate(children):
            vals = self.sell_staging_tree.item(child)['values']
            if str(vals[0]) == ticker_to_find:
                current_idx = i
                break
                
        if current_idx != -1 and current_idx + 1 < len(children):
            next_child = children[current_idx + 1]
            
            self.sell_staging_tree.selection_set(next_child)
            self.sell_staging_tree.focus(next_child)
            
            vals = self.sell_staging_tree.item(next_child)['values']
            self.sell_ticker.set(vals[0])
            
            # Formátování při přeskoku: Kusy s tečkou, Cena s čárkou
            clean_qty = str(vals[1]).replace(',', '.').strip()
            self.sell_qty.delete(0, tk.END)
            self.sell_qty.insert(0, clean_qty)

            # alternativní zobrazení pole Cena - pro UI vždy s čárkou
            #clean_price = str(vals[2]).replace('.', ',').strip()
            # alternativní zobrazení pole Cena - pro UI vždy s tečkou
            clean_price = str(vals[2]).replace(',', '.').strip()
            self.sell_price_entry.delete(0, tk.END)
            self.sell_price_entry.insert(0, clean_price)
            
        self.sell_price_entry.focus_set()
        self.sell_price_entry.select_range(0, tk.END)
        self.sell_price_entry.icursor(tk.END)

    def fill_entry_from_sell_staging(self, event):
        selection = self.sell_staging_tree.selection()
        if not selection: return
        vals = self.sell_staging_tree.item(selection[0])['values']
        self.sell_ticker.set(vals[0])

        # Kusy - vždy s tečkou
        clean_qty = str(vals[1]).replace(',', '.').strip()
        self.sell_qty.delete(0, tk.END)
        self.sell_qty.insert(0, clean_qty)

        # alternativní zobrazení pole Cena - pro UI vždy s čárkou
        #clean_price = str(vals[2]).replace('.', ',').strip()
        # alternativní zobrazení pole Cena - pro UI vždy s tečkou
        clean_price = str(vals[2]).replace(',', '.').strip()
        self.sell_price_entry.delete(0, tk.END)
        self.sell_price_entry.insert(0, clean_price)

    def add_to_sell_staging(self):
        t = self.sell_ticker.get().strip().upper()
        q = self.sell_qty.get().strip()
        p = self.sell_price_entry.get().strip()

        if not t or not q or not p:
            messagebox.showwarning("Chyba", "Vyplňte Ticker, Množství a Cenu.")
            return

        try:
            qty = float(q.replace(",", "."))
            price = float(p.replace(",", "."))
        except ValueError:
            messagebox.showerror("Chyba", "Neplatný formát čísel.")
            return

        fx = self.get_fx_rates()
        cur = self.get_currency_for_ticker(t)
        fx_rate = fx.get(cur, 23.0) 
        
        val_czk = qty * price * fx_rate

        # Podpora více prodejů stejného tickeru (partial fills od brokera):
        # Zjistíme, zda má uživatel v tabulce zrovna kliknutím vybraný nějaký řádek.
        selection = self.sell_staging_tree.selection()
        
        # Pokud je řádek vybraný a ticker se shoduje, provedeme úpravu tohoto konkrétního řádku (Update).
        if selection and str(self.sell_staging_tree.item(selection[0])['values'][0]) == t:
            self.sell_staging_tree.item(selection[0], values=(
                t,
                f"{qty:.3f}".replace('.', ','), 
                f"{price:.2f}".replace('.', ','),
                f"{val_czk:.0f}",
                "❌"
            ))
            # Po úpravě řádek odznačíme, aby další kliknutí na tlačítko "Přidat" přidalo nový řádek
            self.sell_staging_tree.selection_remove(selection[0])
        else:
            # Pokud není nic vybráno, nebo jde o jiný ticker, přidáme VŽDY nový řádek.
            self.sell_staging_tree.insert("", "end", values=(
                t, f"{qty:.3f}".replace('.', ','), f"{price:.2f}".replace('.', ','), f"{val_czk:.0f}", "❌"
            ))

        self.sell_qty.delete(0, tk.END)
        self.sell_price_entry.delete(0, tk.END)

    def delete_sell_staging_row(self, event):
        item = self.sell_staging_tree.selection()
        if item: self.sell_staging_tree.delete(item)

    def execute_sale(self):
        rows = self.sell_staging_tree.get_children()
        if not rows:
            messagebox.showwarning("Prodej", "Seznam k prodeji je prázdný.")
            return

        today = datetime.now().strftime("%Y-%m-%d")
        sales_executed = 0
        failed_sales =[]

        for item in rows:
            vals = self.sell_staging_tree.item(item)['values']
            t = str(vals[0])
            try:
                qty = float(str(vals[1]).replace(',', '.'))
                price = float(str(vals[2]).replace(',', '.'))
            except:
                continue

            if t not in self.ledger or not self.ledger[t]:
                failed_sales.append(f"{t} (Žádné nákupy evidovány)")
                continue

            current_held_qty = sum(float(l['qty']) for l in self.ledger[t])
            if current_held_qty < qty - 0.0001:
                failed_sales.append(f"{t} (Nedostatek kusů: evidujete {current_held_qty:.3f}, chcete prodat {qty:.3f})")
                continue

            # Spuštění FIFO odprodeje
            rem = qty
            self.ledger[t].sort(key=lambda x: x.get("date", "1970-01-01"))

            fx_rates = self.get_fx_rates() # Pro získání kurzu v den prodeje

            while rem > 0.0001 and self.ledger[t]:
                lot = self.ledger[t][0]
                lot_qty = float(lot['qty'])
                sold = min(lot_qty, rem)
                rem -= sold
                lot['qty'] = lot_qty - sold

                # Poměrné rozdělení poplatku z nákupu (pokud prodáváme jen část lotu)
                sold_ratio = sold / lot_qty if lot_qty > 0 else 1.0
                buy_fee_portion = lot.get('fee', 0.0) * sold_ratio
                lot['fee'] = lot.get('fee', 0.0) - buy_fee_portion

                if lot['qty'] < 0.0001:
                    self.ledger[t].pop(0)

                curr = self.get_currency_for_ticker(t)
                
                self.sales_history.append({
                    "ticker": t,
                    "currency": curr,
                    "buy_date": lot['date'],
                    "sell_date": today,
                    "qty": sold,
                    "buy_price": float(lot.get('price_at_buy', 0)),
                    "sell_price": price,
                    # Evidence poplatků a přesných kurzů pro uzavřený obchod
                    "buy_fx_rate": lot.get('fx_rate', fx_rates.get(curr, 23.0)),
                    "sell_fx_rate": fx_rates.get(curr, 23.0),
                    "buy_fee": buy_fee_portion,
                    "sell_fee": 0.0 # Bude zpětně doplněno z CSV
                })

            sales_executed += 1
            self.sell_staging_tree.delete(item) # Úspěšně prodáno, odstraníme ze seznamu

        if sales_executed > 0:
            self.save_data()
            self.update_lots_view()
            # Spustí asynchronní přepočet na záložce Kalendář dividend
            threading.Thread(target=self.refresh_dividends, daemon=True).start()

        if failed_sales:
            msg = "Některé prodeje selhaly (nedostatek evidovaných akcií):\n\n" + "\n".join(failed_sales)
            messagebox.showwarning("Částečný úspěch", msg)
        elif sales_executed > 0:
            messagebox.showinfo("Úspěch", f"Úspěšně realizováno {sales_executed} prodejů (metodou FIFO).")

    # --------------------------------------------------------------------------
    # TAB 3: KALENDÁŘ DIVIDEND
    # --------------------------------------------------------------------------

    def setup_dividend_tab(self):
        frame = tk.Frame(self.notebook, bg="#E8F5E9")
        self.notebook.add(frame, text="Kalendář Dividend")
        
        ctrl_panel = tk.Frame(frame, bg="#E8F5E9")
        ctrl_panel.pack(fill=tk.X, padx=20, pady=10)
        
        self.div_mode_var = tk.StringVar(value="real")
        
        # při kliknutí na radio button se ihned spustí vlákno na pozadí, ukáže se loading a data se přegenerují.
        self.rb_div_target = tk.Radiobutton(ctrl_panel, text="Teoretické cílové portfolio (dle nastavených vah)", 
                                            variable=self.div_mode_var, value="target", 
                                            bg="#E8F5E9", font=("Arial", 12),
                                            command=self.start_refresh_dividends)
        self.rb_div_target.pack(side=tk.LEFT, padx=10)
        
        self.rb_div_real = tk.Radiobutton(ctrl_panel, text="Reálné portfolio (ledger)", 
                                          variable=self.div_mode_var, value="real", 
                                          bg="#E8F5E9", font=("Arial", 12),
                                          command=self.start_refresh_dividends)
        self.rb_div_real.pack(side=tk.LEFT, padx=10)
        
        self.btn_refresh_divs = tk.Button(ctrl_panel, text="📅 NAČÍST DATA", 
                  command=self.start_refresh_dividends,
                  font=("Arial", 12, "bold"), bg="#43A047", fg="white")
        self.btn_refresh_divs.pack(side=tk.LEFT, padx=15)
                  
        self.div_status_lbl = tk.Label(ctrl_panel, text="Klikni pro načtení...", bg="#E8F5E9", fg="grey", font=("Arial", 12))
        self.div_status_lbl.pack(side=tk.LEFT, padx=15)

        content_frame = tk.Frame(frame, bg="#E8F5E9")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        tree_frame = tk.Frame(content_frame)
        tree_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        cols_config = {
            "Datum": 140, 
            "Ticker": 80, 
            "Částka": 160, 
            "Stav": 160, 
            "Nárok (CZK Hrubého)": 160
        }
        # Přidání vertikálního posuvníku
        div_scroll = ttk.Scrollbar(tree_frame)
        div_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Propojení tabulky s posuvníkem (yscrollcommand)
        self.div_tree = ttk.Treeview(tree_frame, columns=list(cols_config.keys()), show="headings", height=15, yscrollcommand=div_scroll.set)

        for col, w in cols_config.items():
            self.div_tree.heading(col, text=col)
            # Nastavení konkrétní šířky pro daný sloupec
            self.div_tree.column(col, anchor="center", width=w)
        
        self.div_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        div_scroll.config(command=self.div_tree.yview)

        # --- Zvýrazňování řádků podle vybrané akcie ---
        self.div_tree.tag_configure("highlight", background="#FFF9C4", font=("Arial", 12, "bold"))
        self.div_tree.bind("<<TreeviewSelect>>", self._on_div_tree_select)

        chart_frame = tk.Frame(content_frame, bg="white", width=400)
        chart_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, padx=(10, 0))
        
        self.div_fig = plt.Figure(figsize=(5, 4), dpi=100)
        self.div_ax = self.div_fig.add_subplot(111)
        self.div_fig.patch.set_facecolor('#E8F5E9') 
        
        self.div_canvas = FigureCanvasTkAgg(self.div_fig, master=chart_frame)
        self.div_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Výchozí popisek na spodku okna
        current_year = datetime.now().year
        self.div_total_lbl = tk.Label(frame, text=f"Celkem {current_year}: 0 Kč", font=("Arial", 14, "bold"), bg="#E8F5E9")
        self.div_total_lbl.pack(pady=10)
        
        # Vizuální loading element pro záložku Dividend
        self.div_loading_state = self._create_loading_card(frame)

    def start_refresh_dividends(self):
        """Příprava před výpočtem dividend - zamkne ovládání a připraví UI."""
        self.btn_refresh_divs.config(state=tk.DISABLED)
        self.rb_div_target.config(state=tk.DISABLED)
        self.rb_div_real.config(state=tk.DISABLED)
        
        for i in self.div_tree.get_children(): self.div_tree.delete(i)
        self.div_status_lbl.config(text="Stahuji data o cenách a dividendách...", fg="blue")
        
        self.div_loading_timer = self.root.after(2000, lambda: self.show_loading(self.div_loading_state, "Stahuji data, prosím, čekejte..."))
        threading.Thread(target=self.refresh_dividends, daemon=True).start()

    def _cleanup_div_loading(self):
        """Bezpečně zruší časovač a skryje animaci na záložce Dividend."""
        if getattr(self, 'div_loading_timer', None):
            self.root.after_cancel(self.div_loading_timer)
            self.div_loading_timer = None
        self.hide_loading(self.div_loading_state)
        self.btn_refresh_divs.config(state=tk.NORMAL)
        self.rb_div_target.config(state=tk.NORMAL)
        self.rb_div_real.config(state=tk.NORMAL)

    def _on_div_tree_select(self, event):
        """Zvýrazní všechny výplaty od stejné akcie po kliknutí na řádek."""
        selection = self.div_tree.selection()
        if not selection:
            return
            
        # Přečteme ticker z právě kliknutého řádku (sloupec Ticker má index 1)
        selected_item = selection[0]
        selected_ticker = str(self.div_tree.item(selected_item, "values")[1])
        
        # Projdeme celou tabulku dividend a obarvíme ty řádky, kde se shoduje ticker
        for item in self.div_tree.get_children():
            row_ticker = str(self.div_tree.item(item, "values")[1])
            
            if row_ticker == selected_ticker:
                # Nastavíme vytvořený tag (zvýrazňovač)
                self.div_tree.item(item, tags=("highlight",))
            else:
                # Ostatní řádky vrátíme do původního stavu
                self.div_tree.item(item, tags=())

    def refresh_dividends(self):
        try:
            self._refresh_dividends_internal()
        finally:
            self.root.after(0, self._cleanup_div_loading)

    def _refresh_dividends_internal(self):
        """
        Stáhne historii dividend od všech firem a vyprojektuje očekávaný výnos na zbytek roku.
        Zohledňuje burzovní pravidlo Ex-Dividend data (nákup musí být před tímto datem).
        """
        # pomocná funkce pro české datum
        def format_cz_date(d_obj):
            months = ["", "leden", "únor", "březen", "duben", "květen", "červen", 
                      "červenec", "srpen", "září", "říjen", "listopad", "prosinec"]
            return f"{d_obj.day}. {months[d_obj.month]} {d_obj.year}"

        mode = self.div_mode_var.get()
        
        fx = self.get_fx_rates()
        
        # Sestavení super-seznamu pro stahování (Cíle + Nákupy + Prodeje)
        all_tickers_set = set(TARGETS.keys())
        all_tickers_set.update(self.ledger.keys())
        for s in self.sales_history: all_tickers_set.add(s['ticker'])
        all_tickers = list(all_tickers_set)
        
        try: 
            raw_data = self._safe_yf_download(all_tickers, period="5d")
            if raw_data.empty or 'Close' not in raw_data:
                raise ValueError("Nedostupná data.")
                
            close_data = raw_data['Close']
            if isinstance(close_data, pd.DataFrame):
                prices_data = close_data.ffill().iloc[-1]
            else:
                prices_data = pd.Series({all_tickers[0]: close_data.ffill().iloc[-1]})
        except Exception as e:
            self.root.after(0, lambda: self.div_status_lbl.config(text="Chyba stahování aktuálních cen akcií.", fg="red"))
            return

        total_value_czk = 0.0
        for t in all_tickers:
            qty_held = sum(l['qty'] for l in self.ledger.get(t,[]))
            if qty_held > 0:
                try:
                    p = float(prices_data[t])
                    if t.endswith(".L"): p /= 100.0
                    # Bezpečný .get fallback
                    total_value_czk += qty_held * p * fx.get(CURRENCIES.get(t, "USD"), 23.0)
                except: pass

        theoretical_qtys = {}
        sim_val = total_value_czk if total_value_czk > 1000 else 100000.0
        
        # --- ZÍSKÁNÍ PŘESNÝCH DAT (Pro případnou dynamickou brzdu) ---
        nom_weights = np.array([TARGETS[t] for t in TARGETS.keys()])
        yields_list = []
        growths_list = []
        db = getattr(self, 'stock_db_from_json', DEFAULT_STOCK_DB)
        
        for t in TARGETS.keys():
            if getattr(self, 'tuner_data_loaded', False) and hasattr(self, 'ordered_tickers') and t in self.ordered_tickers:
                idx = self.ordered_tickers.index(t)
                yields_list.append(self.tuner_stock_divs[idx])
                growths_list.append(self.tuner_upsides[idx])
            else:
                meta = db.get(t, {})
                yields_list.append(meta.get("yield", 0.0) / 100.0)
                growths_list.append(meta.get("growth", 0.0) / 100.0)

        yields_array = np.array(yields_list)
        growths_array = np.array(growths_list)
        
        effective_targets = TARGETS.copy()
        
        # Aplikace dynamické dividendové brzdy na teoretické portfolio, pokud je v nastavení aktivní
        if mode == "target" and getattr(self, 'dyn_targets_enabled', False) and sim_val > 0:
            try:
                yield_cap = getattr(self, 'dyn_yield_cap', 3.0) / 100.0
                abs_target_net_czk = getattr(self, 'dyn_abs_div', 500000.0)
                abs_target_gross_czk = abs_target_net_czk / (1 - DEFAULT_TAX_RATE)
                
                best_w = self._apply_dynamic_dividend_brake(
                    nom_weights=nom_weights,
                    yields_array=yields_array,
                    growths_array=growths_array,
                    projected_total_val=sim_val,
                    abs_target_gross_czk=abs_target_gross_czk,
                    yield_cap=yield_cap
                )
                
                for i, t in enumerate(TARGETS.keys()):
                    effective_targets[t] = float(best_w[i])
            except Exception as e:
                print(f"[!] Chyba výpočtu brzdy pro kalendář dividend: {e}")
        
        # Výpočet teoretických kusů z (případně ubržděných) vah
        for t, weight in effective_targets.items():
            try:
                p = float(prices_data[t])
                if t.endswith(".L"): p /= 100.0
                price_czk = p * fx.get(CURRENCIES.get(t, "USD"), 23.0)
                theoretical_qtys[t] = (sim_val * weight) / price_czk if price_czk > 0 else 0
            except: theoretical_qtys[t] = 0

        total_czk_gross, total_czk_net = 0, 0 
        calendar_rows =[]
        ticker_dividend_totals = {} 
        
        # Získání relativních let pro výpočet
        today_date = datetime.now().date()
        current_year = today_date.year       
        last_year = current_year - 1         
        year_before_last = last_year - 1     
        end_of_year = date(current_year, 12, 31)

        process_tickers = set(list(self.ledger.keys()) + [s['ticker'] for s in self.sales_history]) if mode == "real" else TARGETS.keys()

        for t in process_tickers:
            # --- Ochrana akumulačních ETF ---
            meta = getattr(self, 'stock_db_from_json', DEFAULT_STOCK_DB).get(t, {})
            if meta.get("sector") == "ETF" and meta.get("etf_type") == "Acc":
                continue # Přeskakujeme, tyto fondy dividendy nevyplácí
            
            current_lots = self.ledger.get(t,[])
            real_qty_held = sum(l['qty'] for l in current_lots)
            
            if mode == "real":
                has_history = any(s['ticker'] == t for s in self.sales_history)
                if real_qty_held <= 0.001 and not has_history: continue
                calc_qty_held = real_qty_held
            else:
                calc_qty_held = theoretical_qtys.get(t, 0)
                if calc_qty_held <= 0.001: continue
            
            try:
                hist_divs = self._safe_get_dividends(t)
                
                divs_current_yr = hist_divs[hist_divs.index.year == current_year]
                divs_last_yr = hist_divs[hist_divs.index.year == last_year]
                divs_prev_yr = hist_divs[hist_divs.index.year == year_before_last]
                
                confirmed_months = set() 
                growth_factor = 1.0
                tax_rate = 0.0 if CURRENCIES.get(t, "USD") == "GBP" else DEFAULT_TAX_RATE 
                
                # --- 1. ZPRACOVÁNÍ SKUTEČNÝCH DIVIDEND (Z CSV) ---
                # Skutečná data z CSV se vytáhnou POUZE pro reálné portfolio
                if mode == "real":
                    real_divs_year =[d for d in getattr(self, 'real_dividends', []) if d['date'].startswith(str(current_year)) and d['ticker'] == t]
                    for rd in real_divs_year:
                        pay_date = datetime.strptime(rd['date'], "%Y-%m-%d").date()
                        confirmed_months.add(pay_date.month) # Zablokuje projekci pro tento měsíc
                        
                        gross_val = rd['gross']
                        tax_val = rd['tax']
                        currency = rd.get('currency', 'USD')
                        
                        # Přepočet do CZK hrubého a čistého
                        fx_rate = fx.get(currency, 23.0)
                        czk_gross = gross_val * fx_rate
                        czk_net = (gross_val - tax_val) * fx_rate
                        
                        ticker_dividend_totals[t] = ticker_dividend_totals.get(t, 0) + czk_gross
                        
                        # --- Zjištění případného propadu oproti loňsku ---
                        warning_suffix = ""
                        yf_equiv = gross_val * 100.0 if t.endswith(".L") else gross_val
                        if not divs_last_yr.empty:
                            target_yday = pay_date.timetuple().tm_yday
                            closest_last = None
                            min_diff = 60 # U IBKR CSV je to Pay-Date, takže tolerance musí být větší (až měsíc po Ex-Date)
                            for d_last, amt_last in divs_last_yr.items():
                                diff = abs(d_last.timetuple().tm_yday - target_yday)
                                if diff < min_diff:
                                    min_diff = diff
                                    closest_last = amt_last
                            if closest_last and closest_last > 0:
                                ratio = yf_equiv / closest_last
                                # Varování, pokud dividenda klesla o více než 10 % (ratio < 0.9).
                                # Ignorujeme propady o více než 80 % (ratio < 0.2), to je typicky split akcií nebo jednorázová speciální dividenda.
                                if 0.2 < ratio < 0.9:
                                    warning_suffix = f" ⚠️ (-{(1 - ratio) * 100:.0f} %)"
                        
                        txt = f"{gross_val:.2f} {currency}".replace('.', ',') + warning_suffix
                        calendar_rows.append({
                            "date": pay_date, 
                            "values": (format_cz_date(pay_date), t, txt, "✅ Vyplaceno (IBKR)", f"{czk_gross:.0f} Kč".replace('.', ',')),
                            "czk_gross": czk_gross, 
                            "czk_net": czk_net
                        })
                else:
                    # V teoretickém módu seznam vyprázdníme, aby se fallback z Yahoo aplikoval na celý rok
                    real_divs_year =[]

                # --- 2. ZPRACOVÁNÍ POTVRZENÝCH DIVIDEND (Z YAHOO FINANCE JAKO FALLBACK/TEORIE) ---
                if not divs_current_yr.empty:
                    latest_conf_date = divs_current_yr.index[-1]
                    latest_conf_amt = divs_current_yr.iloc[-1]
                    
                    for d_date, amount in divs_current_yr.items():
                        d_val = d_date.date() # Toto je EX-DATE z Yahoo
                        
                        # KONTROLA PŘEKRYVU (pouze pro reálné portfolio)
                        # (Pay-Date z CSV bývá typicky 0 až 90 dní po Ex-Date z Yahoo), přeskočíme to.
                        is_covered = False
                        if mode == "real":
                            for rd in real_divs_year:
                                rd_date = datetime.strptime(rd['date'], "%Y-%m-%d").date()
                                if 0 <= (rd_date - d_val).days <= 90:
                                    is_covered = True
                                    break
                                    
                        if is_covered: continue
                        
                        confirmed_months.add(d_val.month)
                        
                        # Matematika nároku na dividendu (Nákup musí být PŘED ex-datem)
                        if mode == "real":
                            qty_ledger = sum(l['qty'] for l in current_lots if datetime.strptime(l['date'], "%Y-%m-%d").date() < d_val)
                            qty_sold_later = sum(s['qty'] for s in self.sales_history 
                                                 if s['ticker'] == t 
                                                 and datetime.strptime(s['buy_date'], "%Y-%m-%d").date() < d_val 
                                                 and datetime.strptime(s['sell_date'], "%Y-%m-%d").date() >= d_val)
                            valid_qty = qty_ledger + qty_sold_later
                        else:
                            valid_qty = calc_qty_held

                        if valid_qty > 0.001:
                            if d_val <= today_date:
                                if mode == "real":
                                    status_txt = "Ex-date minul (nárok vznikl)"
                                else:
                                    status_txt = "Teoreticky (minulost)"
                            else:
                                status_txt = "Potvrzeno (budoucí Ex-date)"

                            if t.endswith(".L"): val_c = amount / 100.0; txt = f"{amount:.2f} p".replace('.', ',')
                            else: val_c = amount; txt = f"{amount:.2f} {CURRENCIES.get(t, 'USD')}".replace('.', ',')
                            
                            # --- Zjištění případného propadu oproti loňsku ---
                            warning_suffix = ""
                            if not divs_last_yr.empty:
                                target_yday = d_val.timetuple().tm_yday
                                closest_last = None
                                min_diff = 45 # Yahoo je Ex-Date, tolerance 45 dní stačí
                                for d_last, amt_last in divs_last_yr.items():
                                    diff = abs(d_last.timetuple().tm_yday - target_yday)
                                    if diff < min_diff:
                                        min_diff = diff
                                        closest_last = amt_last
                                if closest_last and closest_last > 0:
                                    ratio = amount / closest_last
                                    # Varování, pokud dividenda klesla o více než 10 % (ratio < 0.9)
                                    if 0.2 < ratio < 0.9:
                                        warning_suffix = f" ⚠️ (-{(1 - ratio) * 100:.0f} %)"
                            
                            txt += warning_suffix
                            
                            czk_val = valid_qty * val_c * fx.get(CURRENCIES.get(t, "USD"), 23.0)
                            net_czk_val = czk_val * (1.0 - tax_rate)
                            ticker_dividend_totals[t] = ticker_dividend_totals.get(t, 0) + czk_val
                            
                            calendar_rows.append({
                                "date": d_val, "values": (format_cz_date(d_val), t, txt, status_txt, f"{czk_val:.0f} Kč".replace('.', ',')),
                                "czk_gross": czk_val, "czk_net": net_czk_val
                            })
                    
                    # Výpočet trendu pro projekci (hledáme stejnou dividendu v loňském roce)
                    closest_last = None
                    matched_d_last = None
                    min_diff = 365
                    target_day_of_year = latest_conf_date.timetuple().tm_yday
                    
                    for d_last_iter, amt_last in divs_last_yr.items():
                        diff = abs(d_last_iter.timetuple().tm_yday - target_day_of_year)
                        if diff < 45 and diff < min_diff:
                            min_diff = diff
                            closest_last = amt_last
                            matched_d_last = d_last_iter

                    if closest_last and matched_d_last:
                        trend_ratio = latest_conf_amt / closest_last
                        
                        # --- Ochrana proti speciálním dividendám (MAIN, HTGC, ARCC) ---
                        # Pokud je skok větší než 25 %, pravděpodobně se srovnává běžná dividenda
                        # se speciální. V takovém případě plošný růstový faktor konzervativně anulujeme (1.0).
                        if trend_ratio > 1.25 or trend_ratio < 0.5:
                            growth_factor = 1.0
                        else:
                            if trend_ratio < 1.0: 
                                growth_factor = trend_ratio
                            elif trend_ratio > 1.0:
                                closest_prev = None
                                min_diff_prev = 365
                                # Odvození data před 2 lety
                                target_day_prev = matched_d_last.timetuple().tm_yday 
                                for d_prev, amt_prev in divs_prev_yr.items():
                                    diff = abs(d_prev.timetuple().tm_yday - target_day_prev)
                                    if diff < 45 and diff < min_diff_prev:
                                        min_diff_prev = diff
                                        closest_prev = amt_prev
                                if closest_prev and (closest_last > closest_prev):
                                    past_ratio = closest_last / closest_prev
                                    growth_factor = (trend_ratio + past_ratio) / 2.0
                                else:
                                    growth_factor = trend_ratio
                                    
                            # Finální bezpečnostní pojistka: max 15% plošný meziroční růst
                            growth_factor = min(growth_factor, 1.15)

                # --- PROJEKCE DO ZBYTKU ROKU ---
                calc_qty_held_proj = real_qty_held if mode == "real" else theoretical_qtys.get(t, 0)
                if calc_qty_held_proj > 0.001:
                    for d_date, amount in divs_last_yr.items():
                        try: proj_date = d_date.date().replace(year=current_year)
                        except ValueError: proj_date = d_date.date() + timedelta(days=365)
                        
                        if proj_date.month in confirmed_months: continue
                            
                        if today_date <= proj_date <= end_of_year:
                            projected_amount = amount * growth_factor
                            if t.endswith(".L"): val_c = projected_amount / 100.0; txt = f"{projected_amount:.2f} p (projekce)".replace('.', ',')
                            else: val_c = projected_amount; txt = f"{projected_amount:.2f} {CURRENCIES.get(t, 'USD')} (projekce)".replace('.', ',')
                            
                            czk_val = calc_qty_held_proj * val_c * fx.get(CURRENCIES.get(t, "USD"), 23.0)
                            net_czk_val = czk_val * (1.0 - tax_rate)
                            ticker_dividend_totals[t] = ticker_dividend_totals.get(t, 0) + czk_val
                            
                            calendar_rows.append({
                                "date": proj_date, "values": (format_cz_date(proj_date), t, txt, f"Projekce (x{growth_factor:.2f})".replace('.', ','), f"{czk_val:.0f} Kč".replace('.', ',')),
                                "czk_gross": czk_val, "czk_net": net_czk_val
                            })
            except Exception as e: print(f"Chyba u {t}: {e}")

        calendar_rows.sort(key=lambda x: x["date"])
        for row in calendar_rows:
            self.root.after(0, lambda vals=row["values"]: self.div_tree.insert("", "end", values=vals))
            total_czk_gross += row["czk_gross"]
            total_czk_net += row["czk_net"]

        # Vykreslení koláčového grafu
        self.div_ax.clear()
        labels, sizes = [],[]
        sorted_divs = sorted(ticker_dividend_totals.items(), key=lambda x: x[1], reverse=True)
        
        for t, val in sorted_divs:
            if val > 0: labels.append(t); sizes.append(val)
        
        if sizes:
            total_size = sum(sizes)
            final_labels =[l if (s/total_size) > 0.03 else "" for l, s in zip(labels, sizes)]
            self.div_ax.pie(sizes, labels=final_labels, autopct=lambda p: f'{p:.1f}%'.replace('.', ',') if p > 3 else '', startangle=140, colors=plt.cm.tab20.colors)
            self.div_ax.set_title("Zdroje dividend")
        else: self.div_ax.text(0.5, 0.5, "Žádná data", ha='center')

        self.div_canvas.draw()
        
        # Aktualizace popisku s výsledkem
        if mode == "target":
            brake_str = " (s aplikovanou dividendovou brzdou)" if getattr(self, 'dyn_targets_enabled', False) else ""
            val_text = f"Hodnota pro výpočet{brake_str}: {sim_val:,.0f} Kč. ".replace(',', ' ')
        else:
            val_text = ""
        
        # Bezpečný přepis UI
        self.root.after(0, lambda: self.div_total_lbl.config(text=f"{val_text}Celkem {current_year}: {total_czk_gross:,.0f} Kč (Čistého: {total_czk_net:,.0f} Kč)".replace(',', ' ')))
        self.root.after(0, lambda: self.div_status_lbl.config(text=f"Hotovo. Zahrnuta historie i projekce.", fg="green"))

    # --------------------------------------------------------------------------
    # TAB 4: TUNING PORTFOLIA A EDITOR AKCIÍ
    # --------------------------------------------------------------------------

    def setup_tuner_tab(self, index=None):
        """Sestaví uživatelské rozhraní pro Monte Carlo tuning portfolia a připojí grafy."""
        self.tuner_frame = tk.Frame(self.notebook, bg="#FFF8E1")
        
        # DYNAMICKÉ UMÍSTĚNÍ: Pokud index není zadán, přidá se na konec. 
        # Pokud je zadán (při refreshi), vloží se na původní místo.
        if index is None:
            self.notebook.add(self.tuner_frame, text="Tuning Portfolia")
        else:
            self.notebook.insert(index, self.tuner_frame, text="Tuning Portfolia")
        
        control_panel = tk.Frame(self.tuner_frame, bg="#FFF8E1", width=550, padx=15, pady=15)
        control_panel.pack(side=tk.LEFT, fill=tk.Y)
        
        title_frame = tk.Frame(control_panel, bg="#FFF8E1")
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        min_v = getattr(self, 'custom_min_w', MIN_W) * 100
        max_v = getattr(self, 'custom_max_w', MAX_W) * 100
        
        str_min_init = f"{min_v:g}".replace('.', ',')
        str_max_init = f"{max_v:g}".replace('.', ',')
        
        self.lbl_tuner_title = tk.Label(title_frame, text=f"Optimalizace ({str_min_init}-{str_max_init}%)", font=("Arial", 18, "bold"), bg="#FFF8E1")
        self.lbl_tuner_title.pack(side=tk.LEFT)
        
        # Uložení reference na tlačítko Změnit akcie
        self.btn_change_stocks = tk.Button(title_frame, text="⚙️ Změnit akcie", command=self.open_portfolio_editor, font=("Arial", 12), bg="#DDD")
        self.btn_change_stocks.pack(side=tk.RIGHT)
        
        # PŘIDÁNO: Textboxy pro uživatelské nastavení limitů vah
        limits_frame = tk.Frame(control_panel, bg="#FFF8E1")
        limits_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(limits_frame, text="Min váha (%):", font=("Arial", 12, "bold"), bg="#FFF8E1").pack(side=tk.LEFT)
        self.entry_min_w = tk.Entry(limits_frame, font=("Arial", 12), width=6)
        self.entry_min_w.pack(side=tk.LEFT, padx=(5, 20))
        self.entry_min_w.insert(0, str_min_init)
        
        tk.Label(limits_frame, text="Max váha (%):", font=("Arial", 12, "bold"), bg="#FFF8E1").pack(side=tk.LEFT)
        self.entry_max_w = tk.Entry(limits_frame, font=("Arial", 12), width=6)
        self.entry_max_w.pack(side=tk.LEFT, padx=(5, 10))
        self.entry_max_w.insert(0, str_max_init)
        
        # Deaktivace tlačítka "Vylepšit" při ručním zásahu do limitů
        def disable_vylepsit_btn(event):
            if hasattr(self, 'btn_auto_tune') and self.btn_auto_tune.winfo_exists():
                self.btn_auto_tune.config(state=tk.DISABLED)
                
        self.entry_min_w.bind("<KeyRelease>", disable_vylepsit_btn)
        self.entry_max_w.bind("<KeyRelease>", disable_vylepsit_btn)
        
        # Zabalení do ohraničeného rámečku s popiskem
        cb_container = tk.LabelFrame(control_panel, text="Které akcie chcete tunit? (nezaškrtlé = fixováno)", bg="#FFF8E1", font=("Arial", 11, "bold"))
        # rámeček se zvětšuje s oknem (slouží jako flexibilní výplň)
        cb_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Vytvoření Canvasu a Scrollbaru pro scrollovatelný obsah
        # minimální výška (height=40), zbytek volného místa si vezme expand=True
        self.cb_canvas = tk.Canvas(cb_container, bg="#FFF8E1", highlightthickness=0, height=40)
        self.cb_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        cb_scrollbar = ttk.Scrollbar(cb_container, orient="vertical", command=self.cb_canvas.yview)
        cb_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.cb_canvas.configure(yscrollcommand=cb_scrollbar.set)
        
        # Samotný frame, ve kterém budou checkboxy, umístěný uvnitř Canvasu
        cb_frame = tk.Frame(self.cb_canvas, bg="#FFF8E1")
        self.cb_canvas_window = self.cb_canvas.create_window((0, 0), window=cb_frame, anchor="nw")
        
        # Automatické přizpůsobení scrollovací oblasti a šířky
        def on_cb_frame_configure(event):
            self.cb_canvas.configure(scrollregion=self.cb_canvas.bbox("all"))
            
        def on_cb_canvas_configure(event):
            self.cb_canvas.itemconfig(self.cb_canvas_window, width=event.width)
            
        cb_frame.bind("<Configure>", on_cb_frame_configure)
        self.cb_canvas.bind("<Configure>", on_cb_canvas_configure)
        
        # Podpora pro scrollování kolečkem myši (aktivní pouze při najetí na Canvas)
        def _on_mousewheel(event):
            self.cb_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            
        self.cb_canvas.bind("<Enter>", lambda e: self.cb_canvas.bind_all("<MouseWheel>", _on_mousewheel))
        self.cb_canvas.bind("<Leave>", lambda e: self.cb_canvas.unbind_all("<MouseWheel>"))
        
        self.tuner_vars = {}
        self.tuner_checkboxes =[] # Uložení referencí na checkboxy
        tickers = sorted(list(TARGETS.keys()))
        for i, t in enumerate(tickers):
            var = tk.BooleanVar(value=True) 
            self.tuner_vars[t] = var
            cb = tk.Checkbutton(cb_frame, text=t, variable=var, bg="#FFF8E1", font=("Arial", 12), command=self.on_checkbox_toggle)
            cb.grid(row=i//3, column=i%3, sticky="w", padx=2)
            self.tuner_checkboxes.append(cb)
            
        btn_frame = tk.Frame(control_panel, bg="#FFF8E1")
        btn_frame.pack(fill=tk.X, pady=5)
        
        self.btn_init_tuner = tk.Button(btn_frame, text="⚡ NAČÍST & SIMULOVAT", 
                                        command=lambda: self.run_tuner_with_loading(lambda: self.initialize_tuner_data(force_download=True), "Stahuji data a simuluji..."),
                                        bg="#F57F17", fg="white", font=("Arial", 11, "bold"))
        self.btn_init_tuner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))

        self.btn_auto_tune = tk.Button(btn_frame, text="✨ VYLEPŠIT", 
                                        command=lambda: self.run_tuner_with_loading(lambda: self.initialize_tuner_data(force_download=False, n_sims=MC_NO_IMPR, auto_improve=True), "Hledám lepší váhy..."),
                                        bg="#0288D1", fg="white", font=("Arial", 11, "bold"))
        self.btn_auto_tune.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(2, 0))
        
        self.tuner_status = tk.Label(control_panel, text="Data nenačtena", bg="#FFF8E1", fg="grey", font=("Arial", 12), wraplength=350)
        self.tuner_status.pack(pady=5)
        
        slider_frame = tk.Frame(control_panel, bg="#FFF8E1")
        slider_frame.pack(fill=tk.X, pady=(5, 0))
        
        # Nadpisy sloupců
        tk.Label(slider_frame, text="Minulost (5 let)", font=("Arial", 13, "bold"), bg="#FFF8E1").grid(row=0, column=0, pady=(0,5), sticky="w")
        tk.Label(slider_frame, text="Budoucnost (1 rok)", font=("Arial", 13, "bold"), bg="#FFF8E1").grid(row=0, column=1, pady=(0,5), sticky="w")

        self.sliders = {}
        s_len = 240 # Přiměřená délka sliderů
        
        # --- Řada 1: Dividenda ---
        tk.Label(slider_frame, text="Hrubá dividenda (na 100k):", bg="#FFF8E1", font=("Arial", 12)).grid(row=1, column=0, sticky="w")
        self.lbl_div_val = tk.Label(slider_frame, text="---", fg="#2E7D32", font=("Arial", 12, "bold"), bg="#FFF8E1")
        self.lbl_div_val.grid(row=2, column=0, sticky="w")
        self.sliders['div'] = tk.Scale(slider_frame, orient=tk.HORIZONTAL, length=s_len, bg="#FFF8E1", resolution=10, showvalue=False, command=lambda v: self.on_slider_change('div', v))
        self.sliders['div'].grid(row=3, column=0, padx=(0, 20))

        tk.Label(slider_frame, text="Bezpečná dividenda (očištěná):", bg="#FFF8E1", font=("Arial", 12)).grid(row=1, column=1, sticky="w")
        self.lbl_fdiv_val = tk.Label(slider_frame, text="---", fg="#0288D1", font=("Arial", 12, "bold"), bg="#FFF8E1")
        self.lbl_fdiv_val.grid(row=2, column=1, sticky="w")
        self.sliders['fdiv'] = tk.Scale(slider_frame, orient=tk.HORIZONTAL, length=s_len, bg="#FFF8E1", resolution=10, showvalue=False, command=lambda v: self.on_slider_change('fdiv', v))
        self.sliders['fdiv'].grid(row=3, column=1)

        # --- Řada 2: Riziko / Propad ---
        tk.Label(slider_frame, text="Max pokles v % (historie):", bg="#FFF8E1", font=("Arial", 12)).grid(row=4, column=0, sticky="w", pady=(10,0))
        self.lbl_dd_val = tk.Label(slider_frame, text="---", fg="#C62828", font=("Arial", 12, "bold"), bg="#FFF8E1")
        self.lbl_dd_val.grid(row=5, column=0, sticky="w")
        self.sliders['dd'] = tk.Scale(slider_frame, orient=tk.HORIZONTAL, length=s_len, bg="#FFF8E1", resolution=0.1, showvalue=False, command=lambda v: self.on_slider_change('dd', v))
        self.sliders['dd'].grid(row=6, column=0, padx=(0, 20))

        tk.Label(slider_frame, text="Propad v krizi (95% scénář):", bg="#FFF8E1", font=("Arial", 12)).grid(row=4, column=1, sticky="w", pady=(10,0))
        self.lbl_fdd_val = tk.Label(slider_frame, text="---", fg="#C62828", font=("Arial", 12, "bold"), bg="#FFF8E1")
        self.lbl_fdd_val.grid(row=5, column=1, sticky="w")
        self.sliders['fdd'] = tk.Scale(slider_frame, orient=tk.HORIZONTAL, length=s_len, bg="#FFF8E1", resolution=0.1, showvalue=False, command=lambda v: self.on_slider_change('fdd', v))
        self.sliders['fdd'].grid(row=6, column=1)

        # --- Řada 3: Růst ---
        tk.Label(slider_frame, text="Celkový růst v %:", bg="#FFF8E1", font=("Arial", 12)).grid(row=7, column=0, sticky="w", pady=(10,0))
        self.lbl_growth_val = tk.Label(slider_frame, text="---", fg="#2E7D32", font=("Arial", 12, "bold"), bg="#FFF8E1")
        self.lbl_growth_val.grid(row=8, column=0, sticky="w")
        self.sliders['growth'] = tk.Scale(slider_frame, orient=tk.HORIZONTAL, length=s_len, bg="#FFF8E1", resolution=0.1, showvalue=False, command=lambda v: self.on_slider_change('growth', v))
        self.sliders['growth'].grid(row=9, column=0, padx=(0, 20))

        tk.Label(slider_frame, text="Očekávaný růst (analytici):", bg="#FFF8E1", font=("Arial", 12)).grid(row=7, column=1, sticky="w", pady=(10,0))
        self.lbl_fgrowth_val = tk.Label(slider_frame, text="---", fg="#0288D1", font=("Arial", 12, "bold"), bg="#FFF8E1")
        self.lbl_fgrowth_val.grid(row=8, column=1, sticky="w")
        self.sliders['fgrowth'] = tk.Scale(slider_frame, orient=tk.HORIZONTAL, length=s_len, bg="#FFF8E1", resolution=0.1, showvalue=False, command=lambda v: self.on_slider_change('fgrowth', v))
        self.sliders['fgrowth'].grid(row=9, column=1)
        
        for s in self.sliders.values(): s.config(state="disabled")

        # --- BLOK ANALÝZY RIZIK (SEMAFOR) ---
        self.risk_frame_container = tk.LabelFrame(control_panel, text="Analýza rizik (nové portfolio)", bg="#FFF8E1", font=("Arial", 12, "bold"))
        self.risk_frame_container.pack(fill=tk.X, pady=(15, 10))
        
        # 1. Volatilita (beta)
        self.lbl_title_beta = tk.Label(self.risk_frame_container, text="Tržní volatilita (beta):", bg="#FFF8E1", font=("Arial", 12))
        self.lbl_title_beta.grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.lbl_risk_beta = tk.Label(self.risk_frame_container, text="---", bg="#FFF8E1", font=("Arial", 12, "bold"))
        self.lbl_risk_beta.grid(row=0, column=1, sticky="w", padx=5)

        # 2. Úrokové riziko
        self.lbl_title_rates = tk.Label(self.risk_frame_container, text="Úrokové riziko (dluhy/REIT/BDC):", bg="#FFF8E1", font=("Arial", 12))
        self.lbl_title_rates.grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.lbl_risk_rates = tk.Label(self.risk_frame_container, text="---", bg="#FFF8E1", font=("Arial", 12, "bold"))
        self.lbl_risk_rates.grid(row=1, column=1, sticky="w", padx=5)

        # 3. Sektorová koncentrace
        self.lbl_title_sector = tk.Label(self.risk_frame_container, text="Nejsilnější sektor:", bg="#FFF8E1", font=("Arial", 12))
        self.lbl_title_sector.grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.lbl_risk_sector = tk.Label(self.risk_frame_container, text="---", bg="#FFF8E1", font=("Arial", 12, "bold"))
        self.lbl_risk_sector.grid(row=2, column=1, sticky="w", padx=5)
        
        # 4. Koncentrace jedné akcie
        self.lbl_title_single = tk.Label(self.risk_frame_container, text="Max. váha jedné akcie:", bg="#FFF8E1", font=("Arial", 12))
        self.lbl_title_single.grid(row=3, column=0, sticky="w", padx=5, pady=2)
        self.lbl_risk_single = tk.Label(self.risk_frame_container, text="---", bg="#FFF8E1", font=("Arial", 12, "bold"))
        self.lbl_risk_single.grid(row=3, column=1, sticky="w", padx=5)

        # Uložení reference na potvrzovací tlačítko
        self.btn_apply_weights = tk.Button(control_panel, text="✓ POUŽÍT NOVÉ VÁHY", command=self.apply_tuned_weights, bg="#2E7D32", fg="white", font=("Arial", 12, "bold"))
        self.btn_apply_weights.pack(pady=10, fill=tk.X)

        # Tabulka Base portfolia
        base_frame = tk.LabelFrame(control_panel, text="Výchozí portfolio", bg="#FFF8E1", font=("Arial", 12, "bold"))
        base_frame.pack(fill=tk.X)
        
        base_perf_frame = tk.Frame(base_frame, bg="#FFF8E1")
        base_perf_frame.pack(fill=tk.X)
        
        tk.Label(base_perf_frame, text="Hrubá dividenda:", bg="#FFF8E1", font=("Arial", 12)).grid(row=0, column=0, sticky="w", pady=2)
        self.lbl_base_div = tk.Label(base_perf_frame, text="---", bg="#FFF8E1", fg="#2E7D32", font=("Arial", 12, "bold"))
        self.lbl_base_div.grid(row=0, column=1, sticky="w", padx=(0,15))
        
        tk.Label(base_perf_frame, text="Bezpečná dividenda:", bg="#FFF8E1", font=("Arial", 12)).grid(row=0, column=2, sticky="w", pady=2)
        self.lbl_base_fdiv = tk.Label(base_perf_frame, text="---", bg="#FFF8E1", fg="#0288D1", font=("Arial", 12, "bold"))
        self.lbl_base_fdiv.grid(row=0, column=3, sticky="w")
        
        tk.Label(base_perf_frame, text="Historický pokles:", bg="#FFF8E1", font=("Arial", 12)).grid(row=1, column=0, sticky="w", pady=2)
        self.lbl_base_dd = tk.Label(base_perf_frame, text="---", bg="#FFF8E1", fg="#C62828", font=("Arial", 12, "bold"))
        self.lbl_base_dd.grid(row=1, column=1, sticky="w", padx=(0,15))
        
        tk.Label(base_perf_frame, text="Krizový propad:", bg="#FFF8E1", font=("Arial", 12)).grid(row=1, column=2, sticky="w", pady=2)
        self.lbl_base_fdd = tk.Label(base_perf_frame, text="---", bg="#FFF8E1", fg="#C62828", font=("Arial", 12, "bold"))
        self.lbl_base_fdd.grid(row=1, column=3, sticky="w")

        tk.Label(base_perf_frame, text="Historický růst:", bg="#FFF8E1", font=("Arial", 12)).grid(row=2, column=0, sticky="w", pady=2)
        self.lbl_base_growth = tk.Label(base_perf_frame, text="---", bg="#FFF8E1", fg="#2E7D32", font=("Arial", 12, "bold"))
        self.lbl_base_growth.grid(row=2, column=1, sticky="w", padx=(0,15))
        
        tk.Label(base_perf_frame, text="Očekávaný růst:", bg="#FFF8E1", font=("Arial", 12)).grid(row=2, column=2, sticky="w", pady=2)
        self.lbl_base_fgrowth = tk.Label(base_perf_frame, text="---", bg="#FFF8E1", fg="#0288D1", font=("Arial", 12, "bold"))
        self.lbl_base_fgrowth.grid(row=2, column=3, sticky="w")

        viz_panel = tk.Frame(self.tuner_frame, bg="white")
        viz_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # --- Přepínač zobrazení grafů ---
        toggle_frame = tk.Frame(viz_panel, bg="white")
        toggle_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.chart_view_var = tk.StringVar(value="new")
        
        rb_new_decay = tk.Radiobutton(toggle_frame, text="Nové s dividendovou brzdou", variable=self.chart_view_var, value="new_decay", bg="white", font=("Arial", 12, "bold"), fg="#0288D1", command=self._redraw_tuner_charts)
        rb_new_decay.pack(side=tk.RIGHT, padx=5)

        rb_new = tk.Radiobutton(toggle_frame, text="Nové", variable=self.chart_view_var, value="new", bg="white", font=("Arial", 12, "bold"), fg="#1976D2", command=self._redraw_tuner_charts)
        rb_new.pack(side=tk.RIGHT, padx=5)
        
        rb_base_decay = tk.Radiobutton(toggle_frame, text="Výchozí s dividendovou brzdou", variable=self.chart_view_var, value="base_decay", bg="white", font=("Arial", 12, "bold"), fg="dimgrey", command=self._redraw_tuner_charts)
        rb_base_decay.pack(side=tk.RIGHT, padx=5)

        rb_base = tk.Radiobutton(toggle_frame, text="Výchozí", variable=self.chart_view_var, value="base", bg="white", font=("Arial", 12, "bold"), fg="grey", command=self._redraw_tuner_charts)
        rb_base.pack(side=tk.RIGHT, padx=5)
        
        tk.Label(toggle_frame, text="Zobrazení portfolia:", bg="white", font=("Arial", 12)).pack(side=tk.RIGHT, padx=10)

        self.fig_tune = plt.figure(figsize=(10, 8))
        self.fig_tune.patch.set_facecolor('white')
        gs = gridspec.GridSpec(2, 2, width_ratios=[1, 1], height_ratios=[1, 1])
        
        self.ax_pie = self.fig_tune.add_subplot(gs[0, 0])
        self.ax_div_pie = self.fig_tune.add_subplot(gs[0, 1])
        self.ax_curve = self.fig_tune.add_subplot(gs[1, 0])
        self.ax_bars = self.fig_tune.add_subplot(gs[1, 1])
        
        self.fig_tune.subplots_adjust(hspace=0.35, wspace=0.3)
        self.canvas_tune = FigureCanvasTkAgg(self.fig_tune, master=viz_panel)
        self.canvas_tune.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        self.canvas_tune.mpl_connect('motion_notify_event', self.on_hover_pie)
        # Skrytí tooltipu při opuštění plochy grafu myší
        self.canvas_tune.mpl_connect('axes_leave_event', lambda e: self._hide_tooltip())
        # Skrytí tooltipu při ztrátě fokusu okna (Alt+Tab do jiné aplikace)
        self.root.bind("<FocusOut>", lambda e: self._hide_tooltip())
        # Zpracování dvojkliku na koláčový graf
        self.canvas_tune.mpl_connect('button_press_event', self.on_click_pie)
        
        self.simulated_portfolios = None
        self.sim_metrics = None
        self.updating_sliders = False 
        self.tuner_base_weights = TARGETS.copy() 
        self.tuner_loading_state = self._create_loading_card(self.tuner_frame)

    def _validate_and_get_limits(self):
        """Načte, zkontroluje a případně opraví uživatelské limity z UI před výpočtem."""
        # Zrušíme naplánované ladění, aby se nepralo s novými limity
        if getattr(self, '_slider_job', None):
            self.root.after_cancel(self._slider_job)
            self._slider_job = None

        # Pokus o načtení MIN váhy
        try:
            min_val = float(self.entry_min_w.get().replace(',', '.'))
        except ValueError:
            min_val = MIN_W * 100.0

        # Pokus o načtení MAX váhy
        try:
            max_val = float(self.entry_max_w.get().replace(',', '.'))
        except ValueError:
            max_val = MAX_W * 100.0

        # Zajištění, že jsme v povolených mezích (0 až 100 %)
        min_val = max(0.0, min(100.0, min_val))
        max_val = max(0.0, min(100.0, max_val))

        # Pokud uživatel prohodil min a max, automaticky je obrátíme
        if min_val > max_val:
            min_val, max_val = max_val, min_val

        # Aktualizace vnitřních proměnných (v desetinném tvaru)
        self.custom_min_w = min_val / 100.0
        self.custom_max_w = max_val / 100.0

        # Přepsání UI textových polí na čisté a opravené hodnoty
        str_min = f"{min_val:g}".replace('.', ',')
        str_max = f"{max_val:g}".replace('.', ',')
        
        self.entry_min_w.delete(0, tk.END)
        self.entry_min_w.insert(0, str_min)
        self.entry_max_w.delete(0, tk.END)
        self.entry_max_w.insert(0, str_max)

        # Aktualizace titulku panelu
        self.lbl_tuner_title.config(text=f"Optimalizace ({str_min}-{str_max}%)")

    def _update_base_labels(self, metrics):
        self.lbl_base_div.config(text=f"{metrics[0]:,.0f} Kč".replace(',', ' '))
        self.lbl_base_dd.config(text=f"{metrics[1]:.1f} %".replace('.', ','))
        self.lbl_base_growth.config(text=f"{metrics[2]:.1f} %".replace('.', ','))
        self.lbl_base_fdiv.config(text=f"{metrics[3]:,.0f} Kč".replace(',', ' '))
        self.lbl_base_fdd.config(text=f"{metrics[4]:.1f} %".replace('.', ','))
        self.lbl_base_fgrowth.config(text=f"{metrics[5]:.1f} %".replace('.', ','))
        
    def on_checkbox_toggle(self):
        if getattr(self, 'tuner_loading_state', {}).get("is_loading"): return
        if not getattr(self, 'tuner_data_loaded', False): return 
        for s in self.sliders.values(): s.config(state="disabled")
        self.run_tuner_with_loading(lambda: self.initialize_tuner_data(force_download=False), "Přepočítávám simulace...")

    def _evaluate_dividend_safety(self, sector, raw_yield, payout):
        """Centrální metoda pro posouzení bezpečnosti dividendy a detekci anomálií."""
        
        # 1. REITs a BDCs (Real Estate, Financial)
        # Payout ratio založené na GAAP EPS je u nich strukturální nesmysl
        # (kvůli masivním odpisům nemovitostí a nerealizovaným ztrátám z přecenění portfolia).
        # U těchto sektorů ho budeme vždy ignorovat jako anomálii (-1).
        if sector in ["Real Estate", "Financial", "Financial Services"]:
            return raw_yield, -1, 1.0

        # 2. Nastavení bezpečného limitu podle sektoru
        # Sektory se stabilním cash-flow (potraviny, pití, utility) snesou vyšší payout.
        if sector in ["Consumer Defensive", "Utilities"]:
            limit = 0.95
        else:
            limit = 0.85 # Běžné firmy (např. Technologie, Zdravotnictví)

        # 3. Detekce jednorázových účetních anomálií u běžných firem
        # Payout < 0 znamená záporné EPS (účetní ztráta).
        # Payout > 1.5 (150 %) znamená masivní propad zisku.
        # Velké dividendové firmy (jako MRK) zřídka sníží dividendu kvůli jednomu 
        # špatnému kvartálu způsobenému odpisy nebo jednorázovou akvizicí.
        if payout < 0 or payout > 1.5:
            return raw_yield, -1, limit

        # 4. Inteligentní proporcionální snížení
        # Pokud firma mírně přetahuje limit (např. payout 1.10 při limitu 0.85),
        # aplikujeme matematický předpoklad: "Firma sníží dividendu přesně o tolik, 
        # aby se dostala na bezpečný limit".
        if payout > limit:
            # Příklad: 0.85 / 1.10 = 0.77 (Predikujeme, že dividendu srazí na 77 % současné hodnoty)
            safe_yield = raw_yield * (limit / payout)
            return safe_yield, payout, limit

        # 5. Dividenda je plně krytá ziskem
        return raw_yield, payout, limit
        
    def initialize_tuner_data(self, force_download=True, n_sims=None, auto_improve=False):
        if n_sims is None:
            n_sims = MC_NO
        try:
            tickers = list(TARGETS.keys())
            
            # Stahování a příprava historických metrik ---
            if force_download or not getattr(self, 'tuner_data_loaded', False):
                self.root.after(0, lambda: self.tuner_loading_state["label"].config(text="Stahuji data, prosím, čekejte..."))
                
                fx = self.get_fx_rates() # Zkusí stáhnout, při chybě tiše použije fallback
                all_to_download = tickers + ["SPY"]
                
                # Použití robustního stahovače
                downloaded = self._safe_yf_download(all_to_download, period="5y")
                
                # Bezpečné ošetření fatální chyby stahování
                if downloaded.empty or 'Close' not in downloaded:
                    self.root.after(0, lambda: messagebox.showerror("Chyba stahování", "Nepodařilo se stáhnout historická data. Zkontrolujte prosím připojení k internetu."))
                    # Musíme schovat točící se kolečka, protože funkce zde končí
                    self.root.after(0, lambda: self.hide_loading(self.tuner_loading_state))
                    return
                
                full_raw_data = downloaded['Close'].replace(0.0, np.nan)
                
                data = full_raw_data[tickers].ffill().bfill()
                if "SPY" in full_raw_data.columns: self.tuner_spy_prices = full_raw_data["SPY"].ffill().bfill()
                else: self.tuner_spy_prices = pd.Series()

                monthly_resampled = data.resample('ME').last()
                monthly_returns = monthly_resampled.pct_change().dropna()
                rel_start_prices = (data.iloc[0] / data.iloc[-1])
                self.ordered_tickers = rel_start_prices.index.tolist()
                
                self.tuner_cov_matrix = monthly_returns.cov() * 12
                self.tuner_cov_matrix = self.tuner_cov_matrix.reindex(index=self.ordered_tickers, columns=self.ordered_tickers)
                
                div_yields = {} 
                today_date = datetime.now().date()
                current_year = today_date.year       
                end_of_year = date(current_year, 12, 31)

                for t in self.ordered_tickers:
                    # --- Ochrana akumulačních ETF ---
                    meta = getattr(self, 'stock_db_from_json', DEFAULT_STOCK_DB).get(t, {})
                    if meta.get("sector") == "ETF" and meta.get("etf_type") == "Acc":
                        div_yields[t] = 0.0
                        continue

                    dy = 0.03
                    try:
                        hist_divs = self._safe_get_dividends(t)
                        divs_current = hist_divs[hist_divs.index.year == current_year]
                        divs_last = hist_divs[hist_divs.index.year == current_year - 1]
                        
                        total_div_local = sum(divs_current)
                        confirmed_months = [d.month for d in divs_current.index]
                        for d_date, amount in divs_last.items():
                            try: proj_date = d_date.date().replace(year=current_year)
                            except: proj_date = d_date.date() + timedelta(days=365)
                            
                            if proj_date.month not in confirmed_months:
                                total_div_local += amount
                        
                        curr_price = float(data[t].iloc[-1])
                        if curr_price > 0:
                            calc_dy = total_div_local / curr_price
                            if 0 < calc_dy <= 0.25: dy = calc_dy
                    except: pass
                    div_yields[t] = dy
                
                self.tuner_hist_prices = data
                self.tuner_stock_divs = np.array([div_yields.get(t, 0.03) for t in self.ordered_tickers])
                self.tuner_stock_growths = rel_start_prices.values 
                self.tuner_period_returns = monthly_returns 
                
                self.root.after(0, lambda: self.tuner_loading_state["label"].config(text="Zjišťuji výhled analytiků (fundamenty)..."))
                safe_divs, upsides = [],[]
                self.tuner_fundamentals = {}
                
                # --- VÝPOČET ČASOVÉHO KROKU PRO EWMA FILTR ---
                now = datetime.now()
                last_update_str = getattr(self, 'last_growth_update', None)
                if last_update_str:
                    try:
                        last_update_date = datetime.fromisoformat(last_update_str)
                        delta_days = (now - last_update_date).total_seconds() / 86400.0
                    except:
                        delta_days = 1.0
                else:
                    delta_days = 1.0
                    
                delta_days = max(0.0, min(delta_days, 365.0))
                decay_factor = math.exp(-delta_days * (math.log(2) / EWMA_HALF_LIFE_DAYS))
                
                for t in self.ordered_tickers:
                    fund = self._safe_get_fundamentals(t)
                    
                    # 1. Bezpečná dividenda (Penalizace při neudržitelném Payout Ratiu)
                    raw_yield = div_yields.get(t, 0.0)
                    payout = fund['payout_ratio']
                    
                    meta = getattr(self, 'stock_db_from_json', DEFAULT_STOCK_DB).get(t, {})
                    sector = meta.get("sector", "Unknown")
                    
                    # U specifických sektorů upravíme limity a detekci účetních anomálií
                    # Výpočet bezpečnosti dividendy
                    safe_yield, payout, limit = self._evaluate_dividend_safety(sector, raw_yield, payout)
                        
                    safe_divs.append(safe_yield)
                    
                    self.tuner_fundamentals[t] = {
                        "payout_ratio": payout,
                        "raw_yield": raw_yield,
                        "safe_yield": safe_yield,
                        "limit": limit,
                        "pe_ratio": fund.get('pe_ratio'),
                        "eps": fund.get('eps'),
                        "beta": fund.get('beta'),
                        "recommendation": fund.get('recommendation')
                    }
                    
                    # 1. Výpočet aktuálního živého růstu (více se opíráme o 5Y historii CAGR, méně o volatilní odhady)
                    idx = self.ordered_tickers.index(t)
                    hist_growth_ratio = 1.0 / self.tuner_stock_growths[idx] if self.tuner_stock_growths[idx] > 0 else 1.0
                    cagr_5y = (hist_growth_ratio ** (1/5.0)) - 1.0 if hist_growth_ratio > 0 else 0.0
                    
                    tp = fund['target_price']
                    cp = fund['current_price']
                    analyst_ups = (tp / cp) - 1.0 if (tp and cp and cp > 0) else cagr_5y
                    
                    if analyst_ups < 0 and cagr_5y > 0.15:
                        live_ups = cagr_5y * 0.8 
                    elif analyst_ups < 0 and cagr_5y > 0.05:
                        live_ups = max(analyst_ups * 0.2 + cagr_5y * 0.8, 0.0) 
                    else:
                        live_ups = (analyst_ups * 0.3) + (cagr_5y * 0.7)

                    # 2. APLIKACE ČASOVĚ ZÁVISLÉHO EWMA FILTRU
                    now = datetime.now()
                    last_update_str = getattr(self, 'last_growth_update', None)
                    if last_update_str:
                        try:
                            delta_days = max(0.0, min((now - datetime.fromisoformat(last_update_str)).total_seconds() / 86400.0, 365.0))
                        except: delta_days = 1.0
                    else: delta_days = 1.0
                    decay_factor = math.exp(-delta_days * (math.log(2) / EWMA_HALF_LIFE_DAYS))

                    db_meta = getattr(self, 'stock_db_from_json', {}).get(t, {})
                    if "growth" in db_meta and last_update_str is not None:
                        saved_growth = db_meta["growth"] / 100.0
                        smoothed_ups = (saved_growth * decay_factor) + (live_ups * (1.0 - decay_factor))
                    else:
                        smoothed_ups = live_ups
                        
                    upsides.append(smoothed_ups)
                    
                self.tuner_safe_divs = np.array(safe_divs)
                self.tuner_upsides = np.array(upsides)
                
                # --- ULOŽENÍ ČERSTVÝCH DAT DO JSON DATABÁZE I Z TUNERU ---
                self.last_growth_update = datetime.now().isoformat()
                if hasattr(self, 'stock_db_from_json'):
                    for i, t in enumerate(self.ordered_tickers):
                        if t in self.stock_db_from_json:
                            if self.stock_db_from_json[t].get("sector") == "ETF" and self.stock_db_from_json[t].get("etf_type") == "Acc":
                                self.stock_db_from_json[t]['yield'] = 0.0
                            else:
                                self.stock_db_from_json[t]['yield'] = round(float(self.tuner_stock_divs[i]) * 100.0, 4)
                            self.stock_db_from_json[t]['growth'] = round(float(upsides[i]) * 100.0, 4)
                    self.save_data()
                    
                self.tuner_data_loaded = True
            
            n_cores = multiprocessing.cpu_count()
            self.root.after(0, lambda: self.tuner_loading_state["label"].config(text=f"Generuji {n_sims} scénářů ({n_cores} jader)..."))
            
            n_assets = len(self.ordered_tickers)
            
            valid_vars = {t: var for t, var in self.tuner_vars.items() if t in self.ordered_tickers}
            active_tickers =[t for t, var in valid_vars.items() if var.get()]
            fixed_tickers =[t for t, var in valid_vars.items() if not var.get()]
            
            active_indices =[self.ordered_tickers.index(t) for t in active_tickers]
            fixed_weights = np.zeros(n_assets)
            
            backup_weights = getattr(self, 'sim_weights', None)
            backup_idx = getattr(self, 'current_sim_idx', None)
            
            if backup_weights is not None and backup_idx is not None and backup_weights.shape[1] == n_assets:
                current_w = backup_weights[backup_idx]
            else:
                current_w = np.array([TARGETS.get(t, 1.0/n_assets) for t in self.ordered_tickers])
                if np.sum(current_w) > 0: current_w = current_w / np.sum(current_w)
                
            for t in fixed_tickers:
                idx = self.ordered_tickers.index(t)
                fixed_weights[idx] = current_w[idx]
                
            target_sum = 1.0 - np.sum(fixed_weights) 
            
            base_w_exact = np.array([TARGETS.get(t, 0.0) for t in self.ordered_tickers])
            if np.sum(base_w_exact) > 0:
                base_w_exact = base_w_exact / np.sum(base_w_exact) 
                
                # 1. Historické metriky
                b_div = np.dot(base_w_exact, self.tuner_stock_divs) * 100000
                b_rets = np.dot(self.tuner_period_returns.values, base_w_exact.T)
                b_cum = (1 + b_rets).cumprod(axis=0)
                b_growth = (b_cum[-1] - 1.0) * 100 if len(b_cum) > 0 else 0
                b_run_max = np.maximum.accumulate(b_cum, axis=0)
                b_dd = np.min((b_cum - b_run_max) / b_run_max, axis=0) * 100
                
                # 2. Budoucí (predikované) metriky
                b_fdiv = np.dot(base_w_exact, self.tuner_safe_divs) * 100000
                b_fgrowth_dec = np.dot(base_w_exact, self.tuner_upsides)
                
                # Volatilita base portfolia pro výpočet krizového propadu
                b_var = np.dot(base_w_exact.T, np.dot(self.tuner_cov_matrix.values, base_w_exact))
                b_vol = np.sqrt(b_var)
                b_fdd = -1.645 * b_vol * 100
                b_fgrowth = b_fgrowth_dec * 100
                
                # 3. Sbalení všech 6 metrik do jednoho pole a odeslání do UI
                b_m =[b_div, b_dd, b_growth, b_fdiv, b_fdd, b_fgrowth, b_vol * 100]
                self.base_metrics_data = b_m # Uložíme pro potřeby kreslení grafu
                
                # Okamžitě propsat zjištěný reálný výnos i do Slideru a do paměti aplikace
                self.last_nominal_yield = float(b_div / 100000.0)
                if hasattr(self, 'dyn_floor_slider'):
                    max_slider_val = round(self.last_nominal_yield * 100, 2)
                    if max_slider_val < 0.5: max_slider_val = 5.0
                    
                    # Zjištění, zda nové reálné maximum nekleslo pod to, co je zrovna manuálně nastaveno
                    current_slider_val = float(self.dyn_floor_slider.get())
                    if current_slider_val > max_slider_val:
                        self.root.after(0, lambda v=max_slider_val: [self.dyn_floor_slider.config(to=v), self.dyn_floor_slider.set(v)])
                        self.dyn_yield_cap = max_slider_val
                    else:
                        self.root.after(0, lambda v=max_slider_val: self.dyn_floor_slider.config(to=v))
                        
                self.root.after(0, lambda m=b_m, bw=base_w_exact: [self._update_base_labels(m), self._update_risk_dashboard(bw, is_base=True)])
            
            # Načtení custom limitů z instance třídy (získané validátorem textových polí)
            adj_min_w = getattr(self, 'custom_min_w', MIN_W)
            adj_max_w = getattr(self, 'custom_max_w', MAX_W)
            
            n_active = len(active_indices)
            if n_active > 0:
                if target_sum <= 0:
                    adj_min_w = 0.0
                    adj_max_w = 0.0
                elif n_active == 1:
                    adj_min_w = target_sum
                    adj_max_w = target_sum
                else:
                    avg_w = target_sum / n_active
                    # Ochrana: I zde už musíme počítat s dynamickými custom limity uživatele.
                    if (adj_min_w * n_active > target_sum - EPS) or (adj_max_w * n_active < target_sum + EPS):
                        spread = avg_w * 0.5
                        adj_min_w = max(0.0, avg_w - spread)
                        adj_max_w = min(1.0, avg_w + spread)
            
            # Lokální pomocná funkce pro propsání finálních (matematicky korektních) limitů do UI a paměti
            def _update_ui_limits(m_min, m_max):
                self.custom_min_w = m_min
                self.custom_max_w = m_max
                
                # Zaokrouhlení na max 2 desetinná místa, aby nevznikaly texty jako 3.33333
                # Formát 'g' se postará o oříznutí přebytečných nul a nahradíme tečku čárkou
                str_min = f"{round(m_min * 100, 2):g}".replace('.', ',')
                str_max = f"{round(m_max * 100, 2):g}".replace('.', ',')
                
                if hasattr(self, 'lbl_tuner_title'):
                    self.lbl_tuner_title.config(text=f"Optimalizace ({str_min}-{str_max}%)")
                if hasattr(self, 'entry_min_w'):
                    self.entry_min_w.delete(0, tk.END)
                    self.entry_min_w.insert(0, str_min)
                if hasattr(self, 'entry_max_w'):
                    self.entry_max_w.delete(0, tk.END)
                    self.entry_max_w.insert(0, str_max)
                    
            # Bezpečné zavolání úpravy UI na hlavním vlákně
            self.root.after(0, lambda: _update_ui_limits(adj_min_w, adj_max_w))

            chunk_size = n_sims // n_cores
            period_returns_vals = self.tuner_period_returns.values 
            
            # Inicializace hodnot pro auto-vylepšení (pokud je aktivní)
            if auto_improve and getattr(self, 'sim_metrics', None) is not None and getattr(self, 'current_sim_idx', None) is not None:
                # Používáme přesné floaty z databáze, nikoliv zaokrouhlené hodnoty ze sliderů!
                best_m = self.sim_metrics[self.current_sim_idx].copy()
                best_w = self.sim_weights[self.current_sim_idx].copy()
            else:
                auto_improve = False
                
            iteration = 1
            
            while True:
                if auto_improve:
                    msg = f"Hledám lepší váhy (Iterace {iteration})..."
                else:
                    msg = f"Generuji {n_sims} scénářů ({n_cores} jader)..."
                
                # Aktualizace textu na UI (bezpečně z hlavního vlákna)
                self.root.after(0, lambda m=msg: self.tuner_loading_state["label"].config(text=m))
                
                tasks =[]
                for _ in range(n_cores):
                    tasks.append((chunk_size, active_indices, fixed_weights, target_sum, 
                                    adj_min_w, adj_max_w, EPS, self.tuner_stock_divs, self.tuner_stock_growths, period_returns_vals,
                                    self.tuner_safe_divs, self.tuner_upsides, self.tuner_cov_matrix.values))
                
                with multiprocessing.Pool(processes=n_cores) as pool:
                    chunk_results = pool.starmap(_worker_simulation_task, tasks)
                    
                w_chunks =[wc for wc, mc in chunk_results if len(wc) > 0]
                m_chunks =[mc for wc, mc in chunk_results if len(mc) > 0]
                
                if not w_chunks:
                    if iteration == 1:
                        self.root.after(0, lambda: messagebox.showerror("Chyba", "Simulace nenašla platná řešení."))
                        return
                    else:
                        break # Pokud selže v pozdější iteraci, cyklus prostě skončí
                        
                new_w = np.vstack(w_chunks)
                new_m = np.vstack(m_chunks)
                
                if auto_improve:
                    # Výpočet HHI pro aktuální batch a dosavadního šampiona
                    new_hhi = np.sum(new_w**2, axis=1)
                    best_hhi = np.sum(best_w**2)

                    # 1. Žádná z prvních 6 metrik nesmí být horší (přidána mikroskopická tolerance na nepřesnost Floatů)
                    # Také se nesmí zhoršit diverzifikace (HHI)
                    eps_tol = 1e-5
                    mask_metrics = np.all(new_m[:, :6] >= best_m[:6] - eps_tol, axis=1)
                    mask_hhi = new_hhi <= best_hhi + eps_tol
                    
                    # 2. Alespoň jedna z 6 metrik (nebo koncentrace HHI) musí být prokazatelně lepší 
                    # Definice prahů:[Div: 1 Kč, DD: 0.01 %, Růst: 0.01 %, Bezpečná div: 1 Kč, Krizový DD: 0.01 %, Cílový růst: 0.01 %]
                    thresholds = np.array([1.0, 0.01, 0.01, 1.0, 0.01, 0.01])
                    strict_mask_metrics = np.any(new_m[:, :6] >= best_m[:6] + thresholds, axis=1)
                    strict_mask_hhi = new_hhi <= best_hhi - 0.001 # Zlepšení HHI alespoň o 0.001
                    
                    # Sloučení masek (Vše musí být stejné nebo lepší a aspoň jedno musí být znatelně lepší)
                    valid_indices = np.where(mask_metrics & mask_hhi & (strict_mask_metrics | strict_mask_hhi))[0]
                    
                    if len(valid_indices) > 0:
                        # Vybereme tu kombinaci, která maximalizuje součet zlepšení napříč metrikami
                        rngs = np.ptp(new_m[:, :6], axis=0)
                        rngs[rngs == 0] = 1.0
                        diffs = new_m[valid_indices, :6] - best_m[:6]
                        norm_diffs = diffs / rngs
                        scores = np.sum(norm_diffs, axis=1)
                        
                        # Neviditelná HHI penalizace slouží jako dokonalý "Tie-Breaker".
                        # Pokud program najde dvě portfolia s podobně vylepšenou dividendou, 
                        # tato penalta matematicky zajistí, že si vždy vybere to rovnoměrnější.
                        hhi_valid = new_hhi[valid_indices]
                        scores -= (HHI_PENALTY * hhi_valid)
                        
                        best_local_idx = valid_indices[np.argmax(scores)]

                        # Uložíme si nového "šampiona" a spustíme další iteraci
                        best_w = new_w[best_local_idx].copy()
                        best_m = new_m[best_local_idx].copy()
                        iteration += 1
                        continue
                    else:
                        # V této iteraci už jsme nenašli nic prokazatelně lepšího. Zastavujeme se na vrcholu.
                        self.sim_weights = np.vstack([best_w, new_w])
                        self.sim_metrics = np.vstack([best_m, new_m])
                        best_idx = 0
                        break
                else:
                    self.sim_weights = new_w
                    self.sim_metrics = new_m
                    dists = np.linalg.norm(self.sim_weights - current_w, axis=1)
                    best_idx = np.argmin(dists)
                    break

            min_div, max_div = np.min(self.sim_metrics[:,0]), np.max(self.sim_metrics[:,0])
            min_dd, max_dd = np.min(self.sim_metrics[:,1]), np.max(self.sim_metrics[:,1])
            min_gr, max_gr = np.min(self.sim_metrics[:,2]), np.max(self.sim_metrics[:,2])
            
            self.root.after(0, lambda: self._setup_sliders_after_load(np.min(self.sim_metrics, axis=0), np.max(self.sim_metrics, axis=0), best_idx))
            
        except Exception as e:
            err_msg = str(e)
            self.root.after(0, lambda msg=err_msg: messagebox.showerror("Chyba", msg))

    def _setup_sliders_after_load(self, mins, maxs, best_idx):
        keys =['div', 'dd', 'growth', 'fdiv', 'fdd', 'fgrowth']
        for i, k in enumerate(keys):
            self.sliders[k].config(from_=mins[i], to=maxs[i], state="normal")
        self.current_sim_idx = best_idx
        self.update_sliders_visuals(from_user_interaction=False)
        self.tuner_status.config(text="Upravte slidery k nalezení ideálních vah.", fg="green")

    def on_slider_change(self, source_key, value):
        if getattr(self, 'tuner_loading_state', {}).get("is_loading"): return
        if self.updating_sliders or self.sim_metrics is None: return
        if self._slider_job: self.root.after_cancel(self._slider_job)
        self._slider_job = self.root.after(100, lambda: self._perform_tuning_calculation(source_key, value))

    def _perform_tuning_calculation(self, source_key, value):
        """Experimentální hledání optima s využitím kvadratické chyby pro neaktivní slidery."""
        val = float(value)
        col_idx = {'div': 0, 'dd': 1, 'growth': 2, 'fdiv': 3, 'fdd': 4, 'fgrowth': 5}[source_key]
        
        # Získání rozsahů (rozpětí max-min) pro všechny 3 metriky kvůli normalizaci
        rngs = np.ptp(self.sim_metrics, axis=0)
        rngs[rngs == 0] = 1.0 # Ochrana proti dělení nulou
        
        # 1. Odchylka u slideru, se kterým právě hýbeme (hlavní cíl, zůstává lineární)
        primary_diff_norm = np.abs(self.sim_metrics[:, col_idx] - val) / rngs[col_idx]
        
        # 2. KVADRATICKÁ CHYBA pro zbylé dva slidery (aby "neutíkaly")
        current_metrics = self.sim_metrics[self.current_sim_idx]
        other_metrics_sq_error = np.zeros(len(self.sim_metrics))
        
        for i in range(6):
            if i != col_idx:
                # Rozdíl normalizujeme a ihned umocníme na druhou
                diff_norm = (self.sim_metrics[:, i] - current_metrics[i]) / rngs[i]
                other_metrics_sq_error += diff_norm ** 2  
                
        # 3. Stabilita vah
        # Ponecháme jako menší pojistku. Pokud najdeme 10 portfolií s perfektními metrikami,
        # vybereme to, které nám nejméně rozhází současné akcie.
        current_w = self.sim_weights[self.current_sim_idx]
        w_dist = np.linalg.norm(self.sim_weights - current_w, axis=1)
        
        # 4. Neviditelná HHI penalizace za koncentraci
        hhi_array = np.sum(self.sim_weights**2, axis=1)

        # Celkové skóre (čím menší, tím lepší)
        # ENFORCEMENT_W = tah na cíl u drženého slideru
        # STABILITY_W = fixace zbylých sliderů pomocí kvadratické chyby
        # 0.1 * w_dist = tie-breaker pro váhy
        # HHI_PENALTY = neviditelný tahák směrem k lepší diverzifikaci
        score = (ENFORCEMENT_W * primary_diff_norm) + (STABILITY_W * other_metrics_sq_error) + (0.1 * w_dist) + (HHI_PENALTY * hhi_array)
        
        best_idx = np.argmin(score)
        
        self.current_sim_idx = best_idx
        self.update_sliders_visuals(from_user_interaction=True, skip_key=source_key)
        self._slider_job = None
        
    def update_sliders_visuals(self, from_user_interaction=False, skip_key=None):
        # 1. Zrušíme případný čekající výpočet, protože UI právě teď nastavujeme na nová data
        if getattr(self, '_slider_job', None):
            self.root.after_cancel(self._slider_job)
            self._slider_job = None

        self.updating_sliders = True
        
        metrics = self.sim_metrics[self.current_sim_idx]
        weights = self.sim_weights[self.current_sim_idx]
        
        # Propsání do popisků
        self.lbl_div_val.config(text=f"{metrics[0]:.0f} Kč".replace(',', ' '))
        self.lbl_dd_val.config(text=f"{metrics[1]:.1f} %".replace('.', ','))
        self.lbl_growth_val.config(text=f"{metrics[2]:.1f} %".replace('.', ','))
        self.lbl_fdiv_val.config(text=f"{metrics[3]:.0f} Kč".replace(',', ' '))
        self.lbl_fdd_val.config(text=f"{metrics[4]:.1f} %".replace('.', ','))
        self.lbl_fgrowth_val.config(text=f"{metrics[5]:.1f} %".replace('.', ','))
        
        # Posun sliderů
        keys =['div', 'dd', 'growth', 'fdiv', 'fdd', 'fgrowth']
        for i, k in enumerate(keys):
            if not (from_user_interaction and skip_key == k):
                self.sliders[k].set(metrics[i])

        # --- AKTUALIZACE SEMAFORU RIZIK ---
        self._update_risk_dashboard(weights)
                
        # Samotné překreslení grafů delegujeme na metodu, která přečte stav přepínačů
        self._redraw_tuner_charts()
        # 2. VYNUCENÍ ZPRACOVÁNÍ: Pošleme Tkinteru instrukci, aby okamžitě zpracoval 
        # všechny události změny sliderů (Scale command). Ty díky flagu 'updating_sliders' 
        # v metodě 'on_slider_change' okamžitě skončí (return) a nenaplánují novou úlohu.
        self.root.update_idletasks()
        self.updating_sliders = False


    def _update_risk_dashboard(self, weights, is_base=False):
        """Vyhodnocuje makro a mikro rizika portfolia a počítá kvantitativní dopady (Stress testy)."""
        db = getattr(self, 'stock_db_from_json', DEFAULT_STOCK_DB)
        
        rate_sensitive_weight = 0.0
        rate_sensitive_total_drop_pct = 0.0
        rate_div_contribution = 0.0
        total_div_yield = 0.0
        sector_weights = {}
        max_single_weight = 0.0
        max_single_ticker = ""
        weighted_beta = 0.0
        total_beta_weight = 0.0
        
        # 1. Agregace dat podle vah
        for i, t in enumerate(self.ordered_tickers):
            w = weights[i]
            if w <= EPSILON_WEIGHT: continue
            
            meta = db.get(t, {})
            sector = meta.get("sector", "Unknown")
            name = meta.get("name", t)
            
            # Získání přesného výnosu z dat Tuneru pro maximální přesnost tooltipu
            if hasattr(self, 'tuner_stock_divs'):
                stock_yield = self.tuner_stock_divs[i]
            else:
                stock_yield = meta.get("yield", 0.0) / 100.0
                
            total_div_yield += w * stock_yield
            
            if w > max_single_weight:
                max_single_weight = w
                max_single_ticker = t
                
            if sector != "ETF":
                sector_weights[sector] = sector_weights.get(sector, 0.0) + w
                
            # Analýza úrokového rizika
            if sector in ["Real Estate", "Utilities"] or t in RATE_HARMED_TICKERS:
                # Tyto akcie trpí (REIT, Utilities)
                rate_sensitive_weight += w
                rate_div_contribution += w * stock_yield
                
                beta_adj = self.tuner_fundamentals[t].get("beta")
                beta_adj = 1.0 if beta_adj is None else beta_adj
                # Simulujeme pokles o 15 %
                rate_sensitive_total_drop_pct += w * (0.15 * max(1.0, beta_adj))
                
            elif t in RATE_BENEFITED_TICKERS or ("Capital" in name and sector in ["Financial", "Financial Services"]):
                # BDC fondy mají plovoucí sazby, z růstu sazeb těží.
                # Fungují jako tlumič. Jejich hodnota při úrokovém šoku historicky neklesá (pokud nedojde rovnou k recesi).
                # Přidáme je do statistiky jako "úrokově citlivé" pro informační účely, ale odečteme je z očekávaného propadu.
                rate_sensitive_weight += w
                # BDC fondy nesníží dividendu kvůli sazbám (naopak ji často zvýší), takže je nepřídáme do rate_div_contribution pro seškrtání.
                
                # Jako tlumič (hedge) mohou dokonce nepatrně ztlumit celkový propad portfolia (např. zhodnocení o 5%)
                rate_sensitive_total_drop_pct -= w * 0.05

            if hasattr(self, 'tuner_fundamentals') and t in self.tuner_fundamentals:
                beta = self.tuner_fundamentals[t].get("beta")
                if beta is not None:
                    weighted_beta += beta * w
                    total_beta_weight += w
                    
        # 2. Vyhodnocení, vizualizace a TOOLTIPY
        
        # A) Beta (Tržní riziko)
        if total_beta_weight > 0:
            final_beta = weighted_beta / total_beta_weight
            if final_beta < 0.85: beta_txt, beta_col = f"{final_beta:.2f} (Defenzivní)", "#2E7D32"
            elif final_beta <= 1.15: beta_txt, beta_col = f"{final_beta:.2f} (Neutrální)", "#F57F17"
            else: beta_txt, beta_col = f"{final_beta:.2f} (Agresivní)", "#C62828"
            
            # Bezpečné naformátování čísel před vložením do textu
            beta_val_str = f"{final_beta:.2f}".replace('.', ',')
            beta_drop_str = f"{(20 * final_beta):.1f}".replace('.', ',')
            
            beta_tt = (f"Tržní volatilita (beta) měří citlivost na pohyby celého trhu.\n"
                       f"Beta = 1.0 znamená, že portfolio plně kopíruje výkyvy trhu.\n\n"
                       f"Vaše vážená beta = {beta_val_str}.\n"
                       f"Při běžném krizovém propadu S&P 500 o 20 % by vaše portfolio\n"
                       f"mělo teoreticky klesnout o {beta_drop_str} %.")
        else:
            beta_txt, beta_col, final_beta = "N/A", "grey", 1.0
            beta_tt = "Nedostatek dat pro výpočet Bety."
            
        # B) Úrokové riziko (Sazby)
        rate_limit = LIMITS["MAX_RATE_SENSITIVE_WEIGHT"]
        rate_str = f"{rate_sensitive_weight*100:.1f} %".replace('.', ',')
        if rate_sensitive_weight <= rate_limit * 0.7: r_col, r_txt = "#2E7D32", f"{rate_str} (Nízké)"
        elif rate_sensitive_weight <= rate_limit: r_col, r_txt = "#F57F17", f"{rate_str} (Zvýšené)"
        else: r_col, r_txt = "#C62828", f"{rate_str} ⚠️ (Vysoké)"
        
        # Kvantitativní výpočet šoku: Akcie padnou o 15 % (ošetřené o betu - vážený průměr citlivostí), dividendy se plošně seškrtají o 10 %
        drop_czk = 100000 * rate_sensitive_total_drop_pct
        drop_pct = rate_sensitive_total_drop_pct * 100
        div_cut_czk = 100000 * rate_div_contribution * 0.10
        yield_before = total_div_yield * 100
        yield_after = (total_div_yield - (rate_div_contribution * 0.10)) * 100
        
        # Bezpečné naformátování
        drop_czk_str = f"{drop_czk:,.0f}".replace(',', ' ')
        div_cut_str = f"{div_cut_czk:,.0f}".replace(',', ' ')
        drop_pct_str = f"{drop_pct:.1f}".replace('.', ',')
        yield_before_str = f"{yield_before:.1f}".replace('.', ',')
        yield_after_str = f"{yield_after:.1f}".replace('.', ',')
        
        rate_tt = (f"REIT, BDC a Utility ({rate_str}) v portfoliu reagují citlivě na úrokové sazby centrálních bank.\n\n"
                   f"Při růstu sazeb se tyto akcie chovají rozdílně:\n"
                   f"📉 REITs a Utility (O, NEE...) trpí, prodražují se jim dluhy.\n"
                   f"📈 BDC fondy (MAIN, ARCC...) těží z plovoucích úroků na svých úvěrech a fungují jako polštář.\n\n"
                   f"Při úrokovém šoku (+2 % sazby) by po započtení tohoto zajištění portfolio 100 000 Kč odepsalo:\n"
                   f"• {drop_czk_str} Kč ({drop_pct_str} %) z hodnoty akcií.\n"
                   f"• {div_cut_str} Kč z ročních dividend od REITs a Utilit ({yield_before_str} % → {yield_after_str} %).\n"
                   f"(Pozn.: Pro BDC fondy je větším rizikem kreditní selhání dlužníků v hluboké recesi, nikoliv samotné sazby).")
        
        # C) Sektorová koncentrace
        if sector_weights:
            max_sector = max(sector_weights, key=sector_weights.get)
            max_sec_w = sector_weights[max_sector]
            sec_str = f"{max_sector} ({max_sec_w*100:.1f} %)".replace('.', ',')
            if max_sec_w <= LIMITS["MAX_SECTOR_WEIGHT"] * 0.8: s_col = "#2E7D32"
            elif max_sec_w <= LIMITS["MAX_SECTOR_WEIGHT"]: s_col = "#F57F17"
            else: s_col = "#C62828"; sec_str += " ⚠️"
            
            sec_w_str = f"{max_sec_w*100:.1f}".replace('.', ',')
            sec_drop_str = f"{(30 * max_sec_w):.1f}".replace('.', ',')
            
            sec_tt = (f"Nejsilnější sektor ({max_sector}) tvoří {sec_w_str} % portfolia.\n\n"
                      f"Pokud toto odvětví zasáhne krize (např. splasknutí tech bubliny)\n"
                      f"a sektor se propadne o 30 %, vaše celkové portfolio odepíše {sec_drop_str} %.\n\n"
                      f"Doporučený limit je max {LIMITS['MAX_SECTOR_WEIGHT']*100:.0f} %, aby vás jeden sektor nepoložil.")
        else:
            sec_str, s_col = "Pouze ETF", "#2E7D32"
            sec_tt = "Máte pouze ETF. Tato jsou vnitřně sektorově diverzifikována."
            
        # D) Riziko koncentrace do jedné firmy (Stock-picking)
        single_str = f"{max_single_weight*100:.1f} %".replace('.', ',')
        if max_single_weight <= LIMITS["MAX_SINGLE_WEIGHT"] * 0.7: sing_col = "#2E7D32"
        elif max_single_weight <= LIMITS["MAX_SINGLE_WEIGHT"]: sing_col = "#F57F17"
        else: sing_col = "#C62828"; single_str += " ⚠️"
        
        sing_w_str = f"{max_single_weight*100:.1f}".replace('.', ',')
        sing_drop_str = f"{(50 * max_single_weight):.1f}".replace('.', ',')
        
        single_tt = (f"Největší pozice ({max_single_ticker}) tvoří {sing_w_str} % majetku.\n\n"
                     f"I ty nejlepší firmy mohou zkrachovat nebo ztratit 50 % hodnoty\n"
                     f"kvůli nečekanému účetnímu skandálu či ztrátě trhu.\n"
                     f"Při takovém scénáři by vaše celkové portfolio ztratilo {sing_drop_str} %.\n\n"
                     f"Diverzifikace vás před tímto 'Stock-picking' rizikem chrání.")

        # 3. Uložení dat do paměti a spuštění překreslení (Trojice: Text, Barva, Tooltip)
        risk_data = {
            'beta': (beta_txt, beta_col, beta_tt),
            'rates': (r_txt, r_col, rate_tt),
            'sector': (sec_str, s_col, sec_tt),
            'single': (single_str, sing_col, single_tt)
        }

        if is_base:
            self._base_risk_data = risk_data
        else:
            self._tuned_risk_data = risk_data

        self._apply_risk_ui()

    def _apply_risk_ui(self):
        """Aplikuje uložená rizika do společného UI panelu podle vybraného radio buttonu."""
        view_mode = getattr(self, 'chart_view_var', tk.StringVar(value="new")).get()
        
        # 1. Výběr správných dat a dynamického nadpisu podle aktuálního režimu
        if view_mode in ["base", "base_decay"]:
            if not hasattr(self, '_base_risk_data'): return
            data = self._base_risk_data
            title = "Analýza rizik (výchozí portfolio)" if view_mode == "base" else "Analýza rizik (výchozí s brzdou)"
        else:
            if not hasattr(self, '_tuned_risk_data'): return
            data = self._tuned_risk_data
            title = "Analýza rizik (nové portfolio)" if view_mode == "new" else "Analýza rizik (nové s brzdou)"

        # 2. Nastavení nadpisu rámečku
        if hasattr(self, 'risk_frame_container'):
            self.risk_frame_container.config(text=title)

        # Pomocná funkce pro navázání Tooltipu na levý text i pravou hodnotu
        def bind_tt(lbl_title, lbl_value, text):
            if hasattr(self, lbl_title):
                widget = getattr(self, lbl_title)
                # Tímto se zajistí, že se předchozí tooltip (např. z base portfolia) bezpečně přepíše
                widget.bind("<Enter>", lambda e, t=text: self._show_tooltip(t))
                widget.bind("<Leave>", lambda e: self._hide_tooltip())
            if hasattr(self, lbl_value):
                widget = getattr(self, lbl_value)
                widget.bind("<Enter>", lambda e, t=text: self._show_tooltip(t))
                widget.bind("<Leave>", lambda e: self._hide_tooltip())

        # Pomocná funkce pro navázání Tooltipu na levý text i pravou hodnotu
        def bind_tt(lbl_title, lbl_value, text):
            if hasattr(self, lbl_title):
                widget = getattr(self, lbl_title)
                # Tímto se zajistí, že se předchozí tooltip (např. z base portfolia) bezpečně přepíše
                widget.bind("<Enter>", lambda e, t=text: self._show_tooltip(t))
                widget.bind("<Leave>", lambda e: self._hide_tooltip())
            if hasattr(self, lbl_value):
                widget = getattr(self, lbl_value)
                widget.bind("<Enter>", lambda e, t=text: self._show_tooltip(t))
                widget.bind("<Leave>", lambda e: self._hide_tooltip())

        if hasattr(self, 'lbl_risk_beta'):
            self.lbl_risk_beta.config(text=data['beta'][0], fg=data['beta'][1])
            self.lbl_risk_rates.config(text=data['rates'][0], fg=data['rates'][1])
            self.lbl_risk_sector.config(text=data['sector'][0], fg=data['sector'][1])
            self.lbl_risk_single.config(text=data['single'][0], fg=data['single'][1])
            
            # Pověšení dynamických Tooltipů
            bind_tt('lbl_title_beta', 'lbl_risk_beta', data['beta'][2])
            bind_tt('lbl_title_rates', 'lbl_risk_rates', data['rates'][2])
            bind_tt('lbl_title_sector', 'lbl_risk_sector', data['sector'][2])
            bind_tt('lbl_title_single', 'lbl_risk_single', data['single'][2])


    def _redraw_tuner_charts(self):
        if getattr(self, 'sim_weights', None) is None: return
        
        view_mode = getattr(self, 'chart_view_var', tk.StringVar(value="new")).get()
        new_weights = self.sim_weights[self.current_sim_idx]
        base_w = np.array([self.tuner_base_weights.get(t, 0) for t in self.ordered_tickers])
        
        # --- 1. VÝPOČET UTLUMENÝCH VAH (BRZDA) ---
        target_yield = 0.03  # Výchozí konzervativní limit 3 %
        if hasattr(self, 'dyn_floor_slider'):
            try:
                target_yield = float(self.dyn_floor_slider.get()) / 100.0
            except:
                pass

        yields_array = self.tuner_stock_divs

        def decay_portfolio_weights(w_nom):
            min_allowed_weights = w_nom * DYN_TARGET_MIN_WEIGHT_FRACTION
            rem_weight = 1.0 - np.sum(min_allowed_weights)
            lowest_yield_available = np.min(yields_array[w_nom > EPSILON_WEIGHT]) if np.any(w_nom > EPSILON_WEIGHT) else 0.0
            
            true_min_portfolio_yield = np.sum(min_allowed_weights * yields_array) + (rem_weight * lowest_yield_available)
            safe_target_yield = max(target_yield, true_min_portfolio_yield + DYN_YIELD_TOLERANCE)
            
            nom_portfolio_yield = np.sum(w_nom * yields_array)
            if nom_portfolio_yield <= safe_target_yield:
                return w_nom.copy()
                
            low, high = 0.0, DYN_BRAKE_MAX_K
            best_w = w_nom.copy()
            
            # --- Toxický yield (0.75 štít) ---
            growths_array = self.tuner_upsides 
            growth_credit = np.maximum(0, growths_array) * 0.75
            toxic_yield = np.maximum(0, yields_array - growth_credit)
            
            active_mask = w_nom > EPSILON_WEIGHT
            if np.any(active_mask):
                toxic_yield[active_mask] -= np.min(toxic_yield[active_mask])
            
            # Načtení uživatelského maxima z UI (ochrana proti přetečení vah)
            max_limit = getattr(self, 'custom_max_w', MAX_W)
            
            for _ in range(DYN_BRAKE_ITERATIONS):
                k = (low + high) / 2.0
                decay_factors = np.exp(-k * toxic_yield)
                w_raw = w_nom * decay_factors
                
                # Zajištění, že nespadneme pod podlahu
                w_raw = np.maximum(w_raw, min_allowed_weights)
                
                if np.sum(w_raw) < 1e-10:
                    high = k
                    continue
                    
                # ---------------------------------------------------------
                # MATEMATICKÁ PROJEKCE S DODRŽENÍM MAXIMÁLNÍCH LIMITŮ
                # ---------------------------------------------------------
                w_norm = w_raw / np.sum(w_raw)
                lambda_shift = 0.0
                for _ in range(20):
                    w_clipped = np.clip(w_norm + lambda_shift, min_allowed_weights, max_limit)
                    diff = 1.0 - np.sum(w_clipped)
                    if abs(diff) < 1e-7:
                        break
                    lambda_shift += diff / len(w_nom)
                    
                w_norm = np.clip(w_norm + lambda_shift, min_allowed_weights, max_limit)
                # ---------------------------------------------------------
                
                simulated_yield = np.sum(w_norm * yields_array)
                
                if simulated_yield > safe_target_yield:
                    low = k
                    best_w = w_norm
                else:
                    high = k
                    best_w = w_norm
            return best_w

        decayed_base_w = decay_portfolio_weights(base_w)
        decayed_new_w = decay_portfolio_weights(new_weights)
        
        # --- 2. VÝBĚR DAT PRO ZOBRAZENÍ A AKTUALIZACE UI ---
        # Zablokování sliderů (smí se používat pouze při ladění "čistého" nového portfolia)
        slider_state = "normal" if view_mode == "new" else "disabled"
        if hasattr(self, 'sliders'):
            for s in self.sliders.values():
                s.config(state=slider_state)
        
        if view_mode == "base":
            plot_weights = base_w
            pie_title_suffix = "(výchozí)"
            main_color = "grey"
        elif view_mode == "base_decay":
            plot_weights = decayed_base_w
            pie_title_suffix = "(výchozí s brzdou)"
            main_color = "dimgrey"
        elif view_mode == "new_decay":
            plot_weights = decayed_new_w
            pie_title_suffix = "(nové s brzdou)"
            main_color = "#0288D1"
        else: # "new"
            plot_weights = new_weights
            pie_title_suffix = "(nové)"
            main_color = "#1976D2"

        # Přepočet a aktualizace textů nad slidery (aby uživatel viděl pravdu i při vypnutém slideru)
        p_div = np.dot(plot_weights, self.tuner_stock_divs) * 100000
        p_rets = np.dot(self.tuner_period_returns.values, plot_weights.T)
        p_cum = (1 + p_rets).cumprod(axis=0)
        p_growth = (p_cum[-1] - 1.0) * 100 if len(p_cum) > 0 else 0
        p_run_max = np.maximum.accumulate(p_cum, axis=0)
        p_dd = np.min((p_cum - p_run_max) / p_run_max, axis=0) * 100
        p_fdiv = np.dot(plot_weights, self.tuner_safe_divs) * 100000
        p_fgrowth_dec = np.dot(plot_weights, self.tuner_upsides)
        p_var = np.dot(plot_weights.T, np.dot(self.tuner_cov_matrix.values, plot_weights))
        p_vol = np.sqrt(p_var)
        p_fdd = -1.645 * p_vol * 100
        p_fgrowth = p_fgrowth_dec * 100

        self.lbl_div_val.config(text=f"{p_div:.0f} Kč".replace(',', ' '))
        self.lbl_dd_val.config(text=f"{p_dd:.1f} %".replace('.', ','))
        self.lbl_growth_val.config(text=f"{p_growth:.1f} %".replace('.', ','))
        self.lbl_fdiv_val.config(text=f"{p_fdiv:.0f} Kč".replace(',', ' '))
        self.lbl_fdd_val.config(text=f"{p_fdd:.1f} %".replace('.', ','))
        self.lbl_fgrowth_val.config(text=f"{p_fgrowth:.1f} %".replace('.', ','))

        # Propagace do panelu "Analýza rizik (Semafor)"
        self._update_risk_dashboard(plot_weights, is_base=(view_mode in ["base", "base_decay"]))
        self._apply_risk_ui()
        
        self.ax_pie.clear(); self.ax_div_pie.clear(); self.ax_curve.clear(); self.ax_bars.clear()
        self._current_pie_weights = plot_weights
        
        # --- 3. KOLÁČOVÉ GRAFY ---
        LABELS_LIMIT_PERCENT = 0.001
        labels_weights = [f"{t}\n{f'{w:.1%}'.replace('.', ',')}" if w > LABELS_LIMIT_PERCENT else "" for t, w in zip(self.ordered_tickers, plot_weights)]
        self.wedges_weights, _ = self.ax_pie.pie(plot_weights, labels=labels_weights, startangle=140, colors=plt.cm.tab20.colors)
        self.ax_pie.set_title(f"Rozložení vah {pie_title_suffix}")
        
        ticker_div_czk = plot_weights * self.tuner_stock_divs * 100000
        div_tickers, div_sizes = [],[]
        sorted_indices = np.argsort(ticker_div_czk)[::-1]
        for i in sorted_indices:
            if ticker_div_czk[i] > 0:
                div_tickers.append(self.ordered_tickers[i]); div_sizes.append(ticker_div_czk[i])
        
        if div_sizes:
            total_div = sum(div_sizes)
            LABELS_LIMIT_DIV = 0.04
            f_labels =[l if (s/total_div) > LABELS_LIMIT_DIV else "" for l, s in zip(div_tickers, div_sizes)]
            self.wedges_divs, _, _ = self.ax_div_pie.pie(div_sizes, labels=f_labels, autopct=lambda p: f'{p:.1f}%'.replace('.', ',') if p > (100*LABELS_LIMIT_DIV) else '', startangle=140, colors=plt.cm.tab20b.colors)
            self.div_data_tickers = div_tickers; self.div_data_sizes = div_sizes
            self.ax_div_pie.set_title(f"Zdroje dividend {pie_title_suffix}")
            
            if len(div_sizes) > 0:
                max_share = div_sizes[0] / total_div
                if max_share > MAX_DIV_SHARE:
                    self.ax_div_pie.text(0, -1.35, f"⚠️ Varování: Akcie {div_tickers[0]} generuje {max_share*100:.1f} % dividend".replace('.', ','), 
                                         ha='center', color='#E65100', fontsize=11, fontweight='bold')
        
        # --- 4. HLAVNÍ GRAF: HISTORIE + PREDIKCE ---
        daily_pct_changes = self.tuner_hist_prices.pct_change().fillna(0)
        
        curve_base = (1 + daily_pct_changes.dot(base_w)).cumprod() * 100000
        curve_base_decayed = (1 + daily_pct_changes.dot(decayed_base_w)).cumprod() * 100000
        curve_new = (1 + daily_pct_changes.dot(new_weights)).cumprod() * 100000
        curve_new_decayed = (1 + daily_pct_changes.dot(decayed_new_w)).cumprod() * 100000
        curve_to_plot = (1 + daily_pct_changes.dot(plot_weights)).cumprod() * 100000
        
        # Kreslení S&P 500
        if hasattr(self, 'tuner_spy_prices') and not self.tuner_spy_prices.empty:
            spy_aligned = self.tuner_spy_prices.reindex(daily_pct_changes.index).ffill().bfill()
            curve_spy = (spy_aligned / spy_aligned.iloc[0]) * 100000
            self.ax_curve.plot(curve_spy.index, curve_spy.values, color='#D32F2F', linestyle=':', linewidth=1.5, label='S&P 500', alpha=0.7)
            
            last_date = curve_spy.index[-1]
            last_val_spy = curve_spy.values[-1]
            future_dates = pd.bdate_range(start=last_date, periods=252)
            
            spy_ann_return = (curve_spy.values[-1] / curve_spy.values[0]) ** (1/5.0) - 1.0
            spy_daily_drift = spy_ann_return / 252.0
            spy_path = last_val_spy * np.exp(spy_daily_drift * np.arange(1, 253))
            self.ax_curve.plot(future_dates, spy_path, color='#D32F2F', linestyle=':', linewidth=1.5, alpha=0.5)

        # Referenční křivky na pozadí
        if view_mode in ["new", "new_decay"]:
            self.ax_curve.plot(curve_base.index, curve_base.values, color='grey', linestyle='--', label='Výchozí', alpha=0.5)
            self.ax_curve.plot(curve_base_decayed.index, curve_base_decayed.values, color='grey', linestyle=':', linewidth=1.2, label='Výchozí s brzdou', alpha=0.5)
            
            if view_mode == "new":
                self.ax_curve.plot(curve_new_decayed.index, curve_new_decayed.values, color=main_color, linestyle=':', linewidth=1.2, label='Nové s brzdou', alpha=0.8)
            else:
                self.ax_curve.plot(curve_new.index, curve_new.values, color=main_color, linestyle='-', linewidth=1.0, label='Nové', alpha=0.5)

        elif view_mode == "base":
            self.ax_curve.plot(curve_base_decayed.index, curve_base_decayed.values, color=main_color, linestyle=':', linewidth=1.2, label='Výchozí s brzdou', alpha=0.8)
        elif view_mode == "base_decay":
            self.ax_curve.plot(curve_base.index, curve_base.values, color=main_color, linestyle='-', linewidth=1.0, label='Výchozí', alpha=0.5)

        # Kreslení hlavní vybrané křivky (dostane Trychtýř nejistoty a Daňovou linii)
        self.ax_curve.plot(curve_to_plot.index, curve_to_plot.values, color=main_color, linewidth=2, label=f'Portfolio {pie_title_suffix} (hrubé)')
        
        # Zdaněná křivka (aplikace srážkové daně z dividend)
        current_weights_div_yield = np.dot(plot_weights, self.tuner_stock_divs)
        tax_drag_annual = current_weights_div_yield * DEFAULT_TAX_RATE
        daily_tax_drag = tax_drag_annual / 252.0
        daily_portfolio_returns = daily_pct_changes.dot(plot_weights)
        daily_net_returns = daily_portfolio_returns - daily_tax_drag
        curve_net = (1 + daily_net_returns).cumprod() * 100000
        
        self.ax_curve.plot(curve_net.index, curve_net.values, color='#81D4FA', linestyle='-', linewidth=1.5, label=f'Portfolio {pie_title_suffix} (zdaněné)')
        
        # Trychtýř (Funnel)
        last_date = curve_to_plot.index[-1]
        last_val = curve_to_plot.values[-1]
        future_dates = pd.bdate_range(start=last_date, periods=252)
        
        daily_drift = (p_fgrowth / 100.0) / 252.0
        cov_mat = self.tuner_cov_matrix.values
        annual_vol = np.sqrt(np.dot(plot_weights.T, np.dot(cov_mat, plot_weights)))
        daily_vol = annual_vol / np.sqrt(252)
        
        time_steps = np.arange(1, 253)
        expected_path = last_val * np.exp((daily_drift - 0.5 * daily_vol**2) * time_steps)
        upper_2sig = last_val * np.exp((daily_drift - 0.5 * daily_vol**2) * time_steps + 2 * daily_vol * np.sqrt(time_steps))
        lower_2sig = last_val * np.exp((daily_drift - 0.5 * daily_vol**2) * time_steps - 2 * daily_vol * np.sqrt(time_steps))

        self.ax_curve.axvline(x=last_date, color='red', linestyle='--', linewidth=1, alpha=0.7)
        self.ax_curve.plot(future_dates, expected_path, color='#F57F17', linestyle='-.', linewidth=2, label='Predikce růstu (střed)')
        self.ax_curve.fill_between(future_dates, lower_2sig, upper_2sig, color='#FFF59D', alpha=0.4, label='95% Trychtýř nejistoty')
        
        # ---------------------------------------------------------------------
        # FIXACE MĚŘÍTKA Y-OSY (Pro snadné porovnávání všech 4 scénářů)
        # ---------------------------------------------------------------------
        # 1. Extrakce extrémů z historických křivek
        c_min = min(curve_base.min(), curve_base_decayed.min(), curve_new.min(), curve_new_decayed.min())
        c_max = max(curve_base.max(), curve_base_decayed.max(), curve_new.max(), curve_new_decayed.max())
        
        # 2. Zohlednění S&P 500, pokud je vykreslen
        if 'curve_spy' in locals() and 'spy_path' in locals():
            c_min = min(c_min, curve_spy.min(), spy_path.min())
            c_max = max(c_max, curve_spy.max(), spy_path.max())
            
        # 3. Zohlednění budoucích trychtýřů všech 4 scénářů
        for w in [base_w, decayed_base_w, new_weights, decayed_new_w]:
            drift = np.dot(w, self.tuner_upsides) / 252.0
            vol = np.sqrt(np.dot(w.T, np.dot(self.tuner_cov_matrix.values, w))) / np.sqrt(252)
            l_val = ((1 + daily_pct_changes.dot(w)).cumprod() * 100000).iloc[-1]
            
            f_low = l_val * np.exp((drift - 0.5 * vol**2) * 252 - 2 * vol * np.sqrt(252))
            f_high = l_val * np.exp((drift - 0.5 * vol**2) * 252 + 2 * vol * np.sqrt(252))
            c_min = min(c_min, f_low)
            c_max = max(c_max, f_high)
            
        # Aplikace limitů (s 5% vizuálním polštářem nahoře i dole)
        margin = (c_max - c_min) * 0.05
        self.ax_curve.set_ylim(c_min - margin, c_max + margin)

        self.ax_curve.set_title(f"Simulace 100k Kč {pie_title_suffix}")
        self.ax_curve.grid(True, linestyle='--', alpha=0.5)
        self.ax_curve.legend(loc='upper left', fontsize=8)

        # --- 5. BAR CHART (Sloupcový graf výkonu po letech) ---
        years = sorted(list(set(self.tuner_hist_prices.index.year)))
        bars_ref, bars_main, lbls = [], [], []
        
        # Automatický výběr referenční křivky pro porovnání
        if view_mode in ["new", "base"]:
            curve_ref_all = curve_base
        else:
            curve_ref_all = curve_base_decayed
            
        curve_main_all = curve_to_plot
        
        for y in years:
            sb = curve_ref_all[curve_ref_all.index.year == y]
            sn = curve_main_all[curve_main_all.index.year == y]
            if len(sb) > 0 and len(sn) > 0:
                bars_ref.append(sb.iloc[-1] - sb.iloc[0])
                bars_main.append(sn.iloc[-1] - sn.iloc[0])
                lbls.append(str(y))

        x = np.arange(len(lbls)); width = 0.35
        if view_mode in ["base", "base_decay"]:
            self.ax_bars.bar(x, bars_main, width*2, label='Total return', color=main_color)
        else:
            self.ax_bars.bar(x - width/2, bars_ref, width, label='Základ', color='lightgrey')
            self.ax_bars.bar(x + width/2, bars_main, width, label='Nové', color='#4CAF50')
        
        # ---------------------------------------------------------------------
        # FIXACE MĚŘÍTKA Y-OSY PRO SLOUPCOVÝ GRAF
        # ---------------------------------------------------------------------
        global_bars = []
        for c in [curve_base, curve_base_decayed, curve_new, curve_new_decayed]:
            for y in years:
                sc = c[c.index.year == y]
                if len(sc) > 0:
                    global_bars.append(sc.iloc[-1] - sc.iloc[0])
                    
        if global_bars:
            gb_min, gb_max = min(global_bars), max(global_bars)
            if gb_min > 0: gb_min = 0  # Pokud jsme vždy v plusu, ať graf začíná přirozeně od 0
            if gb_max < 0: gb_max = 0  # Pro případ globální ztráty (graf visící dolů)
            
            # Aplikace limitů (s 15% vizuálním polštářem)
            pad = (gb_max - gb_min) * 0.15
            self.ax_bars.set_ylim(gb_min - pad, gb_max + pad)

        self.ax_bars.set_xticks(x); self.ax_bars.set_xticklabels(lbls)
        self.ax_bars.set_title("Roční zisk [Kč]")
        self.ax_bars.grid(axis='y', linestyle='--', alpha=0.5); self.ax_bars.legend(fontsize=8)
        
        self.canvas_tune.draw()
        
    def apply_tuned_weights(self):
        if getattr(self, 'tuner_loading_state', {}).get("is_loading"): return
        if self.sim_metrics is None: return
        
        # Zkontrolujeme a opravíme textová pole těsně před zápisem dat do JSONu
        if hasattr(self, '_validate_and_get_limits'):
            self._validate_and_get_limits()
            
        global TARGETS
        new_w = self.sim_weights[self.current_sim_idx]
        
        # Proměnná pro uchování přesného součtu vah všech akcií kromě té úplně poslední
        accumulated_sum = 0.0
        
        # Zjistíme celkový počet akcií v aktuálním tuningu
        total_stocks = len(self.ordered_tickers)
        
        # Projdeme všechny akcie pomocí indexu, abychom bezpečně poznali tu poslední
        for i in range(total_stocks):
            t = self.ordered_tickers[i]
            
            if i < total_stocks - 1:
                # ---------------------------------------------------------
                # PRO VŠECHNY AKCIE KROMĚ POSLEDNÍ
                # ---------------------------------------------------------
                weight = float(new_w[i])
                
                # Zápis do hlavních proměnných
                TARGETS[t] = weight
                self.tuner_base_weights[t] = weight
                
                # Přičteme do průběžného součtu
                accumulated_sum += weight
            else:
                # ---------------------------------------------------------
                # PRO ÚPLNĚ POSLEDNÍ AKCII
                # ---------------------------------------------------------
                # Váhu dopočítáme jako čistý rozdíl, aby součet dal přesně 1.0 (100 %)
                final_weight = 1.0 - accumulated_sum
                
                # Drobná bezpečnostní pojistka: 
                # Kdyby kvůli matematické chybě floatů byl accumulated_sum např. 1.000000001,
                # final_weight by vyšla záporná. Funkce max() zaručí, že nikdy neklesne pod 0.
                final_weight = max(0.0, final_weight)
                
                # Zápis vypočítané poslední váhy do hlavních proměnných
                TARGETS[t] = final_weight
                self.tuner_base_weights[t] = final_weight
                
        self.save_data()
            
        
        # 'metrics' už je pole o 6 prvcích z vybrané simulace, takže ho jen předáme dál
        metrics = self.sim_metrics[self.current_sim_idx]
        self._update_base_labels(metrics)
        self._update_risk_dashboard(new_w, is_base=True)

        # ---------------------------------------------------------------------
        # INVALIDACE STARÝCH VÝPOČTŮ (PROJEVENÍ ZMĚN VE ZBYTKU APLIKACE)
        # ---------------------------------------------------------------------
        # Jelikož proměnná TARGETS je globální, matematické jádro už nové váhy zná.
        # Nyní ale musíme smazat staré výsledky z obrazovek, aby uživatel neprovedl 
        # obchody podle neplatných tabulek a byl nucen si návrhy nechat spočítat znovu.
        
        # 1. Vymazání starého návrhu na záložce "Nákup"
        if hasattr(self, 'buy_tree'):
            for item in self.buy_tree.get_children():
                self.buy_tree.delete(item)
                
        # 2. Vymazání kalkulátoru pro výběr hotovosti na záložce "Prodej"
        # (Tento kalkulátor také používá cílové váhy)
        if hasattr(self, 'sell_staging_tree'):
            for item in self.sell_staging_tree.get_children():
                self.sell_staging_tree.delete(item)
                
        # 3. Invalidace záložky "Kalendář dividend"
        # Pokud si tam uživatel dříve nechal vykreslit "Teoretické portfolio",
        # po změně vah grafy přestanou platit.
        if hasattr(self, 'div_tree') and hasattr(self, 'div_mode_var'):
            if self.div_mode_var.get() == "target":
                # Vyprázdnění tabulky dividend
                for item in self.div_tree.get_children():
                    self.div_tree.delete(item)
                # Změna textu pod grafem, aby bylo zřejmé, že musí načíst data znovu
                if hasattr(self, 'div_total_lbl'):
                    self.div_total_lbl.config(text="Změněny váhy. Prosím, načtěte data znovu.")
                # Změna stavového popisku
                if hasattr(self, 'div_status_lbl'):
                    self.div_status_lbl.config(text="Čekám na přepočet...", fg="grey")

        # Aktualizace maxima slideru na záložce Nákup
        if hasattr(self, 'dyn_floor_slider'):
            # MÍSTO STATICKÉ DATABÁZE POUŽIJEME ŽIVÁ DATA Z TUNERU
            # new_w = váhy z vybrané simulace, self.tuner_stock_divs = pole živých dividendových výnosů
            if hasattr(self, 'tuner_stock_divs') and len(self.tuner_stock_divs) == len(new_w):
                nom_yield = float(np.dot(new_w, self.tuner_stock_divs))
            else:
                nom_yield = getattr(self, 'last_nominal_yield', 0.04)
                
            self.last_nominal_yield = nom_yield # Aktualizujeme paměť aplikace pro tooltipy a start
            max_slider = round(nom_yield * 100, 2)
            
            if max_slider < 0.5: max_slider = 5.0
            
            self.dyn_floor_slider.config(to=max_slider)
            
            # Ochrana: pokud nové maximum kleslo pod to, co měl uživatel zrovna nastaveno
            if float(self.dyn_floor_slider.get()) > max_slider:
                self.dyn_floor_slider.set(max_slider)
                self.dyn_yield_cap = max_slider
                self.save_data()

        # Aktualizace checkboxů na kartě nákupů
        if hasattr(self, '_build_buy_checkboxes'):
            self._build_buy_checkboxes()
            
        messagebox.showinfo("Úspěch", "Nové cílové váhy byly úspěšně aplikovány a uloženy do souboru. Záložka Nákupu bude nyní počítat návrhy s těmito novými vahami.")

    # --------------------------------------------------------------------------
    # TAB 5: STATISTIKY PORTFOLIA A EXPORTY
    # --------------------------------------------------------------------------

    def setup_dashboard_tab(self):
        """Sestaví UI Dashboardu zobrazujícího historický výkon a daňové ovládání."""
        self.dash_frame = tk.Frame(self.notebook, bg="#ECEFF1")
        self.notebook.add(self.dash_frame, text="Statistiky & Daně")
        ctrl_panel = tk.Frame(self.dash_frame, bg="#ECEFF1")
        ctrl_panel.pack(fill=tk.X, padx=10, pady=10)
        
        # Uložení referencí na tlačítka pro možnost jejich deaktivace
        self.btn_refresh_stats = tk.Button(ctrl_panel, text="↻ AKTUALIZOVAT DATA", 
                                          command=self.start_incremental_refresh, 
                                          font=("Arial", 12, "bold"), bg="#37474F", fg="white")
        self.btn_refresh_stats.pack(side=tk.LEFT)

        # Rámeček pro daňový odhad
        tax_info_frame = tk.Frame(ctrl_panel, bg="#ECEFF1")
        tax_info_frame.pack(side=tk.RIGHT, padx=20)
        self.tax_estimate_lbl = tk.Label(tax_info_frame, text=f"Odhad daně za rok {datetime.now().year}: 0 Kč", font=("Arial", 11, "bold"), bg="#ECEFF1", fg="#BF360C")
        self.tax_estimate_lbl.pack()
        
        self.btn_export_tax = tk.Button(ctrl_panel, text="📄 EXPORT PDF + XML (DANĚ)", 
                                        command=self.generate_tax_report, 
                                        font=("Arial", 12, "bold"), bg="#E65100", fg="white")
        self.btn_export_tax.pack(side=tk.RIGHT, padx=10)
        
        self.status_lbl = tk.Label(ctrl_panel, text="Čekám...", bg="#ECEFF1", fg="grey", font=("Arial", 12))
        self.status_lbl.pack(side=tk.LEFT, padx=10)

        content = tk.Frame(self.dash_frame, bg="#ECEFF1")
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.fig, (self.ax1, self.ax2, self.ax3) = plt.subplots(3, 1, figsize=(10, 10), tight_layout=True)
        self.fig.patch.set_facecolor('#ECEFF1')
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=content)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.dash_loading_state = self._create_loading_card(self.dash_frame)

    def _set_dash_controls_state(self, state):
        """Zapíná/vypíná ovládací prvky na kartě Statistiky během výpočtu."""
        if hasattr(self, 'btn_refresh_stats') and self.btn_refresh_stats.winfo_exists():
            self.btn_refresh_stats.config(state=state)
        if hasattr(self, 'btn_export_tax') and self.btn_export_tax.winfo_exists():
            self.btn_export_tax.config(state=state)
            
    def start_incremental_refresh(self):
        # 1. Zvýšíme verzi. Tím se všechna aktuálně běžící vlákna dozví, že jsou zastaralá.
        self.dash_fetch_version = getattr(self, 'dash_fetch_version', 0) + 1
        current_version = self.dash_fetch_version
        
        self.show_loading(self.dash_loading_state, "Stahuji data za 5 let...")
        self._set_dash_controls_state(tk.DISABLED)
        
        # 2. Předáme ID verze přímo do nového vlákna
        threading.Thread(target=self._incremental_fetch_worker, args=(current_version,), daemon=True).start()

    def _incremental_fetch_worker(self, current_version):
        try:
            if not os.path.exists(PORTFOLIO_FILE): return
            
            # Bezpečnostní kontrola - nebylo už spuštěno novější vlákno?
            if getattr(self, 'dash_fetch_version', 0) != current_version: return
            
            all_tickers_set = set(TARGETS.keys())
            all_tickers_set.update(self.ledger.keys())
            for s in self.sales_history: all_tickers_set.add(s['ticker'])
            all_tickers = list(all_tickers_set)

            if not all_tickers: return
            fx = self.get_fx_rates()
            download_tickers = all_tickers + ["SPY"]
            
            self.root.after(0, lambda: self.status_lbl.config(text="Stahuji historii dividend...", fg="blue"))
            all_divs = {}
            for t in all_tickers:
                # Kontrola, zda mezitím nevznikl novější požadavek (např. rychlý restart appky)
                if getattr(self, 'dash_fetch_version', 0) != current_version: 
                    return
                all_divs[t] = self._safe_get_dividends(t)
            
            # Kontrola po stažení dividend (mohlo to trvat 10 vteřin)
            if getattr(self, 'dash_fetch_version', 0) != current_version: return
            
            current_year = datetime.now().year
            start_date = f"{current_year - 5}-01-01"
            
            self.root.after(0, lambda: self.status_lbl.config(text="Stahuji historii měnových kurzů...", fg="blue"))
            fx_history_raw = self._safe_yf_download(["USDCZK=X", "GBPCZK=X"], start=start_date, auto_adjust=False)
            fx_history = fx_history_raw['Close'].ffill().bfill() if 'Close' in fx_history_raw else fx_history_raw.ffill().bfill()

            # Kontrola po stažení FX kurzů
            if getattr(self, 'dash_fetch_version', 0) != current_version: return

            self.root.after(0, lambda: self.status_lbl.config(text="Stahuji 5letou historii cen akcií...", fg="blue"))
            downloaded = self._safe_yf_download(download_tickers, start=start_date, auto_adjust=False)

            if downloaded.empty or 'Close' not in downloaded:
                if getattr(self, 'dash_fetch_version', 0) == current_version:
                    self.root.after(0, lambda: self.status_lbl.config(text="Chyba stahování", fg="red"))
                return

            # Pro PnL grafy potřebujeme striktně reálné čisté ceny na trhu (Close),
            # ale pro šedou hypotetickou simulaci potřebujeme Adj Close, aby simulovala reinvestované dividendy.
            if 'Adj Close' in downloaded:
                c_adj = downloaded['Adj Close'].replace(0.0, np.nan)
                c_raw = downloaded['Close'].replace(0.0, np.nan)
            else:
                c_adj = downloaded['Close'].replace(0.0, np.nan)
                c_raw = c_adj

            if isinstance(c_adj, pd.Series): 
                c_adj = c_adj.to_frame(name=download_tickers[0])
                c_raw = c_raw.to_frame(name=download_tickers[0])
                
            adj_clean = c_adj.ffill().bfill()
            raw_clean = c_raw.ffill().bfill()

            if getattr(self, 'dash_fetch_version', 0) != current_version: return

            self.root.after(0, lambda: self.hide_loading(self.dash_loading_state))
            self.root.after(0, lambda: self.btn_export_tax.config(state=tk.NORMAL))
            
            self.root.after(0, lambda a=adj_clean.copy(), r=raw_clean.copy(), f=fx, fh=fx_history, t=all_tickers, d=all_divs, v=current_version: 
                            self._render_stats_graphs_ui(a, r, f, fh, t, d, True, v))
                
        except Exception as e:
            if getattr(self, 'dash_fetch_version', 0) == current_version:
                print(f"Error in fetch worker: {e}")
                self.root.after(0, lambda: self.status_lbl.config(text="Chyba výpočtu", fg="red"))
        finally:
            if getattr(self, 'dash_fetch_version', 0) == current_version:
                self.root.after(0, lambda: self._set_dash_controls_state(tk.NORMAL))
                self.root.after(0, lambda: self.hide_loading(self.dash_loading_state))

    def _render_stats_graphs_ui(self, hist_prices_adj, hist_prices_raw, fx, fx_history, all_tickers, all_divs, is_final, current_version=None):
        if current_version is not None and getattr(self, 'dash_fetch_version', 0) != current_version:
            return

        try:
            # Pomocná funkce pro bezpečné vytažení historického FX kurzu (pokud není uložen u tradu)
            def get_historical_fx(currency, date_str):
                if currency not in ["USD", "GBP"]: return 1.0
                col = "USDCZK=X" if currency == "USD" else "GBPCZK=X"
                if fx_history is None or fx_history.empty or col not in fx_history.columns: return fx.get(currency, 23.0)
                try:
                    dt = pd.Timestamp(date_str)
                    past = fx_history[col].loc[:dt]
                    if not past.empty: return float(past.iloc[-1])
                    return float(fx_history[col].bfill().iloc[0])
                except: return fx.get(currency, 23.0)

            ledger_dt = {t: [{'date': pd.Timestamp(l['date']), 'qty': l['qty'], 'price_at_buy': l['price_at_buy'], 'fx_rate': l.get('fx_rate'), 'fee': l.get('fee', 0.0)} for l in lots] for t, lots in self.ledger.items()}
            sales_dt = [{'buy_date': pd.Timestamp(s['buy_date']), 'sell_date': pd.Timestamp(s['sell_date']), 'qty': s['qty'], 'ticker': s['ticker'], 'sell_price': s['sell_price'], 'buy_price': s['buy_price'], 'currency': s.get('currency', 'USD'), 'buy_fx': s.get('buy_fx_rate'), 'sell_fx': s.get('sell_fx_rate'), 'buy_fee': s.get('buy_fee', 0.0), 'sell_fee': s.get('sell_fee', 0.0)} for s in self.sales_history]

            ledger_dates = [l['date'] for t, lots in ledger_dt.items() for l in lots]
            max_d = max([hist_prices_raw.index.max(), pd.Timestamp(datetime.now().date())] + ledger_dates)
            full_idx = pd.date_range(start=hist_prices_raw.index.min(), end=max_d)
            
            hist_prices_raw = hist_prices_raw.reindex(full_idx).ffill()
            hist_prices_adj = hist_prices_adj.reindex(full_idx).ffill()
            
            all_buy_dates = [l['date'] for t in self.ledger for l in self.ledger.get(t,[])]
            has_buys = len(all_buy_dates) > 0
            first_buy_dt = pd.Timestamp(min(all_buy_dates)) if has_buys else None
            first_buy_year = first_buy_dt.year if has_buys else 9999

            # =================================================================
            # 1. VÝPOČET PRŮMĚRNÉHO POPLATKU UŽIVATELE PRO S&P 500 BENCHMARK
            # =================================================================
            total_fees_czk = 0.0
            total_volume_czk = 0.0

            for t, lots in ledger_dt.items():
                curr = self.get_currency_for_ticker(t)
                p_factor = 0.01 if t.endswith('.L') else 1.0
                for lot in lots:
                    fx_val = lot.get('fx_rate') or get_historical_fx(curr, lot['date'])
                    val_czk = lot['qty'] * float(lot['price_at_buy']) * p_factor * fx_val
                    total_volume_czk += val_czk
                    total_fees_czk += lot.get('fee', 0.0) * fx_val

            for s in sales_dt:
                curr = s.get('currency', 'USD')
                b_fx = s.get('buy_fx') or get_historical_fx(curr, s['buy_date'])
                s_fx = s.get('sell_fx') or get_historical_fx(curr, s['sell_date'])
                p_factor = 0.01 if s['ticker'].endswith('.L') else 1.0
                
                b_val = s['qty'] * float(s['buy_price']) * p_factor * b_fx
                s_val = s['qty'] * float(s['sell_price']) * p_factor * s_fx
                
                total_volume_czk += (b_val + s_val)
                total_fees_czk += (s.get('buy_fee', 0.0) * b_fx) + (s.get('sell_fee', 0.0) * s_fx)

            # Průměrný poplatek v procentech (např. 0.0015 = 0.15 %)
            # Fallback 0.15% v případě, že je portfolio zatím prázdné
            avg_fee_pct = total_fees_czk / total_volume_czk if total_volume_czk > 0 else 0.0015

            # =================================================================
            # 2. SESTAVENÍ MATIC MNOŽSTVÍ A KŘIVEK
            # =================================================================
            qty_matrix = pd.DataFrame(0.0, index=hist_prices_raw.index, columns=all_tickers)
            for t, lots in ledger_dt.items():
                for lot in lots:
                    if lot['date'] >= qty_matrix.index[0]: qty_matrix.loc[lot['date']:, t] += lot['qty']
                    else: qty_matrix.loc[:, t] += lot['qty']
                    
            for s in sales_dt:
                t = s['ticker']
                if s['buy_date'] >= qty_matrix.index[0]: qty_matrix.loc[s['buy_date']:, t] += s['qty']
                else: qty_matrix.loc[:, t] += s['qty']
                if s['sell_date'] >= qty_matrix.index[0]: qty_matrix.loc[s['sell_date']:, t] -= s['qty']
                else: qty_matrix.loc[:, t] -= s['qty']
            
            # --- SKUTEČNÁ KŘIVKA PORTFOLIA ---
            real_portfolio_curve_actual = pd.Series(0.0, index=hist_prices_raw.index)
            for t in all_tickers:
                if t in hist_prices_raw.columns:
                    p_factor = 0.01 if t.endswith(".L") else 1.0
                    curr = self.get_currency_for_ticker(t)
                    fx_col = "GBPCZK=X" if curr == "GBP" else "USDCZK=X"
                    
                    if fx_col in fx_history.columns:
                        fx_actual_series = fx_history[fx_col].reindex(hist_prices_raw.index).ffill().bfill()
                    else:
                        fx_actual_series = pd.Series(fx.get(curr, 23.0), index=hist_prices_raw.index)
                        
                    real_portfolio_curve_actual += qty_matrix[t] * hist_prices_raw[t] * p_factor * fx_actual_series

            # --- HYPOTETICKÁ SIMULACE (Šedá čára pro minulost) ---
            # Zjištění aktuální celkové hodnoty pro poměrové škálování
            current_values_czk = {}
            total_portfolio_now = 0.0
            last_prices = hist_prices_raw.iloc[-1] 
            
            for t in all_tickers:
                qty_now = sum(l['qty'] for l in self.ledger.get(t,[]))
                if qty_now > 0 and t in hist_prices_raw.columns:
                    p = last_prices[t] / (100.0 if t.endswith(".L") else 1.0)
                    val = p * qty_now * fx.get(self.get_currency_for_ticker(t), 23.0)
                    current_values_czk[t] = val
                    total_portfolio_now += val
            
            actual_weights = {t: val / total_portfolio_now for t, val in current_values_czk.items()} if total_portfolio_now > 0 else TARGETS
            
            # Simulace na bázi denních výnosů (včetně reinvestice dividend přes Adj Close)
            daily_pct_changes = hist_prices_adj.pct_change().fillna(0)
            w_vector = np.array([actual_weights.get(col, 0.0) for col in hist_prices_adj.columns])
            portfolio_daily_returns = daily_pct_changes.dot(w_vector)
            norm_curve = (1 + portfolio_daily_returns).cumprod()
            
            # Škálování simulace (šedé čáry) tak, aby končila na dnešní celkové tržní hodnotě majetku.
            # Tím ukážeme zpětný hypotetický vývoj kapitálu, který dnes reálně na účtu vlastníte.
            scaling_factor = total_portfolio_now / norm_curve.iloc[-1] if norm_curve.iloc[-1] > 0 else 1.0
            sim_curve = norm_curve * scaling_factor

            # --- S&P 500 BENCHMARK (s poplatky) ---
            spy_benchmark_curve = pd.Series(0.0, index=hist_prices_raw.index)
            if "SPY" in hist_prices_raw.columns:
                spy_qty_series = pd.Series(0.0, index=hist_prices_raw.index)
                
                def get_market_price(prices_df, ticker, dt):
                    if ticker not in prices_df.columns: return 0.0
                    series = prices_df[ticker]
                    if dt in series.index: return series[dt]
                    past = series[:dt]
                    if not past.empty: return past.iloc[-1]
                    return series.bfill().iloc[0]

                # Nákupy
                for t, lots in ledger_dt.items():
                    curr = self.get_currency_for_ticker(t)
                    p_factor = 0.01 if t.endswith(".L") else 1.0
                    for lot in lots:
                        dt = lot['date']
                        fx_t = lot.get('fx_rate') or get_historical_fx(curr, dt)
                        stock_market_price = get_market_price(hist_prices_raw, t, dt)
                        
                        # Hrubá investovaná částka v CZK
                        gross_czk_val = lot['qty'] * stock_market_price * p_factor * fx_t
                        
                        # Simulace nákupu SPY: odečteme z ní zjištěný průměrný poplatek
                        fee_czk = gross_czk_val * avg_fee_pct
                        net_czk_val = gross_czk_val - fee_czk
                        
                        spy_p = get_market_price(hist_prices_raw, "SPY", dt)
                        spy_fx = get_historical_fx("USD", dt)
                        
                        if pd.notna(spy_p) and spy_p > 0:
                            spy_shares = net_czk_val / (spy_p * spy_fx)
                            if dt >= spy_qty_series.index[0]: spy_qty_series.loc[dt:] += spy_shares
                            else: spy_qty_series.loc[:] += spy_shares

                # Prodeje v historii
                for s in sales_dt:
                    t = s['ticker']
                    curr = s.get('currency', 'USD')
                    p_factor = 0.01 if t.endswith(".L") else 1.0

                    # 1. Nákup SPY z dřívějška
                    buy_dt = s['buy_date']
                    b_fx = s.get('buy_fx') or get_historical_fx(curr, buy_dt)
                    stock_buy_p = get_market_price(hist_prices_raw, t, buy_dt)
                    
                    gross_buy_czk = s['qty'] * stock_buy_p * p_factor * b_fx
                    net_buy_czk = gross_buy_czk - (gross_buy_czk * avg_fee_pct)
                    
                    spy_buy_p = get_market_price(hist_prices_raw, "SPY", buy_dt)
                    spy_buy_fx = get_historical_fx("USD", buy_dt)
                    if pd.notna(spy_buy_p) and spy_buy_p > 0:
                        spy_buy_shares = net_buy_czk / (spy_buy_p * spy_buy_fx)
                        if buy_dt >= spy_qty_series.index[0]: spy_qty_series.loc[buy_dt:] += spy_buy_shares
                        else: spy_qty_series.loc[:] += spy_buy_shares

                    # 2. Prodej SPY 
                    sell_dt = s['sell_date']
                    s_fx = s.get('sell_fx') or get_historical_fx(curr, sell_dt)
                    stock_sell_p = get_market_price(hist_prices_raw, t, sell_dt)
                    
                    gross_sell_czk = s['qty'] * stock_sell_p * p_factor * s_fx
                    
                    # Aby fiktivní investor mohl vybrat tu samou hrubou částku, 
                    # musí prodat SPY v hodnotě částky + poplatku.
                    fee_czk = gross_sell_czk * avg_fee_pct
                    total_to_sell_czk = gross_sell_czk + fee_czk
                    
                    spy_sell_p = get_market_price(hist_prices_raw, "SPY", sell_dt)
                    spy_sell_fx = get_historical_fx("USD", sell_dt)
                    if pd.notna(spy_sell_p) and spy_sell_p > 0:
                        spy_sell_shares = total_to_sell_czk / (spy_sell_p * spy_sell_fx)
                        if sell_dt >= spy_qty_series.index[0]: spy_qty_series.loc[sell_dt:] -= spy_sell_shares
                        else: spy_qty_series.loc[:] -= spy_sell_shares

                # Přepočet nasbíraných kusů SPY na CZK pomocí živého měnového kurzu
                spy_fx_series = fx_history['USDCZK=X'].reindex(hist_prices_raw.index).ffill().bfill() if 'USDCZK=X' in fx_history.columns else pd.Series(fx.get("USD", 23.0), index=hist_prices_raw.index)
                spy_benchmark_curve = spy_qty_series * hist_prices_raw["SPY"] * spy_fx_series

            # --- GRAF 1: VÝVOJ HODNOTY ---
            self.ax1.clear()
            
            if has_buys:
                # 1. Šedá čára: Hypotetická historie
                sim_to_plot = sim_curve[:first_buy_dt]
                self.ax1.plot(sim_to_plot.index, sim_to_plot.values, color='grey', linestyle='--', alpha=0.6, label="Simulace (hypotetická historie)")
                
                # 2. Oranžová čára: S&P 500 s poplatky
                if "SPY" in hist_prices_raw.columns:
                    spy_data_to_plot = spy_benchmark_curve[spy_benchmark_curve.index >= first_buy_dt]
                    self.ax1.plot(spy_data_to_plot.index, spy_data_to_plot.values, color='#F57F17', linestyle=':', linewidth=1.5, label="S&P 500 Benchmark (vč. poplatků)")

                # 3. Modrá čára: Skutečný účet
                real_actual_to_plot = real_portfolio_curve_actual[real_portfolio_curve_actual.index >= first_buy_dt]
                self.ax1.plot(real_actual_to_plot.index, real_actual_to_plot.values, color='#0D47A1', linewidth=2, label="Reálné portfolio (skutečná hodnota na účtu)")
                
                self.ax1.axvline(x=first_buy_dt, color='red', linestyle='-', alpha=0.4)
            else:
                self.ax1.plot(sim_curve.index, sim_curve.values, color='grey', linestyle='--', alpha=0.6, label="Simulace")
                
            self.ax1.set_title("Vývoj tržní hodnoty portfolia (zohledněny poplatky, FX kurzy i dividendy)")
            self.ax1.grid(True, linestyle='--', alpha=0.5)
            self.ax1.legend()
            self.ax1.set_ylabel("Hodnota [Kč]")

            def custom_formatter(x, pos):
                if abs(x) >= 1000000: return f'{x*1e-6:.1f} mil.'.replace('.', ',')
                elif abs(x) >= 1000: return f'{x*1e-3:.0f} tis.'.replace('.', ',')
                return f'{x:.0f}'
            self.ax1.yaxis.set_major_formatter(FuncFormatter(custom_formatter))

            # --- GRAF 2: ROČNÍ SLOUPCE ČISTÉHO ZISKU ---
            years = sorted(list(set(hist_prices_raw.index.year)))
            growth_vals, div_vals, totals, colors, labels = [], [], [], [], []
            div_history = {t:[] for t in all_tickers}
            
            real_divs_list = getattr(self, 'real_dividends',[])
            
            for y in years:
                y_start, y_end = f"{y}-01-01", f"{y}-12-31"
                
                sub_sim = sim_curve.loc[y_start:y_end]
                if sub_sim.empty: continue
                sim_v_start, sim_v_end = sub_sim.iloc[0], sub_sim.iloc[-1]
                
                sub_real_actual = real_portfolio_curve_actual.loc[y_start:y_end]
                real_v_start_actual = sub_real_actual.iloc[0] if not sub_real_actual.empty else 0.0
                real_v_end_actual = sub_real_actual.iloc[-1] if not sub_real_actual.empty else 0.0

                # A. Skutečné historické náklady na nákup (Cash Out) vč. Poplatků
                buys_cost_actual = 0.0
                for t, lots in self.ledger.items():
                    curr = self.get_currency_for_ticker(t)
                    for l in lots:
                        if l['date'].startswith(str(y)):
                            cost = float(l['price_at_buy']) * l['qty']
                            fx_rate = l.get('fx_rate') or get_historical_fx(curr, l['date'])
                            buys_cost_actual += (cost + l.get('fee', 0.0)) * fx_rate
                            
                for s in self.sales_history:
                    if s['buy_date'].startswith(str(y)):
                        curr = s.get('currency', 'USD')
                        cost = float(s['buy_price']) * s['qty']
                        fx_rate = s.get('buy_fx') or get_historical_fx(curr, s['buy_date'])
                        buys_cost_actual += (cost + s.get('buy_fee', 0.0)) * fx_rate

                # B. Skutečné historické příjmy z prodeje (Cash In) po odečtení Poplatků
                sales_income_actual = 0.0
                for s in self.sales_history:
                    if s['sell_date'].startswith(str(y)):
                        curr = s.get('currency', 'USD')
                        income = float(s['sell_price']) * s['qty']
                        fx_rate = s.get('sell_fx') or get_historical_fx(curr, s['sell_date'])
                        sales_income_actual += (income - s.get('sell_fee', 0.0)) * fx_rate

                # C. Dividendy ošetřené o srážkovou daň
                year_divs_actual = 0.0
                rd_year = [d for d in real_divs_list if d['date'].startswith(str(y))]
                
                for t in all_tickers:
                    meta = getattr(self, 'stock_db_from_json', DEFAULT_STOCK_DB).get(t, {})
                    if meta.get("sector") == "ETF" and meta.get("etf_type") == "Acc":
                        div_history[t].append(0)
                        continue

                    t_div_actual = 0.0
                    curr = self.get_currency_for_ticker(t)
                    
                    # C1. REÁLNÉ (PŘESNÉ) DIVIDENDY (Když už portfolio žilo)
                    if has_buys and y >= first_buy_year:
                        covered_yahoo_dates = []
                        # 1. Z CSV (Naprosto přesné srážky daně)
                        for rd in rd_year:
                            if rd['ticker'] == t:
                                net_div = rd['gross'] - rd.get('tax', 0.0)
                                fx_r = get_historical_fx(rd.get('currency', 'USD'), rd['date'])
                                t_div_actual += net_div * fx_r
                                covered_yahoo_dates.append(datetime.strptime(rd['date'], "%Y-%m-%d").date())
                                
                        # 2. Inteligentní odhad pro nedávné měsíce bez CSV
                        try:
                            d_data = all_divs[t].loc[y_start:y_end]
                            for d_dt, amt in d_data.items():
                                is_covered = False
                                for rd_date in covered_yahoo_dates:
                                    if 0 <= (rd_date - d_dt.date()).days <= 90:
                                        is_covered = True
                                        break
                                if is_covered: continue
                                
                                d_s = pd.Timestamp(d_dt.date())
                                q = sum(l['qty'] for l in ledger_dt.get(t,[]) if l['date'] < d_s)
                                q += sum(s['qty'] for s in sales_dt if s['ticker'] == t and s['buy_date'] < d_s and s['sell_date'] >= d_s)
                                         
                                p_factor = 100.0 if t.endswith(".L") else 1.0
                                tax_rate = DEFAULT_TAX_RATE if self.get_country_for_ticker(t) == "USA" else 0.0
                                net_amt = (amt / p_factor) * q * (1.0 - tax_rate)
                                
                                t_div_actual += net_amt * get_historical_fx(curr, d_s.strftime('%Y-%m-%d'))
                        except: pass
                    
                    # C2. HYPOTETICKÉ DIVIDENDY (Šedé sloupce v minulosti)
                    else:
                        try:
                            d_data = all_divs[t].loc[y_start:y_end]
                            for d_dt, amt in d_data.items():
                                date_str = d_dt.strftime('%Y-%m-%d')
                                hist_price = hist_prices_raw[t].loc[:date_str]
                                p_val = hist_price.iloc[-1] if not hist_price.empty else hist_prices_raw[t].bfill().iloc[0]
                                
                                if pd.notna(p_val) and p_val > 0:
                                    tax_rate = DEFAULT_TAX_RATE if self.get_country_for_ticker(t) == "USA" else 0.0
                                    div_yield_net = (amt / p_val) * (1.0 - tax_rate)
                                    
                                    try: sim_val = sub_sim.loc[date_str]
                                    except: sim_val = sub_sim.loc[:date_str].iloc[-1] if not sub_sim.loc[:date_str].empty else sub_sim.iloc[0]
                                        
                                    if isinstance(sim_val, pd.Series): sim_val = sim_val.iloc[0]
                                    
                                    sim_allocated_czk = sim_val * actual_weights.get(t, 0.0)
                                    t_div_actual += sim_allocated_czk * div_yield_net
                        except: pass

                    year_divs_actual += t_div_actual
                    div_history[t].append(t_div_actual) 

                # D. Finální PnL
                if not has_buys or y < first_buy_year:
                    total_pnl_actual = sim_v_end - sim_v_start
                    growth_only = total_pnl_actual - year_divs_actual
                    colors.append('grey')
                    base = sim_v_start if sim_v_start > 0 else (sim_v_end / 1.1)
                else:
                    capital_gain_actual = (real_v_end_actual - real_v_start_actual) + sales_income_actual - buys_cost_actual
                    total_pnl_actual = capital_gain_actual + year_divs_actual
                    
                    growth_only = capital_gain_actual
                    colors.append('#4CAF50' if total_pnl_actual >= 0 else '#E53935')
                    
                    base = real_v_start_actual + buys_cost_actual
                    if base == 0: base = 1

                growth_vals.append(growth_only)
                div_vals.append(year_divs_actual)
                totals.append(total_pnl_actual)
                
                pct = (total_pnl_actual / base * 100) if base > 0 else 0
                lbl_text = f"{pct:+.1f}%\n{total_pnl_actual/1000:+.1f}k".replace('.', ',')
                labels.append(lbl_text)

            self.ax2.clear()
            self.ax2.yaxis.set_major_formatter(FuncFormatter(custom_formatter))
            
            x = np.arange(len(growth_vals))
            for i in range(len(x)):
                g = growth_vals[i]; d = div_vals[i]; t = totals[i]; c_base = colors[i]  
                
                if g >= 0:
                    self.ax2.bar(x[i], g, color=c_base, label='Čistý kapitálový růst' if i==x[-1] else "")
                    if d > 0: self.ax2.bar(x[i], d, bottom=g, color='#FFC107', label='Čisté přijaté dividendy' if i==x[-1] else "")
                else:
                    if t < 0:
                        # Ztráta pokrývá všechno
                        if c_base == '#E53935': light_c, dark_c = '#EF9A9A', '#C62828'
                        else: light_c, dark_c = 'lightgrey', 'grey'
                            
                        self.ax2.bar(x[i], t, color=light_c, label='Výsledná ztráta' if i==x[-1] else "")
                        if d > 0: self.ax2.bar(x[i], -d, bottom=t, color=dark_c, label='Ztráta pokrytá div.' if i==x[-1] else "")
                    else:
                        self.ax2.bar(x[i], g, color=c_base, label='Pokles ceny akcií' if i==x[-1] else "")
                        if d > 0:
                            self.ax2.bar(x[i], t, color='#FFA000', label='Čistý zisk z div.' if i==x[-1] else "")
                            self.ax2.bar(x[i], abs(g), bottom=t, color='#FFD54F', label='Div. kryjící ztrátu' if i==x[-1] else "")

            self.ax2.grid(True, linestyle='--', alpha=0.5)
            self.ax2.set_ylabel("Zisk [Kč]")
            
            legend_elements =[
                Patch(facecolor='grey', label='Simulace (růst/ztráta)'), 
                Patch(facecolor='#4CAF50', label='Reálný zisk akcií'),
                Patch(facecolor='#E53935', label='Reálná ztráta akcií'),
                Patch(facecolor='#FFC107', label='Čisté dividendy')
            ]
            self.ax2.legend(handles=legend_elements, loc="lower left", fontsize=9)
            
            v_min, v_max = min(min(growth_vals), min(totals), 0), max(max(totals), max(growth_vals), 0)
            y_range = max(v_max - v_min, 2000)
            self.ax2.set_ylim(v_min - (y_range * 0.4), v_max + (y_range * 0.4))
            self.ax2.set_xticks(x); self.ax2.set_xticklabels([str(y) for y in years])
            
            for i in x:
                if labels[i]:
                    va = 'bottom' if totals[i] >= 0 else 'top'
                    offset = (y_range * 0.05) if totals[i] >= 0 else -(y_range * 0.05)
                    self.ax2.text(i, totals[i] + offset, labels[i], ha='center', va=va, fontsize=9, fontweight='bold')

            # --- GRAF 3: DIVIDENDY ---
            self.ax3.clear()
            self.ax3.yaxis.set_major_formatter(FuncFormatter(custom_formatter))
            
            div_sums_for_sorting = {}
            for ticker_name in all_tickers:
                div_sums_for_sorting[ticker_name] = sum(div_history[ticker_name])
                    
            sorted_tickers = sorted(all_tickers, key=lambda x: div_sums_for_sorting.get(x, 0.0), reverse=True)
            active_tickers = [t for t in sorted_tickers if div_sums_for_sorting[t] > 0]
            
            if active_tickers:
                plot_tickers = active_tickers[::-1]
                stack_data = [div_history[t] for t in plot_tickers]
                
                c_map = plt.cm.tab20.colors
                plot_colors = [c_map[i % len(c_map)] for i in range(len(active_tickers))]
                
                self.ax3.stackplot(years, stack_data, labels=plot_tickers, colors=plot_colors, alpha=0.85)
                self.ax3.set_title("Zdroje čistých dividend v čase")
                self.ax3.set_ylabel("Dividendy (Net) [Kč]")
                self.ax3.set_xticks(years)
                self.ax3.set_xticklabels([str(y) for y in years])
                self.ax3.grid(True, linestyle='--', alpha=0.5)
                
                handles, labels_ax3 = self.ax3.get_legend_handles_labels()
                self.ax3.legend(handles[::-1], labels_ax3[::-1], loc='upper left', ncol=math.ceil(len(active_tickers)/4), fontsize=8)

            self.canvas.draw()
            
            if is_final: self.status_lbl.config(text=f"Aktualizováno: {datetime.now().strftime('%H:%M:%S')}", fg="green")
            est = self.calculate_tax_estimate()
            self.root.after(0, lambda: self.tax_estimate_lbl.config(text=f"Odhad daně za rok {datetime.now().year}: {est:,.0f} Kč".replace(',', ' ')))
            
            # --- TICHÝ PŘEPOČET DAT PRO DYNAMICKÝ TOOLTIP (textbox cílová hodnota pasivního příjmu) ---
            self.last_portfolio_value_czk = total_portfolio_now
            
            temp_yield_sum = 0.0
            db_temp = getattr(self, 'stock_db_from_json', DEFAULT_STOCK_DB)
            for t in TARGETS.keys():
                w = TARGETS.get(t, 0.0)
                # Výchozí hodnota je statická z DB
                dy = db_temp.get(t, {}).get('yield', 0.0) / 100.0
                
                # Zkusíme zpřesnit podle stažených dat (all_divs) a posledních cen
                try:
                    if t in hist_prices_raw.columns:
                        price = float(hist_prices_raw[t].iloc[-1])
                        if t.endswith(".L"): 
                            price /= 100.0
                        
                        if price > 0 and t in all_divs:
                            h_divs = all_divs[t]
                            if not h_divs.empty:
                                current_year = datetime.now().year
                                divs_curr = h_divs[h_divs.index.year == current_year]
                                divs_last = h_divs[h_divs.index.year == current_year - 1]
                                
                                total_div = sum(divs_curr)
                                conf_months = [d.month for d in divs_curr.index]
                                for d_date, amt in divs_last.items():
                                    if d_date.month not in conf_months:
                                        total_div += amt
                                        
                                if total_div > 0:
                                    # U britských akcií musíme i dividendu převést z pencí na libry
                                    if t.endswith(".L"):
                                        total_div /= 100.0
                                    calc_dy = total_div / price
                                    if 0 < calc_dy <= 0.25:
                                        dy = calc_dy
                except:
                    pass
                temp_yield_sum += w * dy
                
            self.last_nominal_yield = temp_yield_sum if temp_yield_sum > 0 else 0.04            

            # --- DYNAMICKÁ AKTUALIZACE SLIDERU NA ZÁLOŽCE NÁKUP ---
            if hasattr(self, 'dyn_floor_slider'):
                max_slider_val = round(self.last_nominal_yield * 100, 2)
                if max_slider_val < 0.5: max_slider_val = 5.0
                
                # Zjištění, zda nové reálné maximum nekleslo pod hodnotu, kterou má uživatel zrovna nastavenou
                current_slider_val = float(self.dyn_floor_slider.get())
                if current_slider_val > max_slider_val:
                    # Pokud ano, snížíme hodnotu slideru a uložíme novou konfiguraci
                    self.root.after(0, lambda v=max_slider_val: [self.dyn_floor_slider.config(to=v), self.dyn_floor_slider.set(v)])
                    self.dyn_yield_cap = max_slider_val
                else:
                    self.root.after(0, lambda v=max_slider_val: self.dyn_floor_slider.config(to=v))

            # Zapíšeme přepočtené přesné tržní hodnoty na disk pro příští okamžitý start (použito v tooltipu)
            self.save_data()
            
        except Exception as e:
            if current_version is not None and getattr(self, 'dash_fetch_version', 0) == current_version:
                print(f"Error rendering graphs: {e}")
                self.status_lbl.config(text="Chyba výpočtu grafu", fg="red")

    # --------------------------------------------------------------------------
    # DAŇOVÝ MOTOR (ONE-CLICK EXPORT A PDF)
    # --------------------------------------------------------------------------

    def calculate_tax_estimate(self):
        """Vypočítá informativní odhad daně za aktuální rok."""
        current_year = datetime.now().year
        fx = self.get_fx_rates()
        
        # 1. Prodeje (§10)
        taxable_profit = 0.0
        for sale in self.sales_history:
            if sale['sell_date'].startswith(str(current_year)):
                fx_rate = fx.get(sale['currency'], 23.0)
                profit = (sale['sell_price'] - sale['buy_price']) * sale['qty'] * fx_rate
                if profit > 0: taxable_profit += profit
                
        # 2. Dividendy (§8) - pouze reálné, nikoliv projekce!
        total_div_gross = 0.0
        for rd in getattr(self, 'real_dividends', []):
            if rd['date'].startswith(str(current_year)):
                total_div_gross += rd['gross'] * fx.get(rd.get('currency', 'USD'), 23.0)
        
        # Daňový odhad 
        # Pozn: Pro zjednodušení počítáme daň ze zisku, neřešíme osvobození 100k limitu 
        # (je to jen informativní odhad, aby si investor nechal peníze stranou)
        tax_est = (taxable_profit * DEFAULT_TAX_RATE) + (total_div_gross * DEFAULT_TAX_RATE)
        
        return int(tax_est)

    def generate_tax_report(self):
        if getattr(self, 'dash_loading_state', {}).get("is_loading"): return
        
        year_to_report = datetime.now().year - 1
        self.status_lbl.config(text=f"Generuji PDF a XML {year_to_report}...", fg="blue")
        self.root.update_idletasks()
        
        rates = self.uniform_rates.get(str(year_to_report), {"USD": 23.0, "GBP": 29.0})
        
        # Sekce Prodejů (§10)
        sales_rows =[]
        total_taxable_income = 0.0
        total_taxable_expense = 0.0
        exempt_count = 0
        
        for sale in self.sales_history:
            try:
                s_date = datetime.strptime(sale['sell_date'], "%Y-%m-%d")
                if s_date.year != year_to_report: continue
                
                b_date = datetime.strptime(sale['buy_date'], "%Y-%m-%d")
                
                # --- Přesný výpočet 3letého časového testu (ošetření přestupných let) ---
                try:
                    # Standardní posun přesně o 3 roky dopředu
                    target_date = b_date.replace(year=b_date.year + 3)
                except ValueError:
                    # Fallback pro situaci, kdy nákup proběhl 29. února 
                    # a rok o 3 roky později není přestupný.
                    target_date = b_date.replace(year=b_date.year + 3, day=28)
                
                # Prodej je osvobozen, pokud proběhl striktně PO uplynutí 3 let (tedy nejdříve den poté)
                exempt_by_time = s_date > target_date
                
                if exempt_by_time:
                    exempt_count += 1
                    continue
                
                fx = rates.get(sale['currency'], 1.0)
                income = sale['qty'] * sale['sell_price'] * fx
                cost = sale['qty'] * sale['buy_price'] * fx
                
                total_taxable_income += income
                total_taxable_expense += cost
                profit = income - cost
                
                sales_rows.append({
                    "Datum": sale['sell_date'], "Ticker": sale['ticker'], 
                    "Množství": f"{sale['qty']:.3f}".replace('.', ','),
                    "Příjem": f"{income:,.0f}".replace(",", " "),
                    "Výdaj": f"{cost:,.0f}".replace(",", " "),
                    "Zisk": f"{profit:,.0f}".replace(",", " ")
                })
            except: pass

        # Sekce Dividend (§8)
        div_data = {"USA": [], "UK":[]}
        total_div_usa_gross = 0.0
        total_usa_tax_czk = 0.0 # Měníme odhadovaných 15 % na exaktně vypočítanou daň
        total_div_uk_gross = 0.0
        
        all_tickers = set(list(self.ledger.keys()) + [s['ticker'] for s in self.sales_history])
        
        # --- 1. ZPRACOVÁNÍ SKUTEČNÝCH DIVIDEND (Z IBKR CSV) ---
        # Filtrujeme jen dividendy z daného roku
        real_divs_year =[d for d in getattr(self, 'real_dividends', []) if d['date'].startswith(str(year_to_report))]
        
        for rd in real_divs_year:
            t = rd['ticker']
            gross_czk = rd['gross'] * rates.get(rd.get('currency', 'USD'), 1.0)
            tax_czk = rd['tax'] * rates.get(rd.get('currency', 'USD'), 1.0)
            
            country = self.get_country_for_ticker(t)
            if country == "USA": 
                total_div_usa_gross += gross_czk
                total_usa_tax_czk += tax_czk
                div_data["USA"].append({
                    "Datum": rd['date'], "Ticker": f"{t} (Přesně z CSV)",
                    "Hrubá": f"{gross_czk:,.0f}".replace(",", " "),
                    "Sražená": f"{tax_czk:,.0f}".replace(",", " ")
                })
            else: 
                total_div_uk_gross += gross_czk
                div_data["UK"].append({
                    "Datum": rd['date'], "Ticker": f"{t} (Přesně z CSV)",
                    "Hrubá": f"{gross_czk:,.0f}".replace(",", " "),
                    "Sražená": f"{tax_czk:,.0f}".replace(",", " ")
                })

        # --- 2. ZPRACOVÁNÍ YF DIVIDEND (FALLBACK PRO CHYBĚJÍCÍ OBDOBÍ) ---
        for t in all_tickers:
            meta = getattr(self, 'stock_db_from_json', DEFAULT_STOCK_DB).get(t, {})
            if meta.get("sector") == "ETF" and meta.get("etf_type") == "Acc":
                continue

            try:
                # načtení dat z mezipaměti
                divs = self._safe_get_dividends(t)
                year_divs = divs[divs.index.year == year_to_report]
                if year_divs.empty: continue
                
                for d_date, amount in year_divs.items():
                    div_date_str = d_date.strftime("%Y-%m-%d")
                    
                    # KONTROLA PŘEKRYVU: Yahoo vrací 'Ex-Date', CSV vrací 'Pay-Date'.
                    # Pokud CSV obsahuje k danému tickeru výplatu v rozmezí 0 až 90 dní 
                    # po Ex-Date z Yahoo, znamená to, že data pro tuto dividendu už máme.
                    is_covered = False
                    for rd in real_divs_year:
                        if rd['ticker'] == t:
                            rd_date = datetime.strptime(rd['date'], "%Y-%m-%d")
                            delta_days = (rd_date.date() - d_date.date()).days
                            if 0 <= delta_days <= 90:
                                is_covered = True
                                break
                                
                    if is_covered:
                        continue # Přeskakujeme, máme přesná data z CSV
                    
                    # Jinak počítáme odhad z Yahoo (pokud chybí import za určité měsíce)
                    qty_held = sum(l['qty'] for l in self.ledger.get(t,[]) if l['date'] < div_date_str)
                    qty_sold_later = sum(s['qty'] for s in self.sales_history if s['ticker'] == t 
                                         and s['buy_date'] < div_date_str and s['sell_date'] >= div_date_str)
                    
                    total_qty = qty_held + qty_sold_later
                    
                    if total_qty > 0.001:
                        if t.endswith(".L"): amount /= 100.0
                        fx = rates.get(self.get_currency_for_ticker(t), 1.0)
                        gross_div_czk = total_qty * amount * fx
                        
                        country = self.get_country_for_ticker(t)
                        
                        if country == "USA": 
                            total_div_usa_gross += gross_div_czk
                            withheld = gross_div_czk * DEFAULT_TAX_RATE 
                            total_usa_tax_czk += withheld
                        else: 
                            total_div_uk_gross += gross_div_czk
                            withheld = 0.0 
                            
                        div_data[country].append({
                            "Datum": div_date_str, "Ticker": f"{t} (Odhadováno)",
                            "Hrubá": f"{gross_div_czk:,.0f}".replace(",", " "),
                            "Sražená": f"{withheld:,.0f}".replace(",", " ")
                        })
            except: pass

        totals = {
            "p10_income": total_taxable_income,
            "p10_expense": total_taxable_expense,
            "p10_profit": max(0, total_taxable_income - total_taxable_expense),
            "exempt_count": exempt_count,
            "div_usa_gross": total_div_usa_gross,
            "div_usa_withheld": total_usa_tax_czk, # Nově používáme přesnou zaplacenou daň
            "div_uk_gross": total_div_uk_gross,
            "div_uk_owed": total_div_uk_gross * 0.15 
        }
        
        if totals['p10_income'] <= 100000 and totals['div_usa_gross'] == 0 and totals['div_uk_gross'] == 0:
            messagebox.showinfo(
                "Žádná daňová povinnost", 
                f"Pro rok {year_to_report} nemusíte z tohoto portfolia podávat daňové přiznání!\n\n"
                "• Hrubé zdanitelné příjmy z prodejů nepřesáhly limit 100 000 Kč (dle § 4 odst. 1 písm. t zákona o daních z příjmů).\n"
                "• Ostatní prodeje případně splnily 3letý časový test (dle § 4 odst. 1 písm. u téhož zákona).\n"
                "• Nebyly přijaty žádné dividendy od zahraničních firem.\n\n"
                "Daňový report nebyl vygenerován, protože v něm není co vykazovat."
            )
            self.status_lbl.config(text="Hotovo (Bez daně)", fg="green")
            return
            
        base_filename = f"Danovy_Report_{year_to_report}"
        pdf_filename = f"{base_filename}.pdf"
        xml_filename = f"{base_filename}.xml"
        
        try:
            self.create_pdf(pdf_filename, year_to_report, sales_rows, div_data, totals)
            self.create_xml(xml_filename, totals, year_to_report)
            messagebox.showinfo("Úspěch", f"Reporty za rok {year_to_report} byly vytvořeny v této složce:\n\n1) {pdf_filename} (Návod a přehled)\n2) {xml_filename} (Soubor pro portál MOJE daně)")
        except Exception as e:
            messagebox.showerror("Chyba PDF/XML", str(e))
        finally:
            self.status_lbl.config(text="Hotovo", fg="green")

    def create_xml(self, filename, totals, year):
        """Vygeneruje strojově čitelný .xml soubor pro rychlý import do portálu MojeDaně (formát DPFDP7)."""
        current_year = datetime.now().year
        
        # Od roku 2024 používá finanční správa formát DPFDP7
        root_tag = "DPFDP7" if year >= 2024 else "DPFDP6"
        
        xml =[
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<Pisemnost nazevSW="Czech Investor App" verzeSW="{current_year}">',
            f'  <{root_tag}>'
        ]

        # ---------------------------------------------------------------------
        # 1. VÝPOČET PRO PŘÍLOHU 4: DIVIDENDY (§ 16a - Samostatný základ daně)
        # ---------------------------------------------------------------------
        # Zrušeno nebezpečné zaokrouhlování nahoru/dolů, hodnoty musí být běžná celá čísla
        div_gross = round(totals.get('div_usa_gross', 0) + totals.get('div_uk_gross', 0))
        da_samzakl = 0
        veta_z_xml = ""
        
        if div_gross > 0:
            div_tax_cz = round(div_gross * DEFAULT_TAX_RATE)
            # Zahraniční daň (zde jen z USA, protože UK má daň z dividend 0 %)
            div_foreign = round(totals.get('div_usa_withheld', 0))
            
            # Uznaná daň metodou prostého zápočtu nesmí přesáhnout teoretickou českou daň
            div_recognized = min(div_foreign, div_tax_cz)
            
            # Finální částka k doplacení českému finančnímu úřadu
            tax_to_pay = max(0, div_tax_cz - div_recognized)
            da_samzakl = tax_to_pay
            
            # VetaZ přesně mapuje řádky 401a až 414 v Příloze 4
            veta_z_xml = (
                f'    <VetaZ kc_prij48="{div_gross}" kc_zd48="{div_gross}" '
                f'kc_uhrndzd="{div_gross}" kc_dan415="{div_tax_cz}" '
                f'kc_uh415="{div_gross}" kc_zahr415="{div_foreign}" '
                f'kc_uznzap415="{div_recognized}" da_samzakl4="{tax_to_pay}"/>'
            )

        # ---------------------------------------------------------------------
        # 2. HLAVIČKA PŘIZNÁNÍ (Věta D) a POPLATNÍK (Věta P)
        # ---------------------------------------------------------------------
        # XML XSD striktně vyžaduje určité atributy, jinak XML rovnou odmítne.
        # c_ufo_cil="453" je zástupný kód (FÚ pro hl. m. Prahu), uživatel si ho na portálu snadno změní
        veta_d_attr = f'rok="{year}" dap_typ="B" k_uladis="DPF" dokument="DP7" pln_moc="N" audit="N" c_ufo_cil="453"'
        
        if da_samzakl > 0:
            veta_d_attr += f' da_samzakl="{da_samzakl}"'
            
        xml.append(f'    <VetaD {veta_d_attr}/>')
        xml.append('    <VetaP jmeno="" prijmeni=""/>')

        # ---------------------------------------------------------------------
        # 3. PŘÍPRAVA DAT PRO PRODEJ AKCIÍ (§ 10 - Příloha č. 2)
        # ---------------------------------------------------------------------
        p10_inc = round(totals.get('p10_income', 0))
        p10_exp = round(totals.get('p10_expense', 0))
        
        if p10_inc > 100000:
            p10_prof = max(0, p10_inc - p10_exp)
            
            # VetaO propojujeme Přílohu 2 s hlavním formulářem (řádek 40 = kc_zd10)
            xml.append(f'    <VetaO kc_zd10="{p10_prof}"/>')
            
            # VetaV je sumář Přílohy 2 (řádky 207, 208, 209)
            xml.append(f'    <VetaV kc_prij10="{p10_inc}" kc_vyd10="{p10_exp}" kc_zd10p="{p10_prof}"/>')
            
            # VetaJ je konkrétní detailní řádek v tabulce Přílohy 2 (Kód D = prodej cenných papírů)
            xml.append(f'    <VetaJ druh_prij10="Prodej cenných papírů" kod_dr_prij10="D" prijmy10="{p10_inc}" vydaje10="{p10_exp}" rozdil10="{p10_prof}"/>')

        # Připojení dat o dividendách (Příloha 4), pokud existují
        if veta_z_xml:
            xml.append(veta_z_xml)

        # Uzavření XML
        xml.append(f'  </{root_tag}>')
        xml.append('</Pisemnost>')

        with open(filename, 'w', encoding='utf-8') as f:
            f.write("\n".join(xml))

    def create_pdf(self, filename, year, sales_data, div_data, totals):
        doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elements =[]
        
        try:
            pdfmetrics.registerFont(TTFont('Arial', 'arial.ttf'))
            font_name = 'Arial'
        except: font_name = 'Helvetica'

        styles = getSampleStyleSheet()
        style_h1 = ParagraphStyle('Header1', parent=styles['Heading1'], fontName=font_name, fontSize=18, leading=22, spaceAfter=12)
        style_h2 = ParagraphStyle('Header2', parent=styles['Heading2'], fontName=font_name, fontSize=16, leading=20, spaceBefore=15, spaceAfter=8, textColor=colors.HexColor("#1565C0"))
        style_norm = ParagraphStyle('Normal', parent=styles['Normal'], fontName=font_name, fontSize=12, leading=16, spaceAfter=6)
        style_bold = ParagraphStyle('Bold', parent=styles['Normal'], fontName=font_name, fontSize=12, leading=16, textColor=colors.black, spaceAfter=6)
        style_info = ParagraphStyle('Info', parent=styles['Normal'], fontName=font_name, fontSize=11, leading=14, textColor=colors.black, leftIndent=10, rightIndent=10)

        link_100k = "<a href='https://www.zakonyprolidi.cz/cs/1992-586#p4' color='blue'><u>§ 4 odst. 1 písm. t) zákona o daních z příjmů</u></a>"
        link_3y = "<a href='https://www.zakonyprolidi.cz/cs/1992-586#p4' color='blue'><u>§ 4 odst. 1 písm. u) zákona o daních z příjmů</u></a>"
        
        def draw_info_box(text, bg_color, border_color):
            t = Table([[Paragraph(text, style_info)]], colWidths=[18*cm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), bg_color),
                ('BOX', (0,0), (-1,-1), 1, border_color),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 0.5*cm))

        elements.append(Paragraph(f"INTERNÍ DAŇOVÝ REPORT ({year})", style_h1))
        elements.append(Paragraph("<b>UPOZORNĚNÍ: Tento dokument slouží výhradně jako vaše osobní kalkulačka. NEPŘIKLÁDEJTE JEJ K DAŇOVÉMU PŘIZNÁNÍ. Finanční úřad tyto rozpisy plošně nevyžaduje (pokud si je výslovně nevyžádá při kontrole).</b>", ParagraphStyle('Warning', parent=style_norm, textColor=colors.red)))
        elements.append(Spacer(1, 0.5*cm))

        intro_text = """<b>JAK PŘENÉST DATA DO PŘIZNÁNÍ</b><br/><br/>
        <b>MOŽNOST 1: Automatické nahrání (Doporučeno - Ušetří čas)</b><br/>
        Spolu s tímto PDF byl vygenerován i soubor s koncovkou <b>.xml</b>. Přejděte na státní portál <i>MOJE daně (mojedane.cz)</i> -> Elektronická podání -> Načíst soubor a vyberte tento XML soubor. Systém automaticky předvyplní příslušné tabulky pro akcie a dividendy. Vy pouze doplníte své osobní údaje a ostatní příjmy.<br/><br/>
        <b>MOŽNOST 2: Ruční vyplnění (Papírové formuláře)</b><br/>
        Pokud nevyužijete XML soubor, postupujte přesně podle modrých a červených rámečků uvedených níže v tomto dokumentu. Jsou v nich přesné pokyny pro ruční propsání částek."""
        draw_info_box(intro_text, colors.HexColor("#F5F5F5"), colors.black)

        elements.append(Paragraph("1. Prodej cenných papírů (§10 Ostatní příjmy)", style_h2))
        
        if totals['p10_income'] <= 100000:
            msg = f"<b>ZÁKONNÝ LIMIT NEPŘEKROČEN:</b> Váš celkový hrubý příjem z prodeje v tomto roce činil <b>{totals['p10_income']:,.0f} Kč</b>. Protože nepřesáhl limit 100 000 Kč, jsou tyto prodeje (dle {link_100k}) <b>ZCELA OSVOBOZENY OD DANĚ</b> a do daňového přiznání se <b>VŮBEC NEZAPISUJÍ</b>."
            draw_info_box(msg.replace(",", " "), colors.HexColor("#E8F5E9"), colors.HexColor("#2E7D32"))
        else:
            msg = f"<b>ZÁKONNÝ LIMIT PŘEKROČEN:</b> Váš celkový hrubý příjem z prodeje činil <b>{totals['p10_income']:,.0f} Kč</b>. Protože přesáhl limit 100 000 Kč (dle {link_100k}), <b>MUSÍTE</b> tyto transakce uvést v daňovém přiznání."
            draw_info_box(msg.replace(",", " "), colors.HexColor("#FFF3E0"), colors.HexColor("#E65100"))
            
            if sales_data:
                table_data = [["Datum", "Ticker", "Ks", "Příjem (CZK)", "Výdaj (CZK)", "Zisk (CZK)"]]
                for r in sales_data:
                    table_data.append([r['Datum'], r['Ticker'], r['Množství'], r['Příjem'], r['Výdaj'], r['Zisk']])
                
                t = Table(table_data, colWidths=[3.2*cm, 2.5*cm, 2*cm, 3.5*cm, 3.5*cm, 3.5*cm])
                t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.lightgrey), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('FONTNAME', (0,0), (-1,-1), font_name), ('FONTSIZE', (0,0), (-1,-1), 11), ('GRID', (0,0), (-1,-1), 0.5, colors.grey)]))
                elements.append(t)
                elements.append(Spacer(1, 0.3*cm))
                
                is_loss = totals['p10_expense'] > totals['p10_income']
                vydaje_txt = f"{totals['p10_expense']:,.0f}"
                zaklad_txt = f"{(totals['p10_income'] - totals['p10_expense']):,.0f}" if not is_loss else "0"
                
                loss_warning = ""
                if is_loss:
                    loss_warning = "<br/><i>Poznámka: Dosáhl jste celkové ztráty. V přiznání se příjmy a výdaje vyrovnají - daňový základ bude 0 Kč. Ztrátu z akcií nelze odečíst od jiných typů příjmů (např. ze zaměstnání).</i>"

                instrukce = f"""<b>NÁVOD PRO RUČNÍ VYPLNĚNÍ (§10):</b><br/>
                V přiznání přejděte na <b>Přílohu č. 2</b>. V tabulce č. 2 zvolte Druh příjmu <b>"D - Prodej cenných papírů"</b>.<br/>
                • Do sloupce Příjmy zadejte: <b>{totals['p10_income']:,.0f} Kč</b><br/>
                • Do sloupce Výdaje zadejte: <b>{vydaje_txt} Kč</b><br/>
                • Daňový základ (Zisk) bude: <b>{zaklad_txt} Kč</b>{loss_warning}"""
                
                draw_info_box(instrukce.replace(",", " "), colors.HexColor("#E3F2FD"), colors.HexColor("#1565C0"))

        if totals['exempt_count'] > 0:
            elements.append(Paragraph(f"<i>Poznámka: Aplikace z reportu automaticky skryla {totals['exempt_count']} prodejů, které splnily 3letý časový test a jsou tak dle {link_3y} vždy osvobozeny od daně.</i>", ParagraphStyle('Small', parent=style_norm, fontSize=10, textColor=colors.dimgrey)))
        
        elements.append(Spacer(1, 1*cm))

        elements.append(Paragraph("2. Dividendy ze zahraničí (§16a Samostatný základ daně)", style_h2))
        elements.append(Paragraph("Dividendy ze zahraničí se daní v Příloze č. 4 (Samostatný základ daně). Na rozdíl od starších pravidel se zde nevyplňují samostatné listy pro každý stát, ale zahraniční dividendy a zápočty se sčítají do jedné celkové tabulky.", style_norm))
        elements.append(Spacer(1, 0.5*cm))

        # Ponecháme rozpis pro vizuální kontrolu investora
        if div_data.get("USA"):
            elements.append(Paragraph(f"<b>A) Dividendy ze Spojených států (USA)</b>", style_bold))
            table_data = [["Datum", "Ticker", "Hrubá Div (CZK)", "Zahraniční daň (15%)"]]
            for r in div_data["USA"]: table_data.append([r['Datum'], r['Ticker'], r['Hrubá'], r['Sražená']])
            
            t = Table(table_data, colWidths=[3.5*cm, 3*cm, 4.5*cm, 4.5*cm])
            t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.lightgrey), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('FONTNAME', (0,0), (-1,-1), font_name), ('FONTSIZE', (0,0), (-1,-1), 11), ('GRID', (0,0), (-1,-1), 0.5, colors.grey)]))
            elements.append(t)
            elements.append(Spacer(1, 0.3*cm))
        
        if div_data.get("UK"):
            elements.append(Paragraph(f"<b>B) Dividendy z Velké Británie (UK)</b>", style_bold))
            table_data = [["Datum", "Ticker", "Hrubá Div (CZK)", "Zahraniční daň (0%)"]]
            for r in div_data["UK"]: table_data.append([r['Datum'], r['Ticker'], r['Hrubá'], "0"])
            
            t = Table(table_data, colWidths=[3.5*cm, 3*cm, 4.5*cm, 4.5*cm])
            t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.lightgrey), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('FONTNAME', (0,0), (-1,-1), font_name), ('FONTSIZE', (0,0), (-1,-1), 11), ('GRID', (0,0), (-1,-1), 0.5, colors.grey)]))
            elements.append(t)
            elements.append(Spacer(1, 0.3*cm))

        if not div_data.get("USA") and not div_data.get("UK"):
            elements.append(Paragraph("V tomto roce nebyly přijaty žádné dividendy.", style_norm))
        else:
            # Výpočet celkových částek pro jedinou tabulku Přílohy 4
            total_div = totals['div_usa_gross'] + totals['div_uk_gross']
            total_foreign_tax = totals['div_usa_withheld']  # UK daň je 0
            
            # Daň uznaná k zápočtu (nemůže přesáhnout teoretickou českou daň)
            total_recognized = min(total_foreign_tax, total_div * DEFAULT_TAX_RATE)
            
            # Výsledná daň k zaplacení v ČR
            tax_to_pay = max(0, (total_div * DEFAULT_TAX_RATE) - total_recognized)

            instrukce_p4 = f"""<b>NÁVOD PRO RUČNÍ VYPLNĚNÍ (Příloha č. 4):</b><br/>
            V papírovém formuláři (Příloha č. 4) nehledejte kolonky pro kódy států. Všechny dividendy se sečtou a zapíší jako jeden celek.<br/><br/>
            • Řádek 401a (Příjmy podle § 8 ze zahraničí): <b>{total_div:,.0f} Kč</b><br/>
            • Řádek 406 a 409 (Součty základů daně): <b>{total_div:,.0f} Kč</b><br/>
            • Řádek 410 (Teoretická daň): <b>{total_div * DEFAULT_TAX_RATE:,.0f} Kč</b><br/>
            • Řádek 411 (Příjmy, u nichž se uplatní zápočet): <b>{total_div:,.0f} Kč</b><br/>
            • Řádek 412 (Daň zaplacená v zahraničí): <b>{total_foreign_tax:,.0f} Kč</b><br/>
            • Řádek 413 (Daň uznaná k zápočtu): <b>{total_recognized:,.0f} Kč</b><br/>
            • Řádek 414 (Daň ze samostatného základu): <b>{tax_to_pay:,.0f} Kč</b><br/><br/>
            <i>Hodnota z řádku 414 se následně přenese do Hlavního daňového přiznání na řádek 74a (ve 3. oddílu).</i>"""
            
            draw_info_box(instrukce_p4.replace(",", " "), colors.HexColor("#E3F2FD"), colors.HexColor("#1565C0"))

        if not div_data.get("USA") and not div_data.get("UK"):
            elements.append(Paragraph("V tomto roce nebyly přijaty žádné dividendy.", style_norm))
            
        doc.build(elements)


    # --------------------------------------------------------------------------
    # EDITOR VÝBĚRU AKCIÍ (STOCK UNIVERSE WIZARD)
    # --------------------------------------------------------------------------

    def open_portfolio_editor(self):
        """Spustí modální okno umožňující změnit skladbu portfolia s duálními scrollbary."""
        if self.editor_window is not None and self.editor_window.winfo_exists():
            self.editor_window.lift() 
            self.editor_window.focus_force()
            return
            
        # Validace a uložení ručně zadaných limitů vah ještě před otevřením editoru,
        # aby se po zavření editoru a překreslení UI neztratily.
        if hasattr(self, '_validate_and_get_limits'):
            self._validate_and_get_limits()
            
        source_db = self.stock_db_from_json if hasattr(self, 'stock_db_from_json') else DEFAULT_STOCK_DB
        self.stock_db = json.loads(json.dumps(source_db))
        self.temp_targets = TARGETS.copy()
        
        self.editor_window = tk.Toplevel(self.root)
        editor = self.editor_window
        editor.title("Editor Výběru Akcií")
        
        # Velikost okna 1350px zajišťuje pohodlné zobrazení dlouhých názvů ETF
        editor.geometry("1350x750") 
        editor.grab_set() 
        
        main_container = tk.Frame(editor, padx=10, pady=10)
        main_container.pack(fill=tk.BOTH, expand=True)

        # --- 1. LEVÝ PANEL (Universe) ---
        left_frame = tk.LabelFrame(main_container, text="Tržní nabídka (Universe)", padx=10, pady=10, font=("Arial", 12, "bold"))
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        filter_vars = {}
        for k in TAGS:
            val = self.ethical_filters.get(k, True)
            filter_vars[k] = tk.BooleanVar(value=val)
        
        filter_frame = tk.Frame(left_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(filter_frame, text="Zobrazit sektory:", font=("Arial", 12, "bold")).pack(anchor="w")
        
        f_grid = tk.Frame(filter_frame)
        f_grid.pack(anchor="w")
        idx = 0
        for k, label in TAGS.items():
            cb = tk.Checkbutton(f_grid, text=label, variable=filter_vars[k], font=("Arial", 12),
                                command=lambda: self._refresh_lists(list_available, list_current, filter_vars))
            cb.grid(row=idx//2, column=idx%2, sticky="w", padx=10)
            idx += 1
            
        # Inicializace proměnné pro režim řazení z načtených dat
        self.sort_mode_var = tk.StringVar(value=getattr(self, 'editor_sort_mode', 'metrics'))

        # Rámeček pro výběr řazení
        sort_frame = tk.Frame(left_frame)
        sort_frame.pack(fill=tk.X, pady=(5, 10))
        tk.Label(sort_frame, text="Řazení seznamů:", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        
        rb_metrics = tk.Radiobutton(sort_frame, text="Podle výkonu", variable=self.sort_mode_var, value="metrics", font=("Arial", 11),
                                    command=lambda: self._on_editor_sort_change(list_available, list_current, filter_vars))
        rb_metrics.pack(side=tk.LEFT, padx=5)
        
        rb_alpha = tk.Radiobutton(sort_frame, text="Abecedně", variable=self.sort_mode_var, value="alpha", font=("Arial", 11),
                                  command=lambda: self._on_editor_sort_change(list_available, list_current, filter_vars))
        rb_alpha.pack(side=tk.LEFT, padx=5)            
            
        avail_container = tk.Frame(left_frame)
        avail_container.pack(fill=tk.BOTH, expand=True, pady=5)
        
        vsb_avail = tk.Scrollbar(avail_container, orient="vertical")
        hsb_avail = tk.Scrollbar(avail_container, orient="horizontal")
        
        list_available = tk.Listbox(avail_container, selectmode=tk.SINGLE, font=("Consolas", 12), activestyle='none',
                                    yscrollcommand=vsb_avail.set, xscrollcommand=hsb_avail.set)
        
        list_available.grid(row=0, column=0, sticky="nsew")
        vsb_avail.grid(row=0, column=1, sticky="ns")
        hsb_avail.grid(row=1, column=0, sticky="ew")
        
        avail_container.grid_rowconfigure(0, weight=1)
        avail_container.grid_columnconfigure(0, weight=1)
        
        vsb_avail.config(command=list_available.yview)
        hsb_avail.config(command=list_available.xview)
        
        tk.Label(left_frame, text="Legenda: [ZTRÁTA 2Y % | RŮST 2Y %]  [DIVIDENDA %]", font=("Arial", 11), fg="grey").pack(anchor="w")
        
        search_frame = tk.Frame(left_frame)
        search_frame.pack(fill=tk.X, pady=10)
        self.search_entry = tk.Entry(search_frame, font=("Arial", 12))
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(search_frame, text="🔍 Najít & Analyzovat", font=("Arial", 12, "bold"),
                  command=lambda: self._search_online_stock(list_available, list_current, filter_vars)).pack(side=tk.RIGHT, padx=(10,0))

        # --- 2. PROSTŘEDNÍ PANEL (Tlačítka) ---
        mid_frame = tk.Frame(main_container)
        mid_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        tk.Frame(mid_frame).pack(fill=tk.Y, expand=True) 
        tk.Button(mid_frame, text="Přidat  >>>", width=14, bg="#E3F2FD", font=("Arial", 12, "bold"),
                  command=lambda: self._move_stock(list_available, list_current, "add", filter_vars)).pack(pady=10)
        
        tk.Button(mid_frame, text="<<<  Odebrat", width=14, font=("Arial", 12, "bold"),
                  command=lambda: self._move_stock(list_available, list_current, "remove", filter_vars)).pack(pady=10)
        
        tk.Frame(mid_frame).pack(fill=tk.Y, expand=True) 

        # --- 3. PRAVÝ PANEL (Moje Portfolio) ---
        right_frame = tk.LabelFrame(main_container, text="Moje Aktivní Portfolio", padx=10, pady=10, font=("Arial", 12, "bold"))
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        curr_container = tk.Frame(right_frame)
        curr_container.pack(fill=tk.BOTH, expand=True)
        
        vsb_curr = tk.Scrollbar(curr_container, orient="vertical")
        hsb_curr = tk.Scrollbar(curr_container, orient="horizontal")
        
        list_current = tk.Listbox(curr_container, selectmode=tk.SINGLE, font=("Consolas", 12), activestyle='none',
                                  yscrollcommand=vsb_curr.set, xscrollcommand=hsb_curr.set)
        
        list_current.grid(row=0, column=0, sticky="nsew")
        vsb_curr.grid(row=0, column=1, sticky="ns")
        hsb_curr.grid(row=1, column=0, sticky="ew")
        
        curr_container.grid_rowconfigure(0, weight=1)
        curr_container.grid_columnconfigure(0, weight=1)
        
        vsb_curr.config(command=list_current.yview)
        hsb_curr.config(command=list_current.xview)
        
        self.health_lbl = tk.Label(right_frame, text="Zdraví: ---", font=("Arial", 14, "bold"))
        self.health_lbl.pack(pady=(15, 5))
        self.health_progress = ttk.Progressbar(right_frame, length=300, mode='determinate', maximum=100)
        self.health_progress.pack(fill=tk.X)
        self.health_msg = tk.Label(right_frame, text="", fg="grey", wraplength=350, justify="center", font=("Arial", 12))
        self.health_msg.pack(pady=10)

        # SPODNÍ LIŠTA
        btn_frame = tk.Frame(editor)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=15, padx=20)
        tk.Button(btn_frame, text="💾 Uložit změny a Zavřít", bg="#2E7D32", fg="white", font=("Arial", 12, "bold"), 
                  command=lambda: self._save_portfolio_changes(editor, list_current, filter_vars), height=2).pack(fill=tk.X)
                  
        list_available.bind("<Double-1>", lambda e: self._edit_stock_tags(list_available, list_available, list_current, filter_vars))
        list_current.bind("<Double-1>", lambda e: self._edit_stock_tags(list_current, list_available, list_current, filter_vars))

        self._refresh_lists(list_available, list_current, filter_vars)

    def _on_editor_sort_change(self, list_avail, list_curr, filter_vars):
        """Uloží preferenci řazení do JSONu a okamžitě aktualizuje seznamy."""
        self.editor_sort_mode = self.sort_mode_var.get()
        self.save_data()
        self._refresh_lists(list_avail, list_curr, filter_vars)
        
    def _get_bar_visual(self, val, max_val, char="█"):
        if val is None: return ".........."
        normalized = max(0, min(val, max_val)) / max_val
        filled = int(normalized * 10)
        return (char * filled).ljust(10, '.')

    def _get_growth_bar_visual(self, val, scale=100.0):
        neg_side = 5
        pos_side = 5
        mid_char = "|"
        
        if val is None: return "....." + mid_char + "....."
        
        if val >= 0:
            num = int(min(val, scale) / scale * pos_side)
            if val > 0 and num == 0: num = 1
            left = "." * neg_side
            right = ("█" * num).ljust(pos_side, ".")
            return f"{left}{mid_char}{right}"
        else:
            num = int(min(abs(val), scale) / scale * neg_side)
            if val < 0 and num == 0: num = 1
            left = ("." * (neg_side - num)) + ("▒" * num)
            right = "." * pos_side
            return f"{left}{mid_char}{right}"
            
    def _refresh_lists(self, l_avail, l_curr, f_vars):
        """Vymaže seznamy a naplní je znovu podle aktuálních filtrů, řazení a s ETF prefixem."""
        l_avail.delete(0, tk.END)
        l_curr.delete(0, tk.END)
        
        current_tickers = list(self.temp_targets.keys())
        GROWTH_SCALE = 100.0 
        YIELD_SCALE = 10.0   
        
        def format_row(t, m):
            dy = m.get('yield', 0)
            gr = m.get('growth', 0)
            bar_gro = self._get_growth_bar_visual(gr, GROWTH_SCALE)
            bar_div = self._get_bar_visual(dy, YIELD_SCALE, "▓")
            
            # --- Přidání prefixu ETF ---
            display_name = m['name']
            if m.get("sector") == "ETF":
                display_name = f"ETF - {display_name}"
            
            return f"{t:<6} {bar_gro}  {bar_div}  {display_name}"

        def sort_key(item):
            meta = item[1]
            raw_growth = meta.get('growth', 0)
            raw_yield = meta.get('yield', 0)
            growth_bucket = int(np.clip(raw_growth / (GROWTH_SCALE / 5), -5, 5))
            return (growth_bucket, raw_yield)

        # Určení zvoleného řazení
        sort_mode = getattr(self, "sort_mode_var", None)
        mode = sort_mode.get() if sort_mode else "metrics"

        # Naplnění pravého seznamu (Moje)
        my_items = []
        for t in current_tickers:
            meta = self.stock_db.get(t, {"name": "Unknown", "tags":[], "growth": 0, "yield": 0})
            my_items.append((t, meta))
        
        if mode == "alpha":
            my_items.sort(key=lambda item: item[0])  # Seřadí abecedně podle tickeru
        else:
            my_items.sort(key=sort_key, reverse=True) # Původní řazení podle metrik
            
        for t, meta in my_items:
            l_curr.insert(tk.END, format_row(t, meta))
            is_violation = False
            for tag in meta.get("tags", []):
                if tag in f_vars and not f_vars[tag].get():
                    is_violation = True; break
            if is_violation: l_curr.itemconfig(tk.END, fg="red")
            
        # Naplnění levého seznamu (Dostupné)
        avail_items = []
        for t, meta in self.stock_db.items():
            if t in current_tickers: continue 
            skip = False
            for tag in meta.get("tags", []):
                if tag in f_vars and not f_vars[tag].get(): 
                    skip = True; break
            if skip: continue
            avail_items.append((t, meta))
            
        if mode == "alpha":
            avail_items.sort(key=lambda item: item[0])  # Seřadí abecedně podle tickeru
        else:
            avail_items.sort(key=sort_key, reverse=True) # Původní řazení podle metrik
            
        for t, meta in avail_items:
            l_avail.insert(tk.END, format_row(t, meta))
            
        self._check_portfolio_health(current_tickers)

    def _search_online_stock(self, l_avail, l_curr, f_vars):
        """Vyhledá ticker na Yahoo Finance a zkontroluje podporovanou měnu (USD/GBP)."""
        raw_input = self.search_entry.get().strip().upper()
        if not raw_input: return
        
        alternatives = [raw_input]
        if "." not in raw_input: alternatives.append(raw_input + ".L") 
        elif raw_input.endswith(".L"): alternatives.append(raw_input[:-2]) 
            
        for alt in alternatives:
            if alt in self.stock_db:
                messagebox.showinfo("Již existuje", f"Tento titul (nebo jeho varianta {alt}) už v databázi je.", parent=self.editor_window)
                return
        
        search_candidates = [raw_input]
        if "." not in raw_input: search_candidates.append(raw_input + ".L")
            
        found_info, found_stock_obj, final_ticker = None, None, None
        
        for ticker in search_candidates:
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                name_candidate = info.get('shortName') or info.get('longName') or ""
                if name_candidate and not name_candidate.isdigit():
                    found_info = info
                    found_stock_obj = stock
                    final_ticker = ticker
                    break
            except: continue

        if not found_info:
            messagebox.showerror("Nenalezeno", f"Titul '{raw_input}' nebyl nalezen.", parent=self.editor_window)
            return

        # VALIDACE MĚNY
        currency = found_info.get('currency', '').upper()
        # UK akcie mají měnu buď GBP nebo GBp (pence)
        is_uk = currency in ["GBP", "GBP", "GBP", "GBp"]
        is_us = currency == "USD"
        
        if not (is_uk or is_us):
            messagebox.showerror("Nepodporovaná měna", 
                                 f"Titul {final_ticker} se obchoduje v měně {currency}.\n\n"
                                 "Aplikace aktuálně podporuje pouze USD a GBP. Akcii nelze přidat.", 
                                 parent=self.editor_window)
            return
        
        # Sjednocení symbolu měny pro vnitřní logiku aplikace
        final_currency = "GBP" if is_uk else "USD"

        # --- PRIIPs a ETF LOGIKA ---
        quote_type = found_info.get('quoteType', '').upper()
        is_etf = quote_type in ['ETF', 'MUTUALFUND']
        
        sector = found_info.get('sector', 'Unknown')
        name = found_info.get('shortName') or found_info.get('longName') or final_ticker
        etf_type = None
        
        if is_etf:
            # Kontrola PRIIPs (Americká ETF nemají koncovku burzy .L apod.)
            if "." not in final_ticker and "UCITS" not in name.upper():
                messagebox.showerror("Regulace PRIIPs", 
                                     f"Titul {final_ticker} ({name}) je americké ETF.\n\n"
                                     "Z důvodu evropské regulace PRIIPs nemohou retailoví investoři v ČR "
                                     "americká ETF běžně nakupovat.\n\n"
                                     "Vyhledejte prosím evropskou UCITS alternativu (např. na londýnské burze "
                                     "s koncovkou .L, jako VUSA.L nebo CSPX.L).", 
                                     parent=self.editor_window)
                return
                
            sector = "ETF"
            # Dotaz na typ ETF (Zásadní pro daně a kalendář)
            is_acc = messagebox.askyesno("Typ fondu (ETF)", 
                                         f"Nalezeno ETF: {name}\n\n"
                                         "Je tento fond AKUMULAČNÍ?\n"
                                         "(Tj. nevyplácí dividendy na účet, ale automaticky je reinvestuje do své hodnoty?)\n\n"
                                         "• Zvolte 'Ano' pro Akumulační (bez daní z dividend)\n"
                                         "• Zvolte 'Ne' pro Distribuční (vyplácí hotovost)",
                                         parent=self.editor_window)
            etf_type = "Acc" if is_acc else "Dist"
        # ---------------------------------

        try:
            hist = found_stock_obj.history(period="2y")
            if len(hist) > 1:
                growth_2y = ((hist['Close'].iloc[-1] / hist['Close'].iloc[0]) - 1.0) * 100
            else:
                growth_2y = 0
            
            # Pokud je ETF akumulační, natvrdo anulujeme dividendu
            if is_etf and etf_type == "Acc":
                div_yield = 0.0
            else:
                raw_yield = found_info.get('dividendYield') or found_info.get('trailingAnnualDividendYield') or 0
                div_yield = raw_yield * 100 if 0 < raw_yield < 0.5 else raw_yield
            
            div_str = f"{div_yield:.2f}".replace('.', ',')
            gro_str = f"{growth_2y:.1f}".replace('.', ',')
            
            # Dotaz na přidání do databáze
            if messagebox.askyesno("Nový titul nalezen", 
                                   f"Ticker: {final_ticker}\nNázev: {name}\nSektor: {sector}\n"
                                   f"Dividenda: {div_str}%\nRůst (2r): {gro_str}%\n\n"
                                   f"Chcete přidat do databáze?", parent=self.editor_window):
                
                tags =[]
                confirmed = False
                
                # Malé okno pro kategorizaci rizik
                tag_window = tk.Toplevel(self.editor_window)
                tag_window.title("Kategorizace")
                
                # Pozicování k myši
                x = self.root.winfo_pointerx() + 15
                y = self.root.winfo_pointery() + 15
                tag_window.geometry(f"+{x}+{y}")
                tag_window.transient(self.editor_window) 
                tag_window.grab_set() 
                
                tag_vars = {}
                tk.Label(tag_window, text=f"Označte rizika pro {final_ticker}:", font=("Arial", 12, "bold")).pack(pady=10, padx=20)
                
                for k, v in TAGS.items():
                    var = tk.BooleanVar()
                    tag_vars[k] = var
                    tk.Checkbutton(tag_window, text=v, variable=var, font=("Arial", 12)).pack(anchor="w", padx=30)
                
                def confirm_tags():
                    nonlocal confirmed
                    confirmed = True
                    for k, v in tag_vars.items():
                        if v.get(): tags.append(k)
                    tag_window.grab_release() 
                    tag_window.destroy()
                
                tk.Button(tag_window, text="Potvrdit a Uložit", command=confirm_tags, bg="#E3F2FD", font=("Arial", 12, "bold")).pack(pady=20)
                
                # Čekání na zavření okna kategorizace
                self.editor_window.wait_window(tag_window)
                
                if confirmed:
                    # Ukládáme i typ ETF do DB
                    meta_data = {
                        "name": name, "sector": sector, "tags": tags,
                        "yield": div_yield, "growth": growth_2y, "currency": final_currency
                    }
                    if is_etf: meta_data["etf_type"] = etf_type
                    
                    self.stock_db[final_ticker] = meta_data
                    self._refresh_lists(l_avail, l_curr, f_vars)
                
        except Exception as e:
            messagebox.showerror("Chyba analýzy", f"Data pro {final_ticker} nelze zpracovat: {e}", parent=self.editor_window)

    def _move_stock(self, l_avail, l_curr, direction, f_vars):
        """Přenese akcii mezi nabídkou a aktivním portfoliem (v dočasné paměti)."""
        if direction == "add":
            sel = l_avail.curselection()
            if not sel: return
            text = l_avail.get(sel[0])
            ticker = text.split()[0] # Získání čistého tickeru z formátovaného řádku
            if ticker not in self.temp_targets: self.temp_targets[ticker] = 0.0 
            
        elif direction == "remove":
            sel = l_curr.curselection()
            if not sel: return
            text = l_curr.get(sel[0])
            ticker = text.split()[0]
            if ticker in self.temp_targets: del self.temp_targets[ticker]
            
        self._refresh_lists(l_avail, l_curr, f_vars)

    def _edit_stock_tags(self, source_listbox, l_avail, l_curr, f_vars):
        """Umožňuje upravit etické štítky u již existující akcie po dvojkliku."""
        sel = source_listbox.curselection()
        if not sel: return
        
        text = source_listbox.get(sel[0])
        ticker = text.split()[0]
        if ticker not in self.stock_db: return
        
        current_tags = self.stock_db[ticker].get("tags", [])
        tag_window = tk.Toplevel(self.editor_window)
        tag_window.title("Úprava kategorizace")
        
        # Pozicování k myši
        x = self.root.winfo_pointerx() + 15
        y = self.root.winfo_pointery() + 15
        tag_window.geometry(f"+{x}+{y}")
        tag_window.transient(self.editor_window) 
        tag_window.grab_set() 
        
        tag_vars = {}
        tk.Label(tag_window, text=f"Upravit rizika pro {ticker}:", font=("Arial", 12, "bold")).pack(pady=10, padx=20)
        
        for k, v in TAGS.items():
            var = tk.BooleanVar(value=(k in current_tags))
            tag_vars[k] = var
            tk.Checkbutton(tag_window, text=v, variable=var, font=("Arial", 12)).pack(anchor="w", padx=30)
        
        confirmed = False
        def confirm_tags():
            nonlocal confirmed
            confirmed = True
            self.stock_db[ticker]["tags"] = [k for k, v in tag_vars.items() if v.get()]
            tag_window.grab_release() 
            tag_window.destroy()
        
        tk.Button(tag_window, text="Potvrdit úpravy", command=confirm_tags, bg="#E3F2FD", font=("Arial", 12, "bold")).pack(pady=20)
        self.editor_window.wait_window(tag_window)
        
        if confirmed:
            self._refresh_lists(l_avail, l_curr, f_vars)

    def _check_portfolio_health(self, current_tickers):
        """Analytický modul vyhodnocující diverzifikaci, rizika, růst a cash-flow mixu."""
        score = 100
        warnings = []
        
        count = len(current_tickers)
        if count == 0:
            self.health_progress['value'] = 0
            self.health_lbl.config(text="Zdraví: ---", fg="grey")
            self.health_msg.config(text="Vyberte akcie pro analýzu.")
            return

        # 1. Základní parametry (počet pozic)
        # Pokud má investor ETF, stačí mu pro diverzifikaci i méně než 8 titulů.
        has_etf = any(self.stock_db.get(t, {}).get("sector") == "ETF" for t in current_tickers)
        min_pos = 4 if has_etf else LIMITS["MIN_POSITIONS"]

        if count < min_pos:
            score -= 20
            warnings.append(f"Máte málo pozic ({count}). Doporučeno min. {min_pos}.")
        elif count > LIMITS["MAX_POSITIONS"]:
            score -= 10
            warnings.append(f"Příliš mnoho akcií ({count}). Hrozí nepřehlednost.")
            
        sectors = {}
        bdc_count = 0
        growth_count = 0 
        yield_count = 0 

        for t in current_tickers:
            meta = self.stock_db.get(t, {})
            sec = meta.get("sector", "Unknown")
            sectors[sec] = sectors.get(sec, 0) + 1
            
            if t in ["MAIN", "HTGC", "ARCC", "OBDC"] or "Capital" in meta.get("name", ""):
                bdc_count += 1
            if meta.get("growth", 0) > 10.0:
                growth_count += 1
            if meta.get("yield", 0) > 2.5:
                yield_count += 1
                
        # 2. Vyhodnocení koncentrace (PŘESKAKUJE SEKTOR ETF)
        for sec, num in sectors.items():
            if sec == "ETF": continue # ETF jsou vnitřně diverzifikované, nevadí vysoké zastoupení
            
            if num / count > LIMITS["MAX_SECTOR_WEIGHT"]: 
                score -= 15
                warnings.append(f"Vysoká koncentrace v sektoru {sec}.")
                
        # 3. Vyhodnocení rizikových finančních firem
        if bdc_count / count > 0.3:
            score -= 15
            warnings.append("Vysoký podíl rizikových finančních firem (BDC).")

        # 4. Vyhodnocení Růstu vs. Dividendy
        growth_ratio = growth_count / count
        if growth_ratio < LIMITS["MIN_GROWTH_RATIO"]:
            score -= 15
            warnings.append(f"Nízký růstový potenciál ({int(growth_ratio*100)}% růstových titulů).")

        yield_ratio = yield_count / count
        if yield_ratio < LIMITS["MIN_YIELD_RATIO"]:
            score -= 15
            warnings.append(f"Slabé cash-flow ({int(yield_ratio*100)}% výnosových titulů).")

        # Ochrana proti podtečení nuly
        score = max(0, score)

        # Aktualizace UI
        self.health_progress['value'] = score
        if score > 80: color = "#2E7D32"; txt = "Vynikající"
        elif score > 50: color = "#E65100"; txt = "Průměrné"
        else: color = "#C62828"; txt = "Rizikové"
        
        self.health_lbl.config(text=f"Zdraví složení: {score}% ({txt})", fg=color)
        self.health_msg.config(text="\n".join(warnings) if warnings else "Portfolio je vzorně vyvážené.")

    def _save_portfolio_changes(self, window, l_curr, f_vars):
        """Propíše dočasné změny z editoru do ostrého nastavení a uloží do JSONu."""
        global TARGETS, CURRENCIES
        
        # 1. Zjištění aktuální pozice záložky v Notebooku, aby se po refreshi nepřehodilo pořadí
        try:
            current_index = self.notebook.index(self.tuner_frame)
        except:
            current_index = None # Fallback pro jistotu
            
        # 2. Propis dat do paměti aplikace
        TARGETS.clear()
        TARGETS.update(self.temp_targets)
        
        # Okamžitá registrace měn nově přidaných akcií do globální paměti
        for t, meta in self.stock_db.items():
            if t in TARGETS and "currency" in meta:
                CURRENCIES[t] = meta["currency"]

        self.ethical_filters = {k: v.get() for k, v in f_vars.items()}
        
        # Inteligentní úprava vah při změně počtu titulů
        cnt = len(TARGETS)
        if cnt > 0:
            current_sum = sum(TARGETS.values())
            
            if current_sum <= 0:
                # Ochrana: Všechny váhy jsou nula (např. zcela prázdné portfolio)
                new_w = 1.0 / cnt
                for t in TARGETS: TARGETS[t] = new_w
            elif abs(current_sum - 1.0) > 0.001:
                # Pokud byla akcie odebrána, součet klesne pod 1.0.
                # Abychom base portfolio nerozbili, pouze poměrově zvětšíme 
                # zbývající akcie tak, aby opět tvořily 100 %, ale zachovaly si vzájemné poměry.
                for t in TARGETS: TARGETS[t] = TARGETS[t] / current_sum
                
            # POZNÁMKA: Pokud byla akcie PŘIDÁNA, má zatím váhu 0.0 a current_sum je stále 1.0.
            # V takovém případě kód neudělá NIC. Base portfolio zůstane nedotčené (staré) 
            # a nová akcie čeká na 0 %, dokud jí Tuner nepřidělí novou váhu!
        
        self.stock_db_from_json = self.stock_db
        self.save_data()
        
        self.tuner_data_loaded = False
        window.destroy()
        
        # 3. Reset a znovunačtení záložky Tuning na původním indexu
        self.notebook.forget(self.tuner_frame)
        
        # Ošetření pro metodu setup_tuner_tab, pokud by nepodporovala index
        try:
            self.setup_tuner_tab(index=current_index)
        except TypeError:
            self.setup_tuner_tab() # Fallback, pokud parametr index v metodě chybí
            
        self.notebook.select(self.tuner_frame)
        
        # AUTOMATICKÉ SPUŠTĚNÍ SIMULACE
        # Počkáme 200 ms na překreslení UI a pak automaticky zavoláme stejnou funkci,
        # kterou jinak volá oranžové tlačítko "NAČÍST DATA & SIMULOVAT".
        self.root.after(500, lambda: self.run_tuner_with_loading(
            lambda: self.initialize_tuner_data(force_download=True), 
            "Stahuji data a simuluji..."
        ))
        
        # Aktualizace checkboxů na kartě nákupů
        if hasattr(self, '_build_buy_checkboxes'):
            self._build_buy_checkboxes()
        
    def get_currency_for_ticker(self, ticker):
        """Bezpečně zjistí měnu pro daný ticker z konfigurace, DB nebo odhadem."""
        # 1. Priorita: Slovník CURRENCIES (pro tituly definované přímo v kódu)
        if ticker in CURRENCIES:
            return CURRENCIES[ticker]
        
        # 2. Priorita: Metadata v stock_db (pro tituly přidané uživatelem)
        db = getattr(self, 'stock_db', DEFAULT_STOCK_DB)
        if ticker in db and "currency" in db[ticker]:
            return db[ticker]["currency"]
            
        # 3. Fallback: Odhad podle sufixu (Yahoo standard)
        return "GBP" if ticker.endswith(".L") else "USD"

    def get_country_for_ticker(self, ticker):
        """Určí zemi domicilu pro daňové účely (USA vs. UK/UCITS)."""
        # 1. Priorita: Metadata v databázi (pokud existují)
        db = getattr(self, 'stock_db', DEFAULT_STOCK_DB)
        if ticker in db and "country" in db[ticker]:
            return db[ticker]["country"]
            
        # 2. Sekundární pravidlo: Cokoliv s koncovkou .L je Londýn (UK/UCITS)
        if ticker.endswith(".L"):
            return "UK"
        
        # 3. Default (JNJ, AAPL atd.) je USA
        return "USA"

    # --------------------------------------------------------------------------
    # NÁSTROJE UI (INTERAKTIVNÍ GRAFY A TOOLTIPY)
    # --------------------------------------------------------------------------

    def on_hover_pie(self, event):
        """Detekuje najetí myši nad výseč koláčového grafu a vyvolá tooltip."""
        if event.inaxes is None or getattr(self, 'tuner_loading_state', {}).get("is_loading"):
            self._hide_tooltip()
            return

        target_text = None
        
        # Tooltip pro rozdělení vah
        if event.inaxes == self.ax_pie and hasattr(self, 'wedges_weights'):
            for i, wedge in enumerate(self.wedges_weights):
                if wedge.contains(event)[0]:
                    ticker = self.ordered_tickers[i]
                    weight = getattr(self, '_current_pie_weights', self.sim_weights[self.current_sim_idx])[i]
                    weight_str = f"{weight:.1%}".replace('.', ',')
                    target_text = f"{ticker}\nVáha: {weight_str}"
                    if getattr(self, 'chart_view_var', None) and self.chart_view_var.get() == "new":
                        target_text += f" (dvojklik zafixuje váhu)"

                    # --- NOVÉ: Přidání fundamentů do tooltipu ---
                    if hasattr(self, 'tuner_fundamentals') and ticker in self.tuner_fundamentals:
                        fund = self.tuner_fundamentals[ticker]
                        
                        # 1. Očekávaný růst (již ho máme spočítaný)
                        upside = self.tuner_upsides[i]
                        growth_str = f"{upside*100:+.1f} %".replace('.', ',')
                        
                        # 2. P/E a EPS (Ošetření ETF, která to nemají)
                        pe = fund.get('pe_ratio')
                        eps = fund.get('eps')
                        curr = self.get_currency_for_ticker(ticker)
                        
                        pe_str = f"{pe:.1f}".replace('.', ',') if pe else "N/A"
                        eps_str = f"{eps:.2f} {curr}".replace('.', ',') if eps else "N/A"
                        
                        # 3. Překlad doporučení analytiků
                        rec_raw = fund.get('recommendation')
                        rec_dict = {"buy": "Koupit", "strong_buy": "Silně koupit", "hold": "Držet", "sell": "Prodat", "strong_sell": "Silně prodat", "none": "N/A"}
                        rec_str = rec_dict.get(rec_raw, "N/A") if rec_raw else "N/A"
                        
                        # 4. Citlivost/Riziko pomocí parametru Beta
                        beta = fund.get('beta')
                        if beta is None:
                            risk_str = "N/A"
                        elif beta < 0.8:
                            risk_str = "Konzervativní (nízké výkyvy)"
                        elif beta <= 1.2:
                            risk_str = "Neutrální (kopíruje trh)"
                        else:
                            risk_str = "Agresivní (vysoké výkyvy)"
                            
                        # Poskládání textu pod sebe
                        target_text += f"\n───────────────"
                        target_text += f"\nOčekávaný růst: {growth_str}"
                        target_text += f"\nForward P/E: {pe_str}  |  EPS: {eps_str}"
                        target_text += f"\nTržní riziko: {risk_str}"
                        target_text += f"\nAnalytici radí: {rec_str}"
                        
                    break

        # Tooltip pro zdroje dividend
        elif event.inaxes == self.ax_div_pie and hasattr(self, 'wedges_divs'):
            for i, wedge in enumerate(self.wedges_divs):
                if wedge.contains(event)[0]:
                    ticker = self.div_data_tickers[i]
                    val = self.div_data_sizes[i]
                    total = sum(self.div_data_sizes)
                    
                    val_str = f"{val:,.0f}".replace(',', ' ')
                    pct_str = f"{val/total:.1%}".replace('.', ',')
                    target_text = f"{ticker}\nPodíl: {pct_str}\n({val_str} Kč)"
                    
                    if hasattr(self, 'tuner_fundamentals') and ticker in self.tuner_fundamentals:
                        fund = self.tuner_fundamentals[ticker]
                        meta = getattr(self, 'stock_db_from_json', DEFAULT_STOCK_DB).get(ticker, {})
                        sector = meta.get("sector", "Unknown")
                        
                        # Graf si přečte limit přímo z paměti výpočetního jádra
                        limit = fund.get('limit', 0.9)
                        
                        if fund['payout_ratio'] == -1:
                            target_text += f"\n\nℹ️ Payout poměr ignorován\n(účetní anomálie zisku)"
                        elif fund['payout_ratio'] > limit:
                            pr_str = f"{fund['payout_ratio']*100:.0f} %".replace('.', ',')
                            safe_str = f"{fund['safe_yield']*100:.2f} %".replace('.', ',')
                            target_text += f"\n\n⚠️ Payout: {pr_str}\n(Zisk nepokrývá dividendu!)\nPředpoklad na 1 rok snížen: {safe_str}"
                    break

        if target_text: self._show_tooltip(target_text)
        else: self._hide_tooltip()

    def _show_tooltip(self, text):
        """Vytvoří a napozicuje skutečné nezávislé plovoucí okno u kurzoru myši."""
        if self.pie_tooltip is None:
            self.pie_tooltip = tk.Toplevel(self.root)
            self.pie_tooltip.wm_overrideredirect(True) # Odstraní rámeček okna (minimalistický vzhled)
            self.pie_tooltip.wm_attributes("-topmost", True) # Drží okénko vždy nad ostatními
            
            # Vnitřní label pro text
            self.pie_tooltip_lbl = tk.Label(self.pie_tooltip, text="", bg="#FFFFE1", relief=tk.SOLID, 
                                            borderwidth=1, font=("Arial", 11), justify=tk.LEFT)
            self.pie_tooltip_lbl.pack()
        
        self.pie_tooltip_lbl.config(text=text)
        
        # Souřadnice bereme přímo z obrazovky (bez ohledu na to, kde leží okno appky)
        x = self.root.winfo_pointerx() + 15
        y = self.root.winfo_pointery() + 15
        
        self.pie_tooltip.geometry(f"+{x}+{y}")
        self.pie_tooltip.deiconify() # Zobrazí okénko, pokud bylo skryto

    def _hide_tooltip(self):
        """Skryje plovoucí okénko. Bezpečně ošetřeno pro volání z FocusOut událostí."""
        if getattr(self, 'pie_tooltip', None): 
            self.pie_tooltip.withdraw() # Skryje okénko, ale nezničí ho

    def on_click_pie(self, event):
        """Detekuje dvojklik myší nad výsečí koláčového grafu (pouze pro levý graf vah)."""
        # Ignorujeme obyčejné kliknutí, zajímá nás jen dvojklik
        if not event.dblclick:
            return
        # Reagujeme pouze na kliknutí do hlavního koláčového grafu "Rozložení vah"
        if event.inaxes != self.ax_pie:
            return
        # Během načítání/simulace nedovolíme interakci
        if getattr(self, 'tuner_loading_state', {}).get("is_loading"):
            return
            
        # Zakázání dvojkliku, pokud se uživatel dívá na "base" portfolio
        if getattr(self, 'chart_view_var', None) and self.chart_view_var.get() == "base":
            return
            
        if hasattr(self, 'wedges_weights'):
            for i, wedge in enumerate(self.wedges_weights):
                if wedge.contains(event)[0]:
                    ticker = self.ordered_tickers[i]
                    self._open_fix_weight_dialog(ticker, i)
                    break

    def _open_fix_weight_dialog(self, ticker, idx):
        """Otevře okno pro zadání a validaci fixní váhy dané akcie."""
        if getattr(self, 'sim_weights', None) is None: return
        
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Fixovat {ticker}")
        
        # Otevření dialogu hned u kurzoru myši
        x = self.root.winfo_pointerx() + 15
        y = self.root.winfo_pointery() + 15
        dialog.geometry(f"+{x}+{y}")
        dialog.transient(self.root)
        dialog.grab_set() # Zablokuje interakci s hlavním oknem, dokud se toto nezavře
        dialog.config(bg="#FFF8E1")
        
        tk.Label(dialog, text=f"Zadejte požadovanou fixní váhu pro {ticker} (v %):", 
                 font=("Arial", 12, "bold"), bg="#FFF8E1").pack(pady=(15, 5), padx=20)
        
        # Přečteme aktuálně zobrazenou váhu v grafu
        current_w = self.sim_weights[self.current_sim_idx][idx] * 100
        
        entry_w = tk.Entry(dialog, font=("Arial", 14), width=10, justify="center")
        entry_w.insert(0, f"{current_w:.1f}".replace('.', ','))
        entry_w.pack(pady=10)
        entry_w.focus_set()
        entry_w.select_range(0, tk.END) # Automaticky označí text pro snadné přepsání
        
        def apply_weight(event=None):
            val_str = entry_w.get().strip()
            try:
                new_w_pct = float(val_str.replace(',', '.'))
            except ValueError:
                messagebox.showerror("Chyba", "Zadejte platné číslo.", parent=dialog)
                return
                
            if new_w_pct < 0 or new_w_pct > 100:
                messagebox.showerror("Chyba", "Váha musí být mezi 0 a 100 %.", parent=dialog)
                return
                
            new_w = new_w_pct / 100.0
            
            # --- MATEMATICKÁ VALIDACE REALIZOVATELNOSTI PORTFOLIA ---
            # 1. Aktualizujeme případné změněné limity z hlavního okna
            if hasattr(self, '_validate_and_get_limits'):
                self._validate_and_get_limits()
            min_w = getattr(self, 'custom_min_w', MIN_W)
            max_w = getattr(self, 'custom_max_w', MAX_W)
            
            fixed_sum = 0.0
            active_count = 0
            
            for t, var in self.tuner_vars.items():
                if t not in self.ordered_tickers: continue
                t_idx = self.ordered_tickers.index(t)
                
                if t == ticker:
                    fixed_sum += new_w # Toto je nově zadaná váha z dialogu
                elif not var.get(): 
                    # Akcie je již zafixovaná, přičteme její současnou váhu
                    fixed_sum += self.sim_weights[self.current_sim_idx][t_idx]
                else:
                    # Akcie je aktivní (bude generována Monte Carlem)
                    active_count += 1
                    
            rem_w = 1.0 - fixed_sum # Zbývající kapitál k rozdělení
            eps = 0.001 # Tolerance na plovoucí desetinnou čárku
            
            # Pravidlo 1: Kapitál nesmí přetéct do mínusu
            if rem_w < -eps:
                messagebox.showerror("Nelze aplikovat", 
                    f"Součet všech fixovaných vah by překročil 100 % (byl by {fixed_sum*100:.1f} %).", parent=dialog)
                return
                
            # Pravidlo 2: Pokud nezbyla žádná aktivní akcie, součet MUSÍ být přesně 100 %
            if active_count == 0:
                if abs(rem_w) > eps:
                    messagebox.showerror("Nelze aplikovat", 
                        f"Všechny akcie by byly zafixované, ale jejich součet není 100 % (je {fixed_sum*100:.1f} %).", parent=dialog)
                    return
            # Pravidlo 3: Zbývající kapitál se musí vlézt do aktuálních (Min - Max) mantinelů
            else:
                if rem_w < active_count * min_w - eps:
                    messagebox.showerror("Nelze aplikovat", 
                        f"Zbývající kapitál ({rem_w*100:.1f} %) nelze rozdělit mezi {active_count} aktivních akcií.\n\n"
                        f"Každá aktivní akcie musí dostat alespoň nastavené minimum ({min_w*100:g} %), "
                        f"takže potřebujete nechat volných nejméně {active_count * min_w * 100:.1f} %.", parent=dialog)
                    return
                if rem_w > active_count * max_w + eps:
                    messagebox.showerror("Nelze aplikovat", 
                        f"Zbývající kapitál ({rem_w*100:.1f} %) nelze rozdělit mezi {active_count} aktivních akcií.\n\n"
                        f"I kdyby každá aktivní akcie dostala maximální povolenou alokaci ({max_w*100:g} %), "
                        f"pojaly by dohromady jen {active_count * max_w * 100:.1f} % a zbytek peněz by ležel ladem.", parent=dialog)
                    return
                    
            # --- APLIKACE ZMĚN ---
            # 1. Tichá úprava paměti šampiona, aby si ji inicializátor uměl v dalším kroku načíst
            self.sim_weights[self.current_sim_idx][idx] = new_w
            
            # 2. Vizuální odškrtnutí checkboxu u této akcie (čímž se pro tuner stane fixní)
            self.tuner_vars[ticker].set(False)
            
            dialog.destroy()
            
            # Protože jsme zasáhli do vah, dosavadní šampion pro tlačítko "Vylepšit" přestává platit
            if hasattr(self, 'btn_auto_tune') and self.btn_auto_tune.winfo_exists():
                self.btn_auto_tune.config(state=tk.DISABLED)
                
            # Automatické znovuspuštění simulace s novým fixním nastavením
            self.run_tuner_with_loading(lambda: self.initialize_tuner_data(force_download=False), 
                                        f"Zafixováno {ticker} ({new_w_pct:.1f} %). Simuluji...")

        # UI Tlačítka
        btn_frame = tk.Frame(dialog, bg="#FFF8E1")
        btn_frame.pack(pady=15)
        
        tk.Button(btn_frame, text="Uložit a fixovat", command=apply_weight, 
                  bg="#2E7D32", fg="white", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="Zrušit", command=dialog.destroy, font=("Arial", 12)).pack(side=tk.LEFT, padx=10)
        
        # Pohodlné ovládání klávesnicí
        dialog.bind('<Return>', apply_weight)
        dialog.bind('<Escape>', lambda e: dialog.destroy())

    # --------------------------------------------------------------------------
    # TAB 6: ODMĚNA PRO AUTORA (DONATION)
    # --------------------------------------------------------------------------

    def setup_donation_tab(self):
        """Vykreslí záložku s poděkováním a možnostmi podpory (QR kódy a linky)."""
        don_frame = tk.Frame(self.notebook, bg="#f0f2f5")
        self.notebook.add(don_frame, text="Odměna pro autora")
        
        # Ochrana před Garbage Collectorem pro zobrazení obrázků v Tkinteru
        self.qr_images = {}
        
        # --- Nadpis a text ---
        title = tk.Label(don_frame, text="Podpořte další vývoj aplikace ❤️", font=("Arial", 22, "bold"), bg="#f0f2f5", fg="#1a2a6c")
        title.pack(pady=(50, 15))
        
        msg = ("Tato aplikace vznikla jako osobní projekt pro zjednodušení rebalancování a automatizaci české daňové agendy. Pokud vám aplikace ušetřila hodiny práce, nervy s daňovým přiznáním, nebo vám pomohla vylepšit vaše portfolio, budu velmi vděčný za jakýkoliv dobrovolný příspěvek. Vaše podpora mi pomůže pokrýt čas strávený budoucí údržbou, aktualizací a doplňováním nových funkcí.")
        tk.Label(don_frame, text=msg, font=("Arial", 12), bg="#f0f2f5", justify=tk.CENTER, wraplength=1000).pack(pady=(0, 40))
        
        # --- Karty pro QR kódy ---
        cards_frame = tk.Frame(don_frame, bg="#f0f2f5")
        cards_frame.pack(pady=10)
        
        pp_url = "https://www.paypal.com/qrcodes/managed/a8d3c74b-3833-431d-96b2-0cdef2512cde?utm_source=consweb_more"
        wise_url = "https://wise.com/pay/me/petrz339"
        
        # KARTA: PayPal
        pp_frame = tk.LabelFrame(cards_frame, text=" Přes PayPal ", font=("Arial", 12, "bold"), bg="white", padx=25, pady=20)
        pp_frame.grid(row=0, column=0, padx=200)
        
        self.pp_qr_lbl = tk.Label(pp_frame, text="Načítám QR kód...\n(Vyžaduje internet)", width=25, height=12, bg="white", fg="grey", font=("Arial", 10))
        self.pp_qr_lbl.pack(pady=10)
        
        # KARTA: Wise
        wise_frame = tk.LabelFrame(cards_frame, text=" Přes Wise ", font=("Arial", 12, "bold"), bg="white", padx=25, pady=20)
        wise_frame.grid(row=0, column=1, padx=200)
        
        self.wise_qr_lbl = tk.Label(wise_frame, text="Načítám QR kód...\n(Vyžaduje internet)", width=25, height=12, bg="white", fg="grey", font=("Arial", 10))
        self.wise_qr_lbl.pack(pady=10)
        
        tk.Button(wise_frame, text="Otevřít Wise v prohlížeči", font=("Arial", 12, "bold"), bg="#9FE870", fg="#1A1A1A", 
                  command=lambda: webbrowser.open(wise_url)).pack(fill=tk.X, pady=(15, 0))
                  
        # --- Vlákno pro asynchronní stažení QR kódů přes API ---
        def fetch_qrs():
            try:
                # Stažení PayPal QR (Velikost 220x220)
                pp_api = f"https://api.qrserver.com/v1/create-qr-code/?size=220x220&data={urllib.parse.quote(pp_url)}"
                pp_resp = requests.get(pp_api, timeout=5)
                if pp_resp.status_code == 200:
                    pp_b64 = base64.b64encode(pp_resp.content)
                    self.qr_images['pp'] = tk.PhotoImage(data=pp_b64)
                    self.root.after(0, lambda: self.pp_qr_lbl.config(image=self.qr_images['pp'], text="", width=220, height=220))
            except: 
                self.root.after(0, lambda: self.pp_qr_lbl.config(text="Nelze načíst obrázek.\nPoužijte tlačítko níže."))

            try:
                # Stažení Wise QR
                wise_api = f"https://api.qrserver.com/v1/create-qr-code/?size=220x220&data={urllib.parse.quote(wise_url)}"
                wise_resp = requests.get(wise_api, timeout=5)
                if wise_resp.status_code == 200:
                    wise_b64 = base64.b64encode(wise_resp.content)
                    self.qr_images['wise'] = tk.PhotoImage(data=wise_b64)
                    self.root.after(0, lambda: self.wise_qr_lbl.config(image=self.qr_images['wise'], text="", width=220, height=220))
            except: 
                self.root.after(0, lambda: self.wise_qr_lbl.config(text="Nelze načíst obrázek.\nPoužijte tlačítko níže."))
            
        threading.Thread(target=fetch_qrs, daemon=True).start()


# ==============================================================================
# SPUŠTĚNÍ APLIKACE
# ==============================================================================

if __name__ == "__main__":
    # Inicializace hlavního okna Tkinter
    root = tk.Tk()
    
    # Nastavení minimální velikosti okna pro zachování čitelnosti prvků
    root.minsize(1200, 800)
    
    # Spuštění instance aplikace
    app = CzechInvestorApp(root)
    
    # Vstup do hlavní smyčky událostí
    root.mainloop()
