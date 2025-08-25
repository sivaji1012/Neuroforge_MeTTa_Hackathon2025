const API = "http://127.0.0.1:5000";

async function fetchRoutes() {
  const res = await fetch(`${API}/api/routes`);
  if (!res.ok) throw new Error("Failed to fetch routes");
  return res.json();
}

async function fetchBestRoute(params) {
  const qs = new URLSearchParams(params);
  const res = await fetch(`${API}/api/route?${qs.toString()}`);
  if (!res.ok) {
    const j = await res.json().catch(() => ({}));
    throw new Error(j.error || "No route found");
  }
  return res.json();
}

function renderRoutesTable(data) {
  const el = document.getElementById("routes-table");
  if (!data || !data.routes) {
    el.textContent = "No routes";
    return;
  }
  const rows = data.routes
    .map(
      r =>
        `<tr><td>${r.from}</td><td>${r.to}</td><td>${r.airline}</td><td>${r.duration}h</td><td>$${r.cost}</td></tr>`
    )
    .join("");
  el.innerHTML = `<table>
    <thead><tr><th>From</th><th>To</th><th>Airline</th><th>Duration</th><th>Cost</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

function renderResult(res) {
  const sec = document.getElementById("results");
  sec.hidden = false;

  const pathEl = document.getElementById("path");
  pathEl.innerHTML = `<div class="path">${res.path.join(" → ")}</div>`;

  const t = res.totals;
  document.getElementById("totals").innerHTML = `
    <ul class="totals">
      <li><strong>Duration:</strong> ${t.duration_hours} h</li>
      <li><strong>Cost:</strong> $${t.cost_usd}</li>
      <li><strong>Layovers:</strong> ${t.layovers}</li>
      <li><strong>Score:</strong> ${t.score}</li>
    </ul>
  `;

  const segs = res.edges
    .map(
      e => `<div class="segment">
        <div class="cities">${e.from} → ${e.to}</div>
        <div class="meta">${e.airline} · ${e.duration}h · $${e.cost}</div>
      </div>`
    )
    .join("");
  document.getElementById("segments").innerHTML = segs;
}

document.getElementById("refresh-routes").addEventListener("click", async () => {
  const data = await fetchRoutes().catch(err => ({routes: []}));
  renderRoutesTable(data);
});

document.getElementById("route-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const params = {
    from: document.getElementById("from").value.trim(),
    to: document.getElementById("to").value.trim(),
    w_duration: document.getElementById("w_duration").value || "1.0",
    w_cost: document.getElementById("w_cost").value || "0.0",
    w_layovers: document.getElementById("w_layovers").value || "0.0",
  };
  try {
    const res = await fetchBestRoute(params);
    renderResult(res);
  } catch (err) {
    alert(err.message);
  }
});

// Initial load
fetchRoutes().then(renderRoutesTable).catch(console.error);
