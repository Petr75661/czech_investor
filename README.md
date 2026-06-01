# Czech Investor: Tax & Portfolio Manager
**Profesionální analytika, správa portfolia a automatizace daní v ČR**

---

## O aplikaci
Aplikace je navržena pro české investory, kteří vyžadují matematickou přesnost při rebalancování a zároveň chtějí mít vyřešenou daňovou agendu na jeden klik. Unikátní algoritmus **Monte Carlo** spojený s prediktivním behaviorálním modelem simuluje miliony scénářů pro maximalizaci výnosu, zajištění bezpečného cash-flow a minimalizaci rizika na základě aktuálních odhadů analytiků.

---

## 1. Instalace a zprovoznění

### Krok 1: Instalace prostředí Python
1. Stáhněte si **Python 3.10+** z [python.org](https://www.python.org/).
2. Při instalaci na Windows aktivujte volbu **"Add Python to PATH"**.

### Krok 2: Instalace doplňků (knihoven)
Aplikace využívá pokročilé knihovny pro data, grafiku a generování dokumentů. Otevřete terminál (CMD) a spusťte:
```bash
pip install yfinance yahooquery pandas matplotlib numpy beautifulsoup4 requests reportlab pdfplumber
```

> [!NOTE]
> Architektura stahování dat: Aplikace nevyžaduje žádné API klíče. Spoléhá na knihovnu yfinance a yahooquery. Pokud jeden ze zdrojů Yahoo selže (např. kvůli omezení zátěže), aplikace přepne na druhý.

---

## 2. Klíčové moduly aplikace

### ⚙️ Editor výběru akcií a ETF
Definujte svůj "investiční vesmír" bez omezení.
* **Etické filtry:** Skryjte jedním klikem tabák, zbraně, kasina nebo firmy svázané s rizikem AI bubliny.
* **Plná podpora ETF:** Aplikace rozlišuje distribuční a akumulační UCITS ETF.
* **Analytický pohled:** Inteligentní hodnocení diverzifikace a vyváženosti vašeho mixu (růst vs. cash-flow).

### 📊 Pokročilý tuning portfolia
Zcela unikátní dvouproudá optimalizace (minulost vs. budoucnost).
* **Interaktivní fixace vah:** Dvojklikem na výseč v levém koláčovém grafu můžete zvolené akcii vnutit přesnou cílovou váhu. Monte Carlo algoritmus následně optimalizuje zbytek portfolia kolem tohoto pevného bodu.
* **Trychtýř nejistoty:** Modelování pravděpodobných budoucích scénářů na základě volatility a cílů analytiků.
* **Ochrana před value traps:** Vestavěný "účetní rozum" filtruje nesmyslné hodnoty payout ratií a snižuje rating firmám, které si na dividendu půjčují.
* **Daňová brzda:** Grafy automaticky vizualizují ztrátu na složeném úročení způsobenou srážkovou 15% daní z dividend pro férové srovnání s ETF.

### 🏦 Správa ledgeru (FIFO)
Striktní evidence nákupů a prodejů s respektem k lokální legislativě a poplatkům.
* **IBKR Import (activity statement):** Načtěte CSV od brokera Interactive Brokers a aplikace automaticky spáruje všechny nákupy, zaznamená prodeje metodou FIFO, načte přijaté dividendy (včetně srážkových daní) a provede hloubkový audit vašich otevřených pozic.
* **Optimalizace poplatků brokera:** Algoritmus při nákupu hlídá "minimum trade size" (např. IBKR Tiered minimum 0.35 USD / 1.00 GBP) a brání nesmyslným mikro-nákupům, které by spolkly velké procento na poplatcích.
* **Časový test:** Automatické hlídání 3letého limitu pro osvobození prodejů od daně v ČR (včetně přestupných let).
* **FIFO algoritmus:** Přesný a legislativně korektní odečet kusů od nejstarších lotů.
* **Měnové kurzy:** Samostatný scrapovací robot stahuje aktuální "jednotné kurzy" vyhlášené Ministerstvem financí.

### 📄 Daňový automat (one-click export)
Konec ručního vyplňování a počítání britských pencí.
* **XML Export:** Vygeneruje soubor pro přímé a bezchybné nahrání do portálu **mojedane.cz**.
* **PDF Kuchařka:** Lidsky srozumitelný dokument popisující, které hodnoty opsat do kterých řádků přiznání.
* **Daňová inteligence:** Ignoruje akumulační fondy, správně odděluje americkou (15 %) a britskou (0 %) daň u zdroje.

---

## 3. Investiční logika a rizika

Výchozí nastavení databáze obsahuje portfolio o 24 pozicích. Jde o
diverzifikovanou **"All-Weather Dividend Growth"** strategii kombinující
americký technologický růst, průmyslové giganty a masivní britsko-americké
cash-flow.

### Charakteristika výchozího mixu

| Segment | Vlastnosti | Zastoupené tituly |
| :--- | :--- | :--- |
| **Technologický růst** | Kombinace inovací a navyšování dividend. | `AAPL`, `AVGO`, `MU` |
| **Průmysl a infrastruktura** | Cyklická síla a regulované utility.       | `CAT`, `TT`, `ETN`, `PWR`, `NEE`, `TRIG.L`   |
| **Defenzivní stabilita**     | Odolnost v recesi, zdraví a spotřeba.     | `JNJ`, `ABBV`, `PEP`, `ULVR.L`, `MRK`, `LLY` |
| **Vysoké cash-flow (BDC)**   | Úvěry středním firmám s masivním výnosem. | `MAIN`, `ARCC`, `HTGC`, `TRIN`, `FDUS`       |
| **Reality (REITs)**          | Pronájem nemovitostí a zdravotnická péče. | `O`, `OHI`, `SBRA`                           |
| **Zahraniční diverzifikace** | Expozice na britský finanční trh (v GBP). | `LGEN.L`                                     |

> [!WARNING]
> **INVESTIČNÍ RIZIKA:**
> * **Úrokové riziko:** Sektory REIT, BDC a utilities spoléhají na cizí kapitál a mohou prudce klesat při nečekaném růstu úrokových sazeb centrálních bank.
> * **Měnové riziko:** Investujete v cizích měnách. Posílení CZK vůči USD/GBP technicky snižuje hodnotu vašeho portfolia v korunách, i když akcie samotné rostou.
> * **Závislost na datech:** Aplikace využívá dvě různá API (yfinance a yahooquery), čímž je chráněna proti dočasným výpadkům a rate-limitům. I tak ale může případný globální a dlouhodobý výpadek serverů omezit některé analytické funkce.
> * **Sektorová rizika:** Portfolio obsahuje specifické sektory (REITs, BDC, utilities), které podléhají jiným daňovým a regulačním pravidlům než běžné korporátní akcie.

---

## 4. Automatizace: Plánovač úloh Windows

Pro disciplinované investování doporučujeme nastavit automatické spouštění aplikace v den, kdy provádíte nákupy (např. 1. den v měsíci).

1. Otevřete **Plánovač úloh** (task scheduler) ve Windows.
2. Zvolte **Vytvořit základní úlohu** a pojmenujte ji `Czech Investor Nákup`.
3. Nastavte spouštění **Měsíčně**.
4. V kroku "Akce" zvolte **Spustit program**.
5. Do pole Program/skript vložte cestu k `pythonw.exe` (např. `C:\Users\Jmeno\AppData\Local\Programs\Python\Python312\pythonw.exe`).
6. Do pole **Argumenty** vložte celou cestu k vašemu skriptu (např. `"C:\Investice\stocks.py"`).

> [!TIP]
> Zástupce nebo plánovač volající `pythonw.exe` spustí aplikaci elegantně, aniž by na pozadí zůstalo viset rušivé černé okno terminálu.

---

## 5. Důležité právní upozornění

*Tato aplikace je určena výhradně pro edukační a analytické účely. Autor nenese žádnou odpovědnost za případné finanční ztráty vzniklé investováním na základě simulací v tomto softwaru. Daňový modul generuje podklady na základě aktuálně platných zákonů ČR (ke stažení jednotných kurzů 2025/2026), uživatel by si však měl finální výpočty a nárok na daňové odpočty vždy ověřit u certifikovaného daňového poradce.*
