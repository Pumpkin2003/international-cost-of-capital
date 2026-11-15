import unittest
from finance import cost_of_capital

class TestFinance(unittest.TestCase):
    def test_equal_yields(self):
        x=cost_of_capital(1.23,25.6,30,6.5,4.0,4.0,1.11)
        self.assertEqual(x['usd'],x['foreign'])
    def test_zero_debt(self):
        x=cost_of_capital(1.23,25.6,0,6.5,4.0,3.0,1.11)
        for side in ['usd','foreign']:
            self.assertAlmostEqual(x[side]['wacc'],x[side]['cost_equity'])
    def test_foreign_spread_only(self):
        a=cost_of_capital(1.23,25.6,30,6.5,4.0,3.0,1.11)
        b=cost_of_capital(1.23,25.6,30,6.5,4.0,3.0,1.11,3.11)
        self.assertEqual(a['usd'],b['usd'])
        self.assertNotEqual(a['foreign']['wacc'],b['foreign']['wacc'])
    def test_calculator_example(self):
        x=cost_of_capital(1.23,25.6,30,6.5,4.0,4.0,1.11)
        beta=1.23*(1+(1-.256)*(.3/.7))
        ke=4+beta*6.5
        kd=4+1.11
        wacc=.7*ke+.3*kd*(1-.256)
        self.assertAlmostEqual(x['levered_beta'],beta)
        self.assertAlmostEqual(x['usd']['wacc'],wacc)
if __name__=='__main__': unittest.main()
