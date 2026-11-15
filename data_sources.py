"""Source loaders with explicit freshness, provenance and conservative parsing.
All yield and tax rates are percentage points (e.g., 5.145 = 5.145%).
"""
from __future__ import annotations
import io
import re
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup

OECD_API = ('https://sdmx.oecd.org/public/rest/data/'
            'OECD.CTP.TPS,DSD_TAX_CIT@DF_CIT,2.0/'
            '.A.CIT_C.ST.PT_INC_TAX.S13._Z._Z._Z'
            '?startPeriod=2025&dimensionAtObservation=AllDimensions&format=csvfilewithlabels')
SNAPSHOT = Path(__file__).with_name('oecd_combined_tax_snapshot.csv')
BETA_SNAPSHOT = Path(__file__).with_name('betas.xls')

# Only recognized aliases; never fall back to unrelated jurisdictions.
ALIASES = {'Korea':'South Korea','Korea, Rep.':'South Korea','Korea, Republic of':'South Korea',
           'Türkiye':'Turkey','Turkiye':'Turkey','Czechia':'Czech Republic',
           'Viet Nam':'Vietnam','United States of America':'United States',
           'United Kingdom of Great Britain and Northern Ireland':'United Kingdom',
           'Slovak Republic':'Slovakia'}

def parse_oecd_csv(content):
    df = pd.read_csv(io.BytesIO(content) if isinstance(content,bytes) else io.StringIO(content),low_memory=False)
    required = {'MEASURE','TARGETING','SECTOR','TIME_PERIOD','OBS_VALUE','REF_AREA'}
    if not required.issubset(df.columns):
        raise ValueError(f'OECD CSV missing {sorted(required-set(df.columns))}')
    df = df[(df['MEASURE']=='CIT_C') & (df['TARGETING']=='ST') & (df['SECTOR']=='S13')].copy()
    if 'FREQ' in df: df=df[df['FREQ']=='A']
    df['OBS_VALUE']=pd.to_numeric(df['OBS_VALUE'],errors='coerce')
    df['TIME_PERIOD']=pd.to_numeric(df['TIME_PERIOD'],errors='coerce')
    df=df.dropna(subset=['OBS_VALUE','TIME_PERIOD','REF_AREA'])
    df=df[df['OBS_VALUE'].between(0,65)]
    df=df.sort_values(['REF_AREA','TIME_PERIOD']).drop_duplicates('REF_AREA',keep='last')
    if len(df)<10: raise ValueError('Too few combined statutory tax observations')
    names=df['Reference area'] if 'Reference area' in df else df['REF_AREA']
    out={}
    for (_,row), name in zip(df.iterrows(),names):
        name=ALIASES.get(str(name).strip(),str(name).strip())
        out[name]={'rate':float(row['OBS_VALUE']),'year':int(row['TIME_PERIOD']),'code':str(row['REF_AREA'])}
    return out

def fetch_oecd(get_fn):
    try:
        response=get_fn(OECD_API)
        rows=parse_oecd_csv(response.content)
        return rows,'OECD SDMX API (automatic)',None
    except Exception as e:
        try:
            rows=parse_oecd_csv(SNAPSHOT.read_bytes())
            return rows,'Bundled OECD 2026 CSV snapshot (NOT live)',f'OECD API fetch failed: {type(e).__name__}: {e}'
        except Exception as fall:
            return {},'OECD data unavailable',f'OECD API: {e}; snapshot: {fall}'

def parse_te_bonds(html,country):
    """Read the public 10-year bonds HTML by column header, not loose text matches.
    Returns (rate, observed_date_text); refuses unsupported or ambiguous tables.
    """
    soup=BeautifulSoup(html,'html.parser')
    targets={country.lower(),country.lower()+' 10y'}
    for table in soup.select('table'):
        header=[]
        for tr in table.select('tr')[:4]:
            cells=[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'],recursive=False)]
            if any('yield'==re.sub(r'[^a-z]','',x.lower()) for x in cells):
                header=cells; break
        if not header: continue
        yield_indexes=[i for i,h in enumerate(header) if h.strip().lower()=='yield']
        if len(yield_indexes)!=1: continue
        yi=yield_indexes[0]
        date_indexes=[i for i,h in enumerate(header) if h.strip().lower()=='date']
        for tr in table.select('tr'):
            cells=[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'],recursive=False)]
            if len(cells)<=yi: continue
            # Rows can begin with an icon/flag cell, then country.
            def is_country_cell(value):
                cleaned = re.sub(r'\s+', ' ', value.lower()).strip()
                # Allow a preceding flag emoji; reject prefixes made of letters.
                return any(cleaned == t or (cleaned.endswith(t) and
                           not re.search(r'[a-z]', cleaned[:-len(t)])) for t in targets)
            if not any(is_country_cell(c) for c in cells[:min(yi,3)]):
                continue
            m=re.fullmatch(r'\s*([-+]?\d+(?:\.\d+)?)\s*%?\s*',cells[yi].replace(',',''))
            if not m: continue
            rate=float(m.group(1))
            if not (-5<rate<45): continue
            date = cells[date_indexes[0]] if date_indexes and len(cells)>date_indexes[0] else 'not displayed'
            return rate,date
    raise ValueError('No named 10-year yield row found in accessible HTML table')


def parse_country_yield_html(html):
    soup=BeautifulSoup(html,'html.parser')
    # Only a semantic yield value with explicit nearby 10-year / 10Y context.
    for tr in soup.select('tr'):
        txt=tr.get_text(' ',strip=True)
        if re.search(r'10\s*[- ]?year|10Y',txt,re.I):
            cells=[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'],recursive=False)]
            for c in cells[1:]:
                if re.fullmatch(r'\d{1,2}(?:\.\d{1,5})?%?',c):
                    x=float(c.rstrip('%'))
                    if -5<x<45: return x,'not displayed'
    raise ValueError('10-year yield not identified reliably')
