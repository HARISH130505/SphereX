/**
 * Client-side coordinate and numerical parameter validation.
 */
export function validateCoordinates(ra: number, dec: number): { valid: boolean; error?: string } {
  if (isNaN(ra) || ra < 0 || ra >= 360) {
    return { valid: false, error: "RA must be between 0° and 360°" };
  }
  if (isNaN(dec) || dec < -90 || dec > 90) {
    return { valid: false, error: "Dec must be between -90° and +90°" };
  }
  return { valid: true };
}

export function formatFlux(fluxUjy?: number): string {
  if (fluxUjy === undefined || fluxUjy === null || isNaN(fluxUjy)) return "N/A";
  return `${fluxUjy.toLocaleString(undefined, { maximumFractionDigits: 1 })} μJy`;
}
