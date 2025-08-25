# Optimal Flight Route Finder — Starter Kit

This project is a **minimal, working** flight-route optimizer with:

- **MeTTa** knowledge base for flight facts and queries (see `metta/`).
- A **Flask** backend that computes optimal routes (Dijkstra / A* ready) and can **optionally** read routes from MeTTa.
- A lightweight **frontend** to enter origin/destination, set weights (duration/cost/layovers), and visualize the route.

> ✅ Out of the box, the backend runs with a built-in sample dataset.  
> ✅ If you have Hyperon/MeTTa installed, the backend will **also** load `metta/flight_routes.metta` automatically.

---

### 0) Running the Code

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python app.py

---
## Quick Start

### 1) Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python app.py

The API starts at http://127.0.0.1:5000.

### 2) Frontend

Open frontend/index.html in your browser. It calls the backend APIs directly.

Endpoints

GET /api/routes — Returns the full route table the backend is using (merged from built-in sample + any MeTTa facts loaded).

GET /api/route?from=Toronto&to=Paris&w_duration=0.7&w_cost=0.2&w_layovers=0.1

Computes the best path using Dijkstra with a custom weight:

weight(edge) = w_duration * duration_hours
             + w_cost     * (cost_usd / 100.0)
             + w_layovers * layover_penalty


w_* params are optional (default: 1.0, 0.0, 0.0 = prioritize duration).

Response includes the path, totals, edge-by-edge details, and a breakdown.

MeTTa Integration

Facts are in metta/flight_routes.metta, e.g.:

(flight-route "Toronto" "NewYork" "AirCanada" (duration 1.5) (cost 220) (layovers 0))


Query helpers and (illustrative) algorithm stubs are in metta/algorithms.metta.

getDirectRoutes, neighbors, edge-weight, weight-by-criteria (illustrative MeTTa).

A functional Uniform-Cost (Dijkstra) sketch in pure MeTTa is included as a learning aid.

Note: You can execute MeTTa directly via Hyperon. For production-grade performance we use Python Dijkstra here.

Python ⇄ MeTTa:

If the hyperon Python package is available, the backend will:

load the MeTTa files into a space

run a match query to extract all flight-route facts

merge them into the graph

If hyperon is not installed, the backend still works using the built-in sample routes.

Extend with Real Data

To integrate real routes/schedules:

Write an importer that parses CSV/JSON (e.g., OpenFlights, airline timetables) and
emits MeTTa atoms like (flight-route "YYZ" "JFK" "AC" (duration 1.5) (cost 220) (layovers 0)).

Add time windows (dep "09:30") (arr "11:00") (tz "America/Toronto") and implement
a layover validity check (>= min_connection_minutes) in Python or MeTTa.

Notes

The frontend is intentionally simple (vanilla JS). Swap in React/Tailwind later if desired.

The Python graph uses NetworkX. You can switch to your own A* with a heuristic on great-circle distance.

All units are illustrative:

duration = hours (float)

cost = USD

layovers = 0 for a direct flight edge (the total layovers are computed as stops in the path)