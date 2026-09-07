/*
 * pcg64-core.js
 * -------------
 * Shared bit-exact BigInt JS port of the PCG64 (O'Neill XSL-RR 128/64)
 * state-advance step, seeded the same SplitMix64 way as xoshiro256** so a
 * page can derive both PRNGs' picks from the same combined seed for
 * cross-comparison. Depends on MASK64 and splitmix64Next from
 * xoshiro256.js -- load that first.
 *
 * Exposes: MASK128, PCG_MULT_128, expandSeedToPcgState, rotr64, pcg64Next.
 */
const MASK128 = (1n << 128n) - 1n;
const PCG_MULT_128 = 0x2360ed051fc65da44385df649fccf645n;
function expandSeedToPcgState(combined) {
  let z = combined & MASK64;
  const outs = [];
  for (let i = 0; i < 4; i++) {
    const [nz, o] = splitmix64Next(z);
    z = nz;
    outs.push(o);
  }
  const state = ((outs[0] << 64n) | outs[1]) & MASK128;
  const inc = (((outs[2] << 64n) | outs[3]) | 1n) & MASK128;
  return [state, inc];
}
function rotr64(v, rot) {
  rot &= 63n;
  const shift = (64n - rot) % 64n;
  return ((v >> rot) | (v << shift)) & MASK64;
}
function pcg64Next(state, inc) {
  state = (state * PCG_MULT_128 + inc) & MASK128;
  const xored = (state >> 64n) ^ (state & MASK64);
  const rot = (state >> 122n) & 0x3fn;
  const out = rotr64(xored, rot);
  return [state, out];
}
