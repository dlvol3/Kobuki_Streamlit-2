"""One Q1 model shared by the dashboard, solvers, charts and CSV exports."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from pathlib import Path
import json

import numpy as np


@dataclass(frozen=True)
class Case:
    price: float
    unit_variable_cost: float
    annual_fixed_cost: float
    base_units: tuple[float, ...]
    capex: float
    salvage: float
    initial_nwc: float
    nwc_ratio: float
    tax_rate: float
    risk_free: float
    credit_spread: float
    beta: float
    market_risk_premium: float
    debt_weight: float
    equity_weight: float
    life: int = 7

    @property
    def depreciation(self) -> float:
        return (self.capex - self.salvage) / self.life

    @property
    def kd(self) -> float:
        return self.risk_free + self.credit_spread

    @property
    def ke(self) -> float:
        return self.risk_free + self.beta * self.market_risk_premium

    @property
    def wacc(self) -> float:
        return self.debt_weight * self.kd * (1-self.tax_rate) + self.equity_weight*self.ke


def load_case(path: Path | None = None) -> Case:
    path = path or Path(__file__).parent / "data" / "case_inputs.json"
    values = json.loads(path.read_text())["inputs"]
    values["base_units"] = tuple(values["base_units"])
    case = Case(**values)
    if len(case.base_units) != case.life:
        raise ValueError("The unit-sales path must contain one observation per production year.")
    if abs(case.debt_weight+case.equity_weight-1)>1e-10:
        raise ValueError("Capital weights must sum to one.")
    return case


@dataclass(frozen=True)
class Year:
    year: int
    units: float
    baseline_units: float
    revenue: float
    variable_costs: float
    fixed_costs: float
    depreciation: float
    ebit: float
    tax: float
    nopat: float
    nwc: float
    change_nwc: float
    capex: float
    after_tax_salvage: float
    fcf: float
    pv: float


@dataclass(frozen=True)
class Result:
    sales_coefficient: float
    fixed_cost_change: float
    annual_fixed_cost: float
    npv: float
    irr: float | None
    irr_roots: tuple[float, ...]
    wacc: float
    years: tuple[Year, ...]
    price_coefficient: float = 1.0
    variable_cost_coefficient: float = 1.0
    demand_elasticity: float = 0.0
    effective_sales_coefficient: float = 1.0
    unit_price: float = 0.0
    unit_variable_cost: float = 0.0

    @property
    def cashflows(self) -> tuple[float, ...]:
        return tuple(y.fcf for y in self.years)

    def records(self) -> list[dict]:
        return [asdict(y) for y in self.years]


def irr_roots(cashflows) -> tuple[float, ...]:
    """Solve in x=1/(1+r); keep every admissible real root, r>-1."""
    roots = np.polynomial.polynomial.polyroots(np.asarray(cashflows, dtype=float))
    rates = sorted(1/x.real-1 for x in roots if abs(x.imag)<1e-7 and x.real>1e-12)
    unique = []
    for r in rates:
        if isfinite(r) and (not unique or abs(r-unique[-1])>1e-7):
            unique.append(float(r))
    return tuple(unique)


def _drivers(case, sales_coefficient, fixed_cost_change, price_coefficient,
             variable_cost_coefficient, demand_elasticity):
    """Validate a scenario and apply its hypothetical constant-elasticity response."""
    m, d = float(sales_coefficient), float(fixed_cost_change)
    if not isfinite(m) or m<0:
        raise ValueError("Sales coefficient must be finite and non-negative.")
    if not isfinite(d) or case.annual_fixed_cost+d<0:
        raise ValueError("Annual fixed operating costs cannot be negative.")
    p, v, e = map(float, (price_coefficient, variable_cost_coefficient, demand_elasticity))
    if not isfinite(p) or p<=0:
        raise ValueError("The price coefficient must be finite and strictly positive.")
    if not isfinite(v) or v<0:
        raise ValueError("The variable-cost coefficient must be finite and non-negative.")
    if not isfinite(e) or e<0:
        raise ValueError("The assumed demand elasticity must be finite and non-negative.")
    try:
        effective = m*p**(-e)
    except OverflowError as exc:
        raise ValueError("The price-demand combination produces non-finite volume.") from exc
    if not isfinite(effective) or not isfinite(case.price*p) or not isfinite(case.unit_variable_cost*v):
        raise ValueError("Scenario prices, costs and volumes must remain finite.")
    return m, d, p, v, e, effective


def model(case: Case, sales_coefficient: float = 1, fixed_cost_change: float = 0,
          *, price_coefficient: float = 1.0, variable_cost_coefficient: float = 1.0,
          demand_elasticity: float = 0.0) -> Result:
    """Price changes alter volume as m*p**(-elasticity), with unchanged capacity.

    Elasticity is a user-supplied scenario assumption, not an estimate from the case.
    All production years use the same demand, price and unit-cost coefficients.
    """
    m,d,p,v,e,effective = _drivers(case,sales_coefficient,fixed_cost_change,
                                  price_coefficient,variable_cost_coefficient,demand_elasticity)
    price, unit_cost = case.price*p, case.unit_variable_cost*v
    fixed = case.annual_fixed_cost+d
    initial = -case.capex-case.initial_nwc
    years = [Year(0,0,0,0,0,0,0,0,0,0,case.initial_nwc,case.initial_nwc,case.capex,0,initial,initial)]
    previous_nwc = case.initial_nwc
    for t, base_units in enumerate(case.base_units, 1):
        units = base_units*effective
        revenue = units*price
        variable = units*unit_cost
        ebit = revenue-variable-fixed-case.depreciation
        # Same immediate group-level tax-offset assumption as Group 4's workbook.
        tax = ebit*case.tax_rate
        nopat = ebit-tax
        # Year 7 NWC is zero after complete liquidation; do not add recovery twice.
        nwc = revenue*case.nwc_ratio if t<case.life else 0.0
        change = nwc-previous_nwc
        book = case.capex-case.life*case.depreciation
        salvage = case.salvage-case.tax_rate*(case.salvage-book) if t==case.life else 0.0
        fcf = nopat+case.depreciation-change+salvage
        years.append(Year(t,units,base_units,revenue,variable,fixed,case.depreciation,ebit,tax,nopat,nwc,change,0,salvage,fcf,fcf/(1+case.wacc)**t))
        previous_nwc = nwc
    cashflows = tuple(y.fcf for y in years)
    roots = irr_roots(cashflows)
    return Result(m,d,fixed,sum(y.pv for y in years),roots[0] if len(roots)==1 else None,
                  roots,case.wacc,tuple(years),p,v,e,effective,price,unit_cost)


def npv_only(case: Case, m: float, d: float, *, price_coefficient: float = 1.0,
             variable_cost_coefficient: float = 1.0, demand_elasticity: float = 0.0) -> float:
    """Independent cash-margin expression for fast sensitivity curves."""
    m,d,p,v,e,effective = _drivers(case,m,d,price_coefficient,
                                  variable_cost_coefficient,demand_elasticity)
    price, unit_cost = case.price*p, case.unit_variable_cost*v
    fixed = case.annual_fixed_cost+d
    result = -case.capex-case.initial_nwc
    previous_nwc = case.initial_nwc
    for t, q in enumerate(case.base_units, 1):
        cash_margin = q*effective*(price-unit_cost)-fixed
        ocf = cash_margin*(1-case.tax_rate)+case.depreciation*case.tax_rate
        nwc = q*effective*price*case.nwc_ratio if t<case.life else 0
        flow = ocf-(nwc-previous_nwc)+(case.salvage if t==case.life else 0)
        result += flow/(1+case.wacc)**t
        previous_nwc = nwc
    return float(result)


def solve_sales(case: Case, fixed_cost_change: float, *, price_coefficient: float = 1.0,
                variable_cost_coefficient: float = 1.0, demand_elasticity: float = 0.0) -> float | None:
    """Solve the demand coefficient before the selected price response."""
    kwargs = dict(price_coefficient=price_coefficient,
                  variable_cost_coefficient=variable_cost_coefficient,demand_elasticity=demand_elasticity)
    a = npv_only(case,0,fixed_cost_change,**kwargs)
    slope = npv_only(case,1,fixed_cost_change,**kwargs)-a
    if slope<=0:
        return None
    root = -a/slope
    return float(root) if root>=0 else None


def solve_fixed_cost(case: Case, sales_coefficient: float, *, price_coefficient: float = 1.0,
                     variable_cost_coefficient: float = 1.0, demand_elasticity: float = 0.0) -> float | None:
    tax_adjusted_annuity = (1-case.tax_rate)*sum((1+case.wacc)**-t for t in range(1,case.life+1))
    value = npv_only(case,sales_coefficient,0,price_coefficient=price_coefficient,
                     variable_cost_coefficient=variable_cost_coefficient,demand_elasticity=demand_elasticity)
    if tax_adjusted_annuity<=0:
        return None
    root = value/tax_adjusted_annuity
    # A financial break-even that needs negative operating cost is infeasible.
    return float(root) if root>=-case.annual_fixed_cost else None


def solve_price(case: Case, sales_coefficient: float, fixed_cost_change: float, *,
                variable_cost_coefficient: float = 1.0, demand_elasticity: float = 0.0,
                lower: float = 0.5, upper: float = 1.5) -> tuple[float, ...]:
    """Return every financial break-even price coefficient in [lower, upper].

    The constant-elasticity model has NPV(p)=C+A*p**(1-e)-B*p**(-e).
    Its derivative has at most one positive stationary point. Splitting there
    makes each segment monotone and preserves two roots or a tangent root.
    This is a bounded scenario search; roots outside the bounds are not returned.
    """
    lo,hi = float(lower),float(upper)
    if not isfinite(lo) or not isfinite(hi) or lo<=0 or hi<lo:
        raise ValueError("Price search bounds must be finite, positive and ordered.")
    m,d,p,v,e,effective = _drivers(case,sales_coefficient,fixed_cost_change,
                                  1.0,variable_cost_coefficient,demand_elasticity)
    constant = npv_only(case,0,d)
    coefficient_a = npv_only(case,m,d,variable_cost_coefficient=0)-constant
    coefficient_b = coefficient_a-(npv_only(case,m,d,variable_cost_coefficient=v)-constant)
    def value(price):
        return npv_only(case,m,d,price_coefficient=price,
                        variable_cost_coefficient=v,demand_elasticity=e)
    points = [lo,hi]
    denominator = coefficient_a*(e-1)
    if denominator!=0:
        critical = e*coefficient_b/denominator
        if lo<critical<hi:
            points.append(critical)
    points = sorted(set(points))
    values = [value(x) for x in points]
    tolerance = max(1e-7,max(abs(constant),abs(coefficient_a),abs(coefficient_b))*1e-12)
    roots = [x for x,y in zip(points,values) if abs(y)<=tolerance]
    for left,right,fl,fr in zip(points,points[1:],values,values[1:]):
        if abs(fl)<=tolerance or abs(fr)<=tolerance or fl*fr>=0:
            continue
        for _ in range(100):
            mid = (left+right)/2
            fm = value(mid)
            if abs(fm)<1e-9 or right-left<1e-14:
                break
            if (fl<0)==(fm<0):
                left,fl = mid,fm
            else:
                right,fr = mid,fm
        roots.append(mid)
    unique = []
    for root in sorted(roots):
        if not unique or abs(root-unique[-1])>1e-9:
            unique.append(float(root))
    return tuple(unique)


def solve_unit_variable_cost(case: Case, sales_coefficient: float, fixed_cost_change: float,
                             *, price_coefficient: float = 1.0,
                             demand_elasticity: float = 0.0) -> float | None:
    """Maximum actual EUR/can variable cost at NPV=0, holding other drivers fixed.

    None means even zero unit variable cost cannot clear the hurdle, or no
    positive volume exists so a unique unit-cost threshold is unavailable.
    """
    m,d,p,v,e,effective = _drivers(case,sales_coefficient,fixed_cost_change,
                                  price_coefficient,1.0,demand_elasticity)
    zero_cost_value = npv_only(case,m,d,price_coefficient=p,
                              variable_cost_coefficient=0,demand_elasticity=e)
    per_euro_cost_pv = (1-case.tax_rate)*sum(q*effective/(1+case.wacc)**t
                                           for t,q in enumerate(case.base_units,1))
    if per_euro_cost_pv<=0:
        return None
    root = zero_cost_value/per_euro_cost_pv
    return float(root) if root>=0 else None

