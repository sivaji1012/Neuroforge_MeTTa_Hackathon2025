// Same-origin calls to Flask on :5500
async function fetchRoutes() {
  const res = await fetch(`/api/routes`);
  if (!res.ok) throw new Error("Failed to fetch routes");
  return res.json();
}

async function fetchBestRoute(params) {
  const qs = new URLSearchParams(params);
  const res = await fetch(`/api/route?${qs.toString()}`);
  if (!res.ok) {
    const j = await res.json().catch(() => ({}));
    throw new Error(j.error || "No route found");
  }
  return res.json();
}

async function addFlight(payload) {
  const res = await fetch(`/api/update-flight-data`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const j = await res.json().catch(() => ({}));
    throw new Error(j.error || "Failed to add flight");
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
      <li><strong>Score:</strong> ${t.score} (${t.method})</li>
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
  const data = await fetchRoutes().catch(() => ({routes: []}));
  renderRoutesTable(data);
});

document.getElementById("route-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const params = {
    from: document.getElementById("from").value.trim(),
    to: document.getElementById("to").value.trim(),
    method: document.getElementById("method").value,
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

document.getElementById("add-flight-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    start: document.getElementById("af_from").value.trim(),
    end: document.getElementById("af_to").value.trim(),
    airline: document.getElementById("af_airline").value.trim(),
    duration: parseFloat(document.getElementById("af_duration").value),
    cost: parseFloat(document.getElementById("af_cost").value),
    layovers: parseInt(document.getElementById("af_layovers").value || "0", 10),
  };
  try {
    await addFlight(payload);
    alert("Flight added!");
    const data = await fetchRoutes();
    renderRoutesTable(data);
  } catch (err) {
    alert(err.message);
  }
});

// Initial load
fetchRoutes().then(renderRoutesTable).catch(console.error);
