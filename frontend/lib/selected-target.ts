"use client";
import { useSyncExternalStore } from 'react';
const key='spherex-selected-target';
const targets=['M101','M51','M33','NGC 253','Mira','Delta Cephei','Algol'];
export function predefinedTarget(value:string|null) {
  return targets.find(target=>target.toLowerCase()===value?.toLowerCase()) || 'M101';
}
function subscribe(callback:()=>void) {
  window.addEventListener('spherex-target',callback);
  return ()=>window.removeEventListener('spherex-target',callback);
}
export function selectTarget(value:string) {
  sessionStorage.setItem(key,predefinedTarget(value));
  window.dispatchEvent(new Event('spherex-target'));
}
export function useSelectedTarget() {
  return useSyncExternalStore(subscribe,()=>predefinedTarget(sessionStorage.getItem(key)),()=>'M101');
}
