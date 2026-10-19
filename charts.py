"""Sensitivity curves and actual-scenario comparisons from the shared model."""
import math
import numpy as np
from echarts_component import JsCode

from finance import model, solve_sales, solve_fixed_cost

BG='#FFFFFF'
GRID='#E5EBF1'
INK='#172B42'
MUTED='#62758A'
TEAL='#087D68'
VIOLET='#6652B8'
GOLD='#96600B'
GREY='#8B99AA'


def sensitivity(case, active, axis='Sales coefficient', full_range=False):
    sales_axis=axis=='Sales coefficient'
    root=solve_sales(case,active.fixed_cost_change) if sales_axis else solve_fixed_cost(case,active.sales_coefficient)
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
        selected=model(case,x,active.fixed_cost_change) if sales_axis else model(case,active.sales_coefficient,x)
        rows.append({'x':x,'sales_coefficient':selected.sales_coefficient,'fixed_cost_change_eur':selected.fixed_cost_change,
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
      let heading=SALES ? (x*100).toFixed(2)+'% of Q1 unit sales' : 'Annual fixed-cost change: €'+(x*1000).toLocaleString('en-IE',{maximumFractionDigits:0});
      let html='<div style="font-weight:650;margin-bottom:8px">'+heading+'</div>';
      for(let p of items){if(!Array.isArray(p.value)||p.value[1]===null||p.seriesId==='comparison_link')continue;
        let y=NPV?'€'+(p.value[1]*1000).toLocaleString('en-IE',{maximumFractionDigits:0}):p.value[1].toFixed(6);
        html+='<div style="margin:5px 0">'+p.marker+' '+p.seriesName+': <b>'+y+'</b></div>';
      }return html;
    }""".replace('SALES','true' if sales_axis else 'false').replace('NPV','true' if npv_metric else 'false')).js_code
    opts={
      'backgroundColor':BG,'animation':True,'animationDuration':450,'animationDurationUpdate':450,'animationEasingUpdate':'cubicOut',
      'aria':{'enabled':True,'description':f'{metric} sensitivity to {axis}. Grey denotes the Q1 reference assumptions; the dashed curve uses current assumptions. The ring is the selected scenario, and the diamond marks break-even.'},
      'color':[GREY,color,GOLD],
      'textStyle':{'fontFamily':'Inter, system-ui, sans-serif','color':MUTED},
      'grid':{'left':58,'right':24,'top':66,'bottom':60},
      'legend':{'data':['Q1 reference','Selected assumptions'],'left':0,'top':0,'textStyle':{'color':MUTED,'fontSize':10},'itemWidth':20,'itemHeight':8,'itemGap':12},
      'tooltip':{'trigger':'axis','confine':True,'backgroundColor':'#FFFFFFF5','borderColor':'#D4DEE8','padding':12,'textStyle':{'color':INK,'fontSize':11},'formatter':tooltip,'axisPointer':{'type':'line','lineStyle':{'color':MUTED,'type':'dashed'}}},
      'toolbox':{'show':True,'right':0,'top':-2,'iconStyle':{'borderColor':MUTED},'feature':{'saveAsImage':{'title':'Download PNG','name':f'Kobuki_Group2_{metric}_{"sales" if sales_axis else "cost"}','pixelRatio':2,'backgroundColor':BG}}},
      'xAxis':{'type':'value','min':xmin,'max':xmax,'splitNumber':4,'name':'Unit sales vs Q1' if sales_axis else 'Fixed-cost change / year','nameLocation':'middle','nameGap':38,'nameTextStyle':{'fontSize':11,'color':MUTED},'axisLabel':{'color':MUTED,'fontSize':11,'formatter':xformatter,'hideOverlap':True},'axisLine':{'lineStyle':{'color':'#CBD5E0'}},'axisTick':{'show':False},'splitLine':{'show':False}},
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
