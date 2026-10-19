export default function({data,parentElement}) {
  const container=parentElement.querySelector('#chart');
  container.style.height=data.height||'345px';
  // The only executable callbacks are local functions authored in charts.py.
  function revive(value){
    if(Array.isArray(value))return value.map(revive);
    if(value && typeof value==='object'){
      if(Object.keys(value).length===1 && typeof value.$js==='string'){
        return new Function('return ('+value.$js+')')();
      }
      return Object.fromEntries(Object.entries(value).map(([key,v])=>[key,revive(v)]));
    }
    return value;
  }
  const existing=globalThis.echarts.getInstanceByDom(container);
  const chart=existing||globalThis.echarts.init(container,null,{renderer:'canvas'});
  const reduceMotion=globalThis.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const cache=globalThis.__kobukiChartCache||(globalThis.__kobukiChartCache=new Map());
  const next=revive(data.options);
  if(reduceMotion){next.animation=false;next.series.forEach(s=>{if(s.type==='effectScatter')s.type='scatter';});}
  if(!existing && cache.has(data.chartId) && !reduceMotion){
    const previous=revive(cache.get(data.chartId));
    previous.animation=false;
    chart.setOption(previous,{notMerge:true,silent:true});
  }
  chart.setOption(next,{notMerge:false,replaceMerge:['series'],lazyUpdate:false});
  cache.set(data.chartId,data.options);
  const observer=new ResizeObserver(()=>chart.resize());
  observer.observe(container);
  return ()=>{observer.disconnect();chart.dispose();};
}

