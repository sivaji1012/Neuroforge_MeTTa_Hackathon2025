(() => {
  // ===== API helpers ========================================================
  async function fetchJSON(url, opts) {
    const res = await fetch(url, opts);
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.error || `Request failed: ${res.status}`);
    return body;
  }
  const api = {
    routes: () => fetchJSON(`/api/routes`),
    cities: (source) => fetchJSON(`/api/cities?source=${encodeURIComponent(source)}`).catch(() => ({cities: []})),
    bestRoute: (params) => fetchJSON(`/api/route?${new URLSearchParams(params).toString()}`),
    addFlight: (payload) => fetchJSON(`/api/update-flight-data`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    }),
    mettaDirect: (from, to) => fetchJSON(`/api/metta/direct?${new URLSearchParams({from, to}).toString()}`),
  };

  // ===== Rendering helpers ==================================================
  function renderRoutesTable(data) {
    const el = document.getElementById("routes-table");
    if (!el) return;
    if (!data || !data.routes) { el.textContent = "No routes"; return; }
    const rows = data.routes.map(r =>
      `<tr><td>${r.from}</td><td>${r.to}</td><td>${r.airline}</td><td>${r.duration}h</td><td>$${r.cost}</td></tr>`
    ).join("");
    el.innerHTML = `<table>
      <thead><tr><th>From</th><th>To</th><th>Airline</th><th>Duration</th><th>Cost</th></tr></thead>
      <tbody>${rows}</tbody></table>`;
  }

  function renderResult(res) {
    const sec = document.getElementById("results");
    if (sec) sec.hidden = false;

    const pathEl = document.getElementById("path");
    if (pathEl) pathEl.innerHTML = `<div class="path">${res.path.join(" → ")}</div>`;

    const t = res.totals || {};
    const totalsEl = document.getElementById("totals");
    if (totalsEl) {
      totalsEl.innerHTML = `
        <ul class="totals">
          <li><strong>Duration:</strong> ${t.duration_hours} h</li>
          <li><strong>Cost:</strong> $${t.cost_usd}</li>
          <li><strong>Layovers:</strong> ${t.layovers}</li>
          <li><strong>Score:</strong> ${t.score} (${t.method})</li>
        </ul>`;
    }

    const segsEl = document.getElementById("segments");
    if (segsEl) {
      segsEl.innerHTML = (res.edges || []).map(e => `
        <div class="segment">
          <div class="cities">${e.from} → ${e.to}</div>
          <div class="meta">${e.airline} · ${e.duration}h · $${e.cost}</div>
        </div>`).join("");
    }
  }

  // ===== City cache (hint only; never blocks) ===============================
  const CITY_CACHE = { python: [], metta: [] };
  async function refreshCitiesFor(source) {
    const data = await api.cities(source);
    CITY_CACHE[source] = data.cities || [];
  }

  // ===== Presets (for End User) ============================================
  function weightsFromPreset(preset) {
    switch (preset) {
      case "fastest":          return { w_duration: 1.0, w_cost: 0.0, w_layovers: 0.0 };
      case "cheapest":         return { w_duration: 0.3, w_cost: 1.0, w_layovers: 0.0 };
      case "fewest_layovers":  return { w_duration: 0.4, w_cost: 0.2, w_layovers: 1.0 };
      case "balanced":
      default:                 return { w_duration: 1.0, w_cost: 0.3, w_layovers: 0.2 };
    }
  }

  // ===== Mode toggle (optional; only if elements exist) =====================
  function setMode(mode) {
    const user = document.getElementById("user-panel");
    const admin = document.getElementById("admin-panel");
    if (user)  user.hidden  = mode !== "end";
    if (admin) admin.hidden = mode !== "admin";
    try { localStorage.setItem("fr_mode", mode); } catch {}
  }

  document.addEventListener("DOMContentLoaded", async () => {
    // Preload city caches (safe if endpoints absent)
    refreshCitiesFor("python");
    refreshCitiesFor("metta");

    // ---------- Mode toggle ----------
    const modeEl = document.getElementById("mode");
    if (modeEl) {
      const saved = localStorage.getItem("fr_mode") || "end";
      modeEl.value = saved;
      setMode(saved);
      modeEl.addEventListener("change", e => setMode(e.target.value));
    }

    // ---------- End User form (new UI) ----------
    const userForm = document.getElementById("user-route-form");
    if (userForm) {
      const u_source = document.getElementById("u_source");
      if (u_source) u_source.addEventListener("change", e => refreshCitiesFor(e.target.value));

      userForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const source = (document.getElementById("u_source")?.value || "python").trim();
        const params = {
          from: document.getElementById("u_from").value.trim(),
          to: document.getElementById("u_to").value.trim(),
          source,
          method: "a_star",
          ...weightsFromPreset(document.getElementById("u_preset")?.value || "balanced"),
        };

        // Optional constraints
        const maxLay = document.getElementById("u_max_layovers")?.value;
        const maxDur = document.getElementById("u_max_duration")?.value;
        const maxPri = document.getElementById("u_max_price")?.value;
        const minPri = document.getElementById("u_min_price")?.value;
        if (maxLay) params.max_layovers = maxLay;
        if (maxDur) params.max_duration = maxDur;
        if (maxPri) params.max_price    = maxPri;
        if (minPri) params.min_price    = minPri;

        // Soft hint only (don’t block)
        const known = CITY_CACHE[source] || [];
        const missing = [params.from, params.to].filter(c => !known.includes(c));
        if (missing.length) console.warn(`City(ies) not in ${source}: ${missing.join(", ")}`);

        try {
          const res = await api.bestRoute(params);
          renderResult(res);
        } catch (err) {
          alert(err.message);
        }
      });
    }

    // ---------- Legacy route form (old UI with raw weights) ----------
    const legacyForm = document.getElementById("route-form");
    if (legacyForm) {
      const sourceSel = document.getElementById("source");
      if (sourceSel) sourceSel.addEventListener("change", e => refreshCitiesFor(e.target.value));

      legacyForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const source = (document.getElementById("source")?.value || "python").trim();
        const params = {
          from: document.getElementById("from").value.trim(),
          to: document.getElementById("to").value.trim(),
          method: document.getElementById("method")?.value || "dijkstra",
          source,
          w_duration: document.getElementById("w_duration")?.value || "1.0",
          w_cost: document.getElementById("w_cost")?.value || "0.0",
          w_layovers: document.getElementById("w_layovers")?.value || "0.0",
        };

        const known = CITY_CACHE[source] || [];
        const missing = [params.from, params.to].filter(c => !known.includes(c));
        if (missing.length) console.warn(`City(ies) not in ${source}: ${missing.join(", ")}`);

        try {
          const res = await api.bestRoute(params);
          renderResult(res);
        } catch (err) {
          alert(err.message);
        }
      });
    }

    // ---------- Admin panel ----------
    const refreshBtn = document.getElementById("refresh-routes");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", async () => {
        const data = await api.routes().catch(() => ({routes: []}));
        renderRoutesTable(data);
      });
    }

    const addForm = document.getElementById("add-flight-form");
    if (addForm) {
      addForm.addEventListener("submit", async (e) => {
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
          await api.addFlight(payload);
          alert("Flight added!");
          const data = await api.routes();
          renderRoutesTable(data);
          await refreshCitiesFor("metta");
        } catch (err) {
          alert(err.message);
        }
      });
    }

    const mettaDbg = document.getElementById("metta-debug-form");
    if (mettaDbg) {
      mettaDbg.addEventListener("submit", async (e) => {
        e.preventDefault();
        const from = document.getElementById("md_from").value.trim();
        const to   = document.getElementById("md_to").value.trim();
        const out  = document.getElementById("md_result");
        try {
          const res = await api.mettaDirect(from, to);
          if (out) out.textContent = JSON.stringify(res, null, 2);
        } catch (err) {
          if (out) out.textContent = err.message;
        }
      });
    }

    // ---------- Initial table load (if present) ----------
    if (document.getElementById("routes-table")) {
      api.routes().then(renderRoutesTable).catch(console.error);
    }
  });
})();
