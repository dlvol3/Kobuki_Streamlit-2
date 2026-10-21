SCOPE_VERSION = "sales-price-fixed-v3"
"""Price and fixed-cost sensitivities with automatic price-volume response."""
import math
import numpy as np
from echarts_component import JsCode
from finance import model, npv_only, solve_fixed_cost, solve_price, solve_sales

BG='#FFFFFF'
GRID='#E5EBF1'
INK='#172B42'
MUTED='#62758A'
TEAL='#087D68'
VIOLET='#6652B8'
GOLD='#96600B'
GREY='#8B99AA'
BASE_ELASTICITY=1.0


def _money(value):
    return f'{"-" if value<0 else ""}€{abs(value):,.0f}'


def _series_map(chart):
    return {s['id']:s for s in chart['series']}


def _axis_style():
    return {'axisLine':{'lineStyle':{'color':'#CBD5E0'}},'axisTick':{'show':False},
            'splitLine':{'lineStyle':{'color':GRID,'type':'dashed'}}}


def _result(case,active,price=None,cost=None,elasticity=BASE_ELASTICITY):
    return model(case,active.sales_coefficient,
                 active.fixed_cost_change if cost is None else cost,
                 price_coefficient=active.price_coefficient if price is None else price/case.price,
                 demand_elasticity=elasticity)


def _price_range(case,active,full_range=False):
    current=case.price*active.price_coefficient
    lo=min(case.price*.8,current*.97)
    hi=max(case.price*1.3,current*1.03)
    if full_range:
        lo=min(lo,case.price*.6)
        hi=max(hi,case.price*1.5)
    return max(.01,lo),hi


def operating_sensitivity(case,active,axis='Price per can',full_range=False):
    """Return sweep rows and zero-NPV roots, in the axis's actual units.

    Price axis is EUR/can. Fixed-cost axis is EUR/year change against Q1.
    Q1 reference and selected curves both use an illustrative elasticity of 1;
    only the selected baseline sales path and held operating lever differ.
    """
    if axis not in ('Price per can','Fixed-cost change'):
        raise ValueError('Unknown operating sensitivity axis.')
    price_axis=axis=='Price per can'
    if price_axis:
        lo,hi=_price_range(case,active,full_range)
        roots=tuple(r*case.price for r in solve_price(case,active.sales_coefficient,
            active.fixed_cost_change,demand_elasticity=BASE_ELASTICITY,
            lower=lo/case.price,upper=hi/case.price))
        anchors=[case.price,case.price*active.price_coefficient,*roots]
    else:
        root=solve_fixed_cost(case,active.sales_coefficient,
            price_coefficient=active.price_coefficient,demand_elasticity=BASE_ELASTICITY)
        roots=() if root is None else (root,)
        anchors=[0.,-20000.,active.fixed_cost_change,*roots]
        if full_range:
            lo=-case.annual_fixed_cost
            hi=max(300000.,max(anchors)+50000)
        else:
            pad=max(30000.,(max(anchors)-min(anchors))*.18)
            lo=max(-case.annual_fixed_cost,math.floor((min(anchors)-pad)/25000)*25000)
            hi=math.ceil((max(anchors)+pad)/25000)*25000
            if hi-lo<100000:hi=lo+100000
    xs=sorted(set(float(v) for v in np.linspace(lo,hi,111))|set(anchors))
    rows=[]
    for x in xs:
        if price_axis:
            reference=model(case,price_coefficient=x/case.price,demand_elasticity=BASE_ELASTICITY)
            selected=_result(case,active,price=x)
        else:
            reference=model(case,1,x,demand_elasticity=BASE_ELASTICITY)
            selected=_result(case,active,cost=x)
        rows.append({'x':x,'reference_npv_eur':reference.npv,'current_npv_eur':selected.npv,
                     'reference_irr':reference.irr,'current_irr':selected.irr,
                     'actual_sales_coefficient':selected.effective_sales_coefficient,
                     'price_per_can':selected.unit_price,'annual_fixed_cost':selected.annual_fixed_cost,
                     'wacc':case.wacc})
    return rows,roots


def operating_options(case,active,rows,roots,axis,metric):
    """NPV/IRR view with truthful Q1/current points and fixed hurdle."""
    price_axis=axis=='Price per can'; npv_metric=metric=='NPV'
    color=TEAL if npv_metric else VIOLET
    xf=1 if price_axis else 1000
    yf=1000 if npv_metric else 1
    rk='reference_npv_eur' if npv_metric else 'reference_irr'
    ck='current_npv_eur' if npv_metric else 'current_irr'
    reference=[[r['x']/xf,None if r[rk] is None else r[rk]/yf] for r in rows]
    current=[[r['x']/xf,None if r[ck] is None else r[ck]/yf] for r in rows]
    baseline=model(case,demand_elasticity=BASE_ELASTICITY)
    current_result=_result(case,active)
    bx=case.price if price_axis else 0.
    by=baseline.npv/yf if npv_metric else baseline.irr
    px=active.unit_price if price_axis else active.fixed_cost_change/1000
    py=current_result.npv/yf if npv_metric else current_result.irr
    hurdle=0 if npv_metric else case.wacc
    values=[p[1] for p in reference+current if p[1] is not None]+[hurdle,by]
    if py is not None:values.append(py)
    pad=max((max(values)-min(values))*.16,35 if npv_metric else .015)
    ymin,ymax=min(values)-pad,max(values)+pad
    same=py is not None and abs(px-bx)<1e-10 and abs(py-by)<1e-9
    targetlabel='NPV = 0' if npv_metric else f'WACC {case.wacc:.6f}'
    xformatter=JsCode("function(v){return '€'+v.toFixed(2);}" if price_axis else
                      "function(v){return '€'+Math.round(v)+'k';}").js_code
    tooltip=JsCode("""function(items){
      if(!Array.isArray(items))items=[items];
      let first=items.find(p=>Array.isArray(p.value));if(!first)return '';
      let x=first.value[0];
      let html='<b>'+ (PRICE?'Price €'+x.toFixed(2)+'/can':'Fixed-cost change €'+(x*1000).toLocaleString('en-IE'))+'</b>';
      for(let p of items){if(!Array.isArray(p.value)||p.value[1]===null||p.seriesId==='comparison_link')continue;
        let y=NPV?'€'+(p.value[1]*1000).toLocaleString('en-IE',{maximumFractionDigits:0}):p.value[1].toFixed(6);
        html+='<div style="margin-top:6px">'+p.marker+' '+p.seriesName+': <b>'+y+'</b></div>';
      }return html;
    }""".replace('PRICE','true' if price_axis else 'false').replace('NPV','true' if npv_metric else 'false')).js_code
    marks=[{'yAxis':hurdle,'lineStyle':{'color':GOLD,'type':'dashed'},
            'label':{'formatter':targetlabel,'position':'insideEndBottom','color':GOLD,'fontSize':10}},
           {'xAxis':px,'lineStyle':{'color':color,'type':'dotted','opacity':.5},'label':{'show':False}}]
    pointlabel=('Q1 / NOW\n' if same else 'NOW\n')+(_money(current_result.npv) if npv_metric else f'{py:.6f}' if py is not None else '')
    chart={
        'backgroundColor':BG,'animationDurationUpdate':350,
        'textStyle':{'fontFamily':'Inter, system-ui, sans-serif','color':MUTED},
        'aria':{'enabled':True,'description':f'{metric} sensitivity to {axis}. Both curves link higher prices to lower unit sales using an illustrative elasticity of 1. Grey is Q1 reference; dashed is the selected baseline. The diamond marks zero NPV.'},
        'grid':{'left':55,'right':20,'top':60,'bottom':60},
        'legend':{'type':'scroll','left':0,'right':20,'top':0,'data':['Q1 reference','Selected baseline'],'textStyle':{'color':MUTED,'fontSize':10},'itemWidth':18},
        'tooltip':{'trigger':'axis','confine':True,'formatter':tooltip,'backgroundColor':'#FFFFFFF5','textStyle':{'color':INK,'fontSize':11}},
        'toolbox':{'show':True,'right':0,'top':25,'feature':{'saveAsImage':{'title':'Download PNG','name':f'WakeUp_{metric}_{"price" if price_axis else "cost"}','pixelRatio':2}}},
        'xAxis':{'type':'value','min':rows[0]['x']/xf,'max':rows[-1]['x']/xf,'splitNumber':4,
                 'name':'Price · EUR / can' if price_axis else 'Fixed-cost change / year','nameLocation':'middle','nameGap':38,
                 'nameTextStyle':{'fontSize':10,'color':MUTED},'axisLabel':{'formatter':xformatter,'fontSize':10,'hideOverlap':True,'color':MUTED},**_axis_style()},
        'yAxis':{'type':'value','min':ymin,'max':ymax,'splitNumber':4,'name':'EUR thousands' if npv_metric else 'IRR · decimal','nameGap':20,
                 'nameTextStyle':{'fontSize':10,'color':MUTED},'axisLabel':{'fontSize':10,'color':MUTED,'formatter':JsCode("function(v){return Math.round(v).toLocaleString('en-IE');}" if npv_metric else "function(v){return v.toFixed(2);}").js_code},
                 'axisLine':{'show':False},'axisTick':{'show':False},'splitLine':{'lineStyle':{'color':GRID,'type':'dashed'}}},
        'series':[
            {'id':'q1_curve','name':'Q1 reference','type':'line','data':reference,'showSymbol':False,'connectNulls':False,'lineStyle':{'color':GREY,'width':2.2}},
            {'id':'scenario_curve','name':'Selected baseline','type':'line','data':current,'showSymbol':False,'connectNulls':False,'lineStyle':{'color':color,'width':2.7,'type':'dashed'},
             'markLine':{'silent':True,'symbol':'none','data':marks},
             'markArea':{'silent':True,'label':{'show':False},'data':[[{'yAxis':hurdle,'itemStyle':{'color':'#ECF7F2AA'}},{'yAxis':ymax}],[{'yAxis':ymin,'itemStyle':{'color':'#FFF0F2A6'}},{'yAxis':hurdle}]]}},
            {'id':'q1_point','name':'Q1 baseline','type':'scatter','data':[[bx,by]],'symbol':'emptyCircle','symbolSize':10,'itemStyle':{'color':GREY},'label':{'show':not same,'formatter':'Q1','position':'bottom','color':MUTED,'fontSize':10},'z':5},
            {'id':'current_point','name':'Current scenario','type':'scatter','data':[[px,py]] if py is not None else [],'symbolSize':14,
             'itemStyle':{'color':color,'borderColor':BG,'borderWidth':2},'label':{'show':True,'formatter':pointlabel,'position':'top','distance':12,'fontSize':11,'color':color,'backgroundColor':'#FFFFFFE8','padding':[4,6]},'z':7},
        ]}
    if roots:
        chart['series'].append({'id':'break_even','name':'Break-even','type':'scatter','data':[[r/xf,hurdle] for r in roots],
                                'symbol':'diamond','symbolSize':11,'itemStyle':{'color':GOLD,'borderColor':BG,'borderWidth':1},'z':6})
    if py is not None and not same:
        chart['series'].append({'id':'comparison_link','name':'Q1 to current','type':'line','data':[[bx,by],[px,py]],'showSymbol':False,'silent':True,'lineStyle':{'color':color,'type':'dotted','opacity':.6},'z':4})
    return chart


def sales_sensitivity(case):
    """Only sales volume varies, against each Q1 year; price5.10/cost220k fixed."""
    root=solve_sales(case,-20000)
    anchors=[.9,1.,1.1,root]
    xs=sorted(set(float(v) for v in np.linspace(.8,1.2,101))|set(anchors))
    return [dict(sales_coefficient=x,npv=model(case,x,-20000).npv) for x in xs],root


def sales_options(case,selected=1.1):
    rows,root=sales_sensitivity(case)
    values=[r['npv']/1000 for r in rows]+[0]
    lo,hi=min(values)-50,max(values)+50
    points=[(.9,'Q1 plan −10%'),(1.,'No Q2 extra sales'),(1.1,'Q2 forecast')]
    series=[{'id':'sales_curve','name':'NPV','type':'line','data':[[r['sales_coefficient']*100,r['npv']/1000] for r in rows],
             'showSymbol':False,'lineStyle':{'color':TEAL,'width':2.8},
             'markLine':{'silent':True,'symbol':'none','data':[{'yAxis':0,'lineStyle':{'color':GOLD,'type':'dashed'},'label':{'formatter':'NPV = 0','position':'insideEndTop','color':GOLD}}]},
             'markArea':{'silent':True,'label':{'show':False},'data':[[{'yAxis':0,'itemStyle':{'color':'#ECF7F2AA'}},{'yAxis':hi}]]}},
            {'id':'sales_break_even','name':'Sales break-even','type':'scatter','data':[[root*100,0]],'symbol':'diamond','symbolSize':12,'itemStyle':{'color':GOLD},
             'label':{'show':True,'formatter':f'Break-even {root*100:.2f}% of Q1','position':'bottom','distance':13,'fontSize':10,'color':GOLD,'backgroundColor':'#FFFFFFEA','padding':[3,5]},'z':7}]
    for i,(m,label) in enumerate(points):
        result=model(case,m,-20000)
        series.append({'id':f'sales_example_{i}','name':label,'type':'scatter','data':[[m*100,result.npv/1000]],
                       'symbolSize':15 if abs(m-selected)<1e-8 else 10,
                       'itemStyle':{'color':TEAL if result.npv>=0 else '#BE4660','borderColor':BG,'borderWidth':2},
                       'label':{'show':True,'formatter':label+'\n'+_money(result.npv),'position':'top' if i!=1 else 'bottom','distance':10,'fontSize':10,'color':INK,'backgroundColor':'#FFFFFFEB','padding':[4,6]},'z':6})
    return {'backgroundColor':BG,'animationDurationUpdate':300,'textStyle':{'fontFamily':'Inter,system-ui,sans-serif','color':MUTED},
            'aria':{'enabled':True,'description':'Single-variable sales sensitivity. Price is held at EUR5.10 and annual fixed costs at EUR220000. Sales coefficient scales each year of the Q1 forecast. 100 percent means no additional Q2 sales, not flat annual volume. Only unit sales vary.'},
            'title':{'text':'Price €5.10 · annual fixed costs €220k','left':0,'top':0,'textStyle':{'fontSize':11,'fontWeight':500,'color':MUTED}},
            'grid':{'left':64,'right':34,'top':55,'bottom':67},
            'tooltip':{'trigger':'axis','confine':True,'formatter':JsCode("function(items){let p=items.find(p=>p.seriesId==='sales_curve')||items[0];if(!p||!Array.isArray(p.value))return '';return '<b>'+p.value[0].toFixed(2)+'% of each Q1 year</b><br>NPV €'+(p.value[1]*1000).toLocaleString('en-IE',{maximumFractionDigits:0});}").js_code},
            'toolbox':{'show':True,'right':0,'top':0,'feature':{'saveAsImage':{'title':'Download PNG','name':'WakeUp_sales_only_sensitivity','pixelRatio':2}}},
            'xAxis':{'type':'value','min':80,'max':120,'interval':10,'name':'Sales volume / corresponding Q1 year','nameLocation':'middle','nameGap':39,'nameTextStyle':{'fontSize':11},
                     'axisLabel':{'fontSize':10,'formatter':'{value}%'},**_axis_style()},
            'yAxis':{'type':'value','min':lo,'max':hi,'splitNumber':4,'name':'NPV · EUR thousands','nameTextStyle':{'fontSize':10},'nameGap':20,
                     'axisLabel':{'fontSize':10,'formatter':JsCode("function(v){return Math.round(v).toLocaleString('en-IE');}").js_code},'axisLine':{'show':False},'axisTick':{'show':False},'splitLine':{'lineStyle':{'color':GRID,'type':'dashed'}}},
            'series':series}


def decision_frontier_options(case,active):
    """Price × total annual fixed-cost map: green BELOW zero-NPV cost ceiling."""
    xmin,xmax=_price_range(case,active)
    map_plan=1.1
    current_result=model(case,map_plan,active.fixed_cost_change,price_coefficient=active.price_coefficient,demand_elasticity=BASE_ELASTICITY)
    raw=[]
    for price in np.linspace(xmin,xmax,151):
        root=solve_fixed_cost(case,map_plan,price_coefficient=price/case.price,demand_elasticity=BASE_ELASTICITY)
        raw.append(None if root is None else case.annual_fixed_cost+root)
    finite=[v for v in raw if v is not None]
    ymin=max(0,min(100000,current_result.annual_fixed_cost-80000))
    ymax=max(350000,current_result.annual_fixed_cost+80000,max(finite,default=0)+25000)
    # Exact x-axis intersections keep shaded cells faithful at the plot limits.
    edges=[]
    for fixed in [ymin,ymax]:
        edges.extend(r*case.price for r in solve_price(case,map_plan,fixed-case.annual_fixed_cost,demand_elasticity=BASE_ELASTICITY,lower=xmin/case.price,upper=xmax/case.price))
    xs=sorted(set(float(p) for p in np.linspace(xmin,xmax,151))|{case.price,active.unit_price,4.50,5.355}|set(edges))
    boundary=[];clipped=[]
    for price in xs:
        root=solve_fixed_cost(case,map_plan,price_coefficient=price/case.price,demand_elasticity=BASE_ELASTICITY)
        ceiling=None if root is None else case.annual_fixed_cost+root
        boundary.append([price,None if ceiling is None else ceiling/1000])
        clipped.append(ymin if ceiling is None else min(ymax,max(ymin,ceiling)))
    polygons=[]
    for i in range(len(xs)-1):
        if clipped[i]<=ymin and clipped[i+1]<=ymin:continue
        polygons.append([xs[i],xs[i+1],ymin/1000,clipped[i]/1000,clipped[i+1]/1000])
    area=JsCode("""function(params,api){return {type:'polygon',shape:{points:[api.coord([api.value(0),api.value(2)]),api.coord([api.value(1),api.value(2)]),api.coord([api.value(1),api.value(4)]),api.coord([api.value(0),api.value(3)])]},style:{fill:'#DFF2E8',stroke:'none'}};}""").js_code
    chart={
      'backgroundColor':BG,'animation':False,'textStyle':{'fontFamily':'Inter, system-ui, sans-serif','color':MUTED},
      'aria':{'enabled':True,'description':'Joint price and total annual fixed-cost map. Green shading below the dashed zero-NPV cost ceiling denotes positive project NPV. Higher prices automatically reduce sales under an illustrative elasticity of 1. The Q2 annual sales plan is used throughout. Hollow points mark zero NPV; A, B, C and D show worked price/cost combinations.'},
      'title':{'text':'Annual fixed costs · EUR thousands','left':0,'top':0,'textStyle':{'fontSize':11,'fontWeight':500,'color':MUTED}},
      'legend':{'data':['NPV = 0 boundary'],'left':0,'top':27,'textStyle':{'fontSize':11,'color':MUTED}},
      'grid':{'left':54,'right':18,'top':78,'bottom':65},
      'tooltip':{'trigger':'item','confine':True,'formatter':JsCode("""function(p){if(p.seriesId==='decision_example')return '<b>'+p.data.name+'</b><br>Price €'+p.value[0].toFixed(3)+'/can<br>Annual fixed costs €'+(p.value[1]*1000).toLocaleString('en-IE',{maximumFractionDigits:0})+'<br>NPV €'+p.value[2].toLocaleString('en-IE',{maximumFractionDigits:0})+'<br>Fixed-cost headroom €'+p.value[3].toLocaleString('en-IE',{maximumFractionDigits:0})+'/year';if(p.seriesId==='decision_current')return '<b>Current scenario</b><br>Price €'+p.value[0].toFixed(2)+'/can<br>Annual fixed costs €'+(p.value[1]*1000).toLocaleString('en-IE',{maximumFractionDigits:0})+'<br>NPV €'+p.value[2].toLocaleString('en-IE',{maximumFractionDigits:0});if((p.seriesId==='decision_boundary'||p.seriesId==='decision_example_ceiling')&&p.value[1]!==null)return '<b>Zero-NPV cost ceiling</b><br>Price €'+p.value[0].toFixed(2)+'/can<br>Annual fixed costs €'+(p.value[1]*1000).toLocaleString('en-IE',{maximumFractionDigits:0});return '';}""").js_code},
      'toolbox':{'show':True,'right':0,'top':0,'feature':{'saveAsImage':{'title':'Download PNG','name':'WakeUp_price_fixed_cost_map','pixelRatio':2}}},
      'xAxis':{'type':'value','min':xmin,'max':xmax,'splitNumber':5,'name':'Price · EUR / can','nameLocation':'middle','nameGap':40,'nameTextStyle':{'fontSize':11,'color':MUTED},'axisLabel':{'fontSize':10,'hideOverlap':True,'formatter':JsCode("function(v){return '€'+v.toFixed(2);}").js_code},**_axis_style()},
      'yAxis':{'type':'value','min':ymin/1000,'max':ymax/1000,'splitNumber':5,'name':'','axisLabel':{'fontSize':10,'formatter':JsCode("function(v){return Math.round(v).toLocaleString('en-IE');}").js_code},'axisLine':{'show':False},'axisTick':{'show':False},'splitLine':{'lineStyle':{'color':GRID,'type':'dashed'}}},
      'graphic':[{'type':'text','right':22,'top':83,'style':{'text':'Green: positive NPV','fill':TEAL,'fontSize':10,'backgroundColor':'#FFFFFFCC','padding':4}}],
      'series':[
        {'id':'decision_positive_area','type':'custom','renderItem':area,'data':polygons,'silent':True,'clip':True,'encode':{'x':[0,1],'y':[2,3,4]},'z':1},
        {'id':'decision_boundary','name':'NPV = 0 boundary','type':'line','data':boundary,'showSymbol':False,'connectNulls':False,'clip':True,'lineStyle':{'color':TEAL,'type':'dashed','width':2.7},'z':3,
         'markLine':{'silent':True,'symbol':'none','data':[{'xAxis':case.price,'lineStyle':{'color':GREY,'type':'dotted'},'label':{'formatter':f'Original €{case.price:.2f}','position':'insideStartTop','fontSize':10}}]}},
        {'id':'decision_current','name':'Current scenario','type':'scatter','data':[[active.unit_price,current_result.annual_fixed_cost/1000,current_result.npv]] if abs(active.sales_coefficient-1.1)<1e-9 and not any(abs(active.unit_price-p)<1e-9 and abs(current_result.annual_fixed_cost-f)<1e-6 for p,f in [(4.50,190000),(case.price,220000),(5.355,250000),(4.50,220000)]) else [],'symbolSize':14,'itemStyle':{'color':TEAL if current_result.npv>=0 else '#BE4660','borderColor':BG,'borderWidth':2.5},'label':{'show':True,'formatter':'Now: '+_money(current_result.npv),'position':'bottom','fontSize':10,'color':INK,'backgroundColor':'#FFFFFFEB','padding':[4,6]},'z':6},
      ]}

    examples=[];ceilings=[];connectors=[]
    for name,p,fixed,pos in [('A',4.50,190000,'left'),('B',case.price,220000,'right'),('C',5.355,250000,'bottom'),('D',4.50,220000,'left')]:
        r=model(case,map_plan,fixed-case.annual_fixed_cost,price_coefficient=p/case.price,demand_elasticity=BASE_ELASTICITY)
        root=solve_fixed_cost(case,map_plan,price_coefficient=p/case.price,demand_elasticity=BASE_ELASTICITY)
        if root is None:continue
        ceiling=case.annual_fixed_cost+root
        examples.append({'name':name,'value':[p,fixed/1000,r.npv,ceiling-fixed],'itemStyle':{'color':'#BE4660' if r.npv<0 else INK},'label':{'show':True,'formatter':name,'position':pos,'fontSize':10,'color':INK,'backgroundColor':'#FFFFFFEB','padding':[3,5]}})
        if name in ('A','C'):
            ceilings.append([p,ceiling/1000])
            connectors.append([{'coord':[p,fixed/1000]},{'coord':[p,ceiling/1000]}])
    chart['series'].extend([
        {'id':'decision_example','name':'Worked examples','type':'scatter','data':examples,'symbolSize':11,'itemStyle':{'color':INK,'borderColor':BG,'borderWidth':2},'z':7,
         'markLine':{'silent':True,'symbol':['none','none'],'label':{'show':False},'lineStyle':{'color':GREY,'type':'dotted'},'data':connectors}},
        {'id':'decision_example_ceiling','name':'Example cost ceilings','type':'scatter','data':ceilings,'symbol':'emptyCircle','symbolSize':11,'itemStyle':{'color':TEAL,'borderWidth':2},'z':6}])
    return chart

# Compatibility names for older local entry points; active application uses the
# explicit operating_* API. Sales panel is a separate fixed-price/cost test.
sensitivity=operating_sensitivity
options=operating_options
