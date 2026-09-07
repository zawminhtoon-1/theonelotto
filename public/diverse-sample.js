/*
 * diverse-sample.js
 * -----------------
 * Shared "Diverse sample" generator used by every combo-browser page's
 * 🎲 Generate N buttons. Greedy coverage-maximizing pick: shuffle candidate
 * order once (so ties/starting point aren't biased toward generation
 * order), then for each round pick whichever remaining candidate's numbers
 * have the LOWEST total cumulative usage so far (first strictly-lower score
 * wins, in shuffled order), update usage counts, repeat. Spreads the sample
 * across as many distinct pool numbers as possible instead of a uniform
 * random draw.
 *
 * Depends on page globals set up by each page's own inline <script>:
 * `filtered`, `REMAINING` (arrays of number-arrays) and `getBallColor(n)`.
 * Since it's only invoked later by a button click (never at load time),
 * load order relative to the page's inline script doesn't matter.
 */
function generateSamples(n) {
  const pool = filtered.length > 0 ? filtered : REMAINING;
  const container = document.getElementById('generatedResults');
  if (pool.length === 0) {
    container.innerHTML = '<p style="color:#64748b;font-size:.85rem">No combos match the current filter to sample from.</p>';
    return;
  }
  const count = Math.min(n, pool.length);

  // Shuffle candidate order once (Fisher-Yates), doesn't mutate pool itself.
  const order = Array.from({length: pool.length}, (_, i) => i);
  for (let i = order.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [order[i], order[j]] = [order[j], order[i]];
  }

  const usage = new Map();
  const takenPositions = new Set();
  const picks = [];
  for (let round = 0; round < count; round++) {
    let bestPos = -1;
    let bestScore = Infinity;
    for (let k = 0; k < order.length; k++) {
      if (takenPositions.has(k)) continue;
      const c = pool[order[k]];
      let score = 0;
      for (let m = 0; m < c.length; m++) score += (usage.get(c[m]) || 0);
      if (score < bestScore) {
        bestScore = score;
        bestPos = k;
        if (bestScore === 0 && round === 0) break; // first round: any 0-score combo is equally good, take the first
      }
    }
    const chosen = pool[order[bestPos]];
    takenPositions.add(bestPos);
    picks.push(chosen);
    for (const num of chosen) usage.set(num, (usage.get(num) || 0) + 1);
  }

  const distinctCovered = new Set(picks.flat()).size;
  const sourceLabel = filtered.length > 0 && filtered.length < REMAINING.length ? filtered.length.toLocaleString() + ' filtered' : REMAINING.length.toLocaleString() + ' total';
  container.innerHTML =
    '<div class="gen-hdr">Generated ' + picks.length + ' diverse combo' + (picks.length !== 1 ? 's' : '') +
    ' from ' + sourceLabel + ' — covers ' + distinctCovered + ' distinct pool numbers:</div>' +
    picks.map(c => '<div class="balls gen-row">' + c.map(n2 =>
      '<span class="nb" style="background:' + getBallColor(n2) + '33;color:#e2e8f0;border:1px solid ' + getBallColor(n2) + '">' + n2 + '</span>'
    ).join('') + '</div>').join('');
}
