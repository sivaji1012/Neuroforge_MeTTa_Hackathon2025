# ✈️ Optimal Flight Route Finder

The Optimal Flight Route Finder is a lightweight system for computing the most efficient flight routes between cities.
It integrates **MeTTa** (for knowledge representation), **Python + NetworkX** (for pathfinding), **Flask** (for APIs), and a **frontend UI** (HTML/JS).

---

## 🚀 Features

* **Optimized Pathfinding**: Dijkstra and A\* algorithms for shortest travel time.
* **Custom Weighting**: Users can prioritize duration, cost, or layovers.
* **Constraints**: End users can apply max duration, price limits, or layover constraints.
* **Dynamic Updates**: Admins can add new flights (mirrored in Python graph and optionally MeTTa).
* **Dual Data Sources**:

  * **Python Graph**: Fast in-memory routing.
  * **MeTTa (Live)**: Knowledge representation and reasoning with Hyperon’s MeTTa interpreter.
* **Web UI**: End User mode for searching flights, Admin mode for managing routes.

---

## 🛠️ Deployment

### 1. Clone the repository

```bash
git clone <your_repo_url>
cd MeTTa-Hackathon
```

### 2. Backend setup (WSL/Linux recommended)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

If you want **MeTTa/Hyperon** support:

```bash
pip install hyperon
```

> ⚠️ On Windows native Python, Hyperon often fails to build. WSL2 or Linux is strongly recommended.

### 3. Start the Flask server

```bash
python app.py
```

By default, this runs at:
👉 [http://127.0.0.1:5500](http://127.0.0.1:5500)

### 4. Frontend

The frontend is served by Flask (from `frontend/`), so you can directly open:

```
http://127.0.0.1:5500
```

---

## ⚖️ Windows vs WSL/Linux

### ❌ Limitations on Windows

* `hyperon` (MeTTa runtime) may fail to install due to missing Rust/Cargo toolchain or unsupported dynamic libraries.
* File paths (`.venv/Scripts/activate` vs `.venv/bin/activate`) differ, which can confuse users.
* Networking quirks: Flask binds to `127.0.0.1`, which works in Windows, but Hyperon dependencies often expect Linux.

### ✅ Advantages of WSL/Linux

* Full compatibility with `hyperon` (MeTTa interpreter).
* Easier dependency resolution for `networkx`, `flask`, and Rust-based Python packages.
* Uniform Unix-like environment that matches most production deployments.
* Better performance for I/O and scientific workloads.

---

## 🧮 Algorithms Used

### Dijkstra’s Algorithm

* Finds the shortest weighted path between two cities.
* Guarantees optimality if all edge weights are non-negative.
* In this app, weights are computed as:

```
weight = w_duration * duration_hours
       + w_cost     * (cost / 100)
       + w_layovers * layover_penalty
```

### A\* Algorithm

* Similar to Dijkstra, but guided by a **heuristic** to speed up search.
* Heuristic = estimated flight duration between current city and destination:

  ```
  haversine_distance(city, goal) / cruise_speed
  ```
* Admissible: never overestimates travel time → ensures optimal routes.

### Custom Weighting

* Users can adjust:

  * `w_duration` (default 1.0)
  * `w_cost` (default 0.3–1.0 depending on preset)
  * `w_layovers` (penalty \~1.5h per layover)
* Or apply constraints (e.g., “max price = 500 USD”).

---

## 🔄 System Flow

```mermaid
flowchart TD
  A[User enters query in Frontend] --> B[Frontend JS builds API request]
  B --> C[/api/route (Flask)]
  C -->|source=python| D[Python Graph + NetworkX]
  C -->|source=metta| E[MeTTa Knowledge Base]

  D --> F[Compute route with Dijkstra or A*]
  E --> G[Match & query flight-route atoms]
  G --> F

  F --> H[Return JSON result to Flask]
  H --> I[Frontend JS renders path, totals, segments]
  I --> J[User sees optimized route on screen]
```

---

## 🧩 Architecture Components

### 1. **MeTTa**

* Handles knowledge representation and reasoning.
* Stores structured flight facts:

  ```
  (flight-route "Paris" "Rome" "AirFrance" (duration 2.0) (cost 160) (layovers 0))
  ```
* Can answer reasoning queries:

  * *“What is the fastest route from CityA to CityB?”*

### 2. **Python**

* Middleware between MeTTa and frontend.
* Runs Dijkstra/A\* on either:

  * The in-memory Python graph.
  * A temporary graph rebuilt from live MeTTa atoms.
* Applies custom weights and constraints.

### 3. **Flask**

* REST API provider:

  * `/api/route` → optimized path
  * `/api/routes` → all known routes
  * `/api/update-flight-data` → add flights
  * `/api/metta/direct` → raw MeTTa query
  * `/api/cities` → list known nodes
* Serves the frontend (`index.html`, `script.js`, etc.).

### 4. **Frontend (HTML/JS)**

* Provides two modes:

  * **End User**: pick source/destination, apply presets/constraints.
  * **Admin**: view routes, add new flights, run MeTTa debug queries.
* Communicates via AJAX (`fetch`) with Flask.
* Renders results: best route, total cost/duration/layovers, and flight segments.

---

## 🧪 Example

```bash
# Python Graph source
curl "http://127.0.0.1:5500/api/route?from=Paris&to=Rome&method=a_star&source=python"

# MeTTa source (requires hyperon installed)
curl "http://127.0.0.1:5500/api/route?from=Paris&to=Rome&method=a_star&source=metta"
```

Expected JSON:

```json
{
  "path": ["Paris", "Rome"],
  "edges": [
    {"from": "Paris", "to": "Rome", "airline": "AirFrance", "duration": 2.0, "cost": 160}
  ],
  "totals": {
    "duration_hours": 2.0,
    "cost_usd": 160.0,
    "layovers": 0,
    "score": 20.0,
    "method": "a_star"
  }
}
```

---

## ⚠️ Known Limitations

* Adding new flights via Admin UI updates the **in-memory graph** (and MeTTa if available), but not persisted to `.metta` files.
* Hyperon support is **experimental** and sensitive to environment. Use WSL/Linux for best results.
* Heuristic in A\* considers only **duration**, not cost/layovers.

---

Would you like me to also generate a **deployment diagram (architecture)** in addition to the flowchart, showing how Flask, Python Graph, and MeTTa sit between the frontend and the user?
