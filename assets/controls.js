export default function({data,parentElement,setStateValue}) {
  const salesRange=parentElement.querySelector('#sales-range');
  const costRange=parentElement.querySelector('#cost-range');
  const salesNumber=parentElement.querySelector('#sales-number');
  const costNumber=parentElement.querySelector('#cost-number');
  const salesOutput=parentElement.querySelector('#sales-readout');
  const costOutput=parentElement.querySelector('#cost-readout');
  const values={sales:Number(data.sales),cost:Number(data.cost)};
  salesRange.max=data.sales_max*100;
  salesNumber.max=data.sales_max;
  costRange.max=data.cost_max;
  costNumber.max=data.cost_max;
  parentElement.querySelector('#sales-max').textContent=(data.sales_max*100).toFixed(0)+'%';
  parentElement.querySelector('#cost-max').textContent='+€'+Math.round(data.cost_max/1000)+'k';
  salesRange.value=values.sales*100;
  costRange.value=values.cost;
  salesNumber.value=Number(values.sales.toFixed(6));
  costNumber.value=Number(values.cost.toFixed(2));
  const eur=new Intl.NumberFormat('en-IE',{style:'currency',currency:'EUR',maximumFractionDigits:0});
  function paint(){
    salesOutput.textContent=(values.sales*100).toFixed(2)+'%';
    costOutput.textContent=(values.cost>0?'+':'')+eur.format(values.cost);
    salesRange.style.setProperty('--fill',((values.sales-.5)/(data.sales_max-.5)*100)+'%');
    costRange.style.setProperty('--fill',((values.cost+240000)/(data.cost_max+240000)*100)+'%');
  }
  let timer;
  let lastSent=JSON.stringify({sales:values.sales,cost:values.cost,revision:data.revision});
  function publish(immediate=false){
    clearTimeout(timer);
    const send=()=>{
      const payload={sales:values.sales,cost:values.cost,revision:data.revision};
      const serial=JSON.stringify(payload);
      if(serial!==lastSent){lastSent=serial;setStateValue('scenario',payload);}
    };
    if(immediate)send(); else timer=setTimeout(send,160);
  }
  salesRange.oninput=()=>{values.sales=Number(salesRange.value)/100;salesNumber.value=Number(values.sales.toFixed(6));paint();publish();};
  costRange.oninput=()=>{values.cost=Number(costRange.value);costNumber.value=values.cost;paint();publish();};
  salesRange.onchange=()=>publish(true);
  costRange.onchange=()=>publish(true);
  function exact(which,immediate=true){
    const input=which==='sales'?salesNumber:costNumber;
    const v=Number(input.value),min=Number(input.min),max=Number(input.max);
    if(!Number.isFinite(v)||v<min||v>max){input.setCustomValidity(`Enter a value from ${min} to ${max}.`);input.reportValidity();return;}
    input.setCustomValidity('');values[which]=v;
    salesRange.value=values.sales*100;costRange.value=values.cost;paint();publish(immediate);
  }
  salesNumber.oninput=()=>exact('sales',false);costNumber.oninput=()=>exact('cost',false);
  salesNumber.onchange=()=>exact('sales');costNumber.onchange=()=>exact('cost');
  salesNumber.onblur=()=>exact('sales');costNumber.onblur=()=>exact('cost');
  salesNumber.onkeydown=(event)=>{if(event.key==='Enter')exact('sales');};
  costNumber.onkeydown=(event)=>{if(event.key==='Enter')exact('cost');};
  paint();
  return ()=>clearTimeout(timer);
}

