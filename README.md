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

### Krok 2: Instalace doplňků (Knihoven)
Aplikace využívá pokročilé knihovny pro data, grafiku a generování dokumentů. Otevřete terminál (CMD) a spusťte:
```bash
pip install yfinance pandas matplotlib numpy beautifulsoup4 requests reportlab
```

---

## 2. Klíčové moduly aplikace

### ⚙️ Editor výběru akcií a ETF
Definujte svůj "investiční vesmír" bez omezení.
* **Etické filtry:** Skryjte jedním klikem tabák, zbraně, kasina nebo firmy svázané s rizikem AI bubliny.
* **Plná podpora ETF:** Aplikace rozlišuje distribuční a akumulační UCITS ETF.
* **Analytický pohled:** Inteligentní hodnocení diverzifikace a vyváženosti vašeho mixu (růst vs. cash-flow).

### 📊 Pokročilý Tuning Portfolia
Zcela unikátní dvouproudá optimalizace (Minulost vs. Budoucnost).
* **Trychtýř nejistoty:** Aplikace nestuduje jen minulost, ale pomocí modelování *geometric brownian motion* a výhledů analytiků kreslí pravděpodobný budoucí scénář.
* **Ochrana před value traps:** Vestavěný "účetní rozum" filtruje nesmyslné hodnoty payout ratií a snižuje rating firmám, které si na dividendu půjčují.
* **Daňová brzda:** Grafy automaticky vizualizují ztrátu na složeném úročení způsobenou srážkovou 15% daní z dividend pro férové srovnání s ETF.

### 🏦 Správa Ledgeru (FIFO)
Striktní evidence nákupů a prodejů s respektem k lokální legislativě.
* **Časový test:** Automatické hlídání 3letého limitu pro osvobození prodejů od daně v ČR (včetně přestupných let).
* **FIFO algoritmus:** Přesný a legislativně korektní odečet kusů od nejstarších lotů.
* **Měnové kurzy:** Samostatný scrapovací robot stahuje aktuální "jednotné kurzy" vyhlášené Ministerstvem financí.

### 📄 Daňový Automat (One-Click Export)
Konec ručního vyplňování a počítání britských pencí.
* **XML Export:** Vygeneruje soubor pro přímé a bezchybné nahrání do portálu **mojedane.cz**.
* **PDF Kuchařka:** Lidsky srozumitelný dokument popisující, které hodnoty opsat do kterých řádků přiznání.
* **Daňová inteligence:** Ignoruje akumulační fondy, správně odděluje americkou (15 %) a britskou (0 %) daň u zdroje.

---

## 3. Investiční logika a rizika

Výchozí nastavení databáze je koncipováno jako **"all-weather dividend growth"** strategie kombinující to nejlepší z amerického růstu, silného britského cash-flow a defenzivních králů trhu.

### Charakteristika výchozího mixu

| Segment | Vlastnosti | Zastoupené tituly |
| :--- | :--- | :--- |
| **Technologický růst** | Nízká dividenda, exponenciální růst kapitálu. | `AAPL`, `AVGO`, `CAT` |
| **Defenzivní stabilita** | Odolnost v recesi, dlouhodobě rostoucí výplaty. | `JNJ`, `ABBV`, `PEP`, `ULVR.L`, `NEE`, `MRK` |
| **Vysoký cash-flow** | BDC a REIT tituly s masivním výnosem (6–10 %). | `MAIN`, `ARCC`, `OHI`, `O` |
| **Zahraniční diverzifikace** | Expozice vůči britské libře (GBP). | `LGEN.L`, `TRIG.L` |

> [!WARNING]
> **INVESTIČNÍ RIZIKA:**
> * **Koncentrace v BDC:** Tituly jako ARCC a MAIN tvoří značnou část příjmů. Jsou citlivé na úrokové sazby a stav ekonomiky USA.
> * **Měnové riziko:** Investujete v cizích měnách. Posílení CZK vůči USD/GBP technicky snižuje hodnotu vašeho portfolia v korunách.
> * **Závislost na datech:** Aplikace využívá neoficiální API Yahoo Finance. Aplikace má sice robustní *spot-check*, ale dlouhodobý výpadek serverů může dočasně omezit funkce analýzy.

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
