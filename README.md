# International Cost of Capital | Streamlit app

International Finance course app for comparison of the cost of equity, borrowing cost and WACC in USD and a user-selected local currency. The **calculation formulas are taken from the International Valuation lecture** (slides 574, 577 and 583–585).

## Deploy to Streamlit Community Cloud

1. Upload the **files individually** to the root of your existing public GitHub repository (do not upload the ZIP as one file): `app.py`, `finance.py`, `data_sources.py`, `test_finance.py`, `test_data_sources.py`, `requirements.txt`, `README.md`, `betas.xls`, `oecd_combined_tax_snapshot.csv`.
2. In Streamlit Cloud choose that GitHub repository, branch `main`, and main file path `app.py`. If the app already exists, simply commit the updates; Streamlit normally redeploys automatically.
3. Check the **Data sources & observation dates** section after loading and press **Refresh source data** to attempt new fetches. A refresh updates the *attempt time*, but does not imply that the source published new data.

## Default settings

- Industry: Software (System & Application)
- Target country: United States
- Project tax jurisdiction: United States
- Equity risk premium: 6.5%; target debt share: 30%
- Optional overrides: unlevered industry beta; U.S. and selected-country statutory corporate tax; USD BBB spread; each 10Y yield; foreign-currency BBB spread.

## Exact lecture calculation method

Rates must be converted to decimals inside gross-rate currency conversion expressions. Let `d` denote the debt share and `T` the **same selected project tax rate in both currencies**:

```text
D/E = d / (1 - d)
beta_L = beta_U * [1 + (1-T)*(D/E)]
ke_USD = y_USD + beta_L * ERP
kd_USD = y_USD + s_USD
F = (1 + y_foreign) / (1 + y_USD)
ke_foreign = (1 + ke_USD)*F - 1
s_foreign (automatic) = s_USD * F
kd_foreign = y_foreign + s_foreign
WACC = (1-d)*ke + d*kd*(1-T)
```

The optional **foreign spread override affects only foreign cost of debt and foreign WACC**, not USD results or the cost of foreign equity. The model approximates risk-free rates using local government 10Y yields. It does not add a separate country equity risk premium or fully model sovereign default risks.

## Data retrieval and honest fallback

- **Damodaran betas:** The app downloads the latest published `betas.xls`. If blocked, it tries the Damodaran HTML table; if both fail, it uses the bundled **January 2026 XLS snapshot**, explicitly marked *not live*.
- **Damodaran BBB spread:** Parses the *Baa2/BBB* row for large non-financial service firms from the ratings page. If unreachable, it uses a labeled January 2026 reference **1.11 percentage points** (not live).
- **OECD taxes:** Calls the official **OECD SDMX endpoint** for statutory, *combined* corporate income tax observations (`MEASURE=CIT_C`, `TARGETING=ST`, `SECTOR=S13`), and selects each country's most recent available year. If the API is inaccessible, it uses the provided **2026 OECD CSV snapshot** (not live). This is not the federal-only US rate.
- **Trading Economics:** Reads the public `/bonds` HTML table only when a country and **Yield** column can be identified unambiguously. Some deployments receive dynamically loaded pages or access restrictions: then the app explicitly asks for manual inputs. **Manual yields are never represented as live quotes.** No paid API key is required for the best-effort HTML scraper, but reliable access is not guaranteed.

**Do not use an old downloaded CSV or screenshot as proof of a live fetch.** Verify both data provenance and observations shown by the deployed app.

## How to verify

```bash
python -m pytest -q
```

Run the following required application-level checks in the **Export & verification** section:

1. When U.S. and foreign government yields are equal and foreign spread override is off, U.S. and foreign cost of equity, debt cost and WACC match.
2. Zero debt makes WACC equal equity cost in each currency.
3. Enabling a foreign borrowing spread override changes foreign debt cost and WACC but does not change USD results.

**Independent class example, Colombian peso:** `beta_U=0.80`, `tax=35%`, `debt=30%`, `ERP=6.5%`, `US yield=4%`, `COP yield=12%`, `US BBB spread=1.5%`. Results: `beta_L=1.022857`, `USD ke=10.6486%`, `USD debt=5.5%`, `USD WACC=8.5265%`, `COP ke=19.1600%`, automatic COP spread `1.6154%`, and `COP WACC=16.0670%`. These match lecture slides 578–585. Inputs in this case are intentionally manual and illustrative, not today's market observations.

## Sources

- Damodaran beta XLS: https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls
- Damodaran Baa2/BBB borrowing spread: https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html
- OECD SDMX Corporate Income Tax dataset: https://data-explorer.oecd.org/vis?df%5Bag%5D=OECD.CTP.TPS&df%5Bds%5D=dsDisseminateFinalDMZ&df%5Bid%5D=DSD_TAX_CIT%40DF_CIT&df%5Bvs%5D=2.0
- Trading Economics bonds: https://tradingeconomics.com/bonds

## Submission

The professor requests (1) GitHub repository link, (2) deployed Streamlit link, (3) snapshots of AI interactions, and (4) a brief independent calculation and one verified AI-generated design or calculation choice. Include a screenshot of the **source diagnostics** when testing live data, and take care not to claim unsuccessful website scraping is a successful live feed.

### Country-yield validation (November 2026 fix)

The app first tries the 10-year bond table and then the country's dedicated Trading Economics 10-year government-bond page. It checks that the second page actually names the selected country and 10-year tenor, and reads the **Actual** yield rather than a forecast or daily change. A response may fail because Trading Economics restricts requests; this is not interpreted as a zero or as a 4% yield.

If a quote cannot be validated, the corresponding manual field is initially blank and must be filled explicitly; calculations cannot run until both yields are supplied. Each target country has an independent manual field to prevent a prior country's rate from being carried over. With United States selected as the target, both sides use the same U.S. 10-year yield. Manual numbers are clearly marked as such and should be associated with their own observation date before submission.

The local calculation and parser tests can be run with `python -m pytest -q`. These tests do not guarantee that Trading Economics will permit requests from a particular Streamlit Cloud deployment.


### Broader country coverage (November 2026)

- The country selector includes ISO countries, OECD tax jurisdictions, and all countries discovered from the Trading Economics public 10Y country list. Countries without a published 10Y benchmark remain selectable but require an explicitly sourced manual override.
- Bond retrieval tries the major bond table and the country-specific 10Y page for a precise quote, then the broader [Trading Economics country list](https://tradingeconomics.com/country-list/government-bond-10y). The country list usually rounds yields to two decimal places and publishes month-level *Reference* dates: the app displays those limitations transparently.
- The list is fetched anew after the Refresh button; no yield is invented for absent countries. The browser-friendly public HTML may be blocked or changed by the website, so the code retains the manual override fallback.
- Every newly added source needs observation date and provenance. This is not a guarantee of a live quote for all sovereign states.
