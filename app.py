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
import pycountry
from bs4 import BeautifulSoup
from finance import cost_of_capital
from data_sources import fetch_oecd, parse_te_bonds, parse_te_country_page, parse_te_country_list, TE_COUNTRY_LIST_URL, BETA_SNAPSHOT, OECD_API

st.set_page_config(page_title='International Cost of Capital', page_icon='🌐', layout='wide')

DAMODARAN_BETA = 'https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls'
DAMODARAN_BETA_HTML = 'https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/Betas.html'
DAMODARAN_RATING = 'https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html'
OECD_2026 = 'https://www.oecd.org/en/data/datasets/corporate-income-tax-rates-database.html'
OECD_REPORT = 'https://www.oecd.org/en/publications/corporate-tax-statistics-2026_73af6222-en/full-report/statutory-corporate-income-tax-rates_ce84abb9.html'
TE_BONDS = 'https://tradingeconomics.com/bonds'

# OECD 2026 combined statutory reference rates, checked against lecture slide 550.
# The app attempts a live retrieval first and labels these published-reference fallbacks.
REFERENCE_TAX = {
    'United States':25.5, 'Germany':30.1, 'United Kingdom':25.0,
    'France':36.1, 'Japan':29.7, 'Canada':26.0, 'Australia':30.0,
    'Italy':27.8, 'Spain':25.0, 'Netherlands':25.8, 'Switzerland':19.5,
    'Sweden':20.6, 'Norway':22.0, 'Denmark':22.0, 'Ireland':12.5,
    'Poland':19.0, 'Mexico':30.0, 'South Korea':27.5,
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
    try:
        frame=parse_beta_table(pd.read_excel(BETA_SNAPSHOT,sheet_name=None,header=None).values())
        return frame,'Bundled Damodaran XLS snapshot (NOT live)', '; '.join(errors)
    except Exception as err:
        raise RuntimeError('Industry betas unavailable: '+ '; '.join(errors) + '; snapshot: ' + str(err))


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
    """Latest combined statutory CIT observations from OECD; dated local fallback."""
    return fetch_oecd(get)


def fetch_country_yield(country):
    """Try Trading Economics bonds table and country-specific 10-year quote page."""
    errors=[]
    try:
        rate, observed = parse_te_bonds(get(TE_BONDS).text, country)
        return rate, f'Trading Economics 10Y table | observed: {observed}', None
    except Exception as err:
        errors.append(f'bonds table: {err}')
    slug=COUNTRY_TE_SLUGS.get(country, country.lower().replace(' ', '-'))
    url=f'https://tradingeconomics.com/{slug}/government-bond-yield'
    try:
        rate, observed=parse_te_country_page(get(url).text,country)
        return rate, f'Trading Economics {country} 10Y page | observed: {observed}', None
    except Exception as err:
        errors.append(f'country page: {err}')
    # Coverage extension: the TE 10Y-by-country table contains significantly
    # more countries than the shorter major-bonds page. No hardcoded yields.
    try:
        observations = get_te_country_list()
        match = observations.get(country)
        if match is not None:
            return match['rate'], f'Trading Economics 10Y country list | observed: {match["observed"]} (monthly; rounded quote)', None
        errors.append('country list: selected country not published')
    except Exception as err:
        errors.append(f'country list: {err}')
    return None, 'Trading Economics: quote not validated', '; '.join(errors)


@st.cache_data(ttl=600,show_spinner='Fetching broader country yield coverage...')
def get_te_country_list():
    return parse_te_country_list(get(TE_COUNTRY_LIST_URL).text)


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
st.caption('USD and local-currency cost of equity, borrowing cost & WACC · Lecture-based model')

with st.sidebar:
    st.header('Inputs & data refresh')
    if st.button('↻ Refresh source data',use_container_width=True):
        get_sources.clear()
        quote.clear()
        get_te_country_list.clear()
        st.rerun()

betas,beta_source,beta_error,bbb,bbb_source,bbb_error,taxes,tax_source,tax_error,fetch_time=get_sources()

with st.sidebar:
    industries=betas['Industry'].tolist()
    default_industry='Software (System & Application)'
    industry=st.selectbox('Industry',industries,index=industries.index(default_industry) if default_industry in industries else 0)
    # ISO countries preserve the professor's 'any country' choice. Availability
    # is determined separately from actually published 10Y observations.
    iso_names = {item.name for item in pycountry.countries}
    iso_names -= {'United States', 'United Kingdom'}  # canonical labels retained below
    alias_names = {'United States', 'United Kingdom', 'South Korea', 'Czech Republic',
                   'Turkey', 'Vietnam', 'Russia', 'Taiwan', 'Bolivia', 'Tanzania'}
    available_te = {}
    te_list_error = None
    try:
        available_te = get_te_country_list()
    except Exception as err:
        te_list_error = str(err)
    country_options = sorted((set(COUNTRIES) | set(taxes) | iso_names | alias_names | set(available_te)) - {'Euro area'})
    country=st.selectbox('Target country',country_options,index=country_options.index('United States'))
    if country in available_te:
        st.caption('10Y yield listed by Trading Economics (automatic quote available).')
    else:
        st.caption('This country may need a manual 10Y yield if no validated country quote is available.')
    erp=st.number_input('Equity risk premium (%)',min_value=0.0,max_value=50.0,value=6.5,step=.25)
    debt=st.slider('Debt financing (%)',min_value=0,max_value=95,value=30,step=1)
    use_foreign_tax=st.toggle('Use selected-country tax rate',value=False,help='Off = U.S. project tax rate. The chosen tax rate applies to both sides.')

us_yield,us_yield_source,us_yield_error,us_checked=quote('United States')
foreign_yield,foreign_yield_source,foreign_yield_error,foreign_checked=(us_yield,us_yield_source,us_yield_error,us_checked) if country=='United States' else quote(country)
beta_auto=float(betas.loc[betas.Industry==industry,'Unlevered beta'].iloc[0])

with st.sidebar.expander('Overrides & missing live data',expanded=us_yield is None or foreign_yield is None):
    st.caption('Values are in percent points. Overrides stay visible and are used immediately.')
    override_beta=st.checkbox('Manual unlevered beta')
    beta=st.number_input('Unlevered beta',0.0,10.0,beta_auto,0.05,disabled=not override_beta)
    override_tax_us=st.checkbox('Manual U.S. corporate tax',value=False)
    tax_us=st.number_input('U.S. combined statutory tax (%)',0.0,60.0,float(taxes.get('United States',{'rate':25.5})['rate']),0.1,disabled=not override_tax_us)
    override_tax_foreign=st.checkbox('Manual selected-country corporate tax',value=country not in taxes)
    tax_foreign=st.number_input('Selected-country tax (%)',0.0,60.0,float(taxes.get(country,{'rate':25.0})['rate']),0.1,disabled=not override_tax_foreign)
    override_spread=st.checkbox('Manual USD BBB spread')
    spread_us=st.number_input('USD BBB spread (%)',0.0,30.0,float(bbb),0.05,disabled=not override_spread)
    override_us=st.checkbox('Manual U.S. 10Y yield',value=us_yield is None)
    y_us=st.number_input('U.S. 10Y government yield (%)',min_value=-5.0,max_value=40.0,
                         value=float(us_yield) if us_yield is not None else None,step=.05,
                         placeholder='Required: enter verified U.S. yield',disabled=not override_us,
                         key='manual_us_10y')
    if country=='United States':
        override_local=False
        y_local=None
        st.caption('United States selected: foreign-currency comparison uses the same U.S. yield automatically.')
    else:
        override_local=st.checkbox(f'Manual {country} 10Y yield',value=foreign_yield is None,key=f'override_yield_{country}')
        y_local=st.number_input(f'{country} 10Y government yield (%)',min_value=-5.0,max_value=40.0,
                                value=float(foreign_yield) if foreign_yield is not None else None,
                                step=.05,placeholder=f'Required: enter verified {country} yield',
                                disabled=not override_local,key=f'manual_yield_{country}')
    if us_yield is None or foreign_yield is None:
        st.warning('One or more Trading Economics quotes could not be validated. No assumed 4% yield is inserted. Enter the missing values manually using a dated source.')
    override_foreign_spread=st.checkbox('Manual foreign-currency BBB spread',value=False)
    spread_foreign=st.number_input('Foreign-currency BBB spread (%)',0.0,30.0,float(spread_us),.05,disabled=not override_foreign_spread,help='Off: automatically convert the USD spread using (1 + foreign yield) / (1 + USD yield). On: change only foreign-side debt and WACC.')

beta_used=beta if override_beta else beta_auto
spread_used=spread_us if override_spread else bbb
tax_used=(tax_foreign if override_tax_foreign else taxes.get(country,{'rate':25.0})['rate']) if use_foreign_tax else (tax_us if override_tax_us else taxes.get('United States',{'rate':25.5})['rate'])
yield_us_used=y_us if override_us else us_yield
yield_foreign_used=(y_us if override_us else us_yield) if country=='United States' else (y_local if override_local else foreign_yield)
spread_foreign_used=spread_foreign if override_foreign_spread else None

if yield_us_used is None or yield_foreign_used is None:
    st.error('Cannot calculate: a 10-year yield is missing. Open Overrides & missing live data, enter the missing government yield(s), and cite their dates. No default yield is invented.')
    st.dataframe(pd.DataFrame([
        {'Country':'United States','Source':us_yield_source,'Diagnostic':us_yield_error or '', 'Manual input':y_us},
        {'Country':country,'Source':foreign_yield_source,'Diagnostic':foreign_yield_error or '', 'Manual input':y_local if country!='United States' else y_us}
    ]),hide_index=True,use_container_width=True)
    st.stop()

out=cost_of_capital(beta_used,tax_used,debt,erp,yield_us_used,yield_foreign_used,spread_used,spread_foreign_used)

st.subheader('Project financing comparison')
st.caption(f'{industry} · {country} · {debt}% debt · {erp:.2f}% equity risk premium · {tax_used:.2f}% common project tax rate')
if override_us or override_local:
    st.warning('Manual yield input(s) are active. The displayed WACC is a scenario estimate, NOT a fully verified live-market result. Country-specific overrides do not carry over to other countries.')
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

with st.expander('Calculation method (International Valuation lecture slides 574, 577, 583-585)',expanded=False):
    st.markdown(r'''
- **Relevered beta:** $\beta_L = \beta_U[1+(1-T)(D/E)]$ with $D/E = w_D/(1-w_D)$.
- **USD cost of equity:** $k_{e,USD}=y_{USD}+\beta_L\cdot ERP$.
- **Foreign cost of equity:** $1+k_{e,F}=(1+k_{e,USD})(1+y_F)/(1+y_{USD})$ (rates as decimals).
- **USD pretax cost of debt:** $k_{d,USD}=y_{USD}+s_{USD}$.
- **Foreign BBB spread (automatic):** $s_F=s_{USD}(1+y_F)/(1+y_{USD})$; then $k_{d,F}=y_F+s_F$.
- **WACC:** $WACC=(1-w_D)k_e+w_Dk_d(1-T)$.
- The same project tax rate, debt share, ERP and relevered beta are used for both currencies.
- When enabled, the manual foreign spread override affects only foreign debt cost and foreign WACC.
- The foreign-currency conversion follows the **International Valuation lecture, slides 583–585**. Government yields are proxies; the model assumes a common project tax rate, leverage ratio and ERP, and no separate country equity risk premium.
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
                      'U.S. BBB spread (%)':spread_used,'Foreign BBB spread (%)':out['foreign_spread_used'],
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

st.subheader('Data sources & observation dates')
st.caption(f'Latest fetch attempt: {fetch_time}. This is NOT the observation date. Data is cached up to 60 minutes (bond quotes: 10 minutes). A manual value is not a live quote.')
source_rows=[
    {'Input':'Industry unlevered betas','Source':beta_source,'Source date':'Jan 2026 (Damodaran published analysis)','Link':DAMODARAN_BETA_HTML,'Warning':beta_error or ''},
    {'Input':'BBB USD borrowing spread','Source':bbb_source,'Source date':'Jan 2026 (Damodaran published analysis)','Link':DAMODARAN_RATING,'Warning':bbb_error or ''},
    {'Input':'Corporate taxes','Source':tax_source,'Source date':f"US {taxes.get('United States',{}).get('year','N/A')}; selected {taxes.get(country,{}).get('year','N/A')} (observation years)",'Link':OECD_API,'Warning':tax_error or ''},
    {'Input':'U.S. 10Y yield','Source':('MANUAL: user-provided' if override_us else us_yield_source),'Source date':us_yield_source+'; retrieved '+us_checked,'Link':TE_BONDS,'Warning':us_yield_error or ''},
    {'Input':f'{country} 10Y yield','Source':('MANUAL: user-provided' if (override_local or (country=='United States' and override_us)) else foreign_yield_source),'Source date':foreign_yield_source+'; retrieved '+foreign_checked,'Link':TE_BONDS,'Warning':foreign_yield_error or ''},
]
st.dataframe(pd.DataFrame(source_rows),hide_index=True,use_container_width=True)
if beta_error or bbb_error or tax_error or us_yield_error or foreign_yield_error:
    st.info('Some sources were unavailable or used a dated snapshot. Check the specific warning and observation year in the source table.')
st.markdown(f'**Primary sources:** [Damodaran industry betas]({DAMODARAN_BETA}) · [Damodaran BBB spread]({DAMODARAN_RATING}) · [OECD 2026 taxes]({OECD_REPORT}) · [Trading Economics 10Y bonds]({TE_BONDS}) · [Trading Economics full 10Y country list]({TE_COUNTRY_LIST_URL})')
