import os
from typing import List, Dict, Any
from dataclasses import dataclass
from flask import Flask, request, jsonify
import networkx as nx

# --- Optional MeTTa/Hyperon integration ---
HAVE_HYPERON = False
METTA_INSTANCE = None
try:
    from hyperon import MeTTa  # type: ignore
    HAVE_HYPERON = True
    METTA_INSTANCE = MeTTa()
except Exception:
    HAVE_HYPERON = False
    METTA_INSTANCE = None

# --- Serve frontend & API from the same Flask app on port 5500 ---
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")  # static at /

# -----------------------------
# Data structures
# -----------------------------
@dataclass
class FlightEdge:
    src: str
    dst: str
    airline: str
    duration: float  # hours
    cost: float      # USD
    layovers: int    # 0 for a direct edge

# Built-in sample dataset
SAMPLE_EDGES: List[FlightEdge] = [
    FlightEdge("Toronto", "NewYork",   "AirCanada", 1.5, 220, 0),
    FlightEdge("Toronto", "London",    "AirCanada", 7.2, 520, 0),
    FlightEdge("NewYork", "London",    "Delta",     6.8, 480, 0),
    FlightEdge("NewYork", "Paris",     "Delta",     7.1, 510, 0),
    FlightEdge("London",  "Paris",     "BA",        1.1, 120, 0),
    FlightEdge("London",  "Frankfurt", "Lufthansa", 1.4, 140, 0),
    FlightEdge("Frankfurt","Paris",    "Lufthansa", 1.2, 130, 0),
    FlightEdge("Toronto", "Frankfurt", "Lufthansa", 7.5, 540, 0),
    FlightEdge("Paris",   "Rome",      "AirFrance", 2.0, 160, 0),
    FlightEdge("Frankfurt","Rome",     "Lufthansa", 2.0, 150, 0),
]

GRAPH = nx.DiGraph()

def add_edge_to_graph(edge: FlightEdge):
    GRAPH.add_edge(
        edge.src, edge.dst,
        airline=edge.airline,
        duration=edge.duration,
        cost=edge.cost,
        layovers=edge.layovers
    )

def load_sample_edges():
    for e in SAMPLE_EDGES:
        add_edge_to_graph(e)

# -----------------------------
# Optional: load MeTTa facts
# -----------------------------
def _load_metta_files_into(instance, metta_dir: str):
    for fname in ("flight_routes.metta", "algorithms.metta"):
        fpath = os.path.join(metta_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as fh:
                instance.run(fh.read())

def _pull_edges_from_metta(instance):
    q = '!(match &self (flight-route $from $to $airline (duration $dur) (cost $cost) (layovers $lay)) ($from $to $airline $dur $cost $lay))'
    try:
        results = instance.run(q)
    except Exception:
        return []
    edges = []
    for r in results:
        s = str(r).strip()
        if s.startswith("(") and s.endswith(")"):
            s = s[1:-1]
        parts, tok, in_q = [], "", False
        for ch in s:
            if ch == '"':
                in_q = not in_q
                tok += ch
            elif ch == " " and not in_q:
                if tok:
                    parts.append(tok); tok = ""
            else:
                tok += ch
        if tok: parts.append(tok)
        if len(parts) != 6: continue

        def unq(x: str) -> str:
            return x[1:-1] if len(x) >= 2 and x[0] == '"' and x[-1] == '"' else x

        src, dst, airline = unq(parts[0]), unq(parts[1]), unq(parts[2])
        try:
            duration = float(unq(parts[3])); cost = float(unq(parts[4])); lay = int(unq(parts[5]))
        except Exception:
            continue
        edges.append(FlightEdge(src, dst, airline, duration, cost, lay))
    return edges

def load_metta_edges(metta_dir: str):
    if not (HAVE_HYPERON and METTA_INSTANCE):
        return []
    _load_metta_files_into(METTA_INSTANCE, metta_dir)
    edges = _pull_edges_from_metta(METTA_INSTANCE)
    for e in edges:
        add_edge_to_graph(e)
    return edges

# -----------------------------
# Weighting and Dijkstra
# -----------------------------
LAYOVER_PENALTY_PER_HOP_HOURS = 1.5  # tune 0.5–3.0

def edge_weight(u: str, v: str, attrs: Dict[str, Any],
                w_duration: float, w_cost: float, w_layovers: float) -> float:
    return (
        w_duration * float(attrs.get("duration", 0.0)) +
        w_cost     * (float(attrs.get("cost", 0.0)) / 100.0) +
        w_layovers * LAYOVER_PENALTY_PER_HOP_HOURS
    )

def compute_best_route(src: str, dst: str,
                       w_duration: float, w_cost: float, w_layovers: float):
    if src not in GRAPH or dst not in GRAPH:
        return None

    def w_func(u, v, attrs):
        return edge_weight(u, v, attrs, w_duration, w_cost, w_layovers)

    try:
        path = nx.shortest_path(GRAPH, source=src, target=dst, weight=w_func, method="dijkstra")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None

    edges = []
    total_duration = 0.0
    total_cost = 0.0
    total_layovers = max(0, len(path) - 2)  # edges-1

    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        attrs = GRAPH[u][v]
        edges.append({
            "from": u,
            "to": v,
            "airline": attrs.get("airline"),
            "duration": attrs.get("duration"),
            "cost": attrs.get("cost"),
        })
        total_duration += float(attrs.get("duration", 0.0))
        total_cost     += float(attrs.get("cost", 0.0))

    score = sum(
        edge_weight(path[i], path[i+1], GRAPH[path[i]][path[i+1]], w_duration, w_cost, w_layovers)
        for i in range(len(path) - 1)
    )
    return {
        "path": path,
        "edges": edges,
        "totals": {
            "duration_hours": round(total_duration, 2),
            "cost_usd": round(total_cost, 2),
            "layovers": total_layovers,
            "score": round(score, 3),
        },
    }

# -----------------------------
# Boot
# -----------------------------
def boot():
    GRAPH.clear()
    load_sample_edges()
    metta_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "metta"))
    load_metta_edges(metta_dir)

boot()

# -----------------------------
# API
# -----------------------------
@app.get("/api/routes")
def api_routes():
    data = []
    for u, v, attrs in GRAPH.edges(data=True):
        data.append({
            "from": u, "to": v,
            "airline": attrs.get("airline"),
            "duration": float(attrs.get("duration", 0.0)),
            "cost": float(attrs.get("cost", 0.0)),
            "layovers": int(attrs.get("layovers", 0)),
        })
    return jsonify({"routes": data, "nodes": list(GRAPH.nodes)})

@app.get("/api/route")
def api_route():
    src = request.args.get("from")
    dst = request.args.get("to")
    if not src or not dst:
        return jsonify({"error": "Missing required params: from, to"}), 400
    try:
        w_duration = float(request.args.get("w_duration", "1.0"))
        w_cost     = float(request.args.get("w_cost", "0.0"))
        w_layovers = float(request.args.get("w_layovers", "0.0"))
    except Exception:
        return jsonify({"error": "Weights must be numeric"}), 400

    res = compute_best_route(src, dst, w_duration, w_cost, w_layovers)
    if not res:
        return jsonify({"error": f"No route from {src} to {dst}"}), 404
    return jsonify(res)

def add_fact_to_graph_and_metta(start: str, end: str, airline: str,
                                duration: float, cost: float, layovers: int = 0):
    add_edge_to_graph(FlightEdge(start, end, airline, duration, cost, layovers))
    if HAVE_HYPERON and METTA_INSTANCE:
        atom = f'(flight-route "{start}" "{end}" "{airline}" (duration {duration}) (cost {cost}) (layovers {layovers}))'
        METTA_INSTANCE.run(atom)

@app.post("/api/update-flight-data")
def update_flight_data():
    data = request.get_json(silent=True) or {}
    required = ["start", "end", "airline", "duration", "cost"]
    missing = [k for k in required if k not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400
    try:
        start = str(data["start"]).strip()
        end = str(data["end"]).strip()
        airline = str(data["airline"]).strip()
        duration = float(data["duration"])
        cost = float(data["cost"])
        layovers = int(data.get("layovers", 0))
    except Exception:
        return jsonify({"error": "Invalid field types"}), 400
    add_fact_to_graph_and_metta(start, end, airline, duration, cost, layovers)
    return jsonify({"status": "ok"}), 200

# -----------------------------
# Frontend (same origin)
# -----------------------------
@app.route("/")
def index():
    return app.send_static_file("index.html")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5500, debug=True)
