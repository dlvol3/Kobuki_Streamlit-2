from __future__ import annotations

from html import escape
import json
from math import ceil, isfinite
from pathlib import Path

import pandas as pd
import streamlit as st
from echarts_component import st_echarts
import importlib
from inspect import signature
import finance as _case_model
if not hasattr(_case_model,'solve_price') or 'price_coefficient' not in signature(_case_model.model).parameters:
    _case_model=importlib.reload(_case_model)
import charts as _chart_views
if getattr(_chart_views,'SCOPE_VERSION',None)!='sales-fixed-v4':
    _chart_views=importlib.reload(_chart_views)
from finance import load_case, model, solve_fixed_cost, solve_sales
from charts import operating_options, operating_sensitivity, sales_options, sales_sensitivity, decision_frontier_options
import controls as _controls
if getattr(_controls,'SCOPE_VERSION',None)!='sales-fixed-v4':
    _controls=importlib.reload(_controls)
from controls import vertical_drivers

ROOT=Path(__file__).parent
st.set_page_config(page_title='Wake Up! · investment decision',page_icon='🥤',layout='wide')
st.html((ROOT/'assets/app.css').read_text())
case=load_case()
source=json.loads((ROOT/'data/case_inputs.json').read_text())
ELASTICITY=1.0
if st.session_state.get('simple_scope_version')!=2:
    st.session_state.update(simple_scope_version=2,baseline_id='q1',sales_multiplier=1.,
                            fixed_cost_change=0.,scenario_revision=0,action_note='',action_error='',axis='Can sales')
st.session_state.setdefault('sales_test',1.1)
st.session_state.setdefault('pricing_price',case.price)
st.session_state.setdefault('pricing_fixed_cost',220000.)
if st.session_state.get('axis') not in ['Can sales','Fixed-cost change']:
    st.session_state.axis='Can sales'


def selected_plan():
    return source['presets'][st.session_state.baseline_id]


def change_scenario(sales,cost,note=''):
    st.session_state.sales_multiplier=float(sales)
    st.session_state.fixed_cost_change=float(cost)
    st.session_state.action_note=note
    st.session_state.action_error=''
    st.session_state.scenario_revision+=1


def receive_drivers():
    values=st.session_state.get('drivers',{}).get('scenario',{})
    if values.get('revision')!=st.session_state.scenario_revision:return
    sales,cost=values.get('sales'),values.get('cost')
    if sales is None or cost is None:return
    if not isfinite(float(sales)) or not isfinite(float(cost)) or sales<.5 or cost<-case.annual_fixed_cost:
        st.session_state.action_error='Use a sales coefficient of at least 0.5 and non-negative total annual fixed costs.'
        return
    if abs(float(sales)-st.session_state.sales_multiplier)<1e-12 and abs(float(cost)-st.session_state.fixed_cost_change)<1e-8:return
    st.session_state.sales_multiplier=float(sales)
    st.session_state.fixed_cost_change=float(cost)
    st.session_state.action_note=''
    st.session_state.action_error=''


def baseline(which):
    st.session_state.baseline_id=which
    preset=source['presets'][which]
    change_scenario(preset['sales_coefficient'],preset['fixed_cost_change'])


def reset():baseline('q1')
def reset_q2():baseline('q2')


def no_extra_sales():
    st.session_state.baseline_id='q2'
    change_scenario(1.,-20000)


def sales_downside():
    st.session_state.baseline_id='q2'
    change_scenario(.9,-20000)


def pricing_example(price,fixed):
    st.session_state.pricing_price=float(price)
    st.session_state.pricing_fixed_cost=float(fixed)


def choose_sales_test(coefficient):
    st.session_state.sales_test=float(coefficient)


def break_even_sales():
    root=solve_sales(case,st.session_state.fixed_cost_change)
    if root is None:
        st.session_state.action_error='No sales break-even at these annual fixed costs.'
        return
    change_scenario(root,st.session_state.fixed_cost_change,
                    f'Zero-NPV sales: {root:.6f} × each Q1 year. Annual fixed costs and €5.10 price held unchanged.')


def break_even_costs():
    root=solve_fixed_cost(case,st.session_state.sales_multiplier)
    if root is None:
        st.session_state.action_error='Even zero annual fixed costs cannot reach break-even at this sales level.'
        return
    change_scenario(st.session_state.sales_multiplier,root,
                    f'Zero-NPV annual fixed-cost ceiling: €{case.annual_fixed_cost+root:,.2f}. Can sales and €5.10 price held unchanged.')


def keep_axis_selected():
    if st.session_state.get('axis') is None:st.session_state.axis='Can sales'


def money(value):return ('−' if value<0 else '')+f'€{abs(value):,.0f}'


plan=selected_plan();m=st.session_state.sales_multiplier
price=case.price;d=st.session_state.fixed_cost_change
active=model(case,m,d)
reference=model(case,plan['sales_coefficient'],plan['fixed_cost_change'])
q1=model(case);q2=model(case,1.1,-20000)
is_q1=st.session_state.baseline_id=='q1' and abs(m-1)<1e-10 and abs(d)<1e-8
is_q2=st.session_state.baseline_id=='q2' and abs(m-1.1)<1e-10 and abs(d+20000)<1e-8
label='Q1 baseline' if is_q1 else 'Q2 baseline' if is_q2 else 'Sales & fixed-cost scenario'
if abs(active.npv)<=1:
    status,css,verdict='BREAK-EVEN','neutral','The project just covers its capital cost.'
elif active.npv>0:
    status,css,verdict='ACCEPT','accept','The forecast clears the investment hurdle at this sales level and annual fixed cost.'
else:
    status,css,verdict='REJECT','reject','The forecast falls short of the investment hurdle at this sales level and annual fixed cost.'
st.html(f'''<div class="page-top"><div><div class="case-line">Group 2: Jorge Pablo Yue</div><h1>Wake Up! investment decision</h1></div><div class="case-tag">{label} · 7 years · EUR</div></div>
<div class="verdict {css}"><div class="decision {css}" role="status" aria-live="polite">{status}</div><div class="verdict-copy"><strong>{verdict}</strong><span>{m:.4f}× each Q1 year · price fixed €{price:.2f}/can · annual fixed costs €{active.annual_fixed_cost:,.0f}</span></div></div>''')
irr_text=f'{active.irr:.6f}' if active.irr is not None else 'Unavailable'
npv_css='gold' if abs(active.npv)<=1 else 'green' if active.npv>0 else 'red'
volume_ratio=m
st.html(f'''<div class="metric-grid">
<div class="metric"><div class="metric-label">Net present value</div><div class="metric-value {npv_css}">{money(active.npv)}</div><div class="metric-note">{active.npv:,.2f} EUR · {active.npv-reference.npv:+,.0f} vs selected baseline</div></div>
<div class="metric"><div class="metric-label">Internal rate of return</div><div class="metric-value">{irr_text}</div><div class="metric-note">{'Use NPV when no unique IRR exists.' if active.irr is None else f'{active.irr*100:.4f}%'}</div></div>
<div class="metric"><div class="metric-label">WACC · fixed hurdle</div><div class="metric-value gold">{case.wacc:.6f}</div><div class="metric-note">{case.wacc*100:.4f}%</div></div>
<div class="metric"><div class="metric-label">Cans sold / Q1 forecast</div><div class="metric-value violet">{volume_ratio:.4f}×</div><div class="metric-note">1.0000× = original Q1 forecast</div></div></div>''')
st.html('''<div class="business-context">Q2 adds 16,000 cans in Year 1, 22,000 in Year 2 and 25,000 a year thereafter through promotions and better displays. Its €91,903 NPV leaves limited room for higher spending or lost sales. Use the two controls to see how different can sales and annual fixed costs affect that result.</div>''')
b1,b2,b3,b4=st.columns(4)
b1.button('Q1 baseline',key='reset_q1',on_click=reset,type='primary' if is_q1 else 'secondary',width='stretch')
b2.button('Q2 baseline',key='reset_q2',on_click=reset_q2,type='primary' if is_q2 else 'secondary',width='stretch')
b3.button('No extra Q2 sales',key='no_extra_sales',on_click=no_extra_sales,width='stretch')
b4.button('10% below Q1 · Q2 costs',key='sales_downside',on_click=sales_downside,width='stretch')

controls_col,plots_col=st.columns([.9,2.3],gap='large')
with controls_col:
    st.html('<div class="panel-heading">Can sales & annual fixed costs</div>')
    vertical_drivers(data={'sales':m,'cost':d,'revision':st.session_state.scenario_revision,
                          'sales_max':max(2.,ceil(m*10)/10),
                          'cost_max':max(600000,ceil(d/10000)*10000)},
                     default={'scenario':{'sales':m,'cost':d,'revision':st.session_state.scenario_revision}},
                     on_scenario_change=receive_drivers,key='drivers')
    rows=[]
    for label_t,q in [('Year 1',case.base_units[0]),('Year 2',case.base_units[1]),('Years 3–7 · each',case.base_units[2])]:
        rows.append(f'<div class="sales-row"><span class="period">{label_t}</span><span class="actual">{q*active.effective_sales_coefficient:,.0f} cans<small>{q*(m-1):+,.0f} vs Q1</small></span></div>')
    st.html('<div class="sales-list"><div class="panel-heading">Forecast cans sold</div>'+''.join(rows)+'</div>')
    st.caption('Sales coefficient × each Q1 year: 1.0 gives 160,000 / 220,000 / 250,000 cans; 1.1 gives the Q2 forecast. Price stays €5.10.')
with plots_col:
    a,v=st.columns([2,1],vertical_alignment='center')
    with a:
        axis=st.segmented_control('Sensitivity axis',['Can sales','Fixed-cost change'],key='axis',on_change=keep_axis_selected,label_visibility='collapsed')
    with v:full_range=st.toggle('Full range',key='full_range')
    axis=axis or 'Can sales'
    rows,roots=operating_sensitivity(case,active,axis,full_range=full_range)
    c1,c2=st.columns(2,gap='medium')
    with c1:
        with st.container(border=True,key='npv_panel'):
            st.html('<div class="chart-name">Net present value</div>')
            st_echarts(options=operating_options(case,active,rows,roots,axis,'NPV'),height='365px',key='npv_chart')
    with c2:
        with st.container(border=True,key='irr_panel'):
            st.html('<div class="chart-name">IRR versus WACC</div>')
            st_echarts(options=operating_options(case,active,rows,roots,axis,'IRR'),height='365px',key='irr_chart')
    st.html('<div class="chart-note">Price stays €5.10. The sales coefficient applies to each Q1 year; the fixed-cost change is the same amount each year. WACC stays at 0.102974.</div>')

st.html('<div class="section-title">Figure 1 · What if the extra sales do not arrive?</div>')
st.write('Q2 needs customers to keep buying after the initial promotion. Demand could weaken, a competing drink could take customers or shelf space, or repeat purchases could fade after promotions end. The sales test below shows what these possible setbacks would mean for NPV.')
st.write('Only cans sold change in this test. Price stays €5.10 and annual fixed costs stay €220,000. Each percentage applies to the corresponding Q1 year: 160,000 cans in Year 1, 220,000 in Year 2 and 250,000 a year thereafter.')
s1,s2,s3=st.columns(3)
s1.button('10% below Q1 forecast',key='sales_below_q1',on_click=choose_sales_test,args=(.9,),width='stretch')
s2.button('No extra Q2 sales',key='sales_no_q2',on_click=choose_sales_test,args=(1.,),width='stretch')
s3.button('Q2 forecast: Q1 +10%',key='sales_q2',on_click=choose_sales_test,args=(1.1,),width='stretch')
sales_test=model(case,st.session_state.sales_test,-20000)
sales_labels={.9:'10% below each Q1 year',1.:'No extra Q2 sales',1.1:'Q2 forecast: 10% above each Q1 year'}
st.info(f"{sales_labels[st.session_state.sales_test]} · NPV {money(sales_test.npv)} · Year 1 {case.base_units[0]*st.session_state.sales_test:,.0f} cans · Year 2 {case.base_units[1]*st.session_state.sales_test:,.0f} · Years 3–7 {case.base_units[2]*st.session_state.sales_test:,.0f} each")
st_echarts(options=sales_options(case,st.session_state.sales_test),height='430px',key='sales_only_chart')
_,sales_root=sales_sensitivity(case)
st.write(f'Without Q2’s extra sales, NPV is −€153,491 even after keeping its €220,000 fixed-cost plan. Sales 10% below Q1 make NPV −€398,885. Break-even needs {sales_root*100:.2f}% of each Q1 year: about 6.25% above Q1, or 3.40% below the Q2 forecast. The sales benefit therefore cannot be missed by much.')

st.html('<div id="pricing-decisions" class="section-title">Figure 2 · Price and the fixed-cost limit</div>')
st.write('This map uses the Q2 annual sales plan. Higher prices reduce cans; lower prices increase them. The dashed line is zero NPV. Green below it shows price and annual fixed-cost combinations with positive NPV.')
pricing_active=model(case,1.1,st.session_state.pricing_fixed_cost-case.annual_fixed_cost,price_coefficient=st.session_state.pricing_price/case.price,demand_elasticity=ELASTICITY)
st_echarts(options=decision_frontier_options(case,pricing_active),height='500px',key='decision_map')
e1,e2,e3,e4=st.columns(4)
e1.button('A · €4.50 / €190k',key='map_low_safe',on_click=pricing_example,args=(4.5,190000),width='stretch')
e2.button('B · Q2 baseline',key='map_q2',on_click=pricing_example,args=(5.1,220000),width='stretch')
e3.button('C · €5.355 / €250k',key='map_high_safe',on_click=pricing_example,args=(5.355,250000),width='stretch')
e4.button('D · €4.50 / €220k',key='map_low_loss',on_click=pricing_example,args=(4.5,220000),width='stretch')
st.info(f'Figure 2 only · Price €{pricing_active.unit_price:.3f} · Annual fixed costs €{pricing_active.annual_fixed_cost:,.0f} · NPV {money(pricing_active.npv)}. Main sales and fixed-cost controls stay unchanged.')
example_rows=[]
for name,p,fixed in [('A',4.50,190000),('B',case.price,220000),('C',5.355,250000),('D',4.50,220000)]:
    value=model(case,1.1,fixed-case.annual_fixed_cost,price_coefficient=p/case.price,demand_elasticity=ELASTICITY)
    boundary=case.annual_fixed_cost+solve_fixed_cost(case,1.1,price_coefficient=p/case.price,demand_elasticity=ELASTICITY)
    example_rows.append({'Point':name,'Price / can':f'€{p:.3f}','Annual fixed costs':money(fixed),'Project NPV':money(value.npv),'Break-even fixed costs / year':money(boundary),'Fixed-cost headroom / year':money(boundary-fixed)})
st.dataframe(pd.DataFrame(example_rows),hide_index=True,width='stretch')
st.write('At D, a €4.50 price leaves NPV −€75,735 at €220,000 annual fixed costs. In this assumed response, 13.33% more cans exactly offsets the lower price, so sales revenue stays the same as Q2. Producing those extra cans increases total production spending at €1.60 per can. Fixed costs must fall below €195,832 a year to make this price work. A reduces them to €190,000, leaving just €5,832 a year of headroom and NPV +€18,277. C combines a 5% price rise with €250,000 annual fixed costs; its headroom is €18,432 a year and NPV +€57,761.')
st.write('To improve D, Kobuki could offer a smaller discount, find further fixed-cost savings beyond the Q2 plan, or negotiate lower ingredient and packaging prices or reduce production waste without reducing product quality. Those savings would need to be additional; the Q2 savings are already included.')
st.caption('One assumed response only: cans = Q2 plan cans × €5.10 / price. A 1% price rise reduces cans by about 1%. Lower-price examples assume no extra machine is needed. Other case inputs stay fixed.')

st.html('<div class="section-title">Break-even sales and annual fixed costs</div>')
r1,r2=st.columns(2)
r1.button('Find break-even sales',key='solve_sales',on_click=break_even_sales,width='stretch')
r2.button('Find fixed-cost ceiling',key='solve_costs',on_click=break_even_costs,width='stretch')
if st.session_state.action_note:st.info(st.session_state.action_note)
if st.session_state.action_error:st.warning(st.session_state.action_error)
sales_root=solve_sales(case,d)
cost_root=solve_fixed_cost(case,m)
sales_bound=f'{sales_root:.6f}× Q1 forecast' if sales_root is not None else 'No boundary'
cost_bound=f'€{case.annual_fixed_cost+cost_root:,.2f}/year' if cost_root is not None else 'Even zero annual fixed costs are insufficient'
st.html(f'<div class="threshold"><strong>Sales at zero NPV: {sales_bound}</strong><br>Annual fixed costs held at €{active.annual_fixed_cost:,.0f}; price fixed €5.10.</div><div class="threshold"><strong>Annual fixed-cost ceiling: {cost_bound}</strong><br>Sales held at {m:.4f}× each Q1 year; price fixed €5.10.</div>')
st.html('<div class="business-context">Any extra launch or display spending belongs in annual fixed costs. These are results for the full project before buying the equipment.</div>')

with st.expander('Cash flows',expanded=False):
    display=pd.DataFrame(active.records()).rename(columns={'year':'Year','units':'Cans sold','revenue':'Revenue','ebit':'EBIT','fcf':'FCF','pv':'Present value'})
    core=display[['Year','Cans sold','Revenue','EBIT','FCF','Present value']]
    st.dataframe(core,hide_index=True,width='stretch',column_config={col:st.column_config.NumberColumn(format='%.2f') for col in core.columns if col!='Year'})
    st.download_button('Download full cash flows · CSV',display.to_csv(index=False).encode('utf-8-sig'),'Kobuki_Group2_scenario_cashflows.csv','text/csv')
    st.download_button('Download scenario assumptions · JSON',json.dumps({'baseline':st.session_state.baseline_id,'sales_coefficient_vs_q1':m,'price_per_can':price,'fixed_cost_change':d,'npv':active.npv,'irr':active.irr,'wacc':case.wacc},indent=2),'Kobuki_Group2_scenario.json','application/json')
    st.caption('EUR except cans. Revenue-linked NWC and tax are recalculated. Initial NWC stays €80,000, with full recovery at closure. Tax losses offset other group income immediately.')
st.html(f'<div class="footer-note">Group 2: Jorge Pablo Yue · {escape(source["version"])} · ±€1 NPV treated as break-even.</div><div class="footer-credit">Made by Yue <span>· October 2026</span></div>')
