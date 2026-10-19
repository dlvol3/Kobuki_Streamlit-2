from __future__ import annotations

from html import escape
import json
from math import ceil, isfinite
from pathlib import Path

import pandas as pd
import streamlit as st
from echarts_component import st_echarts

from finance import load_case, model, solve_sales, solve_fixed_cost
from charts import options, sensitivity
from controls import vertical_drivers

ROOT=Path(__file__).parent
st.set_page_config(page_title='Kobuki · sensitivity',page_icon='🥤',layout='wide')
st.html((ROOT/'assets/app.css').read_text())
case=load_case()
source=json.loads((ROOT/'data/case_inputs.json').read_text())

for key,value in {'sales_coefficient':1.0,'fixed_cost_change':0.0,'scenario_revision':0,'action_note':'','action_error':'','axis':'Sales coefficient'}.items():
    st.session_state.setdefault(key,value)


def change_drivers(sales, cost, note=''):
    st.session_state.sales_coefficient=float(sales)
    st.session_state.fixed_cost_change=float(cost)
    st.session_state.action_note=note
    st.session_state.action_error=''
    # Reject any delayed frontend event from before a shortcut/reset action.
    st.session_state.scenario_revision+=1


def receive_drivers():
    state=st.session_state.get('drivers',{})
    values=state.get('scenario',{})
    if values.get('revision')!=st.session_state.scenario_revision:
        return
    sales,cost=values.get('sales'),values.get('cost')
    if sales is None or cost is None:return
    if not isfinite(float(sales)) or not isfinite(float(cost)) or sales<0 or cost<-case.annual_fixed_cost:
        st.session_state.action_error='Invalid input: sales must be non-negative and total fixed costs cannot be negative.'
        return
    if abs(float(sales)-st.session_state.sales_coefficient)<1e-12 and abs(float(cost)-st.session_state.fixed_cost_change)<1e-8:
        return
    st.session_state.sales_coefficient=float(sales)
    st.session_state.fixed_cost_change=float(cost)
    st.session_state.action_note=''
    st.session_state.action_error=''


def reset():
    change_drivers(1,0)


def reset_q2():
    preset=source['presets']['q2']
    change_drivers(preset['sales_coefficient'],preset['fixed_cost_change'])


def break_even_sales():
    cost=st.session_state.fixed_cost_change
    root=solve_sales(case,cost)
    if root is None:
        st.session_state.action_error='No non-negative sales break-even exists under this fixed-cost assumption.'
        return
    change_drivers(root,cost,f'Annual fixed costs held at EUR {case.annual_fixed_cost+cost:,.2f}. Sales break-even: {root:.6f}× the Q1 forecast.')


def break_even_costs():
    sales=st.session_state.sales_coefficient
    root=solve_fixed_cost(case,sales)
    if root is None:
        st.session_state.action_error='At this sales level, even zero annual fixed costs cannot reach break-even. Increase sales before solving costs.'
        return
    change_drivers(sales,root,f'Sales held at {sales:.6f}× the Q1 forecast. Annual fixed costs at break-even: EUR {case.annual_fixed_cost+root:,.2f}.')


def keep_axis_selected():
    if st.session_state.get('axis') is None:
        st.session_state.axis='Sales coefficient'


m=st.session_state.sales_coefficient
d=st.session_state.fixed_cost_change
active=model(case,m,d)
baseline=model(case)
is_q1=abs(m-1)<1e-10 and abs(d)<1e-8
q2=source['presets']['q2']
is_q2=abs(m-q2['sales_coefficient'])<1e-10 and abs(d-q2['fixed_cost_change'])<1e-8
scenario_label='Q1 baseline' if is_q1 else 'Q2 baseline' if is_q2 else 'Custom scenario'
be_sales=solve_sales(case,d)
be_cost=solve_fixed_cost(case,m)
tolerance=1.0
if abs(active.npv)<=tolerance:
    verdict='At break-even: the project just clears its capital cost.'
    status,css='BREAK-EVEN','neutral'
elif active.npv>0:
    verdict='The stated synergies make the project financially viable.' if is_q2 else 'This scenario creates value above the capital hurdle.'
    status,css='ACCEPT','accept'
else:
    verdict='The original forecast does not clear the hurdle.' if abs(m-1)<1e-10 and abs(d)<1e-8 else 'This scenario still falls short of the capital hurdle.'
    status,css='REJECT','reject'

st.html(f'''<div class="page-top"><div><div class="case-line">Group 2: Jorge Pablo Yue</div><h1>Wake Up! sensitivity analysis</h1></div><div class="case-tag">{scenario_label} · 7 years · EUR</div></div>
<div class="verdict {css}"><div class="decision {css}" role="status" aria-live="polite">{status}</div><div class="verdict-copy"><strong>{verdict}</strong><span>{scenario_label} · sales {m:.4f}× · annual fixed costs €{active.annual_fixed_cost:,.0f}</span></div></div>''')

irr_display=f'{active.irr:.6f}' if active.irr is not None else 'Unavailable'
irr_spread=active.irr-case.wacc if active.irr is not None else None
if irr_spread is not None and abs(irr_spread)<1e-9:irr_spread=0.0
irr_note=f'{active.irr*100:.4f}% · spread vs WACC {irr_spread:+.6f}' if active.irr is not None else 'Use NPV; no unique admissible IRR.'
npv_css='gold' if abs(active.npv)<=tolerance else 'green' if active.npv>0 else 'red'
st.html(f'''<div class="metric-grid">
<div class="metric"><div class="metric-label">Net present value</div><div class="metric-value {npv_css}">€{active.npv:,.0f}</div><div class="metric-note">€{active.npv:,.2f} · {active.npv-baseline.npv:+,.0f} vs Q1</div></div>
<div class="metric"><div class="metric-label">Internal rate of return</div><div class="metric-value">{irr_display}</div><div class="metric-note">{irr_note}</div></div>
<div class="metric"><div class="metric-label">WACC · fixed hurdle</div><div class="metric-value gold">{case.wacc:.6f}</div><div class="metric-note">{case.wacc*100:.4f}% · unchanged in every test</div></div>
<div class="metric"><div class="metric-label">Annual fixed operating costs</div><div class="metric-value violet">€{active.annual_fixed_cost:,.0f}</div><div class="metric-note">€{d:+,.2f}/year vs €{case.annual_fixed_cost:,.0f} baseline</div></div></div>''')

b1,b2,b3,b4=st.columns([1,1,1.4,1.4])
b1.button('Q1 baseline',key='reset_q1',on_click=reset,type='primary' if is_q1 else 'secondary',width='stretch')
b2.button('Q2 baseline',key='reset_q2',on_click=reset_q2,type='primary' if is_q2 else 'secondary',width='stretch',help='110% of Q1 unit sales; EUR 40,000 project savings plus EUR 20,000 corporate costs. Net fixed costs: EUR 220,000/year.')
b3.button('Find break-even sales',key='solve_sales',on_click=break_even_sales,width='stretch',help='Hold annual fixed costs unchanged; solve sales for NPV = 0.')
b4.button('Find break-even fixed costs',key='solve_costs',on_click=break_even_costs,width='stretch',help='Hold sales unchanged; solve annual fixed costs for NPV = 0.')
if st.session_state.action_note:st.info(st.session_state.action_note,icon='🔒')
if st.session_state.action_error:st.warning(st.session_state.action_error)

controls_col,plots_col=st.columns([.9,2.3],gap='large')
with controls_col:
    st.html('<div class="panel-heading">Operating assumptions</div><div class="panel-sub">Both controls are measured against Q1.</div>')
    vertical_drivers(data={'sales':m,'cost':d,'revision':st.session_state.scenario_revision,'sales_max':max(2.0,ceil(m*10)/10),'cost_max':max(600000,ceil(d/10000)*10000)},
                     default={'scenario':{'sales':m,'cost':d,'revision':st.session_state.scenario_revision}},on_scenario_change=receive_drivers,key='drivers')
    sales_rows=[]
    for label,q in [('Year 1',case.base_units[0]),('Year 2',case.base_units[1]),('Years 3–7 · each',case.base_units[2])]:
        sales_rows.append(f'<div class="sales-row"><span class="period">{label}</span><span class="actual">{q*m:,.0f} cans<small>{q*(m-1):+,.0f} vs {q:,.0f} base</small></span></div>')
    st.html('<div class="sales-list"><div class="panel-heading">Annual can sales</div>'+''.join(sales_rows)+'</div>')

with plots_col:
    axis_col,view_col=st.columns([2,1],vertical_alignment='center')
    with axis_col:
        axis=st.segmented_control('Sensitivity axis',['Sales coefficient','Fixed-cost change'],key='axis',on_change=keep_axis_selected,label_visibility='collapsed')
    with view_col:
        full_range=st.toggle('Full range',key='full_range',help='Off: focus on Q1, the current scenario and break-even. On: show a wider assumption range.')
    axis=axis or 'Sales coefficient'
    curve_rows,root=sensitivity(case,active,axis,full_range=full_range)
    c1,c2=st.columns(2,gap='medium')
    with c1:
        with st.container(border=True,key='npv_panel'):
            delta=active.npv-baseline.npv
            delta_css='green' if delta>1 else 'red' if delta<-1 else ''
            st.html(f'<div class="chart-name">Net present value</div><div class="chart-delta {delta_css}">{"+" if delta>=0 else "−"}€{abs(delta):,.0f}<span>change vs Q1</span></div>')
            st_echarts(options=options(case,active,curve_rows,root,axis,'NPV'),height='365px',key='npv_chart')
    with c2:
        with st.container(border=True,key='irr_panel'):
            delta=active.irr-baseline.irr if active.irr is not None else None
            delta_css='green' if delta is not None and delta>1e-9 else 'red' if delta is not None and delta<-1e-9 else ''
            delta_text=f'{delta:+.6f}' if delta is not None else 'Unavailable'
            st.html(f'<div class="chart-name">IRR versus WACC</div><div class="chart-delta {delta_css}">{delta_text}<span>change vs Q1 · decimal</span></div>')
            st_echarts(options=options(case,active,curve_rows,root,axis,'IRR'),height='365px',key='irr_chart')
    held=f'fixed-cost change €{d:+,.0f}/year' if axis=='Sales coefficient' else f'sales coefficient {m:.6f}×'
    st.html(f'<div class="chart-note">{"Full range" if full_range else "Decision focus"} · {held} held constant. Open dot: Q1. Ring: current result. Diamond: break-even. Green / pink zones: above / below the hurdle.</div>')
    t1,t2=st.columns(2)
    with t1:
        if be_sales is not None:
            gap=be_sales-m
            st.html(f'<div class="threshold">With annual cost change held at €{d:+,.0f}:<br><strong>Sales break-even = {be_sales:.6f}×</strong><br>{be_sales*100:.3f}% of the original unit-sales path; coefficient gap {gap:+.6f}.</div>')
    with t2:
        if be_cost is not None:
            st.html(f'<div class="threshold">With sales held at {m:.6f}×:<br><strong>Fixed-cost change = €{be_cost:+,.2f}/year</strong><br>Total annual fixed costs at break-even: €{case.annual_fixed_cost+be_cost:,.2f}.</div>')
        else:
            st.html('<div class="threshold">No feasible cost-only break-even at this sales level.<br><strong>Zero annual fixed costs are insufficient.</strong></div>')

with st.expander('Cash flows',expanded=False):
    records=pd.DataFrame(active.records())
    display=records.rename(columns={'year':'Year','units':'Cans sold','baseline_units':'Q1 base cans','revenue':'Revenue','variable_costs':'Variable costs','fixed_costs':'Fixed costs','depreciation':'Depreciation','ebit':'EBIT','tax':'Tax','nopat':'NOPAT','nwc':'Closing NWC','change_nwc':'Change in NWC','capex':'CAPEX','after_tax_salvage':'After-tax salvage','fcf':'FCF','pv':'Present value'})
    core=display[['Year','Cans sold','Revenue','EBIT','FCF','Present value']]
    st.dataframe(core,hide_index=True,width='stretch',column_config={c:st.column_config.NumberColumn(format='%.2f') for c in core.columns if c!='Year'})
    st.download_button('Download full cash flows · CSV',display.to_csv(index=False).encode('utf-8-sig'),'Kobuki_Group2_scenario_cashflows.csv','text/csv')
    st.caption('EUR except cans. Year 7 includes NWC recovery and equipment disposal. Tax losses offset other group income immediately.')

st.html(f'<div class="footer-note">Group 2: Jorge Pablo Yue · {escape(source["version"])} · WACC fixed · ±€1 NPV treated as break-even.</div><div class="footer-credit">Made by Yue <span>· October 2026</span></div>')

