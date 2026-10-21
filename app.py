from __future__ import annotations

from html import escape
import json
from math import ceil, isfinite
from pathlib import Path

import pandas as pd
import streamlit as st
from echarts_component import st_echarts
from finance import load_case, model, solve_sales, solve_fixed_cost, solve_price, solve_unit_variable_cost
from charts import options, sensitivity, pricing_options, decision_frontier_options
from controls import vertical_drivers

ROOT = Path(__file__).parent
st.set_page_config(page_title='Wake Up! · investment decision', page_icon='🥤', layout='wide')
st.html((ROOT/'assets/app.css').read_text())
case = load_case()
source = json.loads((ROOT/'data/case_inputs.json').read_text())
for key, value in {'sales_coefficient':1.0, 'fixed_cost_change':0.0, 'scenario_revision':0,
                   'action_note':'', 'action_error':'', 'axis':'Sales coefficient',
                   'price_per_can':case.price, 'variable_cost_per_can':case.unit_variable_cost,
                   'demand_elasticity':0.0}.items():
    st.session_state.setdefault(key, value)


def commercial_inputs():
    for name, fallback in [('price_per_can',case.price),('variable_cost_per_can',case.unit_variable_cost),('demand_elasticity',0.0)]:
        if st.session_state.get(name) is None:
            st.session_state[name] = fallback
    return dict(price_coefficient=st.session_state.price_per_can/case.price,
                variable_cost_coefficient=st.session_state.variable_cost_per_can/case.unit_variable_cost,
                demand_elasticity=st.session_state.demand_elasticity)


def clear_action():
    st.session_state.action_note = ''
    st.session_state.action_error = ''


def change_drivers(sales, cost, note=''):
    st.session_state.sales_coefficient = float(sales)
    st.session_state.fixed_cost_change = float(cost)
    st.session_state.action_note = note
    st.session_state.action_error = ''
    st.session_state.scenario_revision += 1


def receive_drivers():
    values = st.session_state.get('drivers', {}).get('scenario', {})
    if values.get('revision') != st.session_state.scenario_revision:
        return
    sales, cost = values.get('sales'), values.get('cost')
    if sales is None or cost is None:
        return
    if not isfinite(float(sales)) or not isfinite(float(cost)) or sales < 0 or cost < -case.annual_fixed_cost:
        st.session_state.action_error = 'Demand and total annual fixed costs must be non-negative.'
        return
    if abs(float(sales)-st.session_state.sales_coefficient) < 1e-12 and abs(float(cost)-st.session_state.fixed_cost_change) < 1e-8:
        return
    st.session_state.sales_coefficient = float(sales)
    st.session_state.fixed_cost_change = float(cost)
    clear_action()


def preset(sales, cost, price=None, elasticity=0.0):
    st.session_state.price_per_can = case.price if price is None else price
    st.session_state.variable_cost_per_can = case.unit_variable_cost
    st.session_state.demand_elasticity = elasticity
    change_drivers(sales, cost)


def reset():
    preset(1.0, 0.0)


def reset_q2():
    q = source['presets']['q2']
    preset(q['sales_coefficient'], q['fixed_cost_change'])


def downside():
    preset(1.1*.95, -20000)


def price_stress():
    preset(1.1*.95, -20000, case.price*1.05, 2.0)


def execution_budget():
    preset(1.1*.95, -10000, case.price*1.02, 1.0)
    st.session_state.variable_cost_per_can = 1.55
    st.session_state.action_note = 'Illustrative recovery: demand −5% vs Q2, price +2%, unit cost €1.55, elasticity 1 and €10,000 extra annual execution cost. NPV includes that spending.'


def break_even_sales():
    cost = st.session_state.fixed_cost_change
    root = solve_sales(case, cost, **commercial_inputs())
    if root is None:
        st.session_state.action_error = 'No non-negative demand break-even under the selected price, unit cost and fixed costs.'
        return
    change_drivers(root, cost, f'Other assumptions held constant. Demand break-even: {root:.6f}× Q1 before the price response.')


def break_even_costs():
    sales = st.session_state.sales_coefficient
    root = solve_fixed_cost(case, sales, **commercial_inputs())
    if root is None:
        st.session_state.action_error = 'Even zero annual fixed costs cannot reach break-even. Reassess demand, price and unit cost.'
        return
    change_drivers(sales, root, f'Other assumptions held constant. Annual fixed-cost ceiling: €{case.annual_fixed_cost+root:,.2f}.')


def break_even_price():
    k = commercial_inputs()
    roots = solve_price(case, st.session_state.sales_coefficient, st.session_state.fixed_cost_change,
                        variable_cost_coefficient=k['variable_cost_coefficient'], demand_elasticity=k['demand_elasticity'],
                        lower=.8, upper=1.3)
    if not roots:
        st.session_state.action_error = 'No price break-even found between €4.08 and €6.63. This is a bounded search; inspect the decision map.'
        return
    selected = min(roots, key=lambda r: abs(r-k['price_coefficient']))
    st.session_state.price_per_can = case.price*selected
    st.session_state.action_note = ('Price boundary: '+', '.join(f'€{case.price*r:.4f}' for r in roots)+
                                    '/can. Closest boundary selected; all other assumptions held constant.')
    st.session_state.action_error = ''


def protect_unit_cost():
    k = commercial_inputs()
    root = solve_unit_variable_cost(case, st.session_state.sales_coefficient, st.session_state.fixed_cost_change,
                                   price_coefficient=k['price_coefficient'], demand_elasticity=k['demand_elasticity'])
    if root is None:
        st.session_state.action_error = 'No feasible non-negative unit-cost ceiling under these assumptions.'
        return
    st.session_state.variable_cost_per_can = root
    st.session_state.action_note = f'Unit variable-cost ceiling: €{root:.4f}/can. Demand, price and annual fixed costs held constant.'
    st.session_state.action_error = ''


def keep_axis_selected():
    if st.session_state.get('axis') is None:
        st.session_state.axis = 'Sales coefficient'


m, d = st.session_state.sales_coefficient, st.session_state.fixed_cost_change
k = commercial_inputs()
active = model(case, m, d, **k)
baseline = model(case)
q2 = model(case, 1.1, -20000)
original_commercial = abs(k['price_coefficient']-1)<1e-10 and abs(k['variable_cost_coefficient']-1)<1e-10 and k['demand_elasticity']==0
is_q1 = abs(m-1)<1e-10 and abs(d)<1e-8 and original_commercial
is_q2 = abs(m-1.1)<1e-10 and abs(d+20000)<1e-8 and original_commercial
scenario_label = 'Q1 baseline' if is_q1 else 'Q2 baseline' if is_q2 else 'Management scenario'
be_sales = solve_sales(case, d, **k)
be_cost = solve_fixed_cost(case, m, **k)
unit_ceiling = solve_unit_variable_cost(case, m, d, price_coefficient=k['price_coefficient'], demand_elasticity=k['demand_elasticity'])
price_roots = solve_price(case, m, d, variable_cost_coefficient=k['variable_cost_coefficient'], demand_elasticity=k['demand_elasticity'], lower=.8, upper=1.3)
if abs(active.npv)<=1:
    status, css, verdict = 'BREAK-EVEN', 'neutral', 'The project just earns its capital cost; there is no value cushion.'
elif active.npv>0:
    status, css, verdict = 'ACCEPT', 'accept', 'Positive NPV under these assumptions. Validate demand and delivery costs before committing.'
else:
    status, css, verdict = 'REJECT', 'reject', 'The full investment falls short. Test a credible recovery plan before committing.'
st.html(f'''<div class="page-top"><div><div class="case-line">Group 2: Jorge Pablo Yue</div><h1>Wake Up! investment decision</h1></div><div class="case-tag">{scenario_label} · 7 years · EUR</div></div>
<div class="verdict {css}"><div class="decision {css}" role="status" aria-live="polite">{status}</div><div class="verdict-copy"><strong>{verdict}</strong><span>Actual volume {active.effective_sales_coefficient:.4f}× Q1 · price €{active.unit_price:.3f}/can · fixed costs €{active.annual_fixed_cost:,.0f}/year</span></div></div>''')

irr_display = f'{active.irr:.6f}' if active.irr is not None else 'Unavailable'
irr_note = f'{active.irr*100:.4f}% · WACC {case.wacc:.6f}' if active.irr is not None else 'Use NPV; no unique admissible IRR.'
npv_css = 'gold' if abs(active.npv)<=1 else 'green' if active.npv>0 else 'red'
st.html(f'''<div class="metric-grid">
<div class="metric"><div class="metric-label">Net present value</div><div class="metric-value {npv_css}">€{active.npv:,.0f}</div><div class="metric-note">€{active.npv:,.2f} · {active.npv-q2.npv:+,.0f} vs Q2</div></div>
<div class="metric"><div class="metric-label">Internal rate of return</div><div class="metric-value">{irr_display}</div><div class="metric-note">{irr_note}</div></div>
<div class="metric"><div class="metric-label">Contribution per can</div><div class="metric-value">€{active.unit_price-active.unit_variable_cost:.3f}</div><div class="metric-note">Net selling price less unit variable cost</div></div>
<div class="metric"><div class="metric-label">Actual volume / Q2</div><div class="metric-value violet">{active.effective_sales_coefficient/1.1:.4f}×</div><div class="metric-note">Includes the assumed price response</div></div></div>''')

st.html('''<div class="business-context"><strong>What can move sales?</strong> The case's Q2 uplift depends on promotions and advantageous displays. Weaker retail execution, trial or repeat purchase, competitor offers and price resistance are hypotheses to validate.<br><strong>Decision rule:</strong> protect contribution and cash flow together. A higher price can lose units; cheaper inputs or reduced promotion can weaken demand.</div>
<div class="jump-links"><a href="#sales-costs">Sales & costs</a><a href="#pricing-decisions">Price & demand map</a><a href="#recovery-options">Recovery choices</a></div>''')

b1,b2,b3,b4 = st.columns(4)
b1.button('Q1 baseline', key='reset_q1', on_click=reset, type='primary' if is_q1 else 'secondary', width='stretch')
b2.button('Q2 baseline', key='reset_q2', on_click=reset_q2, type='primary' if is_q2 else 'secondary', width='stretch')
b3.button('Q2 demand −5%', key='downside', on_click=downside, width='stretch')
b4.button('Try price +5% · response 2', key='price_stress', on_click=price_stress, width='stretch', help='Hypothetical: Q2 demand -5%, price +5%, elasticity 2. Not an estimated demand forecast.')

st.html('<div id="sales-costs" class="section-title">Operating choices</div>')
p1,p2,p3 = st.columns(3)
p1.number_input('Net selling price · EUR/can', min_value=.10, value=None, step=.05, format='%.4f', key='price_per_can', on_change=clear_action, help='Realised price after discounts and trade allowances. Original €5.10.')
p2.number_input('Variable cost · EUR/can', min_value=0.0, value=None, step=.02, format='%.4f', key='variable_cost_per_can', on_change=clear_action, help='Original €1.60. Validate procurement, quality and distribution implications.')
p3.number_input('Assumed price elasticity · magnitude', min_value=0.0, max_value=5.0, value=None, step=.25, format='%.2f', key='demand_elasticity', on_change=clear_action, help='0 holds units fixed. Higher values imply a stronger unit-sales response to price; this case supplies no estimate.')
st.caption('Illustrative demand rule: actual cans = Q1 cans × demand coefficient × (price / €5.10)^(−elasticity). At elasticity 0, changing price holds units fixed. All controls apply in every production year; WACC remains 0.102974.')

controls_col, plots_col = st.columns([.9,2.3], gap='large')
with controls_col:
    st.html('<div class="panel-heading">Demand & annual fixed costs</div><div class="panel-sub">Demand is measured before any price response.</div>')
    vertical_drivers(data={'sales':m,'cost':d,'revision':st.session_state.scenario_revision,
                          'sales_max':max(2.0,ceil(m*10)/10),'cost_max':max(600000,ceil(d/10000)*10000)},
                     default={'scenario':{'sales':m,'cost':d,'revision':st.session_state.scenario_revision}},
                     on_scenario_change=receive_drivers,key='drivers')
    rows=[]
    for label,q in [('Year 1',case.base_units[0]),('Year 2',case.base_units[1]),('Years 3–7 · each',case.base_units[2])]:
        rows.append(f'<div class="sales-row"><span class="period">{label}</span><span class="actual">{q*active.effective_sales_coefficient:,.0f} cans<small>{q*(active.effective_sales_coefficient-1):+,.0f} vs Q1</small></span></div>')
    st.html('<div class="sales-list"><div class="panel-heading">Actual annual can sales</div>'+''.join(rows)+'</div>')
with plots_col:
    a,v = st.columns([2,1], vertical_alignment='center')
    with a:
        axis=st.segmented_control('Sensitivity axis',['Sales coefficient','Fixed-cost change'],key='axis',on_change=keep_axis_selected,label_visibility='collapsed')
    with v:
        full_range=st.toggle('Full range',key='full_range')
    axis=axis or 'Sales coefficient'
    curve_rows,root=sensitivity(case,active,axis,full_range=full_range)
    c1,c2=st.columns(2,gap='medium')
    with c1:
        with st.container(border=True,key='npv_panel'):
            st.html('<div class="chart-name">Net present value</div>')
            st_echarts(options=options(case,active,curve_rows,root,axis,'NPV'),height='365px',key='npv_chart')
    with c2:
        with st.container(border=True,key='irr_panel'):
            st.html('<div class="chart-name">IRR versus WACC</div>')
            st_echarts(options=options(case,active,curve_rows,root,axis,'IRR'),height='365px',key='irr_chart')
    st.html('<div class="chart-note">Solid grey: original Q1 assumptions. Dashed line: selected price, unit cost and demand response. Diamond: zero NPV. The demand axis is measured before price response.</div>')

st.html('<div id="pricing-decisions" class="section-title">Price and demand must work together</div>')
st.write('Green shading identifies combinations with positive full-project NPV under the selected costs and price response. The dashed line marks NPV = 0. It is a modelled feasibility region, not a confidence interval or guaranteed safety margin.')
map_col,line_col = st.columns([1.3,1],gap='large')
with map_col:
    st_echarts(options=decision_frontier_options(case,active),height='450px',key='decision_map')
with line_col:
    st_echarts(options=pricing_options(case,active),height='450px',key='pricing_curve')
st.caption(f'Held constant: annual fixed costs €{active.annual_fixed_cost:,.0f}; unit variable cost €{active.unit_variable_cost:.4f}. The map varies price and pre-price demand together. The line chart holds pre-price demand at {m:.4f}× Q1 and compares fixed units with the selected elasticity {active.demand_elasticity:.2f}. Capacity is unverified: green combinations needing more equipment or distribution require a revised investment case.')

st.html('<div id="recovery-options" class="section-title">What would restore positive NPV?</div>')
st.button('Test recovery with execution budget',key='execution_budget',on_click=execution_budget,help='Illustrative combined action: price +2%, unit cost €1.55, elasticity 1, Q2 demand −5%, plus €10,000/year execution spending. A plausible-looking rescue can still have negative NPV.')
r1,r2,r3,r4=st.columns(4)
r1.button('Find break-even demand',key='solve_sales',on_click=break_even_sales,width='stretch')
r2.button('Find fixed-cost ceiling',key='solve_costs',on_click=break_even_costs,width='stretch')
r3.button('Find break-even price',key='solve_price',on_click=break_even_price,width='stretch')
r4.button('Find unit-cost ceiling',key='solve_unit_cost',on_click=protect_unit_cost,width='stretch')
if st.session_state.action_note:
    st.info(st.session_state.action_note)
if st.session_state.action_error:
    st.warning(st.session_state.action_error)
price_limit=', '.join(f'€{case.price*r:.4f}/can' for r in price_roots) if price_roots else 'No boundary in €4.08–€6.63 search range'
recovery=[
    {'Decision lever':'Demand before price response','Zero-NPV boundary':f'{be_sales:.6f}× Q1' if be_sales is not None else 'No feasible demand boundary','Commercial test':'Retailer displays, availability, trial and repeat purchase; include extra execution spend.'},
    {'Decision lever':'Annual fixed operating cost','Zero-NPV boundary':f'€{case.annual_fixed_cost+be_cost:,.2f}/year' if be_cost is not None else 'Even zero fixed costs insufficient','Commercial test':'Protect activities that generate sales; marketing cuts may also reduce the demand coefficient.'},
    {'Decision lever':'Net price per can','Zero-NPV boundary':price_limit,'Commercial test':'Pilot net price and measure lost units. Multiple boundaries can occur when customers react strongly.'},
    {'Decision lever':'Variable cost per can','Zero-NPV boundary':f'€{unit_ceiling:.4f}/can' if unit_ceiling is not None else 'No non-negative unit-cost ceiling','Commercial test':'Procurement or packaging savings must preserve quality, repeat purchase and service.'},
]
st.dataframe(pd.DataFrame(recovery),hide_index=True,width='stretch')
fixed_units=model(case,m,d,price_coefficient=k['price_coefficient'],variable_cost_coefficient=k['variable_cost_coefficient'],demand_elasticity=0)
st.html(f'''<div class="business-context"><strong>Price-response check:</strong> at the selected price, NPV is €{fixed_units.npv:,.0f} if units do not respond, versus €{active.npv:,.0f} with the selected elasticity.<br><strong>CEO action:</strong> validate the retail plan and net realised price, test demand response, secure deliverable savings, and re-run the joint downside before approving. Added promotion or distribution expense belongs in fixed/unit costs; extra capacity or inventory commitments require further CAPEX/NWC modelling.<br><strong>Timing:</strong> these are pre-investment boundaries for the full project. After launch, use remaining incremental cash flows and avoidable costs for continuation decisions.</div>''')

with st.expander('Cash flows',expanded=False):
    records=pd.DataFrame(active.records())
    display=records.rename(columns={'year':'Year','units':'Cans sold','baseline_units':'Q1 base cans','revenue':'Revenue','variable_costs':'Variable costs','fixed_costs':'Fixed costs','depreciation':'Depreciation','ebit':'EBIT','tax':'Tax','nopat':'NOPAT','nwc':'Closing NWC','change_nwc':'Change in NWC','capex':'CAPEX','after_tax_salvage':'After-tax salvage','fcf':'FCF','pv':'Present value'})
    core=display[['Year','Cans sold','Revenue','EBIT','FCF','Present value']]
    st.dataframe(core,hide_index=True,width='stretch',column_config={c:st.column_config.NumberColumn(format='%.2f') for c in core.columns if c!='Year'})
    st.download_button('Download full cash flows · CSV',display.to_csv(index=False).encode('utf-8-sig'),'Kobuki_Group2_scenario_cashflows.csv','text/csv')
    st.download_button('Download scenario assumptions · JSON',json.dumps({'demand_coefficient':m,'fixed_cost_change':d,**k,'npv':active.npv,'irr':active.irr,'wacc':case.wacc},indent=2),'Kobuki_Group2_scenario.json','application/json')
    st.caption('EUR except cans. Current-year revenue drives NWC in Years 1–6; initial NWC stays €80,000 and is fully released at closure. Tax losses offset group income immediately. Existing capacity and WACC are held fixed; demand elasticity is an illustrative assumption.')
st.html(f'<div class="footer-note">Group 2: Jorge Pablo Yue · {escape(source["version"])} · WACC fixed · ±€1 NPV treated as break-even.</div><div class="footer-credit">Made by Yue <span>· October 2026</span></div>')
