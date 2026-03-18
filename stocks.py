import tkinter as tk
from tkinter import messagebox, ttk
import yfinance as yf
import json
import os
from datetime import datetime, timedelta, date
import threading
import math
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Patch
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

# ==============================================================================
# 1. KONFIGURACE A DATABÁZE APLIKACE
# ==============================================================================

PORTFOLIO_FILE = "portfolio_ledger.json"

# Výchozí cílové váhy (TARGETS)
# Reprezentují ideální rozložení kapitálu. Tyto hodnoty jsou v paměti přepsány,
# pokud má uživatel uložené vlastní váhy v JSON souboru.
TARGETS = {
    # Britská část
    "LGEN.L": 0.0962904534140656,   # Legal & General - High Yield
    "ULVR.L": 0.04339500794232023,  # Unilever - Defensive Staples
    "TRIG.L": 0.09496151355735824,  # Renewables Infrastructure - Income

    # Americká část
    "JNJ":    0.04223442407449506,  # Johnson & Johnson - Core Healthcare
    "NEE":    0.04164047745742633,  # NextEra - Green Utility Growth
    "PEP":    0.05009304221313858,  # PepsiCo - Resilient Staples
    "CAT":    0.054606034730671396, # Industrial/Cyclical Growth
    "AAPL":   0.04502803530977044,  # Technology/Quality Growth
    "O":      0.042072155640151904, # Reality
    "ABBV":   0.05092109039456007,  # Farmaceutický gigant
    "MAIN":   0.09148972366558898,  # Business Development Company (úvěry firmám)
    "ARCC":   0.08648783099862456,  # BDC fond
    "OHI":    0.08808725857018594,  # Zdravotnický REIT (domovy s pečovatelskou službou)
    "AVGO":   0.09011472979451929,  # Broadcom
    "MRK":    0.08257822223712338,  # Merck - biotechnologie
}

# Měny jednotlivých titulů pro správný výpočet FX (převodů měn)
CURRENCIES = {
    "LGEN.L": "GBP", "ULVR.L": "GBP", "TRIG.L": "GBP", 
    "JNJ": "USD", "NEE": "USD", "PEP": "USD", "CAT": "USD", "AAPL": "USD",
    "O": "USD", "ABBV": "USD", "MAIN": "USD", "ARCC": "USD", "OHI": "USD", "AVGO": "USD", "MRK": "USD",
}

# Pravidla pro hodnocení "zdraví" portfolia (použito v Editoru akcií)
# --- KONFIGURACE ZDRAVÍ PORTFOLIA ---
LIMITS = {
    "MAX_SINGLE_WEIGHT": 0.15,   
    "MAX_SECTOR_WEIGHT": 0.35,   
    "MAX_BDC_REIT_WEIGHT": 0.25, 
    "MIN_POSITIONS": 8,
    "MAX_POSITIONS": 25,
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
    
    # -- ZDRAVOTNICTVÍ --
    "JNJ":    {"name": "Johnson & Johnson", "sector": "Healthcare", "tags":[], "yield": 3.0, "growth": -5.0},
    "ABBV":   {"name": "AbbVie Inc.", "sector": "Healthcare", "tags":[], "yield": 3.6, "growth": 25.0},
    "PFE":    {"name": "Pfizer Inc.", "sector": "Healthcare", "tags":[], "yield": 6.0, "growth": -35.0},
    "MRK":    {"name": "Merck & Co.", "sector": "Healthcare", "tags":[], "yield": 2.5, "growth": 20.0},

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

    # -- REALITY (REITs) --
    "O":      {"name": "Realty Income", "sector": "Real Estate", "tags":[], "yield": 5.5, "growth": -12.0},
    "OHI":    {"name": "Omega Healthcare", "sector": "Real Estate", "tags":[], "yield": 8.5, "growth": 10.0},
    "VICI":   {"name": "VICI Properties", "sector": "Real Estate", "tags": ["CASINO"], "yield": 5.8, "growth": 5.0},
    "WPC":    {"name": "W. P. Carey", "sector": "Real Estate", "tags":[], "yield": 6.2, "growth": -15.0},

    # -- PRŮMYSL & INFRASTRUKTURA --
    "CAT":    {"name": "Caterpillar Inc.", "sector": "Industrial", "tags":[], "yield": 1.6, "growth": 60.0},
    "LMT":    {"name": "Lockheed Martin", "sector": "Industrial", "tags": ["WEAPONS"], "yield": 2.8, "growth": 10.0},
    "MMM":    {"name": "3M Company", "sector": "Industrial", "tags":[], "yield": 6.5, "growth": -20.0},
    "TRIG.L": {"name": "Renewables Infra", "sector": "Utilities", "tags":[], "yield": 7.5, "growth": -25.0},
    "NEE":    {"name": "NextEra Energy", "sector": "Utilities", "tags":[], "yield": 3.5, "growth": -15.0},

    # -- ENERGIE (FOSILNÍ) --
    "CVX":    {"name": "Chevron Corp.", "sector": "Energy", "tags": ["FOSSIL"], "yield": 4.1, "growth": -5.0},
    "XOM":    {"name": "Exxon Mobil", "sector": "Energy", "tags": ["FOSSIL"], "yield": 3.2, "growth": 10.0},
    "SHEL.L": {"name": "Shell PLC", "sector": "Energy", "tags": ["FOSSIL"], "yield": 4.0, "growth": 15.0},

    # -- ETF SEKTOR (UCITS VARIANTY PRO ČESKÉHO INVESTORA) --
    # Přidán klíč "country": "UK" pro správné daňové škatulkování v PDF a XML
    "VUSA.L": {"name": "Vanguard S&P 500 (Dist)", "sector": "ETF", "tags": [], "yield": 1.2, "growth": 30.0, "etf_type": "Dist", "currency": "USD", "country": "UK"},
    "CSPX.L": {"name": "iShares Core S&P 500 (Acc)", "sector": "ETF", "tags": [], "yield": 0.0, "growth": 31.0, "etf_type": "Acc", "currency": "USD", "country": "UK"},
    "VWRL.L": {"name": "Vanguard All-World (Dist)", "sector": "ETF", "tags": [], "yield": 1.6, "growth": 20.0, "etf_type": "Dist", "currency": "USD", "country": "UK"},
    "VWRA.L": {"name": "Vanguard All-World (Acc)", "sector": "ETF", "tags": [], "yield": 0.0, "growth": 21.0, "etf_type": "Acc", "currency": "USD", "country": "UK"},
    "VHYL.L": {"name": "Vanguard High Div (Dist)", "sector": "ETF", "tags": [], "yield": 3.5, "growth": 12.0, "etf_type": "Dist", "currency": "USD", "country": "UK"},
    "EQQQ.L": {"name": "iShares NASDAQ 100 (Dist)", "sector": "ETF", "tags": [], "yield": 0.5, "growth": 55.0, "etf_type": "Dist", "currency": "USD", "country": "UK"},
    "CNDX.L": {"name": "iShares NASDAQ 100 (Acc)", "sector": "ETF", "tags": [], "yield": 0.0, "growth": 56.0, "etf_type": "Acc", "currency": "USD", "country": "UK"},
    "IWDP.L": {"name": "iShares Global REITs (Dist)", "sector": "ETF", "tags": [], "yield": 3.8, "growth": 2.0, "etf_type": "Dist", "currency": "USD", "country": "UK"},
}

# Parametry pro Monte Carlo tuning portfolia
MIN_W = 0.04
MAX_W = 0.1
EPS = 0.001
ENFORCEMENT_W = 0.5  # Důraz na trefení čísla na slideru
STABILITY_W = 0.5    # Důraz na minimální změnu existujících vah
MC_NO = 200000       # Počet simulovaných portfolií (musí být větší než 20000)
MC_NO_IMPR = 500000  # Počet simulovaných portfolií při vylepšování
MAX_DIV_SHARE = 0.23 # Maximální tolerovaný podíl jedné akcii v celkovém úhrnu dividend
DIV_YIELD_DROP = 0.5 # Očekávaný poměr změny dividend u akcií, které vyplácejí více než 90% zisku
DIV_WARN_FRACTION = 0.03 # Od jakého podílu jednoho zdroje dividend se zobrazí varování
HHI_PENALTY = 2.0    # míra penalizace koncentrace portfolia při optimalizaci (multiplikátor Herfindahl-Hirschmanova indexu)

# ==============================================================================
# 2. JÁDRO PRO MULTIPROCESSING (MONTE CARLO)
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
# 3. HLAVNÍ TŘÍDA APLIKACE (GUI A LOGIKA)
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

        self.root.after(2000, lambda: self.run_dash_with_loading(self.refresh_stats, "Stahuji data, prosím, čekejte..."))

    def on_close(self):
        self.root.destroy()
        sys.exit()

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
                        # OPRAVA: Načtení měn pro VŠECHNY evidované akcie, i ty minulé
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
                    
                    return ledger, history, rates
            except Exception as e: 
                print(f"Varování při načítání JSON: {e}")
        
        self.ethical_filters = {k: True for k in TAGS}
        self.custom_min_w = MIN_W
        self.custom_max_w = MAX_W
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
            "real_dividends": getattr(self, 'real_dividends',[])
        }
        with open(PORTFOLIO_FILE, "w") as f: json.dump(data, f, indent=4)

    def check_and_update_uniform_rates(self):
        current_year = datetime.now().year
        last_year = str(current_year - 1)
        if last_year in self.uniform_rates: return
        threading.Thread(target=self._scrape_worker, args=(last_year,), daemon=True).start()

    def _scrape_worker(self, year):
        import re
        url = f"https://www.kurzy.cz/kurzy-men/jednotny-kurz/{year}/"
        
        # Klíčové hlavičky, aby nás web kurzy.cz nepovažoval za bot a neblokoval
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'cs,en-US;q=0.7,en;q=0.3',
        }

        try:
            # Použijeme Session pro stabilnější připojení
            session = requests.Session()
            resp = session.get(url, headers=headers, timeout=10)
            resp.encoding = 'utf-8'
            
            if resp.status_code != 200:
                raise ConnectionError(f"Server vrátil chybu {resp.status_code}")

            soup = BeautifulSoup(resp.text, 'html.parser')
            rates_found = {}
            targets = {"USD": "USD", "GBP": "GBP"}

            # Projdeme všechny tabulky na stránce
            for table in soup.find_all('table'):
                for row in table.find_all('tr'):
                    cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                    if not cells: continue
                    
                    row_str = " ".join(cells).upper()
                    
                    for symbol, code in targets.items():
                        # Pokud v řádku vidíme kód měny
                        if code in row_str:
                            # Projdeme buňky a hledáme kurz (číslo s 3 des. místy)
                            for cell in cells:
                                # Regex hledá formát: aspoň jedna cifra, čárka/tečka a přesně tři cifry
                                match = re.search(r'(\d+[\,\.]\d{3})', cell)
                                if match:
                                    val = float(match.group(1).replace(',', '.'))
                                    # Pojistka: jednotný kurz je vždy nad 10 Kč (vyloučí roky a jednotky)
                                    if val > 10: 
                                        rates_found[symbol] = val

            # Pokud máme oba kurzy, zapíšeme je
            if "USD" in rates_found and "GBP" in rates_found:
                self.uniform_rates[str(year)] = rates_found
                self.save_data()
            else:
                missing = [k for k in ["USD", "GBP"] if k not in rates_found]
                raise ValueError(f"Chybějící data pro: {', '.join(missing)}")

        except Exception as e:
            # Upozornění uživatele (bezpečně přes hlavní vlákno)
            err_msg = (
                f"Chyba při stahování Jednotných kurzů pro rok {year}:\n{str(e)}\n\n"
                "Aplikace použije odhadované tržní kurzy."
            )
            self.root.after(0, lambda: messagebox.showwarning("Upozornění scraperu", err_msg))

    def get_fx_rates(self):
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
                return {"USD": usd, "GBP": gbp}
        except Exception as e: print(f"FX Warning: {e}")
        return {"USD": 23.5, "GBP": 29.5}

    def fetch_sell_price(self):
        """Spustí stahování aktuální ceny ve vedlejším vlákně, aby UI nezamrzlo."""
        ticker = self.sell_ticker.get().strip().upper()
        if not ticker: return
        
        # Vizuální indikace v Dashboardu (pokud je label dostupný)
        if hasattr(self, 'status_lbl'):
            self.status_lbl.config(text=f"Stahuji cenu pro {ticker}...", fg="blue")
        
        def work():
            try:
                # Použijeme náš robustní downloader
                df = self._safe_yf_download(ticker, period="5d")
                
                if df.empty or 'Close' not in df:
                    raise ValueError(f"Yahoo Finance neposkytl cenu pro {ticker}.")
                
                # Získání Close dat
                close_col = df['Close']
                
                # yfinance může vrátit DataFrame (u více tickerů) nebo Series (u jednoho).
                # Musíme zkontrolovat, co jsme dostali:
                if isinstance(close_col, pd.DataFrame):
                    # Pokud je to DataFrame, vybereme sloupec s tickerem
                    p_val = close_col[ticker].ffill().iloc[-1]
                else:
                    # Pokud je to Series, vezmeme poslední hodnotu přímo
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
                if hasattr(self, 'status_lbl'):
                    self.root.after(0, lambda: self.status_lbl.config(text="Hotovo", fg="green"))

        threading.Thread(target=work, daemon=True).start()

    def _update_sell_price_ui(self, price):
        """Pomocná metoda pro bezpečný zápis ceny do políčka (voláno z after)."""
        self.sell_price_entry.delete(0, tk.END)
        self.sell_price_entry.insert(0, f"{float(price):.2f}".replace('.', ','))

    def _safe_yf_download(self, tickers, period="5y", interval="1d", max_retries=4, auto_adjust=True):
        """Robustní stahovač s ochranou proti vnitřním chybám yfinance (NoneType error)."""
        import time
        import random
        import numpy as np
        import pandas as pd
        from datetime import datetime, timedelta
        
        if isinstance(tickers, str):
            expected_tickers = tickers.split()
        else:
            expected_tickers = list(tickers)
            
        for i in range(max_retries):
            try:
                # 1. HLAVNÍ STAŽENÍ
                data = yf.download(expected_tickers, period=period, interval=interval, 
                                   progress=False, auto_adjust=auto_adjust, actions=False, threads=False)                
                # Ochrana proti vnitřní chybě yfinance, kdy download vrátí None nebo prázdno
                if data is None or data.empty or 'Close' not in data:
                    raise ValueError("Yahoo Finance nevrátil validní data.")
                
                close_data = data['Close'].replace(0.0, np.nan)
                
                # 2. KONTROLA INTEGRITY (SPOT-CHECK)
                if period == "5y":
                    if len(close_data) < 1000:
                        raise ValueError("Vrácena nekompletní historie.")

                    check_dt = datetime.now() - timedelta(days=365 * 2)
                    closest_idx = close_data.index.get_indexer([check_dt], method='nearest')[0]
                    check_date_real = close_data.index[closest_idx]
                    
                    if isinstance(close_data, pd.DataFrame):
                        suspicious_tickers = [t for t in expected_tickers if pd.isna(close_data.at[check_date_real, t])]
                    else:
                        suspicious_tickers = expected_tickers if pd.isna(close_data.iloc[closest_idx]) else []

                    if suspicious_tickers:
                        # Ignorujeme měnové páry v kontrolním bodu, jsou náchylné na krátkodobé výpadky
                        # Akcie jsou prioritou pro kontrolu integrity
                        stocks_only = [t for t in suspicious_tickers if "=" not in t]
                        
                        if stocks_only:
                            start_c = (check_date_real - timedelta(days=5)).strftime('%Y-%m-%d')
                            end_c = (check_date_real + timedelta(days=5)).strftime('%Y-%m-%d')
                            
                            check_data = yf.download(stocks_only, start=start_c, end=end_c,
                                                     progress=False, auto_adjust=auto_adjust, actions=False, threads=False)
                            
                            if check_data is not None and not check_data.empty and 'Close' in check_data:
                                c_close = check_data['Close']
                                found_in_check = []
                                for t in stocks_only:
                                    if isinstance(c_close, pd.DataFrame):
                                        if t in c_close.columns and not c_close[t].dropna().empty:
                                            found_in_check.append(t)
                                    elif not c_close.dropna().empty:
                                        found_in_check.append(t)
                                
                                if found_in_check:
                                    raise ValueError(f"Data pro {found_in_check} v balíku chybí, ale na serveru jsou.")

                # 3. FINÁLNÍ VERIFIKACE
                missing = []
                if isinstance(close_data, pd.DataFrame):
                    for t in expected_tickers:
                        # Měnové páry (FX) mohou mít v historii mezery (svátky), u nich jsme benevolentnější
                        if "=" in t: continue 
                        if t not in close_data.columns or close_data[t].dropna().empty:
                            missing.append(t)
                elif close_data.dropna().empty:
                    missing = expected_tickers

                if missing:
                    raise ValueError(f"Totální výpadek dat pro: {', '.join(missing)}")
                    
                return data
                
            except Exception as e:
                # Zde se zachytí i ten TypeError z vnitřku yfinance
                print(f"Pokus {i+1} selhal: {e}")
                if i < max_retries - 1:
                    time.sleep(2.0 + i + random.uniform(0, 1))
                    
        return pd.DataFrame()

    def _safe_get_dividends(self, ticker, max_retries=3):
        """Inteligentní stahovač dividend s pamětí (Cache) a ochranou proti falešným prázdným datům."""
        import time
        import pandas as pd
        if not hasattr(self, '_div_cache'):
            self._div_cache = {}
            
        # Pokud už byly dividendy v této relaci staženy, vrať je okamžitě z paměti
        if ticker in self._div_cache:
            return self._div_cache[ticker]
            
        for i in range(max_retries):
            try:
                # Ochranná pauza před každým novým dotazem na Yahoo (minimalizuje riziko rate-limitu)
                time.sleep(0.5)
                
                divs = yf.Ticker(ticker).dividends
                
                if divs is not None:
                    # Yahoo občas při rate-limitu nehodí chybu, ale vrátí falešně prázdnou tabulku.
                    # Pokud je prázdná a máme ještě pokusy, zkusíme to raději znovu.
                    if divs.empty and i < max_retries - 1:
                        time.sleep(1.0 + i)
                        continue
                        
                    self._div_cache[ticker] = divs
                    return divs
            except Exception as e:
                print(f"Chyba při stahování dividend pro {ticker}: {e}")
                time.sleep(1.0 + i)
                
        # Při naprostém selhání (nebo pokud firma skutečně dividendy nikdy neplatila)
        print(f"Upozornění: Dividendy pro {ticker} se nepodařilo získat (nebo jsou nulové).")
        empty_series = pd.Series(dtype=float)
        self._div_cache[ticker] = empty_series
        return empty_series

    def _safe_get_fundamentals(self, ticker, max_retries=3):
        """Stahuje fundamentální data pro budoucí predikci (P/E, Výplatní poměr, Cílové ceny analytiků)."""
        import time
        if not hasattr(self, '_fund_cache'):
            self._fund_cache = {}
            
        if ticker in self._fund_cache:
            return self._fund_cache[ticker]
            
        for i in range(max_retries):
            try:
                time.sleep(0.5)
                info = yf.Ticker(ticker).info
                if info:
                    data = {
                        "pe_ratio": info.get('forwardPE') or info.get('trailingPE') or 15.0,
                        "payout_ratio": info.get('payoutRatio') or 0.0,
                        "target_price": info.get('targetMeanPrice'),
                        "current_price": info.get('currentPrice') or info.get('previousClose')
                    }
                    self._fund_cache[ticker] = data
                    return data
            except Exception:
                time.sleep(1.0 + i)
                
        # Při selhání nebo u ETF vrátíme bezpečné neutrální hodnoty
        data = {"pe_ratio": 15.0, "payout_ratio": 0.0, "target_price": None, "current_price": None}
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
        
        # 1. Teoretický návrh (Kalkulátor)
        calc_frame = tk.LabelFrame(main_frame, text="1. Teoretický návrh (Kalkulátor)", bg="#f0f2f5", padx=10, pady=5, font=("Arial", 12, "bold"))
        calc_frame.pack(fill=tk.X, padx=10, pady=5)
        
        top_bar = tk.Frame(calc_frame, bg="#f0f2f5")
        top_bar.pack(pady=5, anchor="w")
        
        tk.Label(top_bar, text="Investice (Kč):", font=("Arial", 12), bg="#f0f2f5").pack(side=tk.LEFT, padx=5)
        self.cash_entry = tk.Entry(top_bar, font=("Arial", 12), width=12)
        self.cash_entry.pack(side=tk.LEFT, padx=5)
        self.cash_entry.insert(0, "70000")
        
        self.btn_calc_buys = tk.Button(top_bar, text="Spočítat návrh", command=self.start_calculate_buys, 
                  bg="#2E7D32", fg="white", font=("Arial", 12, "bold"))
        self.btn_calc_buys.pack(side=tk.LEFT, padx=20)
                  
        tree_container = tk.Frame(calc_frame, bg="#f0f2f5")
        tree_container.pack(fill=tk.X, pady=5)

        tree_scroll = ttk.Scrollbar(tree_container)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        rows_needed = len(TARGETS)
        tree_height = min(rows_needed, 12)

        self.buy_tree = ttk.Treeview(tree_container, columns=("Ticker", "Cíl %", "Cena trh [USD/GBP]", "FX", "CZK (Návrh)", "Hodnota [USD/GBP]", "Ks (Návrh)"), 
                                     show="headings", height=tree_height, yscrollcommand=tree_scroll.set)
        
        for c, w in {"Ticker":90, "Cíl %":70, "Cena trh [USD/GBP]":90, "FX":70, "CZK (Návrh)":120, "Hodnota [USD/GBP]":120, "Ks (Návrh)":120}.items():
            self.buy_tree.heading(c, text=c)
            self.buy_tree.column(c, width=w, anchor="center")
        
        self.buy_tree.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tree_scroll.config(command=self.buy_tree.yview)
        self.buy_tree.bind("<<TreeviewSelect>>", self.fill_entry_from_proposal)

        # 2. Skutečná realizace (Formulář)
        edit_frame = tk.LabelFrame(main_frame, text="2. Skutečná realizace (Zadejte dle výpisu brokera)", bg="#E3F2FD", padx=10, pady=10, font=("Arial", 12, "bold"))
        edit_frame.pack(fill=tk.X, padx=10, pady=5)

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

        # Tlačítko pro automatický import z CSV od IBKR
        tk.Button(edit_frame, text="📥 Import nákupů\nIBKR (.csv)", command=self.import_ibkr_csv, bg="#FF9800", fg="black", font=("Arial", 12, "bold")).grid(row=0, column=5, rowspan=2, padx=(10, 5), sticky="nsew")

        # 3. Fronta pro finální uložení (Staging)
        final_frame = tk.LabelFrame(main_frame, text="3. Seznam realizovaných obchodů (Připraveno k zápisu)", bg="#f0f2f5", padx=10, pady=5, font=("Arial", 12, "bold"))
        final_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.staging_tree = ttk.Treeview(final_frame, columns=("Ticker", "Datum", "Množství", "Cena", "Akce"), show="headings", height=6)
        for c in ("Ticker", "Datum", "Množství", "Cena"):
            self.staging_tree.heading(c, text=c)
            self.staging_tree.column(c, anchor="center")
        self.staging_tree.heading("Akce", text="Smazat")
        self.staging_tree.column("Akce", width=80, anchor="center")
        self.staging_tree.pack(fill=tk.BOTH, expand=True)
        
        self.staging_tree.bind("<Double-1>", self.delete_staging_row)

        self.staging_tree.bind("<Double-1>", self.delete_staging_row)

        btn_bar = tk.Frame(final_frame, bg="#f0f2f5")
        btn_bar.pack(pady=10)
        tk.Button(btn_bar, text="💾 ULOŽIT VŠE DO PORTFOLIA", command=self.commit_staging_to_ledger, 
                  font=("Arial", 14, "bold"), bg="#C62828", fg="white", padx=20).pack()
                  
        # Přidání vizuálního loading elementu pro záložku Nákup (zůstává skrytý)
        self.planner_loading_state = self._create_loading_card(main_frame)

    def start_calculate_buys(self):
        """Příprava před výpočtem - zamkne tlačítko a vyčistí tabulku v hlavním vlákně."""
        self.btn_calc_buys.config(state=tk.DISABLED)
        for i in self.buy_tree.get_children(): self.buy_tree.delete(i)
        
        # Nastavení časovače pro zobrazení animace ozubených kol (pokud to trvá déle než 2 vteřiny)
        self.planner_loading_timer = self.root.after(2000, lambda: self.show_loading(self.planner_loading_state, "Stahuji data, prosím, čekejte..."))
        
        threading.Thread(target=self.calculate_buys, daemon=True).start()

    def calculate_buys(self):
        try:
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

            current_holdings_val = {}
            total_current_portfolio_val = 0.0

            for t in all_tickers:
                qty_held = sum(item['qty'] for item in self.ledger.get(t,[]))
                try:
                    price = float(prices_data[t])
                    cur = CURRENCIES.get(t, "USD")
                    fx_rate = fx.get(cur, 1.0)
                    if t.endswith(".L"): price /= 100.0
                    val_czk = qty_held * price * fx_rate
                    current_holdings_val[t] = val_czk
                    total_current_portfolio_val += val_czk
                except Exception:
                    current_holdings_val[t] = 0

            # Ignorování nulových vah, abychom předešli dělení nulou
            valid_targets =[w for w in TARGETS.values() if w > 0]
            min_target = min(valid_targets) if valid_targets else 1.0
            
            low = 0.0
            high = (total_current_portfolio_val + invest) / min_target 
            virtual_total = 0.0
            
            for _ in range(50):
                mid = (low + high) / 2.0
                required_cash = 0.0
                for t, target in TARGETS.items():
                    ideal_val = mid * target
                    curr_val = current_holdings_val.get(t, 0.0)
                    if ideal_val > curr_val:
                        required_cash += (ideal_val - curr_val)
                        
                if required_cash > invest: high = mid
                else: low = mid; virtual_total = mid

            rows_to_insert =[]
            for t, target in TARGETS.items():
                if target <= 0: continue
                
                try:
                    cur = CURRENCIES.get(t, "USD")
                    price = float(prices_data[t])
                    fx_rate = fx.get(cur, 1.0)
                    if t.endswith(".L"): price /= 100.0
                    price_in_czk = price * fx_rate

                    ideal_val = virtual_total * target
                    curr_val = current_holdings_val.get(t, 0.0)
                    czk_alloc = max(0.0, ideal_val - curr_val)
                    qty = czk_alloc / price_in_czk if price_in_czk > 0 else 0.0

                    if qty < 0.001:
                        qty = 0.0
                        czk_alloc = 0.0

                    qty_rounded = round(qty, 3)
                    orig_val = qty_rounded * price
                    
                    rows_to_insert.append((
                        t, 
                        f"{target:.1%}".replace('.', ','), 
                        f"{price:.2f}".replace('.', ','), 
                        f"{fx_rate:.1f}".replace('.', ','), 
                        f"{czk_alloc:.0f}",
                        f"{orig_val:.2f}".replace('.', ','), 
                        f"» {str(qty_rounded).replace('.', ',')} «"
                    ))
                except Exception as e: print(f"Skipping {t}: {e}")

            # Bezpečný zápis do UI z hlavního vlákna (bezpečné pro Tkinter)
            self.root.after(0, lambda: self._populate_buy_tree(rows_to_insert))

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

    def _populate_buy_tree(self, rows):
        """Pomocná metoda pro bezpečné vypsání dat do tabulky v UI vlákně."""
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
        
        # Převod čárky na tečku i u ceny, ať je to pro kopírování do brokera konzistentní
        clean_price = str(vals[2]).replace(',', '.').strip()
        self.real_price.delete(0, tk.END)
        self.real_price.insert(0, clean_price)

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
        from tkinter import filedialog
        import csv
        
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

            # --- KROK 1: Agregace nákupů z CSV ---
            csv_aggregated = {}
            for row in rows:
                if len(row) > idx_price and row[0] == 'Trades' and row[1] == 'Data':
                    if row[idx_desc] == 'Order' and row[idx_asset] == 'Stocks':
                        qty = safe_float(row[idx_qty])
                        if qty > 0: 
                            sym = map_sym(row[idx_sym])
                            date_str = row[idx_date].split(',')[0].strip()
                            try:
                                parsed_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
                            except ValueError:
                                parsed_date = date_str 
                            
                            price = safe_float(row[idx_price])
                            key = (sym, parsed_date)
                            if key not in csv_aggregated:
                                csv_aggregated[key] = {'qty': 0.0, 'total_value': 0.0}
                            
                            csv_aggregated[key]['qty'] += qty
                            csv_aggregated[key]['total_value'] += qty * price

            # --- KROK 2: Agregace existujících nákupů ---
            existing_aggregated = {}
            for t, lots in self.ledger.items():
                for lot in lots:
                    d = lot.get("date")
                    q = safe_float(lot.get("qty", 0))
                    key = (t, d)
                    existing_aggregated[key] = existing_aggregated.get(key, 0.0) + q
                    
            for item in self.staging_tree.get_children():
                vals = self.staging_tree.item(item)['values']
                t = str(vals[0])
                d = str(vals[1])
                q = safe_float(str(vals[2]).replace(',', '.'))
                key = (t, d)
                existing_aggregated[key] = existing_aggregated.get(key, 0.0) + q

            # --- KROK 3: Vložení chybějícího množství do Staging fronty ---
            added_count = 0
            for (t, d), data in csv_aggregated.items():
                csv_qty = data['qty']
                csv_val = data['total_value']
                exist_qty = existing_aggregated.get((t, d), 0.0)
                missing_qty = csv_qty - exist_qty
                
                if missing_qty > 0.0001:
                    avg_price = csv_val / csv_qty if csv_qty > 0 else 0.0
                    q_str = str(round(missing_qty, 4)).replace('.', ',')
                    p_str = str(round(avg_price, 4)).replace('.', ',')
                    self.staging_tree.insert("", "end", values=(t, d, q_str, p_str, "❌"))
                    added_count += 1

            # =================================================================
            # KROK 3B: ZPRACOVÁNÍ SKUTEČNÝCH DIVIDEND A DANÍ Z CSV
            # =================================================================
            parsed_dividends = {}
            
            # Projdeme celé CSV a najdeme sekce "Dividends" a "Withholding Tax"
            for row in rows:
                if len(row) > 5 and row[0] == 'Dividends' and row[1] == 'Data' and not row[2].startswith('Total'):
                    currency = row[2]
                    date_str = row[3]
                    desc = row[4]
                    amount = safe_float(row[5])
                    
                    # Extrakce tickeru (např. "JNJ(US4781601046) Cash Dividend..." -> "JNJ")
                    raw_ticker = desc.split('(')[0].split(' ')[0].strip()
                    sym = map_sym(raw_ticker)
                    
                    key = (sym, date_str)
                    if key not in parsed_dividends:
                        parsed_dividends[key] = {'gross': 0.0, 'tax': 0.0, 'currency': currency}
                    parsed_dividends[key]['gross'] += amount

                elif len(row) > 5 and row[0] == 'Withholding Tax' and row[1] == 'Data' and not row[2].startswith('Total'):
                    currency = row[2]
                    date_str = row[3]
                    desc = row[4]
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
            # KROK 4: HLOUBKOVÝ AUDIT (KONTROLA OTEVŘENÝCH POZIC)
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

                # B) Výpočet teoretického stavu aplikace k datu reportu
                # Zahrneme uložený Ledger + Staging tabulku - Uložené prodeje
                app_positions = {}
                
                # Započtení nákupů v Ledgeru (pouze do data vygenerování reportu)
                for t, lots in self.ledger.items():
                    for lot in lots:
                        try:
                            lot_d = datetime.strptime(lot["date"], "%Y-%m-%d").date()
                            if lot_d <= report_date:
                                app_positions[t] = app_positions.get(t, 0.0) + safe_float(lot.get("qty", 0))
                        except: pass
                
                # Započtení nákupů právě přidaných do fronty
                for item in self.staging_tree.get_children():
                    vals = self.staging_tree.item(item)['values']
                    t = str(vals[0])
                    try:
                        st_d = datetime.strptime(str(vals[1]), "%Y-%m-%d").date()
                        if st_d <= report_date:
                            app_positions[t] = app_positions.get(t, 0.0) + safe_float(str(vals[2]).replace(',', '.'))
                    except: pass

                # Odečtení historických prodejů
                for sale in self.sales_history:
                    try:
                        sale_d = datetime.strptime(sale["sell_date"], "%Y-%m-%d").date()
                        if sale_d <= report_date:
                            t = sale["ticker"]
                            app_positions[t] = app_positions.get(t, 0.0) - safe_float(sale.get("qty", 0))
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
            if added_count > 0 or added_divs > 0:
                import_msg = f"Nalezeno a naimportováno:\n"
                if added_count > 0:
                    import_msg += f"• {added_count} nových nákupů akcií (čekají dole na potvrzení)\n"
                if added_divs > 0:
                    import_msg += f"• {added_divs} záznamů o skutečných dividendách (rovnou uloženo)\n"
            else:
                import_msg = "Ve výpisu nebyly nalezeny žádné nové nákupy ani dividendy k importu."

            if not audit_performed:
                # Datum nenalezeno, zobrazíme jen výsledek importu
                messagebox.showinfo("Výsledek importu", import_msg + "\n\n(Audit pozic nebyl proveden kvůli chybějícímu datu v CSV.)")
            elif audit_errors:
                # Našly se chyby - zobrazíme Varování (Warning)
                audit_msg = ("\n\n⚠️ UPOZORNĚNÍ - AUDIT POZIC NAŠEL NESROVNALOSTI:\n"
                             f"Váš stav k {report_date.strftime('%d.%m.%Y')} neodpovídá brokerovi:\n\n" + 
                             "\n".join(audit_errors) + 
                             "\n\nMožné příčiny:\n"
                             "1. Máte v JSONu nákup navíc, který v CSV chybí.\n"
                             "2. Udělali jste v minulosti prodej, který jste v appce nezaznamenali.\n"
                             "3. Ručně zadané množství v Ledgeru obsahuje překlep.")
                messagebox.showwarning("Výsledek importu a auditu", import_msg + audit_msg)
            else:
                # Vše sedí na kus přesně - zobrazíme potvrzení (Info)
                success_msg = f"\n\n✅ AUDIT POŘÁDKU: Vaše evidence k {report_date.strftime('%d.%m.%Y')} reportu přesně odpovídá stavu u brokera."
                messagebox.showinfo("Výsledek importu", import_msg + success_msg)

        except Exception as e:
            # Záchranná síť pro nečekané chyby (např. zamčený soubor, chyba oprávnění)
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
        for item in rows:
            vals = self.staging_tree.item(item)['values']
            ticker = vals[0]
            date_str = vals[1]
            qty = float(str(vals[2]).replace(",", "."))
            price = str(vals[3]).replace(",", ".") 

            if ticker not in self.ledger: self.ledger[ticker] =[]
            
            self.ledger[ticker].append({"date": date_str, "qty": qty, "price_at_buy": price})
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


    # --------------------------------------------------------------------------
    # TAB 2: SPRÁVA POZIC A PRODEJŮ (PRODEJ & LEDGER)
    # --------------------------------------------------------------------------

    def setup_sell_tab(self):
        frame = tk.Frame(self.notebook, bg="#fff")
        self.notebook.add(frame, text="Prodej & Ledger")
        ctrl_frame = tk.LabelFrame(frame, text="Realizace prodeje", padx=10, pady=10, font=("Arial", 12, "bold"))
        ctrl_frame.pack(pady=10, padx=20, fill="x")
        
        ctrl_frame.columnconfigure(8, weight=1)
        
        self.sell_ticker = ttk.Combobox(ctrl_frame, values=list(TARGETS.keys()), width=12, font=("Arial", 12))
        self.sell_ticker.grid(row=0, column=1, padx=5)
        tk.Label(ctrl_frame, text="Ticker:", font=("Arial", 12)).grid(row=0, column=0)
        
        self.sell_qty = tk.Entry(ctrl_frame, width=10, font=("Arial", 12))
        self.sell_qty.grid(row=0, column=3, padx=5)
        tk.Label(ctrl_frame, text="Kusy:", font=("Arial", 12)).grid(row=0, column=2)
        
        self.sell_price_entry = tk.Entry(ctrl_frame, width=10, font=("Arial", 12))
        self.sell_price_entry.grid(row=0, column=5, padx=5)
        tk.Label(ctrl_frame, text="Prodejní cena [USD/GBP]:", font=("Arial", 12)).grid(row=0, column=4)
        
        tk.Button(ctrl_frame, text="Stáhnout", command=self.fetch_sell_price, font=("Arial", 12)).grid(row=0, column=6)
        tk.Button(ctrl_frame, text="PRODAT (FIFO)", command=self.execute_sale, bg="#C62828", fg="white", font=("Arial", 12, "bold")).grid(row=0, column=7, padx=20)
        tk.Button(ctrl_frame, text="↻ Aktualizovat seznam", command=self.update_lots_view, font=("Arial", 12)).grid(row=0, column=8, sticky="e", padx=10)
        
        tree_container = tk.Frame(frame)
        tree_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        tree_scroll = ttk.Scrollbar(tree_container)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.lots_tree = ttk.Treeview(tree_container, columns=("Ticker", "Datum", "Množství", "Nákupní cena [GBP/USD]", "Daň"), show="headings", yscrollcommand=tree_scroll.set)
        for c in ("Ticker", "Datum", "Množství", "Nákupní cena [GBP/USD]", "Daň"):
            self.lots_tree.heading(c, text=c)
            self.lots_tree.column(c, anchor="center")

        self.lots_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.lots_tree.yview)

        self.update_lots_view()

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

    def execute_sale(self):
        t = self.sell_ticker.get()
        try: 
            qty = float(self.sell_qty.get().replace(',', '.'))
            price = float(self.sell_price_entry.get().replace(',', '.'))
        except: return
        
        if t not in self.ledger or not self.ledger[t]: 
            messagebox.showwarning("Prodej", f"Zatím nemáte evidované žádné kusy akcie {t} k prodeji.")
            return
        
        rem = qty; today = datetime.now().strftime("%Y-%m-%d")
        
        while rem > 0 and self.ledger[t]:
            lot = self.ledger[t][0]
            sold = min(lot['qty'], rem)
            rem -= sold
            lot['qty'] -= sold
            
            if lot['qty'] < 0.0001: self.ledger[t].pop(0)
            
            self.sales_history.append({
                "ticker": t, 
                "currency": self.get_currency_for_ticker(t),
                "buy_date": lot['date'], 
                "sell_date": today,
                "qty": sold, 
                "buy_price": float(lot.get('price_at_buy', 0)), 
                "sell_price": price
            })
            
        self.save_data()
        self.update_lots_view()
        messagebox.showinfo("Info", "Prodáno.")


    # --------------------------------------------------------------------------
    # TAB 3: KALENDÁŘ DIVIDEND
    # --------------------------------------------------------------------------

    def setup_dividend_tab(self):
        frame = tk.Frame(self.notebook, bg="#E8F5E9")
        self.notebook.add(frame, text="Kalendář Dividend")
        
        ctrl_panel = tk.Frame(frame, bg="#E8F5E9")
        ctrl_panel.pack(fill=tk.X, padx=20, pady=10)
        
        self.div_mode_var = tk.StringVar(value="real")
        self.rb_div_target = tk.Radiobutton(ctrl_panel, text="Teoretické cílové portfolio (Dle nastavených vah)", variable=self.div_mode_var, value="target", bg="#E8F5E9", font=("Arial", 12))
        self.rb_div_target.pack(side=tk.LEFT, padx=10)
        self.rb_div_real = tk.Radiobutton(ctrl_panel, text="Reálné portfolio (Ledger)", variable=self.div_mode_var, value="real", bg="#E8F5E9", font=("Arial", 12))
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
            "Datum": 100, 
            "Ticker": 80, 
            "Částka": 173, 
            "Stav": 174, 
            "Nárok (CZK Hrubého)": 173
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
        
        for t, weight in TARGETS.items():
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
                tax_rate = 0.0 if CURRENCIES.get(t, "USD") == "GBP" else 0.15 
                
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
                        
                        txt = f"{gross_val:.2f} {currency}".replace('.', ',')
                        calendar_rows.append({
                            "date": pay_date, 
                            "values": (pay_date.strftime("%Y-%m-%d"), t, txt, "✅ Vyplaceno (IBKR)", f"{czk_gross:.0f} Kč".replace('.', ',')),
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
                            
                            czk_val = valid_qty * val_c * fx.get(CURRENCIES.get(t, "USD"), 23.0)
                            net_czk_val = czk_val * (1.0 - tax_rate)
                            ticker_dividend_totals[t] = ticker_dividend_totals.get(t, 0) + czk_val
                            
                            calendar_rows.append({
                                "date": d_val, "values": (d_val.strftime("%Y-%m-%d"), t, txt, status_txt, f"{czk_val:.0f} Kč".replace('.', ',')),
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
                                "date": proj_date, "values": (proj_date.strftime("%Y-%m-%d"), t, txt, f"Projekce (x{growth_factor:.2f})".replace('.', ','), f"{czk_val:.0f} Kč".replace('.', ',')),
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
            self.div_ax.set_title("Zdroje Dividend")
        else: self.div_ax.text(0.5, 0.5, "Žádná data", ha='center')

        self.div_canvas.draw()
        
        # Aktualizace popisku s výsledkem
        val_text = f"Hodnota portfolia pro výpočet: {sim_val:,.0f} Kč. ".replace(',', ' ') if mode == "target" else ""
        
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
        cb_container.pack(fill=tk.X, pady=(0, 10))
        
        # Vytvoření Canvasu a Scrollbaru pro scrollovatelný obsah
        # Výška 146 px ukáže zhruba 5 řádků akcií (15 titulů). Při více titulech se objeví posuvník.
        self.cb_canvas = tk.Canvas(cb_container, bg="#FFF8E1", highlightthickness=0, height=146)
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
        tickers = list(TARGETS.keys())
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

        # --- BLOK VOLATILITY (RIZIKA) ---
        tk.Label(control_panel, text="Celkové riziko portfolia (volatilita):", bg="#FFF8E1", font=("Arial", 12, "bold")).pack(anchor="w", pady=(15, 0))
        self.lbl_risk_text = tk.Label(control_panel, text="---", bg="#FFF8E1", font=("Arial", 12, "bold"))
        self.lbl_risk_text.pack(anchor="w", pady=(2, 5))
        self.risk_progress = ttk.Progressbar(control_panel, orient=tk.HORIZONTAL, length=500, mode='determinate', maximum=30)
        self.risk_progress.pack(pady=(0, 10))

        # Uložení reference na potvrzovací tlačítko
        self.btn_apply_weights = tk.Button(control_panel, text="✓ POUŽÍT NOVÉ VÁHY", command=self.apply_tuned_weights, bg="#2E7D32", fg="white", font=("Arial", 12, "bold"))
        self.btn_apply_weights.pack(pady=10, fill=tk.X)

        # Tabulka Base portfolia
        base_frame = tk.LabelFrame(control_panel, text="Aktuální (base)", bg="#FFF8E1", font=("Arial", 12, "bold"))
        base_frame.pack(fill=tk.X)
        
        tk.Label(base_frame, text="Hrubá div:", bg="#FFF8E1", font=("Arial", 12)).grid(row=0, column=0, sticky="w")
        self.lbl_base_div = tk.Label(base_frame, text="---", bg="#FFF8E1", fg="#2E7D32", font=("Arial", 12, "bold"))
        self.lbl_base_div.grid(row=0, column=1, sticky="w", padx=(0,15))
        
        tk.Label(base_frame, text="Bezpečná div:", bg="#FFF8E1", font=("Arial", 12)).grid(row=0, column=2, sticky="w")
        self.lbl_base_fdiv = tk.Label(base_frame, text="---", bg="#FFF8E1", fg="#0288D1", font=("Arial", 12, "bold"))
        self.lbl_base_fdiv.grid(row=0, column=3, sticky="w")
        
        tk.Label(base_frame, text="Pokles:", bg="#FFF8E1", font=("Arial", 12)).grid(row=1, column=0, sticky="w")
        self.lbl_base_dd = tk.Label(base_frame, text="---", bg="#FFF8E1", fg="#C62828", font=("Arial", 12, "bold"))
        self.lbl_base_dd.grid(row=1, column=1, sticky="w", padx=(0,15))
        
        tk.Label(base_frame, text="Krizový propad:", bg="#FFF8E1", font=("Arial", 12)).grid(row=1, column=2, sticky="w")
        self.lbl_base_fdd = tk.Label(base_frame, text="---", bg="#FFF8E1", fg="#C62828", font=("Arial", 12, "bold"))
        self.lbl_base_fdd.grid(row=1, column=3, sticky="w")

        tk.Label(base_frame, text="Růst:", bg="#FFF8E1", font=("Arial", 12)).grid(row=2, column=0, sticky="w")
        self.lbl_base_growth = tk.Label(base_frame, text="---", bg="#FFF8E1", fg="#2E7D32", font=("Arial", 12, "bold"))
        self.lbl_base_growth.grid(row=2, column=1, sticky="w", padx=(0,15))
        
        tk.Label(base_frame, text="Očekávaný růst:", bg="#FFF8E1", font=("Arial", 12)).grid(row=2, column=2, sticky="w")
        self.lbl_base_fgrowth = tk.Label(base_frame, text="---", bg="#FFF8E1", fg="#0288D1", font=("Arial", 12, "bold"))
        self.lbl_base_fgrowth.grid(row=2, column=3, sticky="w")

        tk.Label(base_frame, text="Volatilita:", bg="#FFF8E1", font=("Arial", 12)).grid(row=3, column=0, sticky="w")
        self.lbl_base_vol = tk.Label(base_frame, text="---", bg="#FFF8E1", fg="#F57F17", font=("Arial", 12, "bold"))
        self.lbl_base_vol.grid(row=3, column=1, sticky="w")

        viz_panel = tk.Frame(self.tuner_frame, bg="white")
        viz_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # --- Přepínač zobrazení grafů ---
        toggle_frame = tk.Frame(viz_panel, bg="white")
        toggle_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.chart_view_var = tk.StringVar(value="new")
        
        rb_new = tk.Radiobutton(toggle_frame, text="Nové rozložení vah (tuned)", variable=self.chart_view_var, value="new", bg="white", font=("Arial", 12, "bold"), fg="#1976D2", command=self._redraw_tuner_charts)
        rb_new.pack(side=tk.RIGHT, padx=10)
        
        rb_base = tk.Radiobutton(toggle_frame, text="Aktuální portfolio (base)", variable=self.chart_view_var, value="base", bg="white", font=("Arial", 12, "bold"), fg="grey", command=self._redraw_tuner_charts)
        rb_base.pack(side=tk.RIGHT, padx=10)
        
        tk.Label(toggle_frame, text="Přepínání zobrazení:", bg="white", font=("Arial", 12)).pack(side=tk.RIGHT, padx=10)

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
        if len(metrics) > 6:
            self.lbl_base_vol.config(text=f"{metrics[6]:.1f} %".replace('.', ','))
        
    def on_checkbox_toggle(self):
        if getattr(self, 'tuner_loading_state', {}).get("is_loading"): return
        if not getattr(self, 'tuner_data_loaded', False): return 
        for s in self.sliders.values(): s.config(state="disabled")
        self.run_tuner_with_loading(lambda: self.initialize_tuner_data(force_download=False), "Přepočítávám simulace...")

    def initialize_tuner_data(self, force_download=True, n_sims=None, auto_improve=False):
        import time 
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
                        confirmed_months = [d.date().month for d in divs_current.index]
                        for d_date, amount in divs_last.items():
                            try: proj_date = d_date.date().replace(year=current_year)
                            except: proj_date = d_date.date() + timedelta(days=365)
                            
                            if proj_date.month not in confirmed_months and today_date <= proj_date <= end_of_year:
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
                
                for t in self.ordered_tickers:
                    fund = self._safe_get_fundamentals(t)
                    
                    # 1. Bezpečná dividenda (Penalizace při neudržitelném Payout Ratiu)
                    raw_yield = div_yields.get(t, 0.0)
                    payout = fund['payout_ratio']
                    
                    meta = getattr(self, 'stock_db_from_json', DEFAULT_STOCK_DB).get(t, {})
                    sector = meta.get("sector", "Unknown")
                    
                    # REITs (Real Estate) a BDC (Financial) mají ze zákona uměle vysoký výplatní poměr.
                    # Pro Consumer Defensive (PEP, ULVR) dáme toleranci do 95 %, protože mají extrémně stabilní cash-flow.
                    if sector in ["Real Estate", "Financial"]:
                        limit = 1.5
                    elif sector == "Consumer Defensive":
                        limit = 0.95
                    else:
                        limit = 0.9
                    
                    # Účetní anomálie z odpisů nemovitostí a akvizic (Payout > 200 %, např. O, ABBV).
                    # V takovém případě věříme reálnému cash-flow a dividendu nepenalizujeme.
                    if payout > 2.0:
                        safe_yield = raw_yield
                        payout = -1 # Značka pro Tooltip, že data jsou účetně zkreslená
                    else:
                        safe_yield = raw_yield if payout <= limit else raw_yield * DIV_YIELD_DROP
                        
                    safe_divs.append(safe_yield)
                    
                    self.tuner_fundamentals[t] = {
                        "payout_ratio": payout,
                        "raw_yield": raw_yield,
                        "safe_yield": safe_yield
                    }
                    
                    # 2. Cílový růst (Analytici vs. Historie)
                    tp = fund['target_price']
                    cp = fund['current_price']
                    if tp and cp and cp > 0:
                        ups = (tp / cp) - 1.0
                    else:
                        # Fallback u ETF: Vezmeme průměrný historický roční růst, ale zarovnáme max na 10 %
                        hist_growth_ratio = 1.0 / self.tuner_stock_growths[self.ordered_tickers.index(t)]
                        ann_ret = (hist_growth_ratio ** (1/5.0)) - 1.0 if hist_growth_ratio > 0 else 0.0
                        ups = min(ann_ret, 0.10)
                    upsides.append(ups)
                    
                self.tuner_safe_divs = np.array(safe_divs)
                self.tuner_upsides = np.array(upsides)
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
                self.root.after(0, lambda: self._update_base_labels(b_m))
            
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

        # --- AKTUALIZACE VOLATILITY ---
        if hasattr(self, 'tuner_cov_matrix'):
            cov_mat = self.tuner_cov_matrix.values
            port_var = np.dot(weights.T, np.dot(cov_mat, weights))
            port_vol = np.sqrt(port_var) * 100 
            
            if port_vol < 12.0: risk_word, r_color = "Nízké (konzervativní)", "#2E7D32"
            elif port_vol < 16.0: risk_word, r_color = "Střední (vyvážené)", "#F57F17"
            elif port_vol < 22.0: risk_word, r_color = "Vyšší (dynamické)", "#E65100"
            else: risk_word, r_color = "Vysoké (agresivní)", "#C62828"
                
            vol_str = f"{port_vol:.1f}".replace('.', ',')
            self.lbl_risk_text.config(text=f"{risk_word} ({vol_str} % p.a.)", fg=r_color)
            self.risk_progress['value'] = min(port_vol, 30.0)
                
        # Samotné překreslení grafů delegujeme na metodu, která přečte stav přepínačů
        self._redraw_tuner_charts()
        # 2. VYNUCENÍ ZPRACOVÁNÍ: Pošleme Tkinteru instrukci, aby okamžitě zpracoval 
        # všechny události změny sliderů (Scale command). Ty díky flagu 'updating_sliders' 
        # v metodě 'on_slider_change' okamžitě skončí (return) a nenaplánují novou úlohu.
        self.root.update_idletasks()
        self.updating_sliders = False

    def _redraw_tuner_charts(self):
        if getattr(self, 'sim_weights', None) is None: return
        
        view_mode = getattr(self, 'chart_view_var', tk.StringVar(value="new")).get()
        new_weights = self.sim_weights[self.current_sim_idx]
        base_w = np.array([self.tuner_base_weights.get(t, 0) for t in self.ordered_tickers])
        
        if view_mode == "base":
            plot_weights = base_w
            current_metrics = getattr(self, 'base_metrics_data', [0]*6)
            pie_title_suffix = "(base)"
            main_color = "grey"
        else:
            plot_weights = new_weights
            current_metrics = self.sim_metrics[self.current_sim_idx]
            pie_title_suffix = "(tuned)"
            main_color = "#1976D2"

        self.ax_pie.clear(); self.ax_div_pie.clear(); self.ax_curve.clear(); self.ax_bars.clear()
        self._current_pie_weights = plot_weights
        
        # --- KOLÁČE (Oprava: Odstraněno dvojité násobení stem u formátu %) ---
        labels_weights =[f"{t}\n{w:.1%}".replace('.', ',') if w >= 0.05 else "" for t, w in zip(self.ordered_tickers, plot_weights)]
        self.wedges_weights, _ = self.ax_pie.pie(plot_weights, labels=labels_weights, startangle=140, colors=plt.cm.tab20.colors)
        self.ax_pie.set_title(f"Rozložení vah {pie_title_suffix}")
        
        ticker_div_czk = plot_weights * self.tuner_stock_divs * 100000
        div_tickers, div_sizes = [], []
        sorted_indices = np.argsort(ticker_div_czk)[::-1]
        for i in sorted_indices:
            if ticker_div_czk[i] > 0:
                div_tickers.append(self.ordered_tickers[i]); div_sizes.append(ticker_div_czk[i])
        
        if div_sizes:
            total_div = sum(div_sizes)
            f_labels =[l if (s/total_div) > 0.03 else "" for l, s in zip(div_tickers, div_sizes)]
            self.wedges_divs, _, _ = self.ax_div_pie.pie(div_sizes, labels=f_labels, autopct=lambda p: f'{p:.1f}%'.replace('.', ',') if p > 3 else '', startangle=140, colors=plt.cm.tab20b.colors)
            self.div_data_tickers = div_tickers; self.div_data_sizes = div_sizes
            self.ax_div_pie.set_title(f"Zdroje dividend {pie_title_suffix}")
            
            # --- VAROVÁNÍ NA KONCENTRACI ---
            if len(div_sizes) > 0:
                max_share = div_sizes[0] / total_div
                if max_share > MAX_DIV_SHARE:
                    self.ax_div_pie.text(0, -1.35, f"⚠️ Varování: Akcie {div_tickers[0]} generuje {max_share*100:.1f} % dividend".replace('.', ','), 
                                         ha='center', color='#E65100', fontsize=11, fontweight='bold')
        
        # --- HLAVNÍ GRAF: HISTORIE + PREDIKCE ---
        
        # Výpočet reálného denního výkonu udržovaného portfolia (Constant Weights)
        daily_pct_changes = self.tuner_hist_prices.pct_change().fillna(0)
        daily_portfolio_returns = daily_pct_changes.dot(plot_weights)
        cumulative_growth = (1 + daily_portfolio_returns).cumprod()
        curve_to_plot = cumulative_growth * 100000
        
        # 1. Kreslení S&P 500 (včetně jeho budoucího driftu)
        if hasattr(self, 'tuner_spy_prices') and not self.tuner_spy_prices.empty:
            spy_aligned = self.tuner_spy_prices.reindex(daily_pct_changes.index).ffill().bfill()
            curve_spy = (spy_aligned / spy_aligned.iloc[0]) * 100000
            self.ax_curve.plot(curve_spy.index, curve_spy.values, color='#D32F2F', linestyle=':', linewidth=1.5, label='S&P 500 (SPY)', alpha=0.7)
            
            # Predikce pro SPY (pokračování trendu)
            last_date = curve_spy.index[-1]
            last_val_spy = curve_spy.values[-1]
            future_dates = pd.bdate_range(start=last_date, periods=252)
            
            spy_ann_return = (curve_spy.values[-1] / curve_spy.values[0]) ** (1/5.0) - 1.0
            spy_daily_drift = spy_ann_return / 252.0
            spy_path = last_val_spy * np.exp(spy_daily_drift * np.arange(1, 253))
            self.ax_curve.plot(future_dates, spy_path, color='#D32F2F', linestyle=':', linewidth=1.5, alpha=0.5)

        # 2. Kreslení Baseline (pokud jsme v Tuned módu, dáme ji na pozadí)
        if view_mode == "new":
            base_daily_rets = daily_pct_changes.dot(base_w)
            curve_base = (1 + base_daily_rets).cumprod() * 100000
            self.ax_curve.plot(curve_base.index, curve_base.values, color='grey', linestyle='--', label='Aktuální (base)', alpha=0.6)

        # 3. Kreslení Aktivní křivky (Base nebo Tuned)
        self.ax_curve.plot(curve_to_plot.index, curve_to_plot.values, color=main_color, linewidth=2, label=f'Portfolio {pie_title_suffix} (hrubé)')
        
        # --- VÝPOČET A KRESLENÍ ZDANĚNÉ KŘIVKY (15% daň z dividend) ---
        current_weights_div_yield = np.dot(plot_weights, self.tuner_stock_divs)
        tax_drag_annual = current_weights_div_yield * 0.15
        daily_tax_drag = tax_drag_annual / 252.0
        
        daily_net_returns = daily_portfolio_returns - daily_tax_drag
        curve_net = (1 + daily_net_returns).cumprod() * 100000
        
        self.ax_curve.plot(curve_net.index, curve_net.values, color='#81D4FA', linestyle='-', linewidth=1.5, label=f'Portfolio {pie_title_suffix} (zdaněné)')
        
        # 4. Kreslení Trychtýře pro aktivní křivku
        last_date = curve_to_plot.index[-1]
        last_val = curve_to_plot.values[-1]
        future_dates = pd.bdate_range(start=last_date, periods=252)
        
        daily_drift = (current_metrics[5] / 100.0) / 252.0
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
        
        self.ax_curve.set_title(f"Simulace 100k Kč {pie_title_suffix}")
        self.ax_curve.grid(True, linestyle='--', alpha=0.5)
        self.ax_curve.legend(loc='upper left', fontsize=8)

        # --- BAR CHART ---
        years = sorted(list(set(self.tuner_hist_prices.index.year)))
        bars_base, bars_new, lbls = [], [],[]
        
        # Musíme si vygenerovat Base křivku i pro Tuned režim, aby se dalo kreslit srovnání
        base_daily_rets_all = daily_pct_changes.dot(base_w)
        curve_base_all = (1 + base_daily_rets_all).cumprod() * 100000
        
        # New_weights křivka vychází z nového portfolia
        new_daily_rets_all = daily_pct_changes.dot(new_weights)
        curve_new_all = (1 + new_daily_rets_all).cumprod() * 100000
        
        for y in years:
            sb = curve_base_all[curve_base_all.index.year == y]
            sn = curve_new_all[curve_new_all.index.year == y]
            if len(sb) > 0:
                bars_base.append(sb.iloc[-1] - sb.iloc[0])
                bars_new.append(sn.iloc[-1] - sn.iloc[0])
                lbls.append(str(y))

        x = np.arange(len(lbls)); width = 0.35
        if view_mode == "base":
            self.ax_bars.bar(x, bars_base, width*2, label='Base (total return)', color='grey')
        else:
            self.ax_bars.bar(x - width/2, bars_base, width, label='Base', color='lightgrey')
            self.ax_bars.bar(x + width/2, bars_new, width, label='Tuned', color='#4CAF50')
        
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
        for t, w in zip(self.ordered_tickers, new_w):
            TARGETS[t] = float(w)
            self.tuner_base_weights[t] = float(w) 
            
        self.save_data() 
        
        # 'metrics' už je pole o 6 prvcích z vybrané simulace, takže ho jen předáme dál
        metrics = self.sim_metrics[self.current_sim_idx]
        self._update_base_labels(metrics)
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
                                          command=lambda: self.run_dash_with_loading(self.refresh_stats, "Přepočítávám historii..."), 
                                          font=("Arial", 12, "bold"), bg="#37474F", fg="white")
        self.btn_refresh_stats.pack(side=tk.LEFT)
        
        self.btn_export_tax = tk.Button(ctrl_panel, text="📄 EXPORT PDF (DANĚ)", 
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
            
    def refresh_stats(self):
        if os.path.exists(PORTFOLIO_FILE):
            self.root.after(0, lambda: self.status_lbl.config(text="Přepočítávám historii...", fg="blue"))
            
            all_tickers_set = set(TARGETS.keys())
            all_tickers_set.update(self.ledger.keys())
            for s in self.sales_history: all_tickers_set.add(s['ticker'])
            all_tickers = list(all_tickers_set)
            
            try:
                fx = self.get_fx_rates()
                downloaded = self._safe_yf_download(all_tickers, period="5y", auto_adjust=True)
                
                if downloaded.empty or 'Close' not in downloaded:
                    self.root.after(0, lambda: messagebox.showerror("Chyba stahování", "Data pro statistiky jsou nedostupná. Zkontrolujte internet."))
                    self.root.after(0, lambda: self.status_lbl.config(text="Chyba stahování", fg="red"))
                    return
                
                # Očištění o nuly těsně před zaplněním děr (ffill)
                hist_prices = downloaded['Close'].replace(0.0, np.nan).ffill().bfill()
                if isinstance(hist_prices, pd.Series): hist_prices = hist_prices.to_frame(name=all_tickers[0])
                
                # víkendy a svátky
                # Převedeme všechna data na objekty Datetime
                ledger_dt = {t: [{'date': pd.Timestamp(l['date']), 'qty': l['qty'], 'price_at_buy': l['price_at_buy']} for l in lots] for t, lots in self.ledger.items()}
                sales_dt = [{'buy_date': pd.Timestamp(s['buy_date']), 'sell_date': pd.Timestamp(s['sell_date']), 'qty': s['qty'], 'ticker': s['ticker'], 'sell_price': s['sell_price'], 'buy_price': s['buy_price'], 'currency': s.get('currency', 'USD')} for s in self.sales_history]

                # Roztáhneme časovou osu Yahoo dat na VŠECHNY kalendářní dny (včetně víkendů)
                # Chybějící ceny (sobota/neděle) se doplní z pátku pomocí 'ffill'
                ledger_dates = [l['date'] for t, lots in ledger_dt.items() for l in lots]
                max_d = max([hist_prices.index.max(), pd.Timestamp(datetime.now().date())] + ledger_dates)
                full_idx = pd.date_range(start=hist_prices.index.min(), end=max_d)
                hist_prices = hist_prices.reindex(full_idx).ffill()
                
                all_buy_dates = [l['date'] for t in self.ledger for l in self.ledger.get(t,[])]
                has_buys = len(all_buy_dates) > 0
                
                if has_buys:
                    first_buy_str = min(all_buy_dates)
                    first_buy_dt = pd.Timestamp(first_buy_str)
                    first_buy_year = first_buy_dt.year
                else:
                    first_buy_dt = None
                    first_buy_year = 9999

                # 1. Zjistíme aktuální hodnotu každé pozice v CZK pro výpočet reálných vah
                current_values_czk = {}
                total_portfolio_now = 0.0
                last_prices = hist_prices.iloc[-1]
                
                for t in all_tickers:
                    qty_now = sum(l['qty'] for l in self.ledger.get(t, []))
                    if qty_now > 0 and t in hist_prices.columns:
                        p = last_prices[t] / (100.0 if t.endswith(".L") else 1.0)
                        val = p * qty_now * fx.get(self.get_currency_for_ticker(t), 23.0)
                        current_values_czk[t] = val
                        total_portfolio_now += val
                
                # 2. Vypočítáme aktuální procentuální váhy (actual weights)
                actual_weights = {}
                if total_portfolio_now > 0:
                    actual_weights = {t: val / total_portfolio_now for t, val in current_values_czk.items()}
                else:
                    # Pokud je portfolio prázdné, použijeme TARGETS jako fallback
                    actual_weights = {t: w for t, w in TARGETS.items()}
                    total_portfolio_now = 100000.0 # Fallback pro prázdné portfolio

                # 3. Vygenerujeme normalizovanou Constant Mix křivku (denní rebalancing)
                daily_pct_changes = hist_prices.pct_change().fillna(0)
                
                # Srovnáme váhy do vektoru odpovídajícímu sloupcům v hist_prices
                w_vector = np.array([actual_weights.get(col, 0.0) for col in hist_prices.columns])
                
                # Výpočet denních výnosů portfolia (pro šedou simulační čáru)
                portfolio_daily_returns = daily_pct_changes.dot(w_vector)
                norm_curve = (1 + portfolio_daily_returns).cumprod()
                
                # Škálování simulace (šedá čára) tak, aby končila na dnešní hodnotě majetku
                scaling_factor = total_portfolio_now / norm_curve.iloc[-1]
                sim_curve = norm_curve * scaling_factor

                # --- REKONSTRUKCE REÁLNÉHO VÝVOJE (Modrá čára) ---
                # Vytvoříme matici množství (počet kusů v čase pro každý ticker)
                qty_matrix = pd.DataFrame(0.0, index=hist_prices.index, columns=all_tickers)
                for t, lots in ledger_dt.items():
                    for lot in lots:
                        # Od data nákupu dále přičteme množství k danému tickeru
                        qty_matrix.loc[lot['date']:, t] += lot['qty']
                
                # Výpočet reálné hodnoty portfolia v CZK den po dni
                real_portfolio_curve = pd.Series(0.0, index=hist_prices.index)
                for t in all_tickers:
                    if t in hist_prices.columns:
                        # Převod britských pencí na libry u titulů .L
                        p_factor = 0.01 if t.endswith(".L") else 1.0
                        # Použijeme kurz dané měny
                        fx_val = fx.get(self.get_currency_for_ticker(t), 23.0)
                        real_portfolio_curve += qty_matrix[t] * hist_prices[t] * p_factor * fx_val

                # --- VYKRESLENÍ ---
                self.ax1.clear()
                
                if has_buys:
                    # Šedá čára (Simulace) - co by se stalo, kdybyste dnešní sumu zainvestovali před 5 lety
                    self.ax1.plot(sim_curve[:first_buy_dt].index, sim_curve[:first_buy_dt].values, 
                                  color='grey', linestyle='--', alpha=0.6, label="Simulace (hypotetická historie)")
                    
                    # Modrá čára (Realita) - skutečná hodnota portfolia od prvního nákupu
                    # Ořezáváme data před prvním nákupem, aby graf nezačínal na nule v roce 2021
                    real_data_to_plot = real_portfolio_curve[real_portfolio_curve.index >= first_buy_dt]
                    self.ax1.plot(real_data_to_plot.index, real_data_to_plot.values, 
                                  color='#1976D2', linewidth=2, label="Reálné portfolio (vč. nákupů)")
                    
                    self.ax1.axvline(x=first_buy_dt, color='red', linestyle='-', alpha=0.4)
                else:
                    self.ax1.plot(sim_curve.index, sim_curve.values, color='grey', linestyle='--', alpha=0.6, label="Simulace")

                    
                self.ax1.set_title("Vývoj hodnoty portfolia při reinvestici dividend (simulace a realita)")
                self.ax1.grid(True, linestyle='--', alpha=0.5)
                self.ax1.legend()
                self.ax1.set_ylabel("Hodnota [Kč]")

                # inteligentní popisky osy Y
                from matplotlib.ticker import FuncFormatter
                def custom_formatter(x, pos):
                    # Zabrání vědecké notaci (1e6) a vytvoří hezké české formátování s čárkami
                    if abs(x) >= 1000000: return f'{x*1e-6:.1f} mil.'.replace('.', ',')
                    elif abs(x) >= 1000: return f'{x*1e-3:.0f} tis.'.replace('.', ',')
                    return f'{x:.0f}'
                
                # Aplikováno na osu ihned po vyčištění grafu
                self.ax1.yaxis.set_major_formatter(FuncFormatter(custom_formatter))

                years = sorted(list(set(hist_prices.index.year)))
                growth_vals, div_vals, totals, colors, labels = [], [], [], [],[]
                div_history = {t:[] for t in all_tickers}
                
                # Přednačtení dividend do paměti PŘED cyklem (ušetří desítky API dotazů a zrychlí appku)
                all_divs = {t: self._safe_get_dividends(t) for t in all_tickers}
                
                for y in years:
                    y_start, y_end = f"{y}-01-01", f"{y}-12-31"
                    sub_curve = sim_curve.loc[y_start:y_end]
                    if sub_curve.empty: continue

                    val_start, val_end = sub_curve.iloc[0], sub_curve.iloc[-1]
                    
                    buys_cost = sum(float(l['price_at_buy']) * l['qty'] * fx.get(CURRENCIES.get(t, "USD"), 23.0) 
                                    for t, lots in self.ledger.items() for l in lots if l['date'].startswith(str(y)))
                    sales_income = sum(s['sell_price'] * s['qty'] * fx.get(s.get('currency', 'USD'), 23.0) 
                                       for s in self.sales_history if s['sell_date'].startswith(str(y)))
                    
                    year_divs = 0
                    for t in all_tickers:
                        # --- Ochrana akumulačních ETF ---
                        meta = getattr(self, 'stock_db_from_json', DEFAULT_STOCK_DB).get(t, {})
                        if meta.get("sector") == "ETF" and meta.get("etf_type") == "Acc":
                            div_history[t].append(0) # Do grafu vrstev vložíme nulu
                            continue

                        t_div = 0 
                        try:
                            # Využití bleskové Cache paměti místo dotazování sítě
                            d_data = all_divs[t].loc[y_start:y_end]
                            for d_dt, amt in d_data.items():
                                d_s = pd.Timestamp(d_dt.date())
                                if not has_buys or y < first_buy_year:
                                    q = sum(l['qty'] for l in ledger_dt.get(t,[]))
                                else:
                                    q = sum(l['qty'] for l in ledger_dt.get(t, []) if l['date'] < d_s)
                                    q += sum(s['qty'] for s in sales_dt if s['ticker'] == t 
                                             and s['buy_date'] < d_s and s['sell_date'] >= d_s)
                                currency = self.get_currency_for_ticker(t)
                                t_div += (amt / (100.0 if t.endswith(".L") else 1.0) * q * fx.get(currency, 23.0))
                        except: pass
                        year_divs += t_div
                        div_history[t].append(t_div) 

                    # total_pnl je přesný Total Return vč. reinvestic (protože používáme upravené ceny).
                    # growth_only je vizuální "zbytek", aby se po nasčítání se žlutým sloupcem 
                    # trefila přesná výška Total Returnu.
                    if not has_buys or y < first_buy_year:
                        total_pnl = val_end - val_start
                        growth_only = total_pnl - year_divs
                        colors.append('grey')
                        base = val_start if val_start > 0 else (val_end / 1.1)
                        
                    elif y == first_buy_year:
                        total_pnl = (val_end + sales_income) - buys_cost
                        growth_only = total_pnl - year_divs
                        colors.append('#4CAF50' if total_pnl >= 0 else '#E53935')
                        base = buys_cost
                        
                    else:
                        total_pnl = (val_end + sales_income) - (val_start + buys_cost)
                        growth_only = total_pnl - year_divs
                        colors.append('#4CAF50' if total_pnl >= 0 else '#E53935')
                        base = val_start

                    growth_vals.append(growth_only)
                    div_vals.append(year_divs)
                    totals.append(total_pnl)
                    
                    pct = (total_pnl / base * 100) if base > 0 else 0
                    lbl_text = f"{pct:+.1f}%\n{total_pnl/1000:+.1f}k".replace('.', ',')
                    labels.append(lbl_text)

                self.ax2.clear()
                self.ax2.yaxis.set_major_formatter(FuncFormatter(custom_formatter))
                
                x = np.arange(len(growth_vals))
                
                for i in range(len(x)):
                    g = growth_vals[i]  # Růst / Ztráta ceny
                    d = div_vals[i]     # Hodnota dividend
                    t = totals[i]       # Total Return (g + d)
                    c_base = colors[i]  # Základní barva z předchozí logiky (zelená/šedá/červená)
                    
                    if g >= 0:
                        # STANDARDNÍ RŮST (Vše je v plusu)
                        self.ax2.bar(x[i], g, color=c_base, label='Růst ceny' if i==0 else "")
                        if d > 0:
                            self.ax2.bar(x[i], d, bottom=g, color='#FFC107', label='Dividendy' if i==0 else "")
                            
                    else:
                        # POKLES CENY AKCIÍ
                        if t < 0:
                            # 1) SCÉNÁŘ: Pokles je větší než dividenda (Total je záporný)
                            # Světlejší část ukazuje celkovou výslednou ztrátu
                            # Tmavší část ukazuje ztrátu, kterou smazala dividenda
                            
                            # Odvození tmavší/světlejší barvy podle toho, zda je sloupec Reálný (červený) nebo Simulace (šedý)
                            if c_base == '#E53935': # Červená
                                light_c = '#EF9A9A' # Světle červená
                                dark_c = '#C62828'  # Tmavě červená
                            else: # Šedá
                                light_c = 'lightgrey'
                                dark_c = 'grey'
                                
                            # Vykreslení:
                            # Horní díl (k Total Returnu)
                            self.ax2.bar(x[i], t, color=light_c, label='Výsledná ztráta' if i==0 else "")
                            # Spodní díl (vykrytý dividendou)
                            if d > 0:
                                self.ax2.bar(x[i], -d, bottom=t, color=dark_c, label='Ztráta pokrytá div.' if i==0 else "")
                                
                        else:
                            # 2) SCÉNÁŘ: Pokles ceny, ale Dividenda zachránila rok do Plusu
                            # Šedý/Červený sloupec zůstává ukotven na nule a jde do mínusu
                            self.ax2.bar(x[i], g, color=c_base, label='Ztráta ceny' if i==0 else "")
                            
                            # Žlutá dividenda se rozdělí na Čistý zisk (tmavá) a Kompenzaci (světlá)
                            if d > 0:
                                # Tmavě žlutá (Oranžová) = Skutečný čistý zisk
                                self.ax2.bar(x[i], t, color='#FFA000', label='Čistý zisk z div.' if i==0 else "")
                                # Světle žlutá = Část dividendy, která padla na zalepení díry
                                self.ax2.bar(x[i], abs(g), bottom=t, color='#FFD54F', label='Div. kryjící ztrátu' if i==0 else "")

                self.ax2.grid(True, linestyle='--', alpha=0.5)
                self.ax2.set_ylabel("Zisk [Kč]")
                
                # Zjednodušení legendy, aby v ní nebylo milion položek z cyklu výše
                legend_elements =[
                    Patch(facecolor='grey', label='Simulace (růst/ztráta)'), 
                    Patch(facecolor='#4CAF50', label='Reálný zisk'),
                    Patch(facecolor='#E53935', label='Reálná ztráta'),
                    Patch(facecolor='#FFC107', label='Dividendy'),
                    Patch(facecolor='#FFA000', label='Čistý zisk (když div. porazí ztrátu)')
                ]
                self.ax2.legend(handles=legend_elements, loc="lower left", fontsize=9)
                
                v_min, v_max = min(min(growth_vals), min(totals), 0), max(max(totals), max(growth_vals), 0)
                y_range = max(v_max - v_min, 2000)
                self.ax2.set_ylim(v_min - (y_range * 0.4), v_max + (y_range * 0.4))
                self.ax2.set_xticks(x); self.ax2.set_xticklabels([str(y) for y in years])
                
                for i in x:
                    y_val = totals[i]
                    va = 'bottom' if y_val >= 0 else 'top'
                    offset = (y_range * 0.05) if y_val >= 0 else -(y_range * 0.05)
                    self.ax2.text(i, y_val + offset, labels[i], ha='center', va=va, fontsize=9, fontweight='bold')

                self.ax3.clear()
                # Pro jistotu přidáme formát i do třetího (vrstvového) grafu
                self.ax3.yaxis.set_major_formatter(FuncFormatter(custom_formatter))
                
                div_sums = {t: sum(div_history[t]) for t in all_tickers}
                sorted_tickers = sorted(all_tickers, key=lambda x: div_sums[x], reverse=True)
                active_tickers =[t for t in sorted_tickers if div_sums[t] > 0]
                
                if active_tickers:
                    plot_tickers = active_tickers[::-1]
                    stack_data = [div_history[t] for t in plot_tickers]
                    plot_colors = plt.cm.tab20.colors[:len(active_tickers)][::-1]
                    
                    self.ax3.stackplot(years, stack_data, labels=plot_tickers, colors=plot_colors, alpha=0.85)
                    self.ax3.set_title("Zdroje dividend v čase (Vrstvový graf)")
                    self.ax3.set_ylabel("Dividendy [Kč]")
                    self.ax3.set_xticks(years)
                    self.ax3.set_xticklabels([str(y) for y in years])
                    self.ax3.grid(True, linestyle='--', alpha=0.5)
                    
                    handles, labels = self.ax3.get_legend_handles_labels()
                    self.ax3.legend(handles[::-1], labels[::-1], loc='upper left', ncol=math.ceil(len(active_tickers)/4), fontsize=8)
                else:
                    self.ax3.text(0.5, 0.5, "Zatím žádné dividendy", ha='center', va='center')

                self.canvas.draw()
                self.root.after(0, lambda: self.status_lbl.config(text=f"Aktualizováno: {datetime.now().strftime('%H:%M:%S')}", fg="green"))
            except Exception as e: 
                print(f"Error: {e}")
                self.root.after(0, lambda: self.status_lbl.config(text="Chyba výpočtu", fg="red"))

    # --------------------------------------------------------------------------
    # DAŇOVÝ MOTOR (ONE-CLICK EXPORT A PDF)
    # --------------------------------------------------------------------------

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
                divs = yf.Ticker(t).dividends
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
                            withheld = gross_div_czk * 0.15 
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
            div_tax_cz = round(div_gross * 0.15)
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
            
            # Daň uznaná k zápočtu (nemůže přesáhnout teoretickou českou 15% daň)
            total_recognized = min(total_foreign_tax, total_div * 0.15)
            
            # Výsledná daň k zaplacení v ČR
            tax_to_pay = max(0, (total_div * 0.15) - total_recognized)

            instrukce_p4 = f"""<b>NÁVOD PRO RUČNÍ VYPLNĚNÍ (Příloha č. 4):</b><br/>
            V papírovém formuláři (Příloha č. 4) nehledejte kolonky pro kódy států. Všechny dividendy se sečtou a zapíší jako jeden celek.<br/><br/>
            • Řádek 401a (Příjmy podle § 8 ze zahraničí): <b>{total_div:,.0f} Kč</b><br/>
            • Řádek 406 a 409 (Součty základů daně): <b>{total_div:,.0f} Kč</b><br/>
            • Řádek 410 (15% teoretická daň): <b>{total_div * 0.15:,.0f} Kč</b><br/>
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

        # Naplnění pravého seznamu (Moje)
        my_items = []
        for t in current_tickers:
            meta = self.stock_db.get(t, {"name": "Unknown", "tags":[], "growth": 0, "yield": 0})
            my_items.append((t, meta))
        my_items.sort(key=sort_key, reverse=True)
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
        avail_items.sort(key=sort_key, reverse=True)
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
        
        # Automatické vyvážení vah, pokud došlo ke změně počtu titulů
        cnt = len(TARGETS)
        if cnt > 0:
            current_sum = sum(TARGETS.values())
            has_zero = any(w <= 0 for w in TARGETS.values())
            if abs(current_sum - 1.0) > 0.01 or has_zero:
                new_w = 1.0 / cnt
                for t in TARGETS: TARGETS[t] = new_w
        
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
                    
                    # Bereme váhy z aktuálně překresleného grafu (zajišťuje kompatibilitu s přepínačem Base/Tuned)
                    weight = getattr(self, '_current_pie_weights', self.sim_weights[self.current_sim_idx])[i]
                    
                    # Čárky aplikujeme pouze na samotná čísla, nikoliv na název tickeru
                    weight_str = f"{weight:.1%}".replace('.', ',')
                    target_text = f"{ticker}\nVáha: {weight_str}"
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
                        
                        # --- SYNCHRONIZACE LIMITŮ S VÝPOČETNÍM JÁDREM ---
                        if sector in ["Real Estate", "Financial"]:
                            limit = 1.5
                        elif sector == "Consumer Defensive":
                            limit = 0.95 # PepsiCo (94%) se nyní vejde do limitu
                        else:
                            limit = 0.9
                        
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
# 4. SPUŠTĚNÍ APLIKACE
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
