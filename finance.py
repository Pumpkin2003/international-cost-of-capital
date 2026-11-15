"""International cost of capital model based on lecture slides 574, 577, 583-585.

Rate arguments and outputs are percent points: 6.5 means 6.5%.
"""

def cost_of_capital(beta_u, tax_pct, debt_share_pct, erp_pct,
                    us_yield_pct, local_yield_pct, us_spread_pct,
                    foreign_spread_pct=None):
    tax = tax_pct / 100.0
    debt = debt_share_pct / 100.0
    if not 0 <= debt < 1:
        raise ValueError('Debt share must be >= 0 and < 100%.')
    if not 0 <= tax <= 1:
        raise ValueError('Tax rate must be between 0 and 100%.')
    if beta_u < 0:
        raise ValueError('Unlevered beta cannot be negative.')
    if (1 + us_yield_pct / 100) <= 0 or (1 + local_yield_pct / 100) <= 0:
        raise ValueError('Gross government yield factors must be positive.')

    beta_l = beta_u * (1 + (1 - tax) * debt / (1 - debt))
    factor = (1 + local_yield_pct / 100) / (1 + us_yield_pct / 100)
    ke_us = us_yield_pct + beta_l * erp_pct
    kd_us = us_yield_pct + us_spread_pct
    # Slide 583: convert the entire gross equity return, not just its risk-free portion.
    ke_local = 100 * ((1 + ke_us / 100) * factor - 1)
    # Slide 584: convert the credit spread by the gross government-yield ratio.
    auto_local_spread = us_spread_pct * factor
    local_spread = auto_local_spread if foreign_spread_pct is None else foreign_spread_pct
    kd_local = local_yield_pct + local_spread

    def report(ke, kd):
        return {'cost_equity':ke, 'cost_debt':kd,
                'wacc':(1 - debt) * ke + debt * kd * (1 - tax)}

    return {'levered_beta': beta_l,
            'conversion_factor': factor,
            'auto_foreign_spread': auto_local_spread,
            'foreign_spread_used': local_spread,
            'usd':report(ke_us,kd_us),
            'foreign':report(ke_local,kd_local)}
