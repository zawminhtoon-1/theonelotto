/*
 * xoshiro256.js
 * -------------
 * Shared bit-exact BigInt JS port of xoshiro256** (seeded via SplitMix64),
 * used by every xoshiro-based elimination/seed-scan/stats page on this site.
 * Verified bit-exact against the Python/NumPy reference implementation
 * before any seed scan that depends on it ran.
 *
 * Load this before any inline <script> that calls these functions (plain
 * <script src>, not a module -- everything below is a page-global, same as
 * when this code lived inline on each page).
 *
 * Exposes: MASK64, rotl, splitmix64Next, seedState, xoshiroNext.
 */
const MASK64 = (1n << 64n) - 1n;
// BigInt & MASK64 correctly wraps negative BigInts to 64-bit two's complement, same as Python
function rotl(x, k) {
  x &= MASK64;
  return ((x << BigInt(k)) | (x >> BigInt(64 - k))) & MASK64;
}
function splitmix64Next(z) {
  z = (z + 0x9E3779B97F4A7C15n) & MASK64;
  let zz = z;
  zz = ((zz ^ (zz >> 30n)) * 0xBF58476D1CE4E5B9n) & MASK64;
  zz = ((zz ^ (zz >> 27n)) * 0x94D049BB133111EBn) & MASK64;
  zz = zz ^ (zz >> 31n);
  return [z, zz];
}
function seedState(seed) {
  let z = BigInt(seed) & MASK64;
  const state = [];
  for (let i = 0; i < 4; i++) {
    const [nz, out] = splitmix64Next(z);
    z = nz;
    state.push(out);
  }
  return state;
}
function xoshiroNext(s) {
  const result = (rotl((s[1] * 5n) & MASK64, 7) * 9n) & MASK64;
  const t = (s[1] << 17n) & MASK64;
  s[2] ^= s[0]; s[3] ^= s[1]; s[1] ^= s[2]; s[0] ^= s[3];
  s[2] ^= t;
  s[3] = rotl(s[3], 45);
  return result;
}
