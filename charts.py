"""Sensitivity curves and actual-scenario comparisons from the shared model."""
import math
import numpy as np
from echarts_component import JsCode

from finance import model, npv_only, solve_sales, solve_fixed_cost

BG='#FFFFFF'
GRID='#E5EBF1'
INK='#172B42'
MUTED='#62758A'
TEAL='#087D68'
VIOLET='#6652B8'
GOLD='#96600B'
GREY='#8B99AA'


def scenario_kwargs(active):
    return {name: getattr(active, name, default) for name, default in [('price_coefficient', 1.0), ('variable_cost_coefficient', 1.0), ('demand_elasticity', 0.0)]}


def sensitivity(case, active, axis='Sales coefficient', full_range=False):
    sales_axis=axis=='Sales coefficient'
    kwargs=scenario_kwargs(active)
    root=solve_sales(case,active.fixed_cost_change,**kwargs) if sales_axis else solve_fixed_cost(case,active.sales_coefficient,**kwargs)
    current=active.sales_coefficient if sales_axis else active.fixed_cost_change
    anchors=[1.0,1.1,current] if sales_axis else [0.0,-20000.0,current]
    if root is not None:anchors.append(root)
    if full_range:
        if sales_axis:
            lo=max(0,min(.5,min(anchors)-.05))
            hi=math.ceil(max(1.5,max(anchors)+.1)*10)/10
        else:
            lo=-case.annual_fixed_cost
            hi=math.ceil(max(300000,max(anchors)+30000)/50000)*50000
    elif sales_axis:
        lo=max(0,math.floor((min(anchors)-.07)*20)/20)
        hi=math.ceil((max(anchors)+.07)*20)/20
        if hi-lo<.30:
            lo=max(0,math.floor((lo-(.30-(hi-lo))/2)*20)/20)
            hi=max(hi,lo+.30)
    else:
        pad=max(20000,(max(anchors)-min(anchors))*.15)
        lo=max(-case.annual_fixed_cost,math.floor((min(anchors)-pad)/50000)*50000)
        hi=math.ceil((max(anchors)+pad)/50000)*50000
        if hi-lo<100000:hi=lo+100000
    xs=sorted(set([float(x) for x in np.linspace(lo,hi,111)]+anchors))
    rows=[]
    for x in xs:
        base=model(case,x,0) if sales_axis else model(case,1,x)
        selected=model(case,x,active.fixed_cost_change,**kwargs) if sales_axis else model(case,active.sales_coefficient,x,**kwargs)
        rows.append({'x':x,'sales_coefficient':selected.sales_coefficient,'fixed_cost_change_eur':selected.fixed_cost_change,'effective_sales_coefficient':getattr(selected,'effective_sales_coefficient',selected.sales_coefficient),
                     'reference_npv_eur':base.npv,'current_npv_eur':selected.npv,'reference_irr':base.irr,'current_irr':selected.irr,'wacc':case.wacc})
    return rows,root


def options(case, active, rows, root, axis, metric):
    sales_axis=axis=='Sales coefficient'
    npv_metric=metric=='NPV'
    color=TEAL if npv_metric else VIOLET
    xfactor=1 if sales_axis else 1000
    yfactor=1000 if npv_metric else 1
    base_key='reference_npv_eur' if npv_metric else 'reference_irr'
    active_key='current_npv_eur' if npv_metric else 'current_irr'
    reference=[[r['x']/xfactor,r[base_key]/yfactor if r[base_key] is not None else None] for r in rows]
    current=[[r['x']/xfactor,r[active_key]/yfactor if r[active_key] is not None else None] for r in rows]
    baseline=model(case)
    base_x=1.0 if sales_axis else 0.0
    base_y=baseline.npv/1000 if npv_metric else baseline.irr
    point_x=active.sales_coefficient if sales_axis else active.fixed_cost_change/1000
    point_y=active.npv/1000 if npv_metric else active.irr
    target=0 if npv_metric else case.wacc
    all_y=[p[1] for p in reference+current if p[1] is not None]+[target,base_y]
    if point_y is not None:all_y.append(point_y)
    span=max(all_y)-min(all_y)
    padding=max(span*.20,45 if npv_metric else .018)
    ymin,ymax=min(all_y)-padding,max(all_y)+padding
    xmin,xmax=rows[0]['x']/xfactor,rows[-1]['x']/xfactor
    same=point_y is not None and abs(point_x-base_x)<1e-10 and abs(point_y-base_y)<1e-9
    at_break_even=abs(active.npv)<=1
    current_label=('BREAK-EVEN\n' if at_break_even else 'Q1 / NOW\n' if same else 'NOW\n')+(f'€{active.npv:,.0f}' if npv_metric else f'{point_y:.6f}' if point_y is not None else 'Unavailable')
    label_position='left' if point_x>xmin+(xmax-xmin)*.70 else 'right'
    # Direct labels remain legible when the two scenario points are close.
    label_offset=[0,-30] if abs(point_x-base_x)<(xmax-xmin)*.10 and not same else [0,-10]
    guide_lines=[{'yAxis':target,'name':'NPV = 0' if npv_metric else f'WACC {case.wacc:.6f}',
                  'lineStyle':{'color':GOLD,'type':'dashed','width':1.4},
                  'label':{'show':True,'position':'insideEndBottom','color':GOLD,'fontSize':11,'padding':[4,3],
                           'backgroundColor':'#FFFFFFDD','formatter':'NPV = 0' if npv_metric else f'WACC {case.wacc:.6f}'}}]
    guide_lines.append({'xAxis':point_x,'label':{'show':False},'lineStyle':{'color':color,'type':'dotted','width':1.2,'opacity':.55}})
    if root is not None and not at_break_even:
        guide_lines.append({'xAxis':root/xfactor,'label':{'show':False},'lineStyle':{'color':GOLD,'type':'dotted','width':1,'opacity':.5}})
    xformatter=JsCode("function(v){return Math.round(v*100)+'%';}").js_code if sales_axis else JsCode("function(v){return '€'+Math.round(v)+'k';}").js_code
    tooltip=JsCode("""function(items){
      if(!Array.isArray(items))items=[items];
      let first=items.find(p=>Array.isArray(p.value));if(!first)return '';
      let x=first.value[0];
      let heading=SALES ? (x*100).toFixed(2)+'% of Q1 demand before pricing' : 'Annual fixed-cost change: €'+(x*1000).toLocaleString('en-IE',{maximumFractionDigits:0});
      let html='<div style="font-weight:650;margin-bottom:8px">'+heading+'</div>';
      for(let p of items){if(!Array.isArray(p.value)||p.value[1]===null||p.seriesId==='comparison_link')continue;
        let y=NPV?'€'+(p.value[1]*1000).toLocaleString('en-IE',{maximumFractionDigits:0}):p.value[1].toFixed(6);
        html+='<div style="margin:5px 0">'+p.marker+' '+p.seriesName+': <b>'+y+'</b></div>';
      }return html;
    }""".replace('SALES','true' if sales_axis else 'false').replace('NPV','true' if npv_metric else 'false')).js_code
    opts={
      'backgroundColor':BG,'animation':True,'animationDuration':450,'animationDurationUpdate':450,'animationEasingUpdate':'cubicOut',
      'aria':{'enabled':True,'description':f'{metric} sensitivity to {axis}. Demand is measured before the assumed price response. Grey denotes the Q1 reference assumptions; the dashed curve holds current price, variable cost and elasticity assumptions. The ring is the selected scenario, and the diamond marks break-even.'},
      'color':[GREY,color,GOLD],
      'textStyle':{'fontFamily':'Inter, system-ui, sans-serif','color':MUTED},
      'grid':{'left':58,'right':24,'top':66,'bottom':60},
      'legend':{'data':['Q1 reference','Selected assumptions'],'left':0,'top':0,'textStyle':{'color':MUTED,'fontSize':10},'itemWidth':20,'itemHeight':8,'itemGap':12},
      'tooltip':{'trigger':'axis','confine':True,'backgroundColor':'#FFFFFFF5','borderColor':'#D4DEE8','padding':12,'textStyle':{'color':INK,'fontSize':11},'formatter':tooltip,'axisPointer':{'type':'line','lineStyle':{'color':MUTED,'type':'dashed'}}},
      'toolbox':{'show':True,'right':0,'top':-2,'iconStyle':{'borderColor':MUTED},'feature':{'saveAsImage':{'title':'Download PNG','name':f'Kobuki_Group2_{metric}_{"sales" if sales_axis else "cost"}','pixelRatio':2,'backgroundColor':BG}}},
      'xAxis':{'type':'value','min':xmin,'max':xmax,'splitNumber':4,'name':'Demand before pricing vs Q1' if sales_axis else 'Fixed-cost change / year','nameLocation':'middle','nameGap':38,'nameTextStyle':{'fontSize':11,'color':MUTED},'axisLabel':{'color':MUTED,'fontSize':11,'formatter':xformatter,'hideOverlap':True},'axisLine':{'lineStyle':{'color':'#CBD5E0'}},'axisTick':{'show':False},'splitLine':{'show':False}},
      'yAxis':{'type':'value','min':ymin,'max':ymax,'splitNumber':4,'name':'EUR thousands' if npv_metric else 'IRR · decimal','nameGap':20,'nameTextStyle':{'color':MUTED,'fontSize':11},'axisLabel':{'color':MUTED,'fontSize':11,'formatter':JsCode("function(v){return "+("Math.round(v).toLocaleString('en-IE')" if npv_metric else "v.toFixed(2)")+";}").js_code},'axisLine':{'show':False},'axisTick':{'show':False},'splitLine':{'lineStyle':{'color':GRID,'type':'dashed'}}},
      'series':[
        {'id':'q1_curve','name':'Q1 reference','type':'line','data':reference,'showSymbol':False,'connectNulls':False,'lineStyle':{'width':2.3,'color':GREY},'emphasis':{'focus':'series'},'z':2},
        {'id':'scenario_curve','name':'Selected assumptions','type':'line','data':current,'showSymbol':False,'connectNulls':False,'lineStyle':{'width':2.7,'color':color,'type':'dashed'},
         'markArea':{'silent':True,'label':{'show':False},'data':[[{'yAxis':target,'itemStyle':{'color':'#ECF7F2AA'}},{'yAxis':ymax}],[{'yAxis':ymin,'itemStyle':{'color':'#FFF0F2A6'}},{'yAxis':target}]]},
         'markLine':{'silent':True,'symbol':'none','data':guide_lines},'emphasis':{'focus':'series'},'z':3},
        {'id':'q1_point','name':'Q1 baseline','type':'scatter','data':[[base_x,base_y]],'symbol':'emptyCircle','symbolSize':11,
         'itemStyle':{'color':GREY,'borderWidth':2},'label':{'show':not same,'formatter':'Q1','position':'bottom','distance':9,'color':MUTED,'fontSize':11,'backgroundColor':'#FFFFFFE6','padding':[2,4]},'z':6},
        {'id':'current_point','name':'Current scenario','type':'effectScatter','data':[[point_x,point_y]] if point_y is not None else [],'symbolSize':15,'rippleEffect':{'scale':2.5,'brushType':'stroke','period':4},
         'itemStyle':{'color':color,'borderColor':'#FFFFFF','borderWidth':3},
         'label':{'show':True,'position':label_position,'offset':label_offset,'distance':14,'formatter':current_label,'fontSize':12,'fontWeight':650,'lineHeight':18,'color':color,'backgroundColor':'#FFFFFFF5','borderColor':color,'borderWidth':1,'borderRadius':6,'padding':[7,10]},'z':9},
      ],
    }
    if point_y is not None and not same:
        opts['series'].insert(2,{'id':'comparison_link','name':'Q1 to current','type':'line','data':[[base_x,base_y],[point_x,point_y]],'showSymbol':False,'silent':True,'lineStyle':{'color':color,'type':'dotted','width':1.4,'opacity':.7},'z':4})
    if root is not None:
        opts['series'].append({'id':'break_even','name':'Break-even','type':'scatter','data':[[root/xfactor,target]],'symbol':'diamond','symbolSize':12,'itemStyle':{'color':GOLD,'borderColor':'#FFFFFF','borderWidth':1.5},'z':7})
    return opts


def pricing_options(case, active):
    """Price scenarios: fixed-volume upside versus explicitly assumed demand response.

    All prices, volumes and NPVs are modelled, not observations. Demand before
    pricing, annual fixed costs and unit variable cost remain held constant.
    """
    from finance import solve_price

    lower, upper = .8, 1.3
    elasticity = getattr(active, 'demand_elasticity', 0.0)
    unit_cost = getattr(active, 'variable_cost_coefficient', 1.0)
    selected_price = getattr(active, 'price_coefficient', 1.0)
    roots = solve_price(case, active.sales_coefficient, active.fixed_cost_change,
                        variable_cost_coefficient=unit_cost,
                        demand_elasticity=elasticity, lower=lower, upper=upper)
    coefficients = sorted(set([float(x) for x in np.linspace(lower, upper, 121)]
                              + [1.0] + list(roots)
                              + ([selected_price] if lower <= selected_price <= upper else [])))
    fixed, response = [], []
    for coefficient in coefficients:
        common = dict(price_coefficient=coefficient,
                      variable_cost_coefficient=unit_cost)
        fixed.append([coefficient * case.price,
                      npv_only(case, active.sales_coefficient, active.fixed_cost_change,
                               demand_elasticity=0.0, **common) / 1000])
        response.append([coefficient * case.price,
                         npv_only(case, active.sales_coefficient, active.fixed_cost_change,
                                  demand_elasticity=elasticity, **common) / 1000])
    response_label = f'Response · ε = {elasticity:g}'
    fixed_label = 'Fixed volume'
    if elasticity == 0:
        response_label = 'Fixed volume · ε = 0'
    yvalues = [p[1] for p in fixed + response] + [0]
    span = max(yvalues) - min(yvalues)
    padding = max(span * .13, 25)
    ymin, ymax = min(yvalues) - padding, max(yvalues) + padding
    current_in_range = lower <= selected_price <= upper
    price_formatter = JsCode("function(v){return '€'+v.toFixed(2);}").js_code
    tooltip = JsCode("""function(items){
      if(!Array.isArray(items))items=[items];
      const first=items.find(p=>Array.isArray(p.value));if(!first)return '';
      let html='<b>Price per can: €'+first.value[0].toFixed(2)+'</b>';
      for(const p of items){if(!Array.isArray(p.value))continue;
        html+='<div style="margin-top:6px">'+p.marker+' '+p.seriesName+': <b>€'+
          (p.value[1]*1000).toLocaleString('en-IE',{maximumFractionDigits:0})+'</b></div>';
      }return html;
    }""").js_code
    opts = {
        'backgroundColor': BG, 'animationDurationUpdate': 350,
        'textStyle': {'fontFamily': 'Inter, system-ui, sans-serif', 'color': MUTED},
        'aria': {'enabled': True, 'description':
                 'Modelled NPV as selling price changes, holding pre-price demand, '
                 'annual fixed costs and unit variable cost unchanged. The dashed '
                 f'curve uses an assumed elasticity of {elasticity:g}; this is not '
                 'an estimated customer response. Diamonds are price break-even '
                 'points within 80% to 130% of the original selling price.'},
        'title': {'text': 'NPV · EUR thousands', 'left': 0, 'top': 0,
                  'textStyle': {'fontSize': 11, 'fontWeight': 500, 'color': MUTED}},
        'legend': {'type': 'scroll', 'data': ([fixed_label] if elasticity != 0 else []) + [response_label],
                   'left': 0, 'right': 0, 'top': 27, 'itemWidth': 19, 'itemGap': 12,
                   'textStyle': {'fontSize': 11, 'color': MUTED}},
        'grid': {'left': 52, 'right': 18, 'top': 78, 'bottom': 60},
        'tooltip': {'trigger': 'axis', 'confine': True, 'backgroundColor': '#FFFFFFF5',
                    'borderColor': '#D4DEE8', 'textStyle': {'color': INK, 'fontSize': 11},
                    'formatter': tooltip},
        'toolbox': {'show': True, 'right': 0, 'top': 0,
                    'feature': {'saveAsImage': {'title': 'Download PNG',
                       'name': 'WakeUp_price_volume_tradeoff', 'pixelRatio': 2}}},
        'xAxis': {'type': 'value', 'min': lower * case.price, 'max': upper * case.price,
                  'splitNumber': 5, 'name': 'Price · EUR / can',
                  'nameLocation': 'middle', 'nameGap': 38,
                  'nameTextStyle': {'fontSize': 11, 'color': MUTED},
                  'axisLabel': {'formatter': price_formatter, 'fontSize': 11,
                                'hideOverlap': True, 'color': MUTED},
                  'axisTick': {'show': False}, 'splitLine': {'show': False},
                  'axisLine': {'lineStyle': {'color': '#CBD5E0'}}},
        'yAxis': {'type': 'value', 'min': ymin, 'max': ymax, 'splitNumber': 4,
                  'name': '', 'nameGap': 21,
                  'nameTextStyle': {'fontSize': 11, 'color': MUTED},
                  'axisLabel': {'fontSize': 11, 'color': MUTED,
                    'formatter': JsCode("function(v){return Math.round(v).toLocaleString('en-IE');}").js_code},
                  'axisLine': {'show': False}, 'axisTick': {'show': False},
                  'splitLine': {'lineStyle': {'color': GRID, 'type': 'dashed'}}},
        'series': []}
    if elasticity != 0:
        opts['series'].append({'id': 'price_fixed_volume', 'name': fixed_label,
            'type': 'line', 'data': fixed, 'showSymbol': False,
            'lineStyle': {'color': GREY, 'width': 2.2}, 'z': 2})
    opts['series'].append({'id': 'price_response', 'name': response_label,
        'type': 'line', 'data': response, 'showSymbol': False,
        'lineStyle': {'color': TEAL, 'width': 2.8, 'type': 'dashed'}, 'z': 3,
        'markArea': {'silent': True, 'label': {'show': False}, 'data': [
            [{'yAxis': 0, 'itemStyle': {'color': '#ECF7F2AA'}}, {'yAxis': ymax}],
            [{'yAxis': ymin, 'itemStyle': {'color': '#FFF0F2A6'}}, {'yAxis': 0}]]},
        'markLine': {'silent': True, 'symbol': 'none', 'data': [
            {'yAxis': 0, 'name': 'NPV = 0',
             'lineStyle': {'color': GOLD, 'type': 'dashed', 'width': 1.3},
             'label': {'formatter': 'NPV = 0', 'color': GOLD,
                       'position': 'insideEndBottom'}},
            {'xAxis': case.price, 'name': 'Original price',
             'lineStyle': {'color': GREY, 'type': 'dotted'},
             'label': {'formatter': f'Original €{case.price:.2f}', 'color': MUTED,
                       'position': 'insideEndTop', 'fontSize': 10}}]}})
    opts['series'].append({'id': 'price_current', 'name': 'Current scenario',
        'type': 'scatter', 'data': [[case.price * selected_price, active.npv / 1000]] if current_in_range else [],
        'symbolSize': 12, 'itemStyle': {'color': TEAL, 'borderColor': BG, 'borderWidth': 2},
        'label': {'show': True, 'formatter': f'Now: {"-" if active.npv < 0 else ""}€{abs(active.npv):,.0f}',
                  'position': 'top', 'distance': 10, 'color': TEAL,
                  'fontSize': 11, 'backgroundColor': '#FFFFFFE8', 'padding': [3, 5]}, 'z': 6})
    if roots:
        opts['series'].append({'id': 'price_break_even', 'name': 'Price break-even',
            'type': 'scatter', 'data': [[root * case.price, 0] for root in roots],
            'symbol': 'diamond', 'symbolSize': 12,
            'itemStyle': {'color': GOLD, 'borderColor': BG, 'borderWidth': 1.5}, 'z': 7})
    return opts


def decision_frontier_options(case, active):
    """Joint price-demand decision map with shaded positive-NPV region.

    Only the selected scenario is an outcome marker. Original price and Q2
    demand are benchmarks evaluated under the selected held cost assumptions.
    """
    kwargs = scenario_kwargs(active)
    current_price = case.price * kwargs['price_coefficient']
    xmin = min(case.price * .8, current_price * .97)
    xmax = max(case.price * 1.3, current_price * 1.03)
    ymin = max(0.0, min(.75, active.sales_coefficient - .1))
    ymax = max(1.35, active.sales_coefficient + .1)
    from finance import solve_price
    # Include exact intersections with the plot limits before constructing the
    # fill, so shading begins at a true boundary rather than at a nearby sample.
    edge_prices = []
    for demand in (ymin, ymax):
        edge_prices.extend(root * case.price for root in solve_price(
            case, demand, active.fixed_cost_change,
            variable_cost_coefficient=kwargs['variable_cost_coefficient'],
            demand_elasticity=kwargs['demand_elasticity'],
            lower=xmin / case.price, upper=xmax / case.price))
    price_points = sorted(set([float(x) for x in np.linspace(xmin, xmax, 151)]
                              + [case.price, current_price] + edge_prices))
    boundary, thresholds = [], []
    for price in price_points:
        point_kwargs = dict(kwargs, price_coefficient=price / case.price)
        root = solve_sales(case, active.fixed_cost_change, **point_kwargs)
        top_npv = npv_only(case, ymax, active.fixed_cost_change, **point_kwargs)
        bottom_npv = npv_only(case, ymin, active.fixed_cost_change, **point_kwargs)
        # The positive region is above the root when demand improves NPV.
        # If every visible demand value fails, its fill height is exactly zero.
        if top_npv > 0:
            threshold = ymin if bottom_npv >= 0 else max(ymin, min(ymax, root if root is not None else ymax))
        else:
            threshold = ymax
        thresholds.append(threshold)
        boundary.append([price, root] if root is not None else [price, None])
    polygons = []
    for i in range(len(price_points) - 1):
        left, right = price_points[i], price_points[i+1]
        left_root, right_root = thresholds[i], thresholds[i+1]
        if left_root >= ymax and right_root >= ymax:
            continue
        polygons.append([left, right, left_root, right_root, ymax])
    render_area = JsCode("""function(params, api){
      let p=[api.coord([api.value(0),api.value(4)]),
             api.coord([api.value(1),api.value(4)]),
             api.coord([api.value(1),api.value(3)]),
             api.coord([api.value(0),api.value(2)])];
      return {type:'polygon',shape:{points:p},style:{fill:'#DFF2E8',stroke:'none'}};
    }""").js_code
    price_formatter = JsCode("function(v){return '€'+v.toFixed(2);}").js_code
    demand_formatter = JsCode("function(v){return v.toFixed(2)+'×';}").js_code
    frontier_tooltip = JsCode("""function(p){
      if(p.seriesId==='decision_current')return '<b>Current scenario</b><br>Price €'+p.value[0].toFixed(2)+
        '/can<br>Demand before pricing '+p.value[1].toFixed(4)+'× Q1<br>NPV €'+
        p.value[2].toLocaleString('en-IE',{maximumFractionDigits:0});
      if(p.seriesId==='decision_boundary')return '<b>NPV = 0 boundary</b><br>Price €'+
        p.value[0].toFixed(2)+'/can<br>Minimum demand '+p.value[1].toFixed(4)+'× Q1';
      return '';
    }""").js_code
    return {
        'backgroundColor': BG, 'animation': False,
        'aria': {'enabled': True, 'description':
            'Joint selling-price and pre-price-demand decision map. The dashed '
            'boundary gives zero NPV and the green region gives positive NPV. '
            f'Annual fixed costs are EUR {active.annual_fixed_cost:,.0f}, '
            f'unit variable cost is EUR {case.unit_variable_cost * kwargs["variable_cost_coefficient"]:.2f}, '
            f'and assumed demand elasticity is {kwargs["demand_elasticity"]:g}.'},
        'textStyle': {'fontFamily': 'Inter, system-ui, sans-serif', 'color': MUTED},
        'title': {'text': 'Pre-price demand · × Q1', 'left': 0, 'top': 0,
                  'textStyle': {'fontSize': 11, 'fontWeight': 500, 'color': MUTED}},
        'grid': {'left': 54, 'right': 18, 'top': 78, 'bottom': 65},
        'tooltip': {'trigger': 'item', 'confine': True,
            'formatter': frontier_tooltip, 'backgroundColor': '#FFFFFFF5',
            'textStyle': {'color': INK, 'fontSize': 11}},
        'legend': {'data': ['NPV = 0 boundary'], 'left': 0, 'top': 27,
            'textStyle': {'color': MUTED, 'fontSize': 11}},
        'toolbox': {'show': True, 'right': 0, 'top': 0,
            'feature': {'saveAsImage': {'title': 'Download PNG',
                'name': 'WakeUp_price_demand_decision_map', 'pixelRatio': 2}}},
        'xAxis': {'type': 'value', 'min': xmin, 'max': xmax, 'splitNumber': 5,
            'name': 'Price · EUR / can', 'nameLocation': 'middle', 'nameGap': 40,
            'nameTextStyle': {'fontSize': 11, 'color': MUTED},
            'axisLabel': {'formatter': price_formatter, 'color': MUTED, 'fontSize': 11, 'hideOverlap': True},
            'axisLine': {'lineStyle': {'color': '#CBD5E0'}}, 'axisTick': {'show': False},
            'splitLine': {'lineStyle': {'color': GRID, 'type': 'dashed'}}},
        'yAxis': {'type': 'value', 'min': ymin, 'max': ymax, 'splitNumber': 5,
            'name': '', 'nameGap': 22,
            'nameTextStyle': {'fontSize': 11, 'color': MUTED},
            'axisLabel': {'formatter': demand_formatter, 'color': MUTED, 'fontSize': 11},
            'axisLine': {'show': False}, 'axisTick': {'show': False},
            'splitLine': {'lineStyle': {'color': GRID, 'type': 'dashed'}}},
        'graphic': [{'type': 'text', 'right': 22, 'top': 83,
            'style': {'text': 'Green: positive NPV', 'fill': TEAL, 'fontSize': 11,
                      'backgroundColor': '#FFFFFFBB', 'padding': 4}}],
        'series': [
            {'id': 'decision_positive_area', 'type': 'custom', 'renderItem': render_area,
             'data': polygons, 'silent': True, 'clip': True, 'z': 1,
             'encode': {'x': [0, 1], 'y': [2, 3, 4]}},
            {'id': 'decision_boundary', 'name': 'NPV = 0 boundary', 'type': 'line',
             'data': boundary, 'showSymbol': False, 'connectNulls': False, 'clip': True,
             'lineStyle': {'color': TEAL, 'type': 'dashed', 'width': 2.7}, 'z': 4,
             'markLine': {'silent': True, 'symbol': 'none', 'data': [
                 {'xAxis': case.price, 'lineStyle': {'color': GREY, 'type': 'dotted'},
                  'label': {'formatter': f'Original price €{case.price:.2f}', 'position': 'insideStartTop', 'fontSize': 10}},
                 {'yAxis': 1.1, 'lineStyle': {'color': GREY, 'type': 'dotted'},
                  'label': {'formatter': 'Q2 demand benchmark 1.10×', 'position': 'insideEndTop', 'fontSize': 10}}]}},
            {'id': 'decision_current', 'name': 'Current scenario', 'type': 'scatter',
             'data': [[current_price, active.sales_coefficient, active.npv]], 'symbolSize': 14,
             'itemStyle': {'color': TEAL if active.npv >= 0 else '#BE4660', 'borderColor': BG, 'borderWidth': 2.5},
             'label': {'show': True, 'formatter': f'Now: {"-" if active.npv < 0 else ""}€{abs(active.npv):,.0f}', 'position': 'bottom',
                       'fontSize': 11, 'color': INK, 'backgroundColor': '#FFFFFFEB', 'padding': [4, 6]}, 'z': 6}
        ]}
