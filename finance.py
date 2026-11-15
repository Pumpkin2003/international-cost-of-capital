"""Finance model: percentage values are entered as percent points, e.g. 6.5."""

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
    spread_foreign = us_spread_pct if foreign_spread_pct is None else foreign_spread_pct
    debt_to_equity = debt / (1 - debt)
    beta_l = beta_u * (1 + (1 - tax) * debt_to_equity)
    def one(yield_pct, spread_pct):
        ke = yield_pct + beta_l * erp_pct
        kd = yield_pct + spread_pct
        wacc = (1 - debt) * ke + debt * kd * (1 - tax)
        return {'cost_equity':ke, 'cost_debt':kd, 'wacc':wacc}
    return {'levered_beta':beta_l,
            'usd':one(us_yield_pct, us_spread_pct),
            'foreign':one(local_yield_pct, spread_foreign)}
