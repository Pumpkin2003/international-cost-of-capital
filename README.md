# International Cost of Capital App

A Streamlit academic dashboard comparing cost of equity, pre-tax cost of debt and after-tax WACC in USD vs. a selected country's local currency.

## Quick deployment

1. Create a GitHub repository (for example `international-cost-of-capital`).
2. Upload **all five files**: `app.py`, `finance.py`, `test_finance.py`, `requirements.txt`, `README.md`.
3. In Streamlit Community Cloud choose **Create app**, select the GitHub repository and use `app.py` as entrypoint.
4. Click **Deploy**. You do not need a Trading Economics API key. Live website scraping can fail; the app supplies manually editable yield inputs and explicitly labels source failures.

## Inputs and defaults

- Industry: Software (System & Application)
- Target country: United States
- Tax jurisdiction: United States
- Equity risk premium: 6.5%; financing debt share: 30%
- Damodaran U.S. industry **unlevered** beta: automatically downloaded from `betas.xls`, with an HTML-table fallback and a clearly marked Jan 2026 sample fallback.
- Damodaran Baa2/BBB default spread: large non-financial service firms (Jan 2026 reference 1.11%).
- OECD 2026 corporate tax rate: **the OECD site has no stable public HTML table suitable for simple scraping**. Rates currently shown by default are **reference estimates, not automatically verified OECD 2026 observations**. Verify each chosen country from the linked OECD official source and edit manually. This is an unfinished live-data requirement.
- Trading Economics ten-year government yields: best-effort website scrape. If values are not reliably accessible, manual input is required. The program makes no claim that illustrative 4% input is live.
- For more countries, choose from the selector and manually supply tax and yield when automated coverage is missing.

## Model (class formula confirmation required)

All rate inputs use percentage points (e.g., `6.5`, not `0.065`). For a selected **single project tax rate** T and w_D = debt share:

- D/E = w_D / (1 - w_D)
- Levered beta = unlevered beta * [1 + (1 - T) * D/E]
- Currency cost of equity = own 10Y government yield + levered beta * common equity risk premium
- Currency pre-tax debt cost = own 10Y government yield + BBB spread
- Currency WACC = (1 - w_D) * currency cost of equity + w_D * currency debt cost * (1 - T)

Foreign BBB spread defaults to the USD spread, unless manually overridden. The USD results do **not** depend on this override.

**Important:** This model is a classroom yield-based proxy; the user said the precise formula set would be provided during class. Confirm and revise `finance.py` if the instructor uses a different international cost-of-capital conversion method. Sovereign/FX risk adjustments are not modeled.

## Verification

Run `python -m unittest -v test_finance` locally. In-app verification expanders also check:

1. Equal government yields and shared spreads => identical rates.
2. Zero debt => WACC equals cost of equity.
3. Overwriting the foreign BBB spread does not affect USD results.

## Data integrity and dates

- All live sources are shown with URLs and fetch-attempt timestamps.
- A refresh button invalidates caches; cache alone is not proof of a new source observation.
- A source's **publication date** differs from a **fetch timestamp**.
- You should independently confirm a sample calculation using a spreadsheet or calculator and save screenshots of the app output, prompts, and checks.

## Primary sources

- [Damodaran U.S. betas XLS](https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls)
- [Damodaran Baa2/BBB spread](https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html)
- [OECD Corporate Income Tax Rates Database 2026](https://www.oecd.org/en/data/datasets/corporate-income-tax-rates-database.html)
- [Trading Economics government bonds](https://tradingeconomics.com/bonds)
