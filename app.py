"""International Cost of Capital | Streamlit classroom project.

All rate inputs use percentage points (6.5 means 6.5%).
The finance model is isolated in finance.py so class formulas can be updated easily.
"""
import io
import re
from datetime import datetime, timezone
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from finance import cost_of_capital

st.set_page_config(page_title='International Cost of Capital', page_icon='🌐', layout='wide')

DAMODARAN_BETA = 'https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls'
DAMODARAN_BETA_HTML = 'https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/Betas.html'
DAMODARAN_RATING = 'https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html'
OECD_2026 = 'https://www.oecd.org/en/data/datasets/corporate-income-tax-rates-database.html'
OECD_REPORT = 'https://www.oecd.org/en/publications/corporate-tax-statistics-2026_73af6222-en/full-report/statutory-corporate-income-tax-rates_ce84abb9.html'
TE_BONDS = 'https://tradingeconomics.com/bonds'

# OECD combined statutory reference values for a small selection, not a live feed.
# These values are explicitly marked as illustrative until verified against OECD.
REFERENCE_TAX = {
    'United States':25.6, 'Germany':29.9, 'United Kingdom':25.0,
    'France':25.8, 'Japan':29.7, 'Canada':26.2, 'Australia':30.0,
    'Italy':27.8, 'Spain':25.0, 'Netherlands':25.8, 'Switzerland':19.6,
    'Sweden':20.6, 'Norway':22.0, 'Denmark':22.0, 'Ireland':12.5,
    'Poland':19.0, 'Mexico':30.0, 'South Korea':26.4,
    'New Zealand':28.0, 'Austria':23.0, 'Belgium':25.0,
    'Finland':20.0, 'Portugal':29.5, 'Brazil':34.0,
    'India':25.2, 'China':25.0, 'Singapore':17.0,
    'Turkey':25.0, 'Hungary':9.0,
}
COUNTRIES = sorted(set(REFERENCE_TAX) | {'Argentina','Chile','Colombia','Czech Republic','Greece','Indonesia','Israel','Malaysia','Romania','Saudi Arabia','South Africa','Thailand','United Arab Emirates','Vietnam'})
COUNTRY_TE_SLUGS = {'United States':'united-states','United Kingdom':'united-kingdom','South Korea':'south-korea','Czech Republic':'czech-republic','United Arab Emirates':'united-arab-emirates'}


def now_utc():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')


def get(url):
    response = requests.get(url, timeout=18, headers={'User-Agent':'Mozilla/5.0 (compatible; AcademicProject/1.0)', 'Accept-Language':'en-US,en;q=0.9'})
    response.raise_for_status()
    return response


def number(raw):
    text = str(raw).replace('\u2212','-').replace(',','').replace('%','').strip()
    return float(re.search(r'[-+]?\d+(?:\.\d+)?',text).group())


def parse_beta_table(tables):
    for df in tables:
        frame = df.copy()
        # Damodaran's XLS has several title rows before the actual table header.
        if all(isinstance(c, (int, float)) or str(c).startswith('Unnamed') for c in frame.columns):
            for ix in range(min(25, len(frame))):
                row_text = [str(x).strip().lower() for x in frame.iloc[ix].tolist()]
                if any('industry name' in x for x in row_text) and any('unlevered beta' in x for x in row_text):
                    frame.columns = [str(x).strip() for x in frame.iloc[ix]]
                    frame = frame.iloc[ix+1:].copy()
                    break
        if isinstance(frame.columns,pd.MultiIndex):
            frame.columns = [' '.join(map(str,c)) for c in frame.columns]
        frame.columns = [str(c).strip() for c in frame.columns]
        industry_cols = [c for c in frame.columns if 'industry name' in c.lower()]
        beta_cols = [c for c in frame.columns if 'unlevered beta' in c.lower() and 'correct' not in c.lower()]
        if industry_cols and beta_cols:
            result = frame[[industry_cols[0],beta_cols[0]]].copy()
            result.columns=['Industry','Unlevered beta']
            result['Unlevered beta']=pd.to_numeric(result['Unlevered beta'],errors='coerce')
            result['Industry']=result['Industry'].astype(str).str.strip()
            result=result.dropna().query('`Unlevered beta` >= 0')
            result=result[~result.Industry.str.contains('Total Market|Average|Industry Name',case=False,na=False)]
            if len(result)>=10:
                return result.drop_duplicates('Industry').sort_values('Industry').reset_index(drop=True)
    raise ValueError('No recognizable unlevered-beta table found')


def fetch_betas():
    errors=[]
    try:
        data=get(DAMODARAN_BETA).content
        frame=parse_beta_table(pd.read_excel(io.BytesIO(data),sheet_name=None,header=None).values())
        return frame,'Damodaran U.S. betas.xls',None
    except Exception as err:
        errors.append(f'XLS: {err}')
    try:
        # The alternate HTML table is the same U.S. sector dataset.
        frame=parse_beta_table(pd.read_html(io.StringIO(get(DAMODARAN_BETA_HTML).text)))
        return frame,'Damodaran U.S. beta HTML',None
    except Exception as err:
        errors.append(f'HTML: {err}')
    return pd.DataFrame({'Industry':['Software (System & Application)'], 'Unlevered beta':[1.23]}), 'Reference sample: Damodaran Jan 2026 (NOT refreshed)', '; '.join(errors)


def fetch_bbb():
    try:
        soup=BeautifulSoup(get(DAMODARAN_RATING).text,'html.parser')
        for tr in soup.select('tr'):
            cells=[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'],recursive=False)]
            if any('Baa2/BBB' in cell for cell in cells):
                pos=next(i for i,c in enumerate(cells) if 'Baa2/BBB' in c)
                if pos+1 < len(cells):
                    value=number(cells[pos+1])
                    if 0 < value < 15:
                        return value,'Damodaran Baa2/BBB large non-financial',None
        # Fallback to page text in case cells are structured unusually.
        match=re.search(r'Baa2\s*/\s*BBB\s*</t[dh]>\s*<t[dh][^>]*>\s*([\d.]+)\s*%',get(DAMODARAN_RATING).text,re.I)
        if match:
            return float(match.group(1)),'Damodaran Baa2/BBB large non-financial',None
        raise ValueError('BBB row not found')
    except Exception as err:
        return 1.11,'Reference: Damodaran Jan 2026 (NOT refreshed)',str(err)


def fetch_tax_rates():
    """Attempt machine-readable OECD data; never mislabel reference data as live."""
    # OECD Data Explorer currently offers SDMX export behind an interactive UI;
    # the report itself is not a reliable machine-readable country table.
    # Use a manually curated reference with an explicit 'unverified' label.
    return REFERENCE_TAX.copy(), 'Reference estimates; verify against OECD 2026', 'OECD web report does not expose a stable country-rate HTML table. Supply or verify the displayed values manually.'


def fetch_country_yield(country):
    """Best-effort scrape; Trading Economics can block/dynamically render pages."""
    slug=COUNTRY_TE_SLUGS.get(country,re.sub(r'[^a-z0-9]+','-',country.lower()).strip('-'))
    urls=[f'https://tradingeconomics.com/{slug}/government-bond-yield',TE_BONDS]
    problems=[]
    for url in urls:
        try:
            html=get(url).text
            soup=BeautifulSoup(html,'html.parser')
            if url != TE_BONDS:
                # Individual country page: look for the headline indicator value.
                for selector in ['#p','[id="p"]','[data-symbol*="10Y"]']:
                    tag=soup.select_one(selector)
                    if tag:
                        val=number(tag.get_text(' ',strip=True))
                        if -5 < val < 40: return val,url,None
            else:
                for tr in soup.select('tr'):
                    cells=[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'],recursive=False)]
                    if cells and cells[0].strip().lower() in {country.lower(),country.lower()+' 10y'}:
                        for cell in cells[1:4]:
                            try:
                                val=number(cell)
                                if -5 < val < 40: return val,url,None
                            except (AttributeError,ValueError): pass
                # Some Trading Economics responses serialize quote tables in JSON.
                for match in re.finditer(r'"(?:Country|Name)"\s*:\s*"'+re.escape(country)+r'"',html,re.I):
                    excerpt=html[max(0,match.start()-200):match.end()+500]
                    m=re.search(r'"(?:Last|Price|Value)"\s*:\s*"?([-+]?\d+(?:\.\d+)?)',excerpt,re.I)
                    if m:
                        val=float(m.group(1))
                        if -5 < val < 40: return val,url,None
            problems.append(f'{url}: no trustworthy displayed 10Y value')
        except Exception as err:
            problems.append(f'{url}: {err}')
    return None,'No live Trading Economics quote','; '.join(problems)


@st.cache_data(ttl=3600,show_spinner='Fetching published sources...')
def get_sources():
    betas,beta_source,beta_error=fetch_betas()
    bbb,bbb_source,bbb_error=fetch_bbb()
    taxes,tax_source,tax_error=fetch_tax_rates()
    return betas,beta_source,beta_error,bbb,bbb_source,bbb_error,taxes,tax_source,tax_error,now_utc()


@st.cache_data(ttl=600,show_spinner='Checking Trading Economics...')
def quote(country):
    return (*fetch_country_yield(country),now_utc())


st.markdown('''<style>
.block-container {padding-top:2rem; max-width:1180px;}
[data-testid="stMetric"] {border:1px solid #dbe3ee; border-radius:12px; padding:15px;}
.caption {color:#64748b;font-size:.86rem}
</style>''',unsafe_allow_html=True)
st.title('🌐 International Cost of Capital')
st.caption('Compare project financing costs in USD and a selected local currency · Academic model')

with st.sidebar:
    st.header('Inputs & data refresh')
    if st.button('↻ Refresh source data',use_container_width=True):
        get_sources.clear()
        quote.clear()
        st.rerun()

betas,beta_source,beta_error,bbb,bbb_source,bbb_error,taxes,tax_source,tax_error,fetch_time=get_sources()

with st.sidebar:
    industries=betas['Industry'].tolist()
    default_industry='Software (System & Application)'
    industry=st.selectbox('Industry',industries,index=industries.index(default_industry) if default_industry in industries else 0)
    country=st.selectbox('Target country',COUNTRIES,index=COUNTRIES.index('United States'))
    erp=st.number_input('Equity risk premium (%)',min_value=0.0,max_value=50.0,value=6.5,step=.25)
    debt=st.slider('Debt financing (%)',min_value=0,max_value=95,value=30,step=1)
    use_foreign_tax=st.toggle('Use selected-country tax rate',value=False,help='Off = U.S. project tax rate. The chosen tax rate applies to both sides.')

us_yield,us_yield_source,us_yield_error,us_checked=quote('United States')
foreign_yield,foreign_yield_source,foreign_yield_error,foreign_checked=quote(country)
beta_auto=float(betas.loc[betas.Industry==industry,'Unlevered beta'].iloc[0])

with st.sidebar.expander('Overrides & missing live data',expanded=us_yield is None or foreign_yield is None):
    st.caption('Values are in percent points. Overrides stay visible and are used immediately.')
    override_beta=st.checkbox('Manual unlevered beta')
    beta=st.number_input('Unlevered beta',0.0,10.0,beta_auto,0.05,disabled=not override_beta)
    override_tax_us=st.checkbox('Manual U.S. corporate tax',value=False)
    tax_us=st.number_input('U.S. combined statutory tax (%)',0.0,60.0,float(taxes.get('United States',25.6)),0.1,disabled=not override_tax_us)
    override_tax_foreign=st.checkbox('Manual selected-country corporate tax',value=country not in taxes)
    tax_foreign=st.number_input('Selected-country tax (%)',0.0,60.0,float(taxes.get(country,25.0)),0.1,disabled=not override_tax_foreign)
    override_spread=st.checkbox('Manual USD BBB spread')
    spread_us=st.number_input('USD BBB spread (%)',0.0,30.0,float(bbb),0.05,disabled=not override_spread)
    override_us=st.checkbox('Manual U.S. 10Y yield',value=us_yield is None)
    y_us=st.number_input('U.S. 10Y government yield (%)',-5.0,40.0,float(us_yield if us_yield is not None else 4.0),.05,disabled=not override_us)
    override_local=st.checkbox('Manual selected-country 10Y yield',value=foreign_yield is None)
    y_local=st.number_input('Selected-country 10Y government yield (%)',-5.0,40.0,float(foreign_yield if foreign_yield is not None else 4.0),.05,disabled=not override_local)
    override_foreign_spread=st.checkbox('Manual foreign-currency BBB spread',value=False)
    spread_foreign=st.number_input('Foreign-currency BBB spread (%)',0.0,30.0,float(spread_us),.05,disabled=not override_foreign_spread,help='Off: use the same BBB spread as USD. On: only foreign-side debt cost changes.')

beta_used=beta if override_beta else beta_auto
spread_used=spread_us if override_spread else bbb
tax_used=(tax_foreign if override_tax_foreign else taxes.get(country,25.0)) if use_foreign_tax else (tax_us if override_tax_us else taxes.get('United States',25.6))
yield_us_used=y_us if override_us else us_yield
yield_foreign_used=y_local if override_local else foreign_yield
spread_foreign_used=spread_foreign if override_foreign_spread else None

if yield_us_used is None or yield_foreign_used is None:
    st.error('A live 10-year yield could not be retrieved. Enter a manual yield in the sidebar to calculate. No missing quote is presented as live.')
    st.stop()

out=cost_of_capital(beta_used,tax_used,debt,erp,yield_us_used,yield_foreign_used,spread_used,spread_foreign_used)

st.subheader('Project financing comparison')
st.caption(f'{industry} · {country} · {debt}% debt · {erp:.2f}% equity risk premium · {tax_used:.2f}% common project tax rate')
col_us,col_foreign=st.columns(2,gap='large')
for col,label,result,yield_rate in [(col_us,'🇺🇸 USD',out['usd'],yield_us_used),(col_foreign,f'🌍 {country} currency',out['foreign'],yield_foreign_used)]:
    with col:
        st.markdown(f'#### {label}')
        st.metric('WACC',f"{result['wacc']:.2f}%")
        c1,c2=st.columns(2)
        c1.metric('Cost of equity',f"{result['cost_equity']:.2f}%")
        c2.metric('Pre-tax cost of debt',f"{result['cost_debt']:.2f}%")
        st.caption(f'10Y government yield: {yield_rate:.3f}%')

st.caption(f"Relevered equity beta: {out['levered_beta']:.4f} · D/E = {debt/(100-debt):.4f} · Selected project tax jurisdiction: {'Foreign' if use_foreign_tax else 'United States'}")

with st.expander('Formulas and assumptions',expanded=True):
    st.markdown(r'''
- **Relevered beta:** $\beta_L = \beta_U[1+(1-T)(D/E)]$ with $D/E = w_D/(1-w_D)$.
- **Cost of equity (each currency):** $k_e = y_{10Y}+\beta_L ERP$.
- **Pre-tax cost of debt:** $k_d=y_{10Y}+s_{BBB}$.
- **WACC:** $WACC=(1-w_D)k_e+w_Dk_d(1-T)$.
- The same project tax rate, debt share, ERP and relevered beta are used for both currencies.
- Foreign BBB spread **defaults to the USD BBB spread**; switching on the foreign spread override affects only foreign debt and WACC.
- These are classroom **proxy assumptions**, not arbitrage-free FX conversion of nominal discount rates. Country-specific sovereign risk, inflation, currency premia and debt-credit differences are not modeled. Replace formulas if your professor specifies a different method.
- Corporate statutory rates are headline rates; actual project taxation can differ.
''')

st.subheader('All-industry comparison')
records=[]
for _,row in betas.iterrows():
    tmp=cost_of_capital(float(row['Unlevered beta']),tax_used,debt,erp,yield_us_used,yield_foreign_used,spread_used,spread_foreign_used)
    records.append({'Industry':row['Industry'],'Unlevered beta':row['Unlevered beta'], 'Levered beta':tmp['levered_beta'],
                    'USD cost of equity (%)':tmp['usd']['cost_equity'],'USD cost of debt (%)':tmp['usd']['cost_debt'],'USD WACC (%)':tmp['usd']['wacc'],
                    'Foreign cost of equity (%)':tmp['foreign']['cost_equity'],'Foreign cost of debt (%)':tmp['foreign']['cost_debt'],'Foreign WACC (%)':tmp['foreign']['wacc']})
comparison=pd.DataFrame(records)
st.dataframe(comparison,hide_index=True,use_container_width=True,height=350)
plot=comparison.set_index('Industry')[['USD WACC (%)','Foreign WACC (%)']].sort_values('USD WACC (%)')
st.bar_chart(plot,height=330)

st.subheader('Export & verification')
output=pd.DataFrame([{'Industry':industry,'Country':country,'Tax jurisdiction':'Foreign' if use_foreign_tax else 'United States','Tax (%)':tax_used,
                      'ERP (%)':erp,'Debt share (%)':debt,'Unlevered beta':beta_used,'Levered beta':out['levered_beta'],
                      'U.S. 10Y yield (%)':yield_us_used,'Foreign 10Y yield (%)':yield_foreign_used,
                      'U.S. BBB spread (%)':spread_used,'Foreign BBB spread (%)':spread_foreign if override_foreign_spread else spread_used,
                      'USD cost of equity (%)':out['usd']['cost_equity'],'USD debt cost (%)':out['usd']['cost_debt'],'USD WACC (%)':out['usd']['wacc'],
                      'Foreign cost of equity (%)':out['foreign']['cost_equity'],'Foreign debt cost (%)':out['foreign']['cost_debt'],'Foreign WACC (%)':out['foreign']['wacc'],
                      'Fetched / checked at (UTC)':fetch_time}])
c1,c2=st.columns(2)
c1.download_button('Download selected case (.csv)',data=output.to_csv(index=False).encode(),file_name='cost_of_capital_selected.csv',mime='text/csv')
c2.download_button('Download all industries (.csv)',data=comparison.to_csv(index=False).encode(),file_name='cost_of_capital_all_industries.csv',mime='text/csv')

with st.expander('Verify three required invariants'):
    equal=cost_of_capital(beta_used,tax_used,debt,erp,5.0,5.0,spread_used,None)
    zero=cost_of_capital(beta_used,tax_used,0,erp,yield_us_used,yield_foreign_used,spread_used,None)
    changed=cost_of_capital(beta_used,tax_used,debt,erp,yield_us_used,yield_foreign_used,spread_used,spread_used+1)
    checks={
        'Equal yields + equal spreads => identical results':all(abs(equal['usd'][k]-equal['foreign'][k])<1e-10 for k in ['cost_equity','cost_debt','wacc']),
        'Zero debt => WACC equals cost of equity':all(abs(zero[c]['wacc']-zero[c]['cost_equity'])<1e-10 for c in ['usd','foreign']),
        'Foreign spread override leaves USD unchanged':all(abs(changed['usd'][k]-out['usd'][k])<1e-10 for k in ['cost_equity','cost_debt','wacc']),
    }
    for name,pair in checks.items(): st.write(('✅' if pair else '❌')+' '+name)

st.subheader('Sources, observations & freshness')
st.caption(f'Latest fetch attempt: {fetch_time}. This is the retrieval time, NOT necessarily the source observation date. Data is cached for up to 60 minutes (TE quotes: 10 minutes).')
source_rows=[
    {'Input':'Industry unlevered betas','Source':beta_source,'Source date':'Jan 2026 (Damodaran published analysis)','Link':DAMODARAN_BETA_HTML,'Warning':beta_error or ''},
    {'Input':'BBB USD borrowing spread','Source':bbb_source,'Source date':'Jan 2026 (Damodaran published analysis)','Link':DAMODARAN_RATING,'Warning':bbb_error or ''},
    {'Input':'Corporate taxes','Source':tax_source,'Source date':'2026 OECD database (reference estimates NOT verified)','Link':OECD_2026,'Warning':tax_error or ''},
    {'Input':'U.S. 10Y yield','Source':us_yield_source,'Source date':us_checked+' (retrieval time; quote date unavailable)','Link':TE_BONDS,'Warning':us_yield_error or ''},
    {'Input':f'{country} 10Y yield','Source':foreign_yield_source,'Source date':foreign_checked+' (retrieval time; quote date unavailable)','Link':TE_BONDS,'Warning':foreign_yield_error or ''},
]
st.dataframe(pd.DataFrame(source_rows),hide_index=True,use_container_width=True)
if beta_error or bbb_error or tax_error or us_yield_error or foreign_yield_error:
    st.warning('Some inputs could not be verified from live machine-readable sources. Inspect source warnings above and use manual overrides. Reference values are not live observations.')
st.markdown(f'**Primary sources:** [Damodaran industry betas]({DAMODARAN_BETA}) · [Damodaran BBB spread]({DAMODARAN_RATING}) · [OECD 2026 taxes]({OECD_REPORT}) · [Trading Economics 10Y bonds]({TE_BONDS})')
