from finance import cost_of_capital


def nearly(a, b, eps=1e-9):
    assert abs(a-b) < eps, (a,b)


def test_colombia_lecture_example():
    r=cost_of_capital(.8,35,30,6.5,4,12,1.5)
    nearly(r['levered_beta'], 0.8 * (1+.65*3/7))
    nearly(r['usd']['cost_equity'],10.648571428571428)
    nearly(r['usd']['cost_debt'],5.5)
    nearly(r['usd']['wacc'],8.5265)
    nearly(r['foreign']['cost_equity'], 100*((1+10.648571428571428/100)*(1.12/1.04)-1))
    nearly(r['auto_foreign_spread'],1.5*1.12/1.04)
    nearly(r['foreign']['wacc'],16.067)


def test_equal_yields():
    r=cost_of_capital(1.2,25,30,6.5,4,4,1.5)
    for key in ('cost_equity','cost_debt','wacc'):
        nearly(r['usd'][key],r['foreign'][key])


def test_no_debt():
    r=cost_of_capital(1.2,25,0,6.5,4,9,1.5)
    for side in ('usd','foreign'):
        nearly(r[side]['wacc'],r[side]['cost_equity'])


def test_foreign_spread_override():
    a=cost_of_capital(1.2,25,30,6.5,4,9,1.5)
    b=cost_of_capital(1.2,25,30,6.5,4,9,1.5,3.5)
    assert a['usd']==b['usd']
    nearly(a['foreign']['cost_equity'],b['foreign']['cost_equity'])
    assert a['foreign']['cost_debt'] != b['foreign']['cost_debt']
    assert a['foreign']['wacc'] != b['foreign']['wacc']
