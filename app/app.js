const D = window.STORY_DATA;
// Palette: Okabe-Ito (colorblind-safe). Gold is used only for gold-plated listings.
let INK = '#222222';
const BLUE = '#3A6EA5', GRAY = '#A0A4A8', SOLD = '#009E73', GOLD = '#B8860B', POS = '#D55E00', NEG = '#0072B2';
const OKABE = ['#009E73', '#56B4E9', '#E69F00', '#D55E00'];
const cfg = {responsive: true, displayModeBar: false};
// ---------- light / dark theme (follows prefers-color-scheme; remembered in localStorage)
const THEMES = {light: {ink: '#222222', grid: '#E6E6E6', zero: '#BDBDBD', hoverBg: '#222222', hoverInk: '#FFFFFF', band: 'rgba(58,110,165,0.16)', gap: 'rgba(120,120,120,0.16)'},
                dark: {ink: '#E8E8E8', grid: '#30353B', zero: '#5A6068', hoverBg: '#F2F2F2', hoverInk: '#111111', band: 'rgba(138,180,248,0.20)', gap: 'rgba(200,200,200,0.12)'}};
let theme = localStorage.getItem('theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
const applyTheme = t => { theme = t; INK = THEMES[t].ink; document.documentElement.dataset.theme = t;
  const b = document.getElementById('themeToggle'); if (b) { b.textContent = t === 'dark' ? '☀ Light mode' : '☾ Dark mode'; b.setAttribute('aria-pressed', t === 'dark'); } };
applyTheme(theme);
const AXF = () => ({gridcolor: THEMES[theme].grid, zerolinecolor: THEMES[theme].zero, linecolor: THEMES[theme].zero, automargin: true});
const lay = (o = {}) => { const L = Object.assign({margin: {l: 70, r: 20, t: 40, b: 50}, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
  font: {family: 'Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif', size: 13, color: INK}, hoverlabel: {bgcolor: THEMES[theme].hoverBg, font: {color: THEMES[theme].hoverInk}},
  legend: {orientation: 'h', x: 0, y: 1.02, yanchor: 'bottom', bgcolor: 'rgba(0,0,0,0)'}}, o);
  L.font = Object.assign({}, L.font, {color: INK}); L.xaxis = Object.assign({}, AXF(), L.xaxis); L.yaxis = Object.assign({}, AXF(), L.yaxis); return L; };
const $ = id => document.getElementById(id);
const H = (id, html) => { const e = $(id); if (e) e.innerHTML = html; };
const usd = v => (v < 0 ? '−$' : '$') + Math.abs(Math.round(v)).toLocaleString();
const usd2 = v => (v < 0 ? '−$' : '$') + Math.abs(v).toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 2});
const pct = (v, d = 0) => (100 * v).toFixed(d) + '%';
const num = v => Math.round(v).toLocaleString();
const pfmt = p => p < 0.001 ? 'p < 0.001' : 'p = ' + p.toFixed(3);
const isMobile = () => innerWidth < 760;
const mkey = m => { const [a, b] = m.split(' '); return ({Series: 0, SE: 1, Ultra: 2}[a] ?? 3) * 100 + (+b || 0); };
const opts = (el, vals, sel, labels) => { el.innerHTML = vals.map((v, i) => `<option value="${v}"${v === sel ? ' selected' : ''}>${labels ? labels[i] : v}</option>`).join(''); };
const wilson = (k, n) => { if (!n) return [NaN, NaN]; const z = 1.96, p = k / n, d = 1 + z * z / n, c = (p + z * z / (2 * n)) / d, h = z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [c - h, c + h]; };

const LOGT = {tickvals: [25, 50, 100, 250, 500, 1000, 2500, 5000], ticktext: ['$25', '$50', '$100', '$250', '$500', '$1k', '$2.5k', '$5k']};
const O = D.overview, G = D.gold, A = D.auctions, T = D.trajectories, S = D.survival, SM = D.sale_model, PM = D.price_model;
const soldN = O.outcome_counts.sold;
const s3 = D.ask_used.find(r => r.model === 'Series 3'), u3 = D.ask_used.find(r => r.model === 'Ultra 3'), s9 = D.ask_used.find(r => r.model === 'Series 9');
const surv = Object.fromEntries(S.table.map(r => [r.position, r]));

// ---------- hero and headline cards
H('hN', num(O.listings)); H('hSold', num(soldN));
H('hGaps', `${O.gap_hours.toFixed(0)} hours (${pct(1 - O.covered_share)} of the window)`);
$('cards').innerHTML = [
  [num(O.listings), 'listings tracked'], [num(soldN), 'sales recorded'],
  [s3.ratio.toFixed(1) + '×', 'Series 3 ask ÷ sale price'], [`${G.sold} of ${G.n}`, '24k gold listings sold', 'gold'],
  [pct(A.k / A.n), 'of auctions sold']].map(([v, k, c]) => `<div><b class="${c || ''}">${v}</b><small>${k}</small></div>`).join('');
const findings = [
  ['Sellers ask far more than buyers pay for old models.', `A used Series 3 is listed at a median ${usd(s3.ask)} but sells for ${usd(s3.sold)}: ${s3.ratio.toFixed(1)}× (95% CI ${s3.ratio_lo.toFixed(1)}–${s3.ratio_hi.toFixed(1)}×). For the Ultra 3 the gap is ${u3.ratio.toFixed(2)}×.`, '#asking'],
  ['Price drives speed.', `New fixed-price listings asking under 90% of the going rate were ${pct(surv['Below 90%'].sold_72h)} sold within 72 hours; those asking more than 150% were ${pct(surv['Above 150%'].sold_72h)}.`, '#speed'],
  ['Gold-plated watches did not clear.', `None of the ${G.n} 24k gold listings sold or ended during the week. Their median ask is ${G.median_sold_ratio.toFixed(1)}× what a standard watch of the same model sells for.`, '#gold'],
  ['Newer models and established sellers sell at auction.', `${pct(A.new_gen.k / A.new_gen.n)} of Series 9 and 10 auctions sold, against ${pct(A.series3.k / A.series3.n)} for the Series 3. Each tenfold increase in seller feedback raises the odds of a sale by about ${pct(A.adjusted.log_fb.or_ - 1)}.`, '#auctions'],
  ['Most of an auction’s price arrives at the end.', `With 48–72 hours left, the current bid is a median ${pct(T.table.find(r => r.bin === '48–72 h').median)} of the final price.`, '#auctions'],
  ['Model and condition set the price.', `A CatBoost model predicts sale prices with grouped cross-validated R² ${PM.metrics.r2.toFixed(2)} (median error ${usd(PM.metrics.median_ae)}); auctions sell for about ${usd(-PM.format_shap[0].mean)} less than the same watch at a fixed price.`, '#models']];
$('findings').innerHTML = findings.map(([h, p, a], i) => `<div><span>${i + 1}</span><h5><a href="${a}">${h}</a></h5><p>${p}</p></div>`).join('');

// ---------- filters
const MODELS = [...new Set(D.ask_sold.map(r => r.m))].sort((a, b) => mkey(a) - mkey(b));
opts($('fModel'), [''].concat(MODELS), '', ['All models'].concat(MODELS));
opts($('fCond'), ['All'].concat(D.cond_order), 'Used', ['All conditions'].concat(D.cond_order));
opts($('fFmt'), ['All'].concat(D.format_order), 'All', ['All formats'].concat(D.format_order));
const F = () => ({m: $('fModel').value, c: $('fCond').value, f: $('fFmt').value});

// ---------- 1. asking vs sold
H('tAsk', `Part I could only see asking prices. With sales recorded, the gap between what sellers ask and what buyers pay is large, and it grows as models age. For used watches the median ask is <b>${s3.ratio.toFixed(1)}×</b> the median sale price for the Series 3 (${usd(s3.ask)} vs ${usd(s3.sold)}), <b>${s9.ratio.toFixed(2)}×</b> for the Series 9 (${usd(s9.ask)} vs ${usd(s9.sold)}) and <b>${u3.ratio.toFixed(2)}×</b> for the Ultra 3 (${usd(u3.ask)} vs ${usd(u3.sold)}). Old, cheap watches have the most stale, optimistic listings; current models trade close to their asking price. Use the filters to change the condition or format.`);
function drawAsk() {
  const f = F(), rows = D.ask_sold.filter(r => r.c === f.c && r.f === f.f).sort((a, b) => mkey(a.m) - mkey(b.m));
  if (!rows.length) { Plotly.react('askChart', [], lay({annotations: [{text: 'Not enough sales for this combination', showarrow: false, xref: 'paper', yref: 'paper', x: .5, y: .5}]}), cfg); Plotly.react('ratioChart', [], lay(), cfg); $('fNote').textContent = 'no data'; return; }
  const hi = rows.map(r => !f.m || r.m === f.m), op = hi.map(h => h ? 1 : 0.25);
  const ys = rows.map(r => r.m);
  const tr = [
    {type: 'scatter', mode: 'lines', x: rows.flatMap(r => [r.sold, r.ask, null]), y: rows.flatMap(r => [r.m, r.m, null]), line: {color: GRAY, width: 3}, hoverinfo: 'skip', showlegend: false},
    {type: 'scatter', mode: 'markers', name: 'median sale price', x: rows.map(r => r.sold), y: ys, marker: {color: SOLD, size: 11, opacity: op},
      error_x: {type: 'data', symmetric: false, array: rows.map(r => r.sq3 - r.sold), arrayminus: rows.map(r => r.sold - r.sq1), color: SOLD, thickness: 1, width: 0},
      customdata: rows.map(r => [r.ns, r.slo, r.shi]), hovertemplate: '%{y}: sold for a median $%{x:,.0f}<br>95% CI $%{customdata[1]:,.0f}–$%{customdata[2]:,.0f} · %{customdata[0]} sales<extra></extra>'},
    {type: 'scatter', mode: 'markers', name: 'median asking price', x: rows.map(r => r.ask), y: ys, marker: {color: BLUE, size: 11, opacity: op},
      customdata: rows.map(r => [r.na]), hovertemplate: '%{y}: asking a median $%{x:,.0f}<br>%{customdata[0]:,} active listings<extra></extra>'}];
  Plotly.react('askChart', tr, lay({margin: {l: 80, r: 20, t: 40, b: 50}, xaxis: Object.assign({title: 'USD (log scale)', type: 'log'}, LOGT), yaxis: {autorange: 'reversed', type: 'category'}}), cfg);
  const rr = rows.map(r => r.ask / r.sold);
  Plotly.react('ratioChart', [{type: 'bar', x: ys, y: rr, marker: {color: rr.map((v, i) => hi[i] ? (v >= 1.5 ? POS : BLUE) : GRAY)},
    customdata: rows.map(r => [r.ask / r.shi, r.ask / r.slo]), text: rr.map(v => v.toFixed(2) + '×'), textposition: 'outside', cliponaxis: false,
    hovertemplate: '%{x}: %{y:.2f}× (95% CI %{customdata[0]:.2f}–%{customdata[1]:.2f}×)<extra></extra>'}],
    lay({margin: {l: 60, r: 20, t: 30, b: 70}, yaxis: {title: 'ask ÷ sale price', rangemode: 'tozero'}, xaxis: {tickangle: -45},
      shapes: [{type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 1, y1: 1, line: {color: GRAY, dash: 'dash', width: 1}}]}), cfg);
  const ns = rows.filter((r, i) => hi[i]).reduce((s, r) => s + r.ns, 0);
  $('fNote').textContent = `${ns.toLocaleString()} sales in view`;
}
const br = D.bridge.filter(r => r.part2_n_sold >= 10).sort((a, b) => b.part1_mean_ask - a.part1_mean_ask);
const b2 = D.bridge.find(r => r.model === 'Series 2'), b4 = D.bridge.find(r => r.model === 'Series 4'), bu3 = D.bridge.find(r => r.model === 'Ultra 3');
H('tBridge', `Part I found that the Series 2 (${usd(b2.part1_mean_ask)}) and Series 4 (${usd(b4.part1_mean_ask)}) averaged higher asking prices than the Ultra 3 (${usd(bu3.part1_mean_ask)}), because so many of them were gold-plated (${pct(b2.part1_gold_share)} of Series 2 listings). On eBay this week, a Series 2 sold for a median <b>${usd(b2.part2_median_sold)}</b> (${b2.part2_n_sold} sales) and a Series 4 for <b>${usd(b4.part2_median_sold)}</b>, while an Ultra 3 sold for <b>${usd(bu3.part2_median_sold)}</b>. Once sales replace asking prices, the ranking flips back to what you would expect.`);
function drawBridge() {
  const ys = br.map(r => r.model);
  Plotly.react('bridgeChart', [
    {type: 'bar', orientation: 'h', name: 'Part I: average asking price', y: ys, x: br.map(r => r.part1_mean_ask), marker: {color: br.map(r => r.part1_gold_share >= 0.3 ? GOLD : BLUE)},
      customdata: br.map(r => [r.part1_gold_share * 100, r.part1_n]), hovertemplate: '%{y}: Part I average ask $%{x:,.0f}<br>%{customdata[0]:.0f}% gold-plated · %{customdata[1]} listings<extra></extra>'},
    {type: 'bar', orientation: 'h', name: 'Part II: median sale price', y: ys, x: br.map(r => r.part2_median_sold), marker: {color: SOLD},
      customdata: br.map(r => [r.part2_n_sold]), hovertemplate: '%{y}: Part II median sale $%{x:,.0f} (%{customdata[0]} sales)<extra></extra>'}],
    lay({barmode: 'group', margin: {l: 80, r: 20, t: 50, b: 50}, xaxis: {title: 'USD'}, yaxis: {autorange: 'reversed'}, bargap: 0.25}), cfg);
}

// ---------- 2. time to sale
H('tSpeed', `For ${num(S.n)} fixed-price listings that went up during the week, the opening ask relative to the going rate (the median sale price for the same model and condition) predicts how quickly they sold. Overall, ${pct(S.sold_72h)} sold within 72 hours. Listings priced <b>below 90%</b> of the going rate reached <b>${pct(surv['Below 90%'].sold_72h)}</b> by 72 hours; listings priced <b>above 150%</b> reached only <b>${pct(surv['Above 150%'].sold_72h)}</b> (log-rank test across the four groups, ${S.logrank_p < 1e-10 ? 'p < 10⁻¹⁰' : pfmt(S.logrank_p)}).`);
function drawKM() {
  const tr = [];
  S.curves.forEach((c, i) => {
    const col = OKABE[i];
    tr.push({type: 'scatter', mode: 'lines', x: c.hours.concat([...c.hours].reverse()), y: c.hi.concat([...c.lo].reverse()), fill: 'toself', fillcolor: col + '26', line: {width: 0}, hoverinfo: 'skip', showlegend: false});
    tr.push({type: 'scatter', mode: 'lines', name: 'ask ' + c.position.toLowerCase() + ' of market', x: c.hours, y: c.sold, line: {color: col, width: 2.5, shape: 'hv'},
      hovertemplate: `${c.position}: %{y:.0%} sold by %{x} h<extra></extra>`});
  });
  Plotly.react('kmChart', tr, lay({margin: {l: 60, r: 20, t: 60, b: 50}, xaxis: {title: 'hours since the listing started', range: [0, 168], dtick: 24}, yaxis: {title: 'share sold', tickformat: '.0%', rangemode: 'tozero'}}), cfg);
}
$('kmTable').innerHTML = '<tr><th>Opening ask vs market</th><th>Listings</th><th>Sold by 24 h</th><th>Sold by 72 h</th><th>Sold by 120 h</th></tr>' +
  S.table.map(r => `<tr><td>${r.position}</td><td>${num(r.n)}</td><td>${pct(r.sold_24h)}</td><td>${pct(r.sold_72h)} <small>(${pct(r.sold_72h_lo)}–${pct(r.sold_72h_hi)})</small></td><td>${pct(r.sold_120h)}</td></tr>`).join('');

// ---------- 3. gold
$('goldBig').textContent = `${G.sold} of ${G.n}`;
H('goldTxt', `24k gold-plated listings recorded a sale during the week. None of them ended either: all ${G.n} are Good 'Til Cancelled listings that were still up when collection stopped.`);
H('tGold1', `In Part I, gold plating made older watches look like the most valuable on the market. Part II tracked ${G.n} listings whose title mentions 24k gold (${G.kinds['Gold-plated watch']} plated watches, plus a few with gold parts, a band and a plating service). Their median ask is <b>${usd(G.median_ask)}</b> (middle half ${usd(G.ask_q1)}–${usd(G.ask_q3)}): <b>${G.median_ask_ratio.toFixed(1)}×</b> the median ask of a standard watch of the same model and <b>${G.median_sold_ratio.toFixed(1)}×</b> what one actually sells for.`);
function drawGold() {
  const t = G.by_model.slice().sort((a, b) => mkey(a.model) - mkey(b.model)), ys = t.map(r => `${r.model} (${r.n})`);
  Plotly.react('goldChart', [
    {type: 'scatter', mode: 'lines', x: t.flatMap(r => [r.plain_sold, r.median_ask, null]), y: ys.flatMap(y => [y, y, null]), line: {color: 'rgba(184,134,11,0.3)', width: 4}, hoverinfo: 'skip', showlegend: false},
    {type: 'scatter', mode: 'markers', name: 'standard watch: median sale', x: t.map(r => r.plain_sold), y: ys, marker: {color: SOLD, size: 10}, hovertemplate: '%{y}: standard watch sells for $%{x:,.0f}<extra></extra>'},
    {type: 'scatter', mode: 'markers', name: 'standard watch: median ask', x: t.map(r => r.plain_ask), y: ys, marker: {color: BLUE, size: 10}, hovertemplate: '%{y}: standard watch asks $%{x:,.0f}<extra></extra>'},
    {type: 'scatter', mode: 'markers+text', name: '24k gold-plated: median ask', x: t.map(r => r.median_ask), y: ys, marker: {color: GOLD, size: 13, symbol: 'diamond'},
      text: t.map(r => (r.median_ask / r.plain_sold).toFixed(0) + '×'), textposition: 'middle right', textfont: {color: GOLD, size: 12},
      hovertemplate: '%{y}: gold-plated asks $%{x:,.0f}<extra></extra>'}],
    lay({margin: {l: 110, r: 30, t: 50, b: 50}, xaxis: Object.assign({title: 'USD (log scale)', type: 'log'}, LOGT), yaxis: {autorange: 'reversed', type: 'category'}}), cfg);
  const mid = G.age_bins.slice(0, -1).map((b, i) => (b + G.age_bins[i + 1]) / 2);
  Plotly.react('goldAge', [
    {type: 'bar', name: `other fixed-price watches (${num(G.n_other)})`, x: mid, y: G.age_other, marker: {color: GRAY}, opacity: 0.7, hovertemplate: '%{x:.2f} years: %{y:.1%}<extra>others</extra>'},
    {type: 'bar', name: `24k gold listings (${G.n})`, x: mid, y: G.age_gold, marker: {color: GOLD}, opacity: 0.85, hovertemplate: '%{x:.2f} years: %{y:.1%}<extra>gold</extra>'}],
    lay({barmode: 'overlay', bargap: 0.05, title: {text: 'How long the listings have been up', font: {size: 14}, x: 0, xanchor: 'left'}, margin: {l: 60, r: 10, t: 50, b: 50}, legend: {orientation: 'v', x: 0.98, xanchor: 'right', y: 0.98, yanchor: 'top'},
      xaxis: {title: 'listing age (years)'}, yaxis: {title: 'share of listings', tickformat: '.0%'}}), cfg);
  const sc = G.seller_counts, top = sc.slice(0, 3), rest = sc.slice(3).reduce((a, b) => a + b, 0);
  const lab = ['Seller A', 'Seller B', 'Seller C', `${sc.length - 3} others`], val = top.concat([rest]);
  Plotly.react('goldSellers', [{type: 'bar', orientation: 'h', y: lab, x: val, marker: {color: [GOLD, GOLD, GOLD, GRAY]}, text: val.map(v => `${v} (${pct(v / G.n)})`), textposition: 'outside', cliponaxis: false, hovertemplate: '%{y}: %{x} listings<extra></extra>'}],
    lay({title: {text: `${pct(G.top3_share)} of gold listings come from three sellers`, font: {size: 14}, x: 0, xanchor: 'left'}, margin: {l: 90, r: 60, t: 50, b: 50}, xaxis: {title: 'gold listings'}, yaxis: {autorange: 'reversed'}}), cfg);
}
H('tGold2', `The listings are old and concentrated. The median gold listing has been up for <b>${G.median_age_years.toFixed(1)} years</b> (${pct(G.share_older_2y)} for more than two), against ${Math.round(12 * G.other_median_age_years)} months for other active fixed-price watches, and one seller accounts for ${pct(G.top_seller_share)} of them. eBay's lifetime counters show they are not unsellable: of the ${G.lifetime_n} with full details, ${pct(1 - G.lifetime_never)} have sold at least one unit since they were posted (${num(G.lifetime_total)} units in total, a median of ${G.lifetime_per_year_median.toFixed(2)} per listing per year). Several are multi-quantity listings that a seller keeps open.`);
H('tGold3', `<b>What zero sales does and does not show.</b> A week is short for a listing that sells a unit every few years. Among comparable standard listings (fixed price, New or Open box, up for a year or more, same models), ${pct(G.window_comp_rate, 1)} sold during the week. At that rate about ${G.window_expected.toFixed(1)} of the ${G.plated_n} plated watches would be expected to sell, and seeing none has a probability of about ${G.window_p_zero.toFixed(2)}: unusual but not decisive. Of the ${num(G.window_pricey_n)} comparable standard listings priced at $500 or more, ${G.window_pricey_k} sold. The stronger evidence is the price gap: gold-plated watches ask many times what the same model clears at, so their asking prices say little about what the market pays. That is the gold-plating pitfall from Part I, now measured against sales.`);

// ---------- 4. auctions
const aNG = A.new_gen, aS3 = A.series3, adj = A.adjusted;
H('tAuc', `Of ${num(A.n)} ended auctions for single watches, ${pct(A.k / A.n)} sold (95% CI ${pct(A.ci[0])}–${pct(A.ci[1])}); the rest ended without a winning bid. The oldest models are the hardest to sell: ${pct(aNG.k / aNG.n)} of Series 9 and 10 auctions sold (${aNG.k} of ${aNG.n}) against ${pct(aS3.k / aS3.n)} of Series 3 auctions (${aS3.k} of ${aS3.n}; difference ${pct(A.new_vs_s3.diff)}, 95% CI ${pct(A.new_vs_s3.lo)}–${pct(A.new_vs_s3.hi)}, Fisher ${pfmt(A.new_vs_s3.p)}).`);
H('tAuc2', `Seller feedback matters: auctions from sellers with 10,000+ feedback sold far more often than those from new sellers, and in a logistic regression controlling for model family, generation, condition and shipping, each tenfold increase in feedback score multiplies the odds of a sale by <b>${adj.log_fb.or_.toFixed(2)}</b> (95% CI ${adj.log_fb.lo.toFixed(2)}–${adj.log_fb.hi.toFixed(2)}). Free shipping looks helpful in the raw rates (${pct(A.free_shipping.p1)} vs ${pct(A.free_shipping.p2)}), but the adjusted odds ratio is ${adj.free.or_.toFixed(2)} (95% CI ${adj.free.lo.toFixed(2)}–${adj.free.hi.toFixed(2)}): the raw gap is explained by who offers free shipping and what they sell.`);
const aucRow = (c, m) => A.cube.find(r => r.c === c && r.m === m);
function drawAuc() {
  const f = F(), c = f.c === 'Refurbished' ? 'All' : f.c;
  const rows = A.cube.filter(r => r.c === c && r.m !== 'All').sort((a, b) => mkey(a.m) - mkey(b.m));
  const all = aucRow(c, 'All') || aucRow('All', 'All');
  const rate = rows.map(r => r.k / r.n), ci = rows.map(r => wilson(r.k, r.n));
  Plotly.react('aucModel', [{type: 'scatter', mode: 'markers', x: rate, y: rows.map(r => r.m),
    marker: {color: rows.map(r => !f.m || r.m === f.m ? BLUE : GRAY), size: 11},
    error_x: {type: 'data', symmetric: false, array: ci.map((w, i) => w[1] - rate[i]), arrayminus: ci.map((w, i) => rate[i] - w[0]), color: GRAY, thickness: 1.5, width: 0},
    customdata: rows.map(r => [r.k, r.n]), hovertemplate: '%{y}: %{x:.0%} sold (%{customdata[0]} of %{customdata[1]})<extra></extra>'}],
    lay({margin: {l: 80, r: 20, t: 40, b: 50}, title: {text: `Condition: ${c === 'All' ? 'all' : c}${f.c === 'Refurbished' ? ' (too few refurbished auctions)' : ''}`, font: {size: 13}, x: 0, xanchor: 'left'},
      xaxis: {title: 'auctions that sold', tickformat: '.0%', range: [0, 1]}, yaxis: {autorange: 'reversed', type: 'category'},
      shapes: [{type: 'line', x0: all.k / all.n, x1: all.k / all.n, yref: 'paper', y0: 0, y1: 1, line: {color: GRAY, dash: 'dash', width: 1}}]}), cfg);
  let r = aucRow(c, f.m || 'All'), note = '';
  if (!r) { r = aucRow(c, 'All'); note = ' (too few auctions for this model; showing all models)'; }
  const fb = r.fb.map(([k, n]) => n ? k / n : null), fci = r.fb.map(([k, n]) => wilson(k, n));
  const who = `${f.m || 'All models'} · ${c === 'All' ? 'all conditions' : c}${note}`;
  Plotly.react('aucFb', [{type: 'bar', x: A.feedback_labels, y: fb, marker: {color: BLUE},
    error_y: {type: 'data', symmetric: false, array: fci.map((w, i) => fb[i] == null ? 0 : w[1] - fb[i]), arrayminus: fci.map((w, i) => fb[i] == null ? 0 : fb[i] - w[0]), color: GRAY, thickness: 1.2},
    customdata: r.fb, hovertemplate: 'feedback %{x}: %{y:.0%} sold (%{customdata[0]} of %{customdata[1]})<extra></extra>'}],
    lay({title: {text: 'By seller feedback score<br><span style="font-size:11px">' + who + '</span>', font: {size: 14}, x: 0, xanchor: 'left'}, margin: {l: 60, r: 10, t: 70, b: 50}, yaxis: {tickformat: '.0%', range: [0, 1.05], title: 'auctions that sold'}}), cfg);
  const sh = r.ship.map(([k, n]) => n ? k / n : null), sci = r.ship.map(([k, n]) => wilson(k, n));
  Plotly.react('aucShip', [{type: 'bar', x: ['free shipping', 'paid shipping'], y: sh, marker: {color: [SOLD, GRAY]},
    error_y: {type: 'data', symmetric: false, array: sci.map((w, i) => sh[i] == null ? 0 : w[1] - sh[i]), arrayminus: sci.map((w, i) => sh[i] == null ? 0 : sh[i] - w[0]), color: GRAY, thickness: 1.2},
    customdata: r.ship, hovertemplate: '%{x}: %{y:.0%} sold (%{customdata[0]} of %{customdata[1]})<extra></extra>'}],
    lay({title: {text: 'By shipping (raw rates)<br><span style="font-size:11px">' + who + '</span>', font: {size: 14}, x: 0, xanchor: 'left'}, margin: {l: 60, r: 10, t: 70, b: 50}, yaxis: {tickformat: '.0%', range: [0, 1.05]}}), cfg);
}
const tb = Object.fromEntries(T.table.map(r => [r.bin, r]));
H('tTraj', `For ${num(T.n)} sold auctions the collector recorded the bid repeatedly as the end approached. With 48–72 hours left the current bid was a median <b>${pct(tb['48–72 h'].median)}</b> of the final price; with 1–3 hours left, ${pct(tb['1–3 h'].median)}. Even in the last 15 minutes ${pct(T.late_rose_share)} of auctions still rose, by a median ${pct(T.late_median_jump, 1)} (95% CI ${pct(T.late_jump_ci[0], 1)}–${pct(T.late_jump_ci[1], 1)}). Sold auctions drew a median of ${T.final_bids_median} bids. A bid seen days before the end says little about the final price.`);
const TB = ['72 h+', '48–72 h', '24–48 h', '12–24 h', '6–12 h', '3–6 h', '1–3 h', '15 min–1 h', '0–15 min'];
const binOf = h => h >= 72 ? 0 : h >= 48 ? 1 : h >= 24 ? 2 : h >= 12 ? 3 : h >= 6 ? 4 : h >= 3 ? 5 : h >= 1 ? 6 : h >= 0.25 ? 7 : 8;
function drawTraj() {
  const f = F(), t = TB.map(b => tb[b]).filter(Boolean), x = t.map(r => r.bin);
  const tr = [
    {type: 'scatter', mode: 'lines', x: x.concat([...x].reverse()), y: t.map(r => r.q3).concat(t.map(r => r.q1).reverse()), fill: 'toself', fillcolor: THEMES[theme].band, line: {width: 0}, name: 'middle 50% of auctions', hoverinfo: 'skip'},
    {type: 'scatter', mode: 'lines+markers', x, y: t.map(r => r.median), name: 'median', line: {color: BLUE, width: 3}, marker: {size: 8}, customdata: t.map(r => r.n), hovertemplate: '%{x} before the end: median %{y:.0%} of final (%{customdata} auctions)<extra></extra>'}];
  // each auction: the latest bid seen in each window, as in the summary band
  const paths = {}; T.paths.forEach(([id, m, h, p]) => { if (f.m && m !== f.m) return; const P = (paths[id] = paths[id] || {m, by: {}}), b = binOf(h);
    if (!(b in P.by) || h < P.by[b][0]) P.by[b] = [h, p]; });
  const ids = Object.keys(paths);
  ids.forEach((id, i) => { const pts = Object.keys(paths[id].by).map(Number).sort((a, b) => a - b).map(b => [TB[b], paths[id].by[b][1]]);
    tr.push({type: 'scatter', mode: 'lines', x: pts.map(q => q[0]), y: pts.map(q => q[1]),
    line: {color: GRAY, width: 1}, opacity: 0.45, showlegend: i === 0, name: 'individual auctions', hovertemplate: `${paths[id].m}: %{y:.0%} of final<extra></extra>`}); });
  Plotly.react('trajChart', tr, lay({margin: {l: 60, r: 20, t: 60, b: 70}, xaxis: {type: 'category', categoryorder: 'array', categoryarray: TB, title: 'time before the auction ended'},
    yaxis: {tickformat: '.0%', range: [0, 1.08], title: 'current bid ÷ final price'},
    shapes: [{type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 1, y1: 1, line: {color: SOLD, dash: 'dash', width: 1}}],
    annotations: [{xref: 'paper', x: 0, y: 1, yanchor: 'bottom', xanchor: 'left', text: f.m && !ids.length ? `final price · no sampled ${f.m} auctions` : 'final price', showarrow: false, font: {color: SOLD, size: 11}}]}), cfg);
}

// ---------- 5a. sale-probability explainer
const SD = SM.grid.dims, sm = SM.metrics;
H('tSale', `A CatBoost classifier, trained on ${num(sm.n)} ended auctions first seen before their first bid (${num(sm.events)} sold), estimates the chance an auction sells from its settings at listing time. Validated with 5-fold cross-validation grouped by seller, it reaches an AUC of <b>${sm.auc.toFixed(2)}</b> (95% CI ${sm.auc_ci[0].toFixed(2)}–${sm.auc_ci[1].toFixed(2)}), against ${sm.auc_logit.toFixed(2)} for a logistic regression on the same inputs: modest, but real. The opening bid relative to the going rate is the strongest input.`);
opts($('sModel'), SD.model, 'Series 9'); opts($('sCond'), SD.condition, 'Used');
opts($('sRatio'), SD.ratio.map(String), '1', SD.ratio.map(v => pct(v) + ' of market'));
opts($('sFb'), SD.feedback.map(String), '500', SD.feedback.map(v => v.toLocaleString()));
const sIdx = (m, c, r, s, f) => ((((SD.model.indexOf(m) * SD.condition.length + SD.condition.indexOf(c)) * SD.ratio.length + SD.ratio.indexOf(r)) * SD.ship.length + SD.ship.indexOf(s)) * SD.feedback.length + SD.feedback.indexOf(f));
function drawSale() {
  const m = $('sModel').value, c = $('sCond').value, r = +$('sRatio').value, s = $('sShip').value, fb = +$('sFb').value;
  const p = SM.grid.prob[sIdx(m, c, r, s, fb)] / 1000;
  const curve = SD.ratio.map(x => SM.grid.prob[sIdx(m, c, x, s, fb)] / 1000);
  const ar = aucRow('All', m), n = ar ? ar.n : 0;
  H('sOut', `<span class="big2">${pct(p)}</span><small>predicted chance of selling</small><br>${m} · ${c} · opening bid ${pct(r)} of market · ${s === 'yes' ? 'free' : 'paid'} shipping · feedback ${fb.toLocaleString()}<br><small>${n} ended ${m} auctions in the data${n < 20 ? ': treat this estimate with extra caution' : ''}. Base rate ${pct(sm.base_rate)}.</small>`);
  Plotly.react('saleCurve', [{type: 'scatter', mode: 'lines+markers', x: SD.ratio, y: curve, line: {color: BLUE, width: 3}, marker: {size: 8}, hovertemplate: 'opening bid %{x:.0%} of market: %{y:.0%}<extra></extra>'},
    {type: 'scatter', mode: 'markers', x: [r], y: [p], marker: {color: POS, size: 15, line: {color: '#fff', width: 2}}, hoverinfo: 'skip', showlegend: false}],
    lay({showlegend: false, margin: {l: 60, r: 20, t: 30, b: 50}, xaxis: {title: 'opening bid as a share of the going rate', tickformat: '.0%'}, yaxis: {title: 'predicted chance of selling', tickformat: '.0%', range: [0, 1]}}), cfg);
}
['sModel', 'sCond', 'sRatio', 'sShip', 'sFb'].forEach(id => $(id).onchange = drawSale);
$('saleCards').innerHTML = [[sm.auc.toFixed(2), 'AUC, grouped CV'], [sm.auc_logit.toFixed(2), 'logistic baseline AUC'], [sm.brier.toFixed(3), `Brier (base rate ${sm.brier_base.toFixed(3)})`], [num(sm.sellers), 'sellers in the folds']].map(([v, k]) => `<div><b>${v}</b><small>${k}</small></div>`).join('');
function drawSaleDiag() {
  const R = SM.reliability;
  Plotly.react('saleRel', [{type: 'scatter', mode: 'lines', x: [0, 0.8], y: [0, 0.8], line: {color: GRAY, dash: 'dash', width: 1}, hoverinfo: 'skip', name: 'perfect calibration'},
    {type: 'scatter', mode: 'lines+markers', x: R.map(r => r.predicted), y: R.map(r => r.observed), name: 'out-of-fold', line: {color: BLUE, width: 2.5}, marker: {size: 9},
      error_y: {type: 'data', symmetric: false, array: R.map(r => r.hi - r.observed), arrayminus: R.map(r => r.observed - r.lo), color: GRAY}, customdata: R.map(r => r.n), hovertemplate: 'predicted %{x:.0%} → observed %{y:.0%} (n=%{customdata})<extra></extra>'}],
    lay({title: {text: 'Calibration (quintiles of out-of-fold predictions)', font: {size: 14}, x: 0, xanchor: 'left'}, margin: {l: 60, r: 10, t: 70, b: 50}, xaxis: {title: 'predicted', tickformat: '.0%', range: [0, 0.8]}, yaxis: {title: 'observed', tickformat: '.0%', range: [0, 0.8]}}), cfg);
  const I = SM.importance.filter(r => r[1] > 0.005).slice(0, 10);
  Plotly.react('saleImp', [{type: 'bar', orientation: 'h', y: I.map(r => r[0]), x: I.map(r => r[1]), marker: {color: I.map((r, i) => i < 3 ? BLUE : GRAY)}, hovertemplate: '%{y}: %{x:.2f}<extra></extra>'}],
    lay({title: {text: 'What drives the prediction (mean |SHAP|, log-odds)', font: {size: 14}, x: 0, xanchor: 'left'}, margin: {l: 170, r: 10, t: 50, b: 50}, yaxis: {autorange: 'reversed'}}), cfg);
}

// ---------- 5b. price estimator with SHAP waterfall
const PG = PM.grid, pmm = PM.metrics, LBL = D.labels;
H('tPrice', `A CatBoost regressor, trained on ${num(pmm.n)} sales from ${num(pmm.sellers)} sellers, predicts the sale price from the watch and the listing. With 5-fold cross-validation grouped by seller it explains <b>${pct(pmm.r2)}</b> of the variance (R² ${pmm.r2.toFixed(2)}), with a median absolute error of <b>${usd(pmm.median_ae)}</b> (${pct(pmm.mape_median)} of the price). A simple model-and-condition median already gets R² ${pmm.r2_base.toFixed(2)}, so the model's gain is in the details: material, case size and format. Pick a watch to see what it would sell for and why.`);
const PMODELS = [...new Set(PG.rows.map(r => r[0]))];
opts($('pModel'), PMODELS, 'Series 9'); opts($('pCond'), D.cond_order, 'Used'); opts($('pFmt'), D.format_order, 'Fixed price');
let lastWf = null;
function drawPrice() {
  const m = $('pModel').value, c = $('pCond').value, f = $('pFmt').value, s = $('pShip').value;
  const row = PG.rows.find(r => r[0] === m && r[1] === c && r[2] === f && r[3] === s); if (!row) return;
  const [, , , , mat, size, cel, ti, pred, nSold] = row, sh = row.slice(PG.cols.length);
  const val = {model: m, condition_group: c, format: f, free_shipping: s, material: mat, case_size: size + ' mm', cellular: cel ? 'yes' : 'no', titanium: ti ? 'yes' : 'no'};
  let items = PG.shap.map((k, i) => [k, sh[i]]).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
  const top = items.slice(0, 6), other = items.slice(6).reduce((a, b) => a + b[1], 0);
  const labs = top.map(([k]) => `${LBL[k] || k}${val[k] != null ? ' = ' + val[k] : ''}`).concat(['other features']);
  const vals = top.map(r => r[1]).concat([other]);
  Plotly.react('priceWf', [{type: 'waterfall', orientation: 'h', base: PM.expected, y: labs.concat(['prediction']), x: vals.concat([0]), measure: vals.map(() => 'relative').concat(['total']),
    text: vals.map(v => (v >= 0 ? '+' : '−') + '$' + Math.abs(v).toFixed(0)).concat([usd(pred)]), textposition: 'outside', cliponaxis: false,
    increasing: {marker: {color: POS}}, decreasing: {marker: {color: NEG}}, totals: {marker: {color: SOLD}}, connector: {line: {color: GRAY, width: 1}},
    hovertemplate: '%{y}: %{text}<extra></extra>'}],
    lay({margin: {l: isMobile() ? 150 : 230, r: 50, t: 40, b: 50}, yaxis: {autorange: 'reversed'}, xaxis: {title: 'predicted sale price (USD)'},
      annotations: [{xref: 'x', yref: 'paper', x: PM.expected, y: 1, yanchor: 'bottom', text: 'average prediction ' + usd(PM.expected), showarrow: false, font: {size: 11}}],
      shapes: [{type: 'line', x0: PM.expected, x1: PM.expected, yref: 'paper', y0: 0, y1: 1, line: {color: GRAY, dash: 'dot', width: 1}}]}), cfg);
  const askRow = D.ask_sold.find(r => r.c === c && r.f === 'All' && r.m === m);
  H('pOut', `<span class="big2">${usd(pred)}</span><small>predicted sale price</small><br>${m} · ${c} · ${f} · ${s === 'yes' ? 'free' : 'paid'} shipping<br><small>${nSold} recorded ${m} sales in ${c} condition${nSold < 10 ? ': little data, so the model leans on similar models' : ''}.${askRow ? ` Active listings ask a median ${usd(askRow.ask)}.` : ''}</small>`);
}
['pModel', 'pCond', 'pFmt', 'pShip'].forEach(id => $(id).onchange = drawPrice);
$('priceCards').innerHTML = [[pmm.r2.toFixed(2), 'R², grouped CV'], [usd(pmm.mae), 'mean abs. error'], [usd(pmm.median_ae), 'median abs. error'], [pmm.r2_base.toFixed(2), 'baseline R² (model × condition)']].map(([v, k]) => `<div><b>${v}</b><small>${k}</small></div>`).join('');
function drawPriceImp() {
  const I = PM.importance.slice(0, 10);
  Plotly.react('priceImp', [{type: 'bar', orientation: 'h', y: I.map(r => r[0]), x: I.map(r => r[1]), marker: {color: I.map((r, i) => i < 3 ? SOLD : GRAY)}, text: I.map(r => usd2(+r[1].toFixed(2))), textposition: 'outside', cliponaxis: false, hovertemplate: '%{y}: ±$%{x:.2f}<extra></extra>'}],
    lay({title: {text: 'What drives the sale price (mean |SHAP|, USD)', font: {size: 14}, x: 0, xanchor: 'left'}, margin: {l: 170, r: 60, t: 50, b: 50}, yaxis: {autorange: 'reversed'}}), cfg);
}

// ---------- how the data was collected
H('tCol', `There is no public feed of completed eBay sales, so the data had to be collected while the listings were live. A Python collector polled the official eBay Browse API (US marketplace, Smart Watches category, brand Apple) from Monday, October 19 to Monday, October 26, 2026, and stored every observation in SQLite: ${num(O.snapshots)} snapshots of ${num(O.listings)} listings from ${num(O.sellers)} sellers, using ${num(O.api_calls)} API calls.`);
$('steps').innerHTML = [
  '<b>Daily full sweep</b> across 17 price bands, seeing ' + num(O.sweep_items_min) + '–' + num(O.sweep_items_max) + ' listings each time.',
  '<b>New listings</b> every 30 minutes, newest first, so listings are seen soon after they go up.',
  '<b>Ending soon</b> every 20 minutes: auctions with under 45 minutes left. A <b>final look</b> runs every minute for the last 4 minutes.',
  '<b>Item details</b> every 5 minutes (up to 60 per run): condition, seller feedback, sold counters and shipping, quoted to ZIP 80202.',
  '<b>End checks</b> 10 minutes, 3 hours and 24 hours after a listing ends, to read the outcome.',
  '<b>Outcome inference.</b> An auction with bids is recorded as sold, and one without bids as unsold (high confidence). A fixed-price listing whose sold counter rose is sold (high confidence; medium when Best Offer was on, since the accepted price is unknown). Anything else that ended is “outcome unknown” (low confidence) and is not counted as a sale.',
  '<b>Budget.</b> 5,000 calls a day with a 5% safety margin and 1,200 calls held back for end checks; exponential backoff on rate-limit and server errors.'].map(s => `<li>${s}</li>`).join('');
H('tGaps', `<b>Gaps.</b> Collection stopped three times, for ${O.gap_hours.toFixed(0)} hours in total: ${D.gaps.map(g => `${g.label} (${g.hours.toFixed(1)} h)`).join('; ')}. Auctions that ended inside a gap are missing their final look but still have an end check, and listings that went up and sold inside a gap were never seen. Results over time mark these spans.`);
H('tPrivacy', `<b>Privacy.</b> Only cleaned, aggregated data is published. Seller names, item IDs, URLs, titles, descriptions and photos are dropped; sellers are replaced by salted, non-reversible hashes, and this app holds only summary tables and model outputs.`);
function drawCol() {
  const a = D.activity, gapShapes = D.gaps.map(g => ({type: 'rect', xref: 'x', yref: 'paper', x0: g.start, x1: g.end, y0: 0, y1: 1, fillcolor: THEMES[theme].gap, line: {width: 0}, layer: 'below'}));
  Plotly.react('colChart', [
    {type: 'bar', x: a.hours, y: a.calls, name: 'API calls per hour', marker: {color: BLUE}, hovertemplate: '%{x}: %{y:,} calls<extra></extra>'},
    {type: 'scatter', mode: 'lines', x: a.hours, y: a.obs, name: 'observations per hour', yaxis: 'y2', line: {color: '#E69F00', width: 1.5}, connectgaps: false, hovertemplate: '%{x}: %{y:,} observations<extra></extra>'},
    {type: 'scatter', mode: 'markers', x: [null], y: [null], name: 'collection gap', marker: {color: THEMES[theme].gap, size: 14, symbol: 'square'}, hoverinfo: 'skip'}],
    lay({margin: {l: 60, r: 60, t: 50, b: 50}, shapes: gapShapes, xaxis: {type: 'date'}, yaxis: {title: 'API calls'},
      yaxis2: Object.assign(AXF(), {overlaying: 'y', side: 'right', title: 'observations', showgrid: false})}), cfg);
}

// ---------- limitations
$('limitList').innerHTML = [
  `<b>One week, with gaps.</b> ${O.window_hours.toFixed(0)} hours of collection, of which ${O.gap_hours.toFixed(0)} were lost to downtime. Slow-selling listings, like the gold-plated ones, need a longer window.`,
  `<b>Sale prices for Best Offer listings are an upper bound.</b> eBay does not reveal accepted offers, so a fixed-price sale is recorded at the listed price.`,
  `<b>Unknown outcomes.</b> ${num(O.outcome_counts.ended_unknown)} listings ended without a readable outcome (removed, ended early, or not re-checked in time). They are not counted as sales, so fixed-price sell-through is a lower bound.`,
  `<b>Latest-value fields.</b> The database keeps the most recent value of each listing field. eBay removes Best Offer and Buy It Now from auctions once they get a bid, so those flags would leak the outcome; they were left out of the auction models.`,
  `<b>Title-based features.</b> Model, material and gold plating come from regular expressions on titles, and ${pct(O.brand_missing_share)} of listings leave the brand field empty, so some listings are misclassified or dropped.`,
  `<b>Associations, not causes.</b> Sellers choose prices, formats and shipping together. The adjusted estimates control for what was measured, not for everything a buyer sees.`].map(s => `<li>${s}</li>`).join('');

// ---------- render and wire up
function drawFiltered() { drawAsk(); drawAuc(); drawTraj(); }
function renderAll() { drawFiltered(); drawBridge(); drawKM(); drawGold(); drawSale(); drawSaleDiag(); drawPrice(); drawPriceImp(); drawCol(); }
['fCond', 'fFmt'].forEach(id => $(id).onchange = drawFiltered);
$('fModel').onchange = () => { const m = $('fModel').value;
  if (m && SD.model.includes(m)) $('sModel').value = m; if (m && PMODELS.includes(m)) $('pModel').value = m;
  drawFiltered(); drawSale(); drawPrice(); };
$('fReset').onclick = () => { $('fModel').value = ''; $('fCond').value = 'Used'; $('fFmt').value = 'All'; drawFiltered(); };
$('themeToggle').onclick = () => { applyTheme(theme === 'dark' ? 'light' : 'dark'); localStorage.setItem('theme', theme); renderAll(); };
renderAll();
