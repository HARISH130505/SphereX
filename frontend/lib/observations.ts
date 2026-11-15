/** Use the server-issued identity consistently in state, keys and API requests. */
export function observationKey(observation: { product_id: string }): string {
  return observation.product_id;
}
