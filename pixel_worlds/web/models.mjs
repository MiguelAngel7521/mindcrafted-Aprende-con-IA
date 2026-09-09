// Modelos educativos de la demostración. Sin red ni dependencias.
export function circuit(voltage, resistance, closed) {
  if (!Number.isFinite(voltage) || !Number.isFinite(resistance) || resistance <= 0 || voltage < 0) throw new Error('Valores eléctricos inválidos');
  const current=closed ? voltage/resistance : 0;
  return {current,power:voltage*current,complete:closed && Math.abs(current-2)<0.025};
}
export function transformEquation(state, operation, amount) {
  if (!Number.isFinite(amount) || amount<=0 || amount>20) throw new Error('Usa un número entre 0 y 20, mayor que cero.');
  const {a,b,c}=state;
  const next=operation==='subtract'?{a,b:b-amount,c:c-amount}:operation==='add'?{a,b:b+amount,c:c+amount}:operation==='divide'?{a:a/amount,b:b/amount,c:c/amount}:operation==='multiply'?{a:a*amount,b:b*amount,c:c*amount}:null;
  if(!next)throw new Error('Operación desconocida');
  if(Object.values(next).some(v=>!Number.isFinite(v)||Math.abs(v)>10000)||Math.abs(next.a)<1e-8)throw new Error('Reinicia la balanza para seguir trabajando con cantidades pequeñas.');
  return {...next,complete:Math.abs(next.a-1)<1e-8 && Math.abs(next.b)<1e-8 && Math.abs(next.c-5)<1e-8};
}
export function ecosystem(water,pollinators) {
  if(![water,pollinators].every(v=>Number.isFinite(v)&&v>=0&&v<=100))throw new Error('Usa valores entre 0 y 100.');
  // Índice ilustrativo de dos factores limitantes. No es una predicción biológica.
  const reproduction=Math.round(Math.min(water,pollinators));
  return {reproduction,limiting:water===pollinators?'Ambos factores':water<pollinators?'Agua':'Polinizadores',complete:reproduction>=75};
}
