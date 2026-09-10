/*
 * site-nav.js
 * -----------
 * Single-source site navigation for every static HTML page. Fixes the
 * recurring "stale nav" problem: previously every public/*.html page (and
 * its generator script) baked its own literal copy of the nav CSS/HTML/JS,
 * so adding a page meant hand-editing N different generator scripts and
 * inevitably some got missed or forgotten.
 *
 * Now the nav lives in exactly ONE place (this file). To use it, a page
 * needs exactly one line, as the very first thing inside <body>:
 *
 *   <body>
 *   <script src="/site-nav.js"></script>
 *   ...
 *
 * No mount div, no CSS link, no per-page active-link script needed -- this
 * file injects its own <style>, inserts the nav markup right before itself
 * (via document.currentScript), marks the active link from
 * location.pathname, and wires up a mobile hamburger menu (the old nav was
 * hover-only, which doesn't work on touch devices).
 *
 * To add/change a link: edit NAV_HTML below, once. Every page picks up the
 * change on next load -- nothing to regenerate.
 */
(function () {
  var NAV_HTML =
    '<nav class="site-nav">' +
      '<a class="nav-logo" href="/">🎱 The<span>One</span>Lotto</a>' +
      '<div class="nav-search-wrap">' +
        '<input type="search" class="nav-search" placeholder="🔍 Search pages…" aria-label="Search navigation">' +
      '</div>' +
      '<button class="nav-hamburger" type="button" aria-label="Menu" aria-expanded="false">☰</button>' +
      '<div class="nav-groups">' +
        '<div class="nav-group">' +
          '<div class="nav-group-btn">Data <span class="arrow">▼</span></div>' +
          '<div class="nav-dropdown"><div class="nav-dropdown-inner">' +
            '<div class="nav-dd-label">Results</div>' +
            '<a href="/loto6">🏠 Loto 6 Home</a>' +
            '<a href="/history">📋 History</a>' +
            '<a href="/numbers">🔢 Numbers</a>' +
          '</div></div>' +
        '</div>' +
        '<div class="nav-group">' +
          '<div class="nav-group-btn">Predict <span class="arrow">▼</span></div>' +
          '<div class="nav-dropdown"><div class="nav-dropdown-inner">' +
            '<div class="nav-dd-label">Prediction Tools</div>' +
            '<a href="/predictions">🎯 Predictions</a>' +
            '<a href="/backtest.html">📊 Backtest</a>' +
            '<a href="/combo_evo.html">🧬 Combo Evo</a>' +
            '<div class="nav-divider"></div>' +
            '<div class="nav-dd-label">Strategy</div>' +
            '<a href="/overdue.html">⏳ Overdue</a>' +
            '<a href="/state_machine.html">🔄 State Machine</a>' +
            '<a href="/modular_cycle.html">🔁 Modular Cycle</a>' +
            '<a href="/next_relation.html">🔗 Next Relation</a>' +
            '<a href="/lstm_predict.html">🧠 LSTM Neural Net</a>' +
            '<div class="nav-divider"></div>' +
            '<div class="nav-dd-label">N-Draw Avg</div>' +
            '<a href="/avg_hub.html">⬡ All N-Draw Avg (2–43)</a>' +
            '<div class="nav-divider"></div>' +
            '<div class="nav-dd-label">N-Draw Avg Shift</div>' +
            '<a href="/avg_shift_hub.html">⇄ All N-Shift Avg (2–43)</a>' +
            '<div class="nav-divider"></div>' +
            '<div class="nav-dd-label">Random Seed</div>' +
            '<a href="/random_seed_backtest.html">🎲 Random Seed (±1,236,700)</a>' +
            '<a href="/k7_seed_coverage.html">📈 K=7 Seed Coverage</a>' +
            '<a href="/k7_seed_hit_1000.html">🗺️ K=7 Seed-Hit (1000 draws)</a>' +
          '</div></div>' +
        '</div>' +
        '<div class="nav-group">' +
          '<div class="nav-group-btn">Xoshiro Research <span class="arrow">▼</span></div>' +
          '<div class="nav-dropdown"><div class="nav-dropdown-inner">' +
            '<div class="nav-dd-label">Xoshiro256** Seed Scans</div>' +
            '<a href="/xoshiro_seed_scan_k33.html">🎯 K=33, seeds 0–1,000,000</a>' +
            '<a href="/xoshiro_seed_scan_k38.html">🔷 K=38, seeds 0–1,000,000</a>' +
            '<a href="/xoshiro_seed_detail_neg7070245.html">🔎 K=38 Seed #-7,070,245 Detail (stopped scan spot-check)</a>' +
            '<a href="/xoshiro_seed_scan_k20.html">🎲 K=20, seeds ±3,000,000 (2050 draws)</a>' +
            '<a href="/xoshiro_seed_scan_k30.html">🎲 K=30, seeds ±3,000,000 (2050 draws)</a>' +
            '<a href="/pcg64_seed_scan_k38.html">🎲 PCG64 K=38, seeds ±5,000,000 (2050 draws)</a>' +
            '<div class="nav-divider"></div>' +
            '<div class="nav-dd-label">Predictions</div>' +
            '<a href="/xoshiro_elim_2135.html">✂️ Draw #2135 Elimination (Base only)</a>' +
            '<details class="nav-archive"><summary>📦 Past draws (#2128–#2134)</summary>' +
              '<a href="/xoshiro_elim_2128.html">✂️ Draw #2128 Elimination</a>' +
              '<a href="/xoshiro_elim_2129.html">✂️ Draw #2129 Elimination</a>' +
              '<a href="/xoshiro_elim_2130.html">✂️ Draw #2130 Elimination</a>' +
              '<a href="/xoshiro_elim_2131.html">✂️ Draw #2131 Elimination</a>' +
              '<a href="/xoshiro_elim_2132.html">✂️ Draw #2132 Elimination</a>' +
              '<a href="/xoshiro_elim_2133.html">✂️ Draw #2133 Elimination</a>' +
              '<a href="/xoshiro_elim_2134.html">✂️ Draw #2134 Elimination (native K=38 Base)</a>' +
              '<a href="/xo_pcg_elim_2134.html">✂️ Draw #2134 Elimination (xoshiro × PCG64 Base)</a>' +
              '<a href="/pcg64_top3_elim_2134.html">✂️ Draw #2134 Elimination (Top-3 PCG64 Seeds Base)</a>' +
            '</details>' +
            '<a href="/xoshiro_k38_5seed_intersection.html">✂️ K=38 5-Seed Intersection Backtest</a>' +
            '<a href="/xoshiro_k35_5seed_intersection.html">✂️ K=35 5-Seed Intersection Backtest</a>' +
            '<a href="/xoshiro_k38_x_modularcycle_k28_intersection.html">✂️ Modular Cycle (K=28) × K=38</a>' +
            '<a href="/xoshiro_k38_x_modularcycle_k33_intersection.html">✂️ Modular Cycle (K=33) × K=38</a>' +
            '<a href="/xoshiro_elim_backtest100.html">🎯 Full Elimination Backtest (100 Draws)</a>' +
            '<a href="/xoshiro_base_review100.html">🧪 Base Pool Construction Review (100 Draws)</a>' +
            '<a href="/xoshiro_base_review1000.html">🧪 Base Pool Construction Review (1000 Draws)</a>' +
            '<a href="/xoshiro_k38_x_modularcycle_k38_stats.html">📊 Modular Cycle (native K=38) × K=38 — Stats</a>' +
            '<a href="/triple_k38_stats.html">📊 Triple K=38 — xoshiro × Modular Cycle × PCG64 — Stats</a>' +
            '<a href="/xo_pcg_k38_stats.html">📊 Two-Way K=38 — xoshiro × PCG64 — Stats</a>' +
          '</div></div>' +
        '</div>' +
        '<div class="nav-group">' +
          '<div class="nav-group-btn">Analyze <span class="arrow">▼</span></div>' +
          '<div class="nav-dropdown"><div class="nav-dropdown-inner">' +
            '<div class="nav-dd-label">Pattern Analysis</div>' +
            '<a href="/special.html">⭐ Special</a>' +
            '<a href="/consecutive.html">🔗 Consecutive</a>' +
            '<div class="nav-divider"></div>' +
            '<div class="nav-dd-label">Position</div>' +
            '<a href="/position.html">📍 Position Freq</a>' +
            '<a href="/pos_predict.html">📊 Pos 1–6 Predict</a>' +
          '</div></div>' +
        '</div>' +
        '<div class="nav-group">' +
          '<div class="nav-group-btn">Loto7 <span class="arrow">▼</span></div>' +
          '<div class="nav-dropdown"><div class="nav-dropdown-inner">' +
            '<div class="nav-dd-label">Loto 7 (7 from 37 + 2 bonus)</div>' +
            '<a href="/loto7">🏠 Loto 7 Home</a>' +
            '<a href="/loto7/history">📋 History</a>' +
            '<a href="/loto7/predictions">🎯 Predictions</a>' +
            '<a href="/loto7_backtest.html">📊 Backtest</a>' +
            '<a href="/loto7_backtest100_multik.html">🎯 100-Draw Multi-K Backtest</a>' +
            '<a href="/loto7_backtest_full.html">📊 Full-History Backtest</a>' +
            '<details class="nav-archive"><summary>📦 Past draws (#691, #693)</summary>' +
              '<a href="/loto7_elim_691.html">✂️ Draw #691 Elimination</a>' +
              '<a href="/loto7_elim_693.html">✂️ Draw #693 Elimination</a>' +
              '<a href="/pcg64_elim_693.html">✂️ Draw #693 Elimination (PCG64 Seed Base)</a>' +
            '</details>' +
            '<a href="/xoshiro_seed_scan_loto7_k25.html">🌀 Xoshiro Seed Scan K=25 (±1,000,000)</a>' +
            '<a href="/xoshiro_seed_scan_loto7_k28.html">🌀 Xoshiro Seed Scan K=28 (±1,000,000)</a>' +
            '<a href="/xoshiro_seed_scan_loto7_k30.html">🌀 Xoshiro Seed Scan K=30 (±1,000,000)</a>' +
            '<a href="/pcg64_seed_scan_loto7_k30.html">🎲 PCG64 Seed Scan K=30, seeds ±5,000,000 (650 draws)</a>' +
          '</div></div>' +
        '</div>' +
        '<div class="nav-group">' +
          '<div class="nav-group-btn">MiniLoto <span class="arrow">▼</span></div>' +
          '<div class="nav-dropdown"><div class="nav-dropdown-inner">' +
            '<div class="nav-dd-label">MiniLoto (5 from 31 + 1 bonus)</div>' +
            '<a href="/miniloto">🏠 Latest Draw</a>' +
            '<a href="/miniloto/history">📋 History</a>' +
            '<a href="/miniloto/predictions">🎯 Predictions</a>' +
            '<a href="/miniloto_backtest.html">📊 Backtest</a>' +
            '<a href="/miniloto_rl23_minus_all19.html">🧮 RL K=23 minus All-16 K=19</a>' +
          '</div></div>' +
        '</div>' +
      '</div>' +
    '</nav>';

  var NAV_CSS =
    '.site-nav{position:fixed;top:0;left:0;right:0;height:52px;background:#0a0f1e;' +
      'border-bottom:1px solid #1e293b;display:flex;align-items:center;padding:0 20px;' +
      'gap:0;z-index:9999;box-shadow:0 2px 16px rgba(0,0,0,.6)}' +
    '.site-nav .nav-logo{font-size:1rem;font-weight:800;color:#f1f5f9;text-decoration:none;' +
      'white-space:nowrap;margin-right:24px;flex-shrink:0;letter-spacing:-.01em}' +
    '.site-nav .nav-logo span{color:#38bdf8}' +
    '.nav-groups{display:flex;gap:4px;align-items:center}' +
    '.nav-group{position:relative}' +
    '.nav-group-btn{display:flex;align-items:center;gap:5px;padding:7px 14px;border-radius:7px;' +
      'cursor:pointer;font-size:.82rem;font-weight:600;color:#94a3b8;' +
      'border:1px solid transparent;transition:.15s;white-space:nowrap;user-select:none}' +
    '.nav-group-btn:hover,.nav-group:hover .nav-group-btn{color:#f1f5f9;background:#1e293b;border-color:#334155}' +
    '.nav-group-btn .arrow{font-size:.6rem;opacity:.6;transition:transform .2s}' +
    '.nav-group:hover .nav-group-btn .arrow{transform:rotate(180deg)}' +
    '.nav-dropdown{display:none;position:absolute;top:100%;left:0;' +
      'background:transparent;padding-top:6px;z-index:10000;min-width:170px}' +
    '.nav-dropdown-inner{background:#0d1526;border:1px solid #1e293b;border-radius:10px;' +
      'padding:6px;box-shadow:0 12px 32px rgba(0,0,0,.7);max-height:70vh;overflow-y:auto}' +
    '.nav-group:hover .nav-dropdown{display:block}' +
    '.nav-dropdown a{display:flex;align-items:center;gap:8px;padding:8px 12px;' +
      'border-radius:6px;color:#94a3b8;text-decoration:none;font-size:.82rem;' +
      'white-space:nowrap;transition:.12s}' +
    '.nav-dropdown a:hover{color:#f1f5f9;background:#1e293b}' +
    '.nav-dropdown a.active{color:#38bdf8;background:#0c2340}' +
    '.nav-dd-label{font-size:.68rem;font-weight:700;color:#475569;padding:6px 12px 2px;' +
      'text-transform:uppercase;letter-spacing:.06em}' +
    '.nav-divider{height:1px;background:#1e293b;margin:4px 0}' +
    '.nav-hamburger{display:none;background:none;border:none;color:#94a3b8;font-size:1.3rem;' +
      'cursor:pointer;padding:6px 8px;margin-left:auto;line-height:1}' +
    '.nav-hamburger:hover{color:#f1f5f9}' +
    '.nav-search-wrap{flex:0 1 190px;margin-right:10px}' +
    '.nav-search{width:100%;background:#0d1526;border:1px solid #1e293b;border-radius:7px;' +
      'color:#e2e8f0;font-size:.8rem;padding:6px 10px;outline:none;transition:.15s;' +
      'font-family:inherit}' +
    '.nav-search::placeholder{color:#475569}' +
    '.nav-search:focus{border-color:#38bdf8;background:#0a0f1e}' +
    '.nav-archive{margin:2px 0}' +
    '.nav-archive summary{display:flex;align-items:center;gap:8px;list-style:none;cursor:pointer;' +
      'padding:8px 12px;border-radius:6px;color:#64748b;font-size:.82rem;white-space:nowrap;transition:.12s}' +
    '.nav-archive summary::-webkit-details-marker{display:none}' +
    '.nav-archive summary::marker{content:""}' +
    '.nav-archive summary:hover{color:#f1f5f9;background:#1e293b}' +
    '.nav-archive summary::after{content:"▸";margin-left:auto;font-size:.65rem;opacity:.6;transition:transform .15s}' +
    '.nav-archive[open] summary::after{transform:rotate(90deg)}' +
    '.nav-archive a{padding-left:28px}' +
    // Search results mode: force the full vertical panel layout (same shape
    // as the mobile hamburger panel) at ANY viewport width, show only groups
    // with a match, and auto-expand archived (<details>) sections that
    // contain one -- overrides the hover-dropdown/media-query rules below.
    '.site-nav.search-mode .nav-groups{display:flex!important;position:fixed;top:52px;left:0;right:0;bottom:0;' +
      'background:#0a0f1e;flex-direction:column;align-items:stretch;padding:8px;overflow-y:auto;gap:2px;z-index:9998}' +
    '.site-nav.search-mode .nav-group{width:100%}' +
    '.site-nav.search-mode .nav-group:not(.has-match){display:none}' +
    '.site-nav.search-mode .nav-group-btn{width:100%;justify-content:space-between;padding:13px 10px;cursor:default}' +
    '.site-nav.search-mode .nav-group-btn:hover{background:none;border-color:transparent;color:#94a3b8}' +
    '.site-nav.search-mode .nav-group-btn .arrow{display:none}' +
    '.site-nav.search-mode .nav-dropdown{position:static;padding-top:0;min-width:0;display:block}' +
    '.site-nav.search-mode .nav-dropdown-inner{box-shadow:none;border:none;background:transparent;' +
      'padding:0 0 6px 14px;max-height:none;border-radius:0;overflow:visible}' +
    '.site-nav.search-mode .nav-dropdown a{padding:11px 12px}' +
    '@media (max-width: 860px){' +
      '.site-nav{padding:0 12px}' +
      '.nav-hamburger{display:block}' +
      '.nav-search-wrap{flex:1 1 auto;margin:0 8px}' +
      '.nav-groups{display:none;position:fixed;top:52px;left:0;right:0;bottom:0;' +
        'background:#0a0f1e;flex-direction:column;align-items:stretch;' +
        'padding:8px;overflow-y:auto;gap:2px;z-index:9998}' +
      '.nav-groups.open{display:flex}' +
      '.nav-group{width:100%}' +
      '.nav-group-btn{width:100%;justify-content:space-between;padding:13px 10px}' +
      '.nav-group:hover .nav-dropdown{display:none}' +
      '.nav-dropdown{position:static;padding-top:0;min-width:0}' +
      '.nav-dropdown-inner{box-shadow:none;border:none;background:transparent;' +
        'padding:0 0 6px 14px;max-height:none;border-radius:0}' +
      '.nav-group.open .nav-dropdown{display:block}' +
      '.nav-dropdown a{padding:11px 12px}' +
    '}';

  var thisScript = document.currentScript;

  // Inject CSS.
  var styleEl = document.createElement('style');
  styleEl.textContent = NAV_CSS;
  document.head.appendChild(styleEl);

  // Inject nav markup right before this <script> tag (works whether the tag
  // is the first thing in <body> or, on legacy pages that still keep the
  // old placeholder, anywhere else -- no mount div required).
  if (thisScript && thisScript.parentNode) {
    thisScript.insertAdjacentHTML('beforebegin', NAV_HTML);
  } else {
    // Fallback (e.g. script injected dynamically without currentScript
    // support): prepend to <body>.
    document.body.insertAdjacentHTML('afterbegin', NAV_HTML);
  }

  // Mark the active link from the current path.
  var path = window.location.pathname;
  var links = document.querySelectorAll('.nav-dropdown a');
  for (var i = 0; i < links.length; i++) {
    var a = links[i];
    var href = a.getAttribute('href');
    if (!href) continue;
    var hrefPath = href.split('#')[0];
    if (hrefPath === path || (hrefPath !== '/' && path.indexOf(hrefPath) === 0)) {
      a.classList.add('active');
    }
  }

  // Mobile hamburger: toggles the full nav-groups panel open/closed.
  var hamburger = document.querySelector('.nav-hamburger');
  var groups = document.querySelector('.nav-groups');
  if (hamburger && groups) {
    hamburger.addEventListener('click', function () {
      var open = groups.classList.toggle('open');
      hamburger.setAttribute('aria-expanded', open ? 'true' : 'false');
      hamburger.textContent = open ? '✕' : '☰';
    });
    // Tapping a link closes the panel (so navigating away doesn't leave it stuck open).
    for (var j = 0; j < links.length; j++) {
      links[j].addEventListener('click', function () {
        groups.classList.remove('open');
        hamburger.setAttribute('aria-expanded', 'false');
        hamburger.textContent = '☰';
      });
    }
  }

  // On touch/narrow screens, :hover doesn't open dropdowns -- tapping a
  // group button toggles its own dropdown open/closed instead. (Desktop
  // hover behavior is untouched; this listener only changes what happens
  // on click, which hover doesn't trigger.)
  var groupBtns = document.querySelectorAll('.nav-group-btn');
  for (var k = 0; k < groupBtns.length; k++) {
    groupBtns[k].addEventListener('click', function (e) {
      var group = e.currentTarget.closest('.nav-group');
      if (!group) return;
      var wasOpen = group.classList.contains('open');
      var allGroups = document.querySelectorAll('.nav-group.open');
      for (var g = 0; g < allGroups.length; g++) allGroups[g].classList.remove('open');
      if (!wasOpen) group.classList.add('open');
    });
  }

  // Nav search: live-filters every link's text across all dropdowns
  // (including collapsed "Past draws" archives, which auto-expand when one
  // of their links matches). Clearing the box restores normal hover/tap
  // navigation and re-collapses the archives.
  var searchInput = document.querySelector('.nav-search');
  var siteNavEl = document.querySelector('.site-nav');
  if (searchInput && siteNavEl) {
    var allGroupEls = document.querySelectorAll('.nav-group');
    var runFilter = function () {
      var q = searchInput.value.trim().toLowerCase();
      if (!q) {
        siteNavEl.classList.remove('search-mode');
        var links = document.querySelectorAll('.nav-dropdown a');
        for (var i = 0; i < links.length; i++) links[i].style.display = '';
        for (var g2 = 0; g2 < allGroupEls.length; g2++) allGroupEls[g2].classList.remove('has-match');
        var archivesReset = document.querySelectorAll('.nav-archive');
        for (var d = 0; d < archivesReset.length; d++) archivesReset[d].open = false;
        return;
      }
      siteNavEl.classList.add('search-mode');
      for (var gi = 0; gi < allGroupEls.length; gi++) {
        var group = allGroupEls[gi];
        var groupLinks = group.querySelectorAll('.nav-dropdown a');
        var anyMatch = false;
        for (var li = 0; li < groupLinks.length; li++) {
          var link = groupLinks[li];
          var matches = link.textContent.toLowerCase().indexOf(q) !== -1;
          link.style.display = matches ? '' : 'none';
          if (matches) anyMatch = true;
        }
        group.classList.toggle('has-match', anyMatch);
        var archives = group.querySelectorAll('.nav-archive');
        for (var ai = 0; ai < archives.length; ai++) {
          var archiveLinks = archives[ai].querySelectorAll('a');
          var archiveMatch = false;
          for (var li2 = 0; li2 < archiveLinks.length; li2++) {
            if (archiveLinks[li2].style.display !== 'none') { archiveMatch = true; break; }
          }
          archives[ai].open = archiveMatch;
        }
      }
    };
    searchInput.addEventListener('input', runFilter);
    searchInput.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        searchInput.value = '';
        runFilter();
        searchInput.blur();
      }
    });
  }
})();
