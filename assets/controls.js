export default function({data,parentElement,setStateValue}) {
  const priceRange=parentElement.querySelector('#price-range');
  const costRange=parentElement.querySelector('#cost-range');
  const priceNumber=parentElement.querySelector('#price-number');
  const costNumber=parentElement.querySelector('#cost-number');
  const priceOutput=parentElement.querySelector('#price-readout');
  const costOutput=parentElement.querySelector('#cost-readout');
  const values={price:Number(data.price),cost:Number(data.cost)};
  priceRange.min=data.price_min;priceRange.max=data.price_max;
  priceNumber.min=data.price_min;priceNumber.max=data.price_max;
  costRange.max=data.cost_max;costNumber.max=data.cost_max;
  parentElement.querySelector('#price-max').textContent='€'+Number(data.price_max).toFixed(2);
  parentElement.querySelector('#price-min').textContent='€'+Number(data.price_min).toFixed(2);
  parentElement.querySelector('#cost-max').textContent='+€'+Math.round(data.cost_max/1000)+'k';
  priceRange.value=values.price;costRange.value=values.cost;
  priceNumber.value=Number(values.price.toFixed(8));costNumber.value=Number(values.cost.toFixed(2));
  const eur=new Intl.NumberFormat('en-IE',{style:'currency',currency:'EUR',maximumFractionDigits:0});
  function paint(){
    priceOutput.textContent='€'+values.price.toFixed(4);
    costOutput.textContent=(values.cost>0?'+':'')+eur.format(values.cost);
    priceRange.style.setProperty('--fill',((values.price-data.price_min)/(data.price_max-data.price_min)*100)+'%');
    costRange.style.setProperty('--fill',((values.cost+240000)/(data.cost_max+240000)*100)+'%');
  }
  let timer;
  let lastSent=JSON.stringify({price:values.price,cost:values.cost,revision:data.revision});
  function publish(immediate=false){
    clearTimeout(timer);
    const send=()=>{
      const payload={price:values.price,cost:values.cost,revision:data.revision};
      const serial=JSON.stringify(payload);
      if(serial!==lastSent){lastSent=serial;setStateValue('scenario',payload);}
    };
    if(immediate)send();else timer=setTimeout(send,160);
  }
  priceRange.oninput=()=>{values.price=Number(priceRange.value);priceNumber.value=values.price;paint();publish();};
  costRange.oninput=()=>{values.cost=Number(costRange.value);costNumber.value=values.cost;paint();publish();};
  priceRange.onchange=()=>publish(true);costRange.onchange=()=>publish(true);
  function exact(which,immediate=true){
    const input=which==='price'?priceNumber:costNumber;
    if(input.value.trim()==='')return;
    const v=Number(input.value),min=Number(input.min),max=Number(input.max);
    if(!Number.isFinite(v)||v<min||v>max){input.setCustomValidity(`Enter a value from ${min} to ${max}.`);input.reportValidity();return;}
    input.setCustomValidity('');values[which]=v;
    priceRange.value=values.price;costRange.value=values.cost;paint();publish(immediate);
  }
  priceNumber.oninput=()=>exact('price',false);costNumber.oninput=()=>exact('cost',false);
  priceNumber.onchange=()=>exact('price');costNumber.onchange=()=>exact('cost');
  priceNumber.onblur=()=>exact('price');costNumber.onblur=()=>exact('cost');
  priceNumber.onkeydown=(e)=>{if(e.key==='Enter')exact('price');};
  costNumber.onkeydown=(e)=>{if(e.key==='Enter')exact('cost');};
  paint();return ()=>clearTimeout(timer);
}
