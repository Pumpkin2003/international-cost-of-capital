from data_sources import parse_oecd_csv, parse_te_bonds, parse_te_country_page, SNAPSHOT

def test_oecd_combined_tax_filter():
    records = parse_oecd_csv(SNAPSHOT.read_bytes())
    # Combined statutory rates, NOT the federal-only US 21% rate.
    assert round(records['United States']['rate'],2) == 25.53
    assert round(records['Germany']['rate'],2) == 30.13
    assert records['United States']['year'] == 2026
    assert len(records) >= 100

def test_te_country_matches_yield_not_chg():
    html='''<table><thead><tr><th>Major10Y</th><th>Yield</th><th>Chg</th><th>Date</th></tr></thead><tbody>
    <tr><td>🇺🇸 United States</td><td>5.1450</td><td>0.0110</td><td>Nov/13</td></tr>
    <tr><td>Germany</td><td>3.3762</td><td>0.0506</td><td>Nov/13</td></tr></tbody></table>'''
    assert parse_te_bonds(html,'United States') == (5.145,'Nov/13')
    assert parse_te_bonds(html,'Germany') == (3.3762,'Nov/13')

def test_te_rejects_unspecified_page():
    try:
        parse_te_bonds('<html><p>Germany 3.3%</p></html>','Germany')
    except ValueError:
        pass
    else:
        raise AssertionError('Should reject page without a 10Y yield table')


def test_country_page_exact_actual():
    html='<html><h1>Germany 10-Year Bond Yield</h1><p>Actual</p><span>3.3762</span><p>Daily Change</p><span>0.0506%</span><p>Nov 13, 2026</p></html>'
    rate, date=parse_te_country_page(html, 'Germany')
    assert rate == 3.3762
    assert date == 'Nov 13, 2026'

def test_country_page_rejects_other_country_and_tenor():
    html='<html><h1>Germany 2-Year Bond Yield</h1><p>Actual 3.3762 Daily Change</p></html>'
    import pytest
    with pytest.raises(ValueError): parse_te_country_page(html, 'Germany')
    with pytest.raises(ValueError): parse_te_country_page(html.replace('Germany','France'), 'Germany')
