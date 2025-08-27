/* ---------- helpers ---------- */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const fmt2 = (n) => (Math.round(n * 100) / 100).toFixed(2);

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

/* ---------- DOM refs ---------- */
const healthBadge = $('#healthBadge');

const fromSel   = $('#fromSel');
const toSel     = $('#toSel');
const methodSel = $('#methodSel');

const tripOne   = document.querySelector('input[name="tripType"][value="oneway"]');
const tripRet   = document.querySelector('input[name="tripType"][value="return"]');
const tripMulti = document.querySelector('input[name="tripType"][value="multicity"]');
const multiStopsWrap = $('#multiStopsWrap'); // optional container (exists if you used the optional tweak)
const multiStops     = $('#multiStops');     // textarea for stops (optional)

const wd = $('#wd'), wc = $('#wc'), wl = $('#wl');
const wdVal = $('#wdVal'), wcVal = $('#wcVal'), wlVal = $('#wlVal');

const presetButtons = $$('.btn.chip');
const maxLayoversInp = $('#maxLayovers');
const sortSel = $('#sortSel');

const dateOut = $('#dateOut');
const dateRet = $('#dateRet');
const flexDates = $('#flexDates');

const swapBtn = $('#swapBtn');
const searchBtn = $('#searchBtn');

const metricsBox = $('#metrics');
const resultBox  = $('#result');
const routesTable = $('#routesTable');

/* ---------- state ---------- */
let nodes = []; // city list
let routes = []; // raw edges for Known Routes

/* ---------- boot ---------- */
boot();

function boot() {
  bindUI();
  refreshHealth();
  loadRoutes();
  updateTripTypeUI();  // set correct visibility at start
  reflectWeights();
}

/* ---------- UI bindings ---------- */
function bindUI() {
  swapBtn.addEventListener('click', () => {
    const a = fromSel.value;
    fromSel.value = toSel.value;
    toSel.value = a;
  });

  [tripOne, tripRet, tripMulti].forEach(r =>
    r.addEventListener('change', updateTripTypeUI)
  );

  wd.addEventListener('input', reflectWeights);
  wc.addEventListener('input', reflectWeights);
  wl.addEventListener('input', reflectWeights);

  presetButtons.forEach(btn => {
    btn.addEventListener('click', () => applyPreset(btn.dataset.preset));
  });

  searchBtn.addEventListener('click', onSearch);
}

function updateTripTypeUI() {
  // show both date inputs for return, only outbound for one-way, and (optionally) show multi-city textarea
  const isReturn = tripRet.checked;
  const isMulti  = tripMulti.checked;

  // Outbound date always visible by HTML; Return date is meaningful only for Return
  if (dateRet) {
    dateRet.disabled = !isReturn;
    dateRet.parentElement.style.opacity = isReturn ? '1' : '0.5';
  }

  if (multiStopsWrap && multiStops) {
    multiStopsWrap.style.display = isMulti ? 'block' : 'none';
  }
}

function reflectWeights() {
  wdVal.textContent = fmt2(parseFloat(wd.value));
  wcVal.textContent = fmt2(parseFloat(wc.value));
  wlVal.textContent = fmt2(parseFloat(wl.value));
}

function applyPreset(name) {
  if (name === 'fastest') {
    wd.value = 1.0; wc.value = 0.0; wl.value = 0.0;
  } else if (name === 'cheapest') {
    wd.value = 0.3; wc.value = 1.5; wl.value = 0.2;
  } else if (name === 'fewest') {
    wd.value = 0.3; wc.value = 0.0; wl.value = 1.5;
  }
  reflectWeights();
}

/* ---------- health & routes ---------- */
async function refreshHealth() {
  try {
    const h = await getJSON('/api/health');
    const msg = `MeTTa:${h.hyperon ? 'on' : 'off'} • nodes:${h.nodes} • edges:${h.edges}`;
    healthBadge.textContent = msg;
    healthBadge.classList.remove('badge--error');
  } catch (e) {
    healthBadge.textContent = 'backend offline';
    healthBadge.classList.add('badge--error');
  }
}

async function loadRoutes() {
  try {
    const data = await getJSON('/api/routes');
    nodes = (data.nodes || []).slice().sort();
    routes = data.routes || [];
    fillCitySelect(fromSel, nodes);
    fillCitySelect(toSel, nodes);
    // default sensible pair
    if (nodes.includes('Toronto')) fromSel.value = 'Toronto';
    if (nodes.includes('London'))  toSel.value = 'London';
    renderKnownRoutes(routes);
  } catch (e) {
    routesTable.innerHTML = `<div class="result empty">Failed to load routes.</div>`;
  }
}

function fillCitySelect(sel, list) {
  sel.innerHTML = '';
  list.forEach(n => {
    const opt = document.createElement('option');
    opt.value = n; opt.textContent = n;
    sel.appendChild(opt);
  });
}

function renderKnownRoutes(rows) {
  if (!rows?.length) {
    routesTable.innerHTML = `<div class="result empty">No routes.</div>`;
    return;
  }
  let html = `
    <table class="grid">
      <thead>
        <tr>
          <th>From</th><th>To</th><th>Airline</th>
          <th>Duration (h)</th><th>Cost (USD)</th>
        </tr>
      </thead>
      <tbody>
  `;
  rows.forEach(r => {
    html += `
      <tr>
        <td>${r.from}</td><td>${r.to}</td>
        <td>${r.airline ?? ''}</td>
        <td>${fmt2(r.duration ?? 0)}</td>
        <td>${fmt2(r.cost ?? 0)}</td>
      </tr>
    `;
  });
  html += `</tbody></table>`;
  routesTable.innerHTML = html;
}

/* ---------- search flow ---------- */
async function onSearch() {
  clearResult();

  const src  = fromSel.value;
  const dst  = toSel.value;
  const meth = (methodSel.value || 'dijkstra').toLowerCase();

  if (!src || !dst) {
    showResultError('Choose origin and destination.');
    return;
  }

  const w_duration = parseFloat(wd.value || '0');
  const w_cost     = parseFloat(wc.value || '0');
  const w_layovers = parseFloat(wl.value || '0');
  const max_layovers = parseInt(maxLayoversInp.value || '0', 10);

  try {
    if (tripOne.checked) {
      const res = await queryOneWay({src, dst, meth, w_duration, w_cost, w_layovers, max_layovers});
      renderRoute(res);
    } else if (tripRet.checked) {
      const there = await queryOneWay({src, dst, meth, w_duration, w_cost, w_layovers, max_layovers});
      const back  = await queryOneWay({src: dst, dst: src, meth, w_duration, w_cost, w_layovers, max_layovers});
      if (!there || !back) {
        showSummary(there, meth); // show what we have
        showResultError('No operating route in one direction.');
        return;
      }
      renderRoundTrip(there, back, meth);
    } else if (tripMulti.checked) {
      // Build legs = [from, ...stops..., to]
      const stops = (multiStops?.value || '')
        .split(',')
        .map(s => s.trim())
        .filter(Boolean);
      const chain = [src, ...stops, dst];

      if (chain.length < 2) {
        showResultError('Please enter at least one destination.');
        return;
      }

      const legs = [];
      let total = { duration: 0, cost: 0, layovers: 0, score: 0 };
      for (let i = 0; i < chain.length - 1; i++) {
        const legRes = await queryOneWay({
          src: chain[i], dst: chain[i+1], meth, w_duration, w_cost, w_layovers, max_layovers
        });
        if (!legRes) {
          // show partial + error
          if (legs.length > 0) {
            renderLegsSummary(legs, meth);
          }
          showResultError(`No route for segment ${chain[i]} → ${chain[i+1]}.`);
          return;
        }
        legs.push(legRes);
        total.duration += legRes.totals?.duration_hours || 0;
        total.cost     += legRes.totals?.cost_usd || 0;
        total.layovers += legRes.totals?.layovers || 0;
        total.score    += legRes.totals?.score || 0;
      }
      renderMultiCity(legs, total, meth);
    }
  } catch (e) {
    showResultError(`Network error: ${e.message}`);
  }
}

async function queryOneWay({src, dst, meth, w_duration, w_cost, w_layovers, max_layovers}) {
  const params = new URLSearchParams({
    from: src, to: dst,
    method: meth,
    w_duration: String(w_duration),
    w_cost: String(w_cost),
    w_layovers: String(w_layovers),
    max_layovers: String(max_layovers)
  });

  // Optional date/flex values – currently not used by backend but passed for future use
  if (dateOut?.value) params.set('date_out', dateOut.value);
  if (flexDates?.checked) params.set('flex', '1');

  const url = `/api/route?${params.toString()}`;
  const res = await getJSON(url);
  if (res.error) return null;
  // attach method label for rendering
  res.totals = res.totals || {};
  res.totals.method = (meth === 'a_star' || meth === 'a*') ? 'A*' :
                      (meth === 'metta' ? 'MeTTa' : 'Dijkstra');
  return res;
}

/* ---------- renderers ---------- */
function clearResult() {
  metricsBox.innerHTML = '';
  resultBox.classList.remove('empty');
  resultBox.innerHTML = `<div class="result">Searching…</div>`;
}

function showSummary(res, methodLabel) {
  metricsBox.innerHTML = summaryTiles({
    duration: res?.totals?.duration_hours ?? 0,
    cost: res?.totals?.cost_usd ?? 0,
    layovers: res?.totals?.layovers ?? 0,
    score: res?.totals?.score ?? 0,
    method: methodLabel?.toUpperCase?.() || res?.totals?.method || 'method'
  });
}

function renderRoute(res) {
  if (!res) {
    showResultError('No route for that direction (try reversing or allowing more layovers).');
    return;
  }
  showSummary(res, res.totals?.method);

  // legs table
  let html = `
    <table class="grid">
      <thead>
        <tr>
          <th>From</th><th>To</th><th>Airline</th>
          <th>Duration (h)</th><th>Cost (USD)</th>
        </tr>
      </thead><tbody>
  `;
  (res.edges || []).forEach(e => {
    html += `<tr>
      <td>${e.from}</td><td>${e.to}</td>
      <td>${e.airline ?? ''}</td>
      <td>${fmt2(e.duration ?? 0)}</td>
      <td>${fmt2(e.cost ?? 0)}</td>
    </tr>`;
  });
  html += `</tbody></table>`;
  resultBox.innerHTML = html;
}

function renderRoundTrip(there, back, meth) {
  const total = {
    duration_hours: (there.totals?.duration_hours || 0) + (back.totals?.duration_hours || 0),
    cost_usd:       (there.totals?.cost_usd || 0)       + (back.totals?.cost_usd || 0),
    layovers:       (there.totals?.layovers || 0)       + (back.totals?.layovers || 0),
    score:          (there.totals?.score || 0)          + (back.totals?.score || 0),
    method: meth.toUpperCase()
  };
  metricsBox.innerHTML = summaryTiles({
    duration: total.duration_hours, cost: total.cost_usd,
    layovers: total.layovers, score: total.score, method: total.method
  });

  let html = `
    <h3 style="margin:0 0 8px 0">Path: ${there.path?.join(' → ') || ''} → ${back.path?.join(' → ') || ''}</h3>
    <table class="grid">
      <thead><tr>
        <th>From</th><th>To</th><th>Airline</th>
        <th>Duration (h)</th><th>Cost (USD)</th>
      </tr></thead><tbody>
  `;
  [...(there.edges || []), ...(back.edges || [])].forEach(e => {
    html += `<tr>
      <td>${e.from}</td><td>${e.to}</td>
      <td>${e.airline ?? ''}</td>
      <td>${fmt2(e.duration ?? 0)}</td>
      <td>${fmt2(e.cost ?? 0)}</td>
    </tr>`;
  });
  html += `</tbody></table>`;
  resultBox.innerHTML = html;
}

function renderLegsSummary(legs, meth) {
  // compute totals
  const t = legs.reduce((acc, r) => {
    acc.duration += r.totals?.duration_hours || 0;
    acc.cost     += r.totals?.cost_usd || 0;
    acc.layovers += r.totals?.layovers || 0;
    acc.score    += r.totals?.score || 0;
    return acc;
  }, {duration:0, cost:0, layovers:0, score:0});
  metricsBox.innerHTML = summaryTiles({
    duration: t.duration, cost: t.cost, layovers: t.layovers, score: t.score, method: meth.toUpperCase()
  });

  let html = `
    <table class="grid">
      <thead><tr>
        <th>From</th><th>To</th><th>Airline</th>
        <th>Duration (h)</th><th>Cost (USD)</th>
      </tr></thead><tbody>
  `;
  legs.forEach(r => (r.edges || []).forEach(e => {
    html += `<tr>
      <td>${e.from}</td><td>${e.to}</td>
      <td>${e.airline ?? ''}</td>
      <td>${fmt2(e.duration ?? 0)}</td>
      <td>${fmt2(e.cost ?? 0)}</td>
    </tr>`;
  }));
  html += `</tbody></table>`;
  resultBox.innerHTML = html;
}

function renderMultiCity(legs, total, meth) {
  metricsBox.innerHTML = summaryTiles({
    duration: total.duration, cost: total.cost, layovers: total.layovers, score: total.score, method: meth.toUpperCase()
  });

  let html = `
    <table class="grid">
      <thead><tr>
        <th>From</th><th>To</th><th>Airline</th>
        <th>Duration (h)</th><th>Cost (USD)</th>
      </tr></thead><tbody>
  `;
  legs.forEach(r => (r.edges || []).forEach(e => {
    html += `<tr>
      <td>${e.from}</td><td>${e.to}</td>
      <td>${e.airline ?? ''}</td>
      <td>${fmt2(e.duration ?? 0)}</td>
      <td>${fmt2(e.cost ?? 0)}</td>
    </tr>`;
  }));
  html += `</tbody></table>`;
  resultBox.innerHTML = html;
}

function summaryTiles({duration, cost, layovers, score, method}) {
  return `
    <div class="pill"><b>${fmt2(duration)}</b><span>Duration</span></div>
    <div class="pill"><b>$${fmt2(cost)}</b><span>Cost</span></div>
    <div class="pill"><b>${layovers ?? 0}</b><span>Layovers</span></div>
    <div class="pill"><b>${fmt2(score)}</b><span>Score</span></div>
    <div class="pill alt"><b>${(method || 'method').toUpperCase()}</b><span>method</span></div>
  `;
}

function showResultError(msg) {
  resultBox.innerHTML = `<div class="result empty">${msg}</div>`;
}
