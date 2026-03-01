# Czech Investor: Tax & Portfolio Manager
**Profesionální analytika, správa portfolia a automatizace daní v ČR**

## O aplikaci
Aplikace je navržena pro české investory, kteří vyžadují matematickou přesnost při rebalancování a zároveň chtějí mít vyřešenou daňovou agendu na jeden klik. Unikátní algoritmus **Monte Carlo** simuluje velké množství scénářů pro optimalizaci vašeho výnosu při zachování bezpečných limitů.

---

## 1. Instalace a zprovoznění

### Krok 1: Instalace prostředí Python
1. Stáhněte si **Python 3.10+** z [python.org](https://www.python.org/).
2. Při instalaci na Windows nezapomeňte aktivovat volbu **"Add Python to PATH"**.

### Krok 2: Instalace doplňků (knihoven)
Aplikace využívá pokročilé knihovny pro data, grafiku a generování dokumentů. Otevřete terminál (CMD) a spusťte:
```bash
pip install yfinance pandas matplotlib numpy beautifulsoup4 requests reportlab
```

## 2. Klíčové moduly aplikace
⚙️ Editor výběru akcií

Umožňuje definovat váš "investiční vesmír".

*Etické filtry: Skryjte jedním klikem Tabák, Zbraně, Kasina nebo AI bubliny.
*Vizuální analýza: ASCII pruhy ukazují bipolární růst za 2 roky a dividendový výnos.
*Online hledání: Automatické dohledání tickerů (US i UK trhy) včetně stažení metrik.

📊 Tuning Portfolia

Matematické jádro postavené na Moderní teorii portfolia.

*Reality Check: Srovnání vaší křivky s indexem S&P 500.
*Risk Meter: Výpočet roční volatility a drawdownu v reálném čase.
*Multi-core: Simulace využívá všechna jádra vašeho CPU pro bleskový výpočet.

🏦 Správa Ledgeru (FIFO)

Striktní evidence nákupů pro daňové účely.

*Časový test: Automatické hlídání 3letého limitu pro osvobození od daně v ČR.
*FIFO prodeje: Přesný odečet kusů od nejstarších lotů.
*Měnové kurzy: Automatické stahování jednotných kurzů MFČR.

📄 Daňový Automat

Konec ručního vyplňování daňového přiznání.

*XML Export: Soubor pro přímé nahrání do portálu mojedane.cz.
*PDF Kuchařka: Podrobný návod, do kterých řádků přiznání co opsat.
*Limity: Automatické vyhodnocení osvobození do 100 000 Kč příjmu.

## 3. Investiční logika a rizika

Aplikace hlídá tzv. "Zdraví portfolia". Pokud se pokusíte vytvořit příliš koncentrovaný mix, bar zdraví zčervená. Výchozí nastavení je koncipováno jako "All-Weather Dividend Growth" strategie.

*Charakteristika výchozího mixu
*Segment	Vlastnosti	Zastoupené tituly
*Technologický růst	Nízká dividenda, vysoký růst kapitálu.	AAPL, AVGO, CAT
*Defenzivní stabilita	Odolnost v recesi, stabilní výplata.	JNJ, ABBV, PEP, ULVR.L, NEE
*Vysoký cash-flow	BDC a REIT tituly s výnosem 6–10 %.	MAIN, HTGC, OHI, O
*Zahraniční diverzifikace	Expozice vůči britské libře (GBP).	LGEN.L, TRIG.L

⚠️ INVESTIČNÍ RIZIKA:

*Koncentrace v BDC: Tituly jako HTGC a MAIN tvoří značnou část příjmů. Jsou citlivé na úrokové sazby a stav ekonomiky USA.
*Měnové riziko: Investujete v cizích měnách. Posílení CZK vůči USD/GBP snižuje hodnotu vašeho portfolia v korunách.
*Závislost na datech: Aplikace využívá neoficiální API Yahoo Finance. V případě změny struktury jejich webu může dojít k dočasnému výpadku stahování dat.

## 4. Automatizace: Plánovač úloh Windows

Pro disciplinované investování doporučujeme nastavit automatické spouštění aplikace v den, kdy provádíte nákupy (např. 1. den v měsíci).

1. Otevřete Plánovač úloh (Task Scheduler) ve Windows.
2. Zvolte Vytvořit základní úlohu a pojmenujte ji Czech Investor Nákup.
3. Nastavte spouštění Měsíčně.
4. V kroku "Akce" zvolte Spustit program.
5. Do pole Program/skript vložte cestu k pythonw.exe (např. C:\Users\Jmeno\AppData\Local\Programs\Python\Python312\pythonw.exe).
6. Do pole Argumenty vložte celou cestu k vašemu skriptu (např. "C:\Investice\stocks.py").

💡 Tip: Verze pythonw.exe spustí aplikaci přímo v grafickém režimu bez rušivého černého okna terminálu.

## 5. Důležité právní upozornění

Tato aplikace je určena výhradně pro edukační a analytické účely. Autor nenese žádnou odpovědnost za případné finanční ztráty vzniklé investováním na základě simulací v tomto softwaru. Daňový modul generuje podklady na základě aktuálně platných zákonů ČR k roku 2025/2026, uživatel by si však měl finální výpočty vždy ověřit u certifikovaného daňového poradce.
