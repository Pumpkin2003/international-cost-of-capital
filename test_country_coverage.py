import pytest
from data_sources import parse_te_country_list

HTML='''<html><table><thead><tr><th>Country</th><th>Last</th><th>Previous</th><th>Reference</th><th>Unit</th></tr></thead><tbody>'''+''.join(
    f'<tr><td>{x}</td><td>{v}</td><td>3.0</td><td>Nov/26</td><td>%</td></tr>'
    for x,v in [('United States','5.15'),('Germany','3.39'),('France','4.92'),('Colombia','12.7'),('Singapore','2.33'),('Ireland','3.53'),('Sweden','3.10'),('Italy','4.43'),('Belgium','4.36'),('Austria','3.61'),('Finland','3.77'),('Japan','2.86'),('Canada','3.86'),('Australia','5.14'),('Norway','4.38'),('Portugal','3.82')]
)+'''<tr><td>Report</td><td>90000</td><td></td><td>Jul/21</td><td>%</td></tr><tr><td>Andorra</td><td></td><td></td><td></td><td></td></tr></tbody></table></html>'''

def test_broad_yields():
    result=parse_te_country_list(HTML)
    assert result['Colombia']['rate']==12.7
    assert result['Singapore']['observed']=='Nov/26'
    assert 'Andorra' not in result
    assert 'Report' not in result
    assert len(result)==16

def test_reject_unidentified_tables():
    with pytest.raises(ValueError):parse_te_country_list('<html><table><tr><td>France</td><td>4.92</td></tr></table></html>')
