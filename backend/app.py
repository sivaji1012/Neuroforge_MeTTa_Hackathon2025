import os
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from flask import Flask, request, jsonify
from flask_cors import CORS
import networkx as nx

# Optional MeTTa/Hyperon integration
HAVE_HYPERON = False
try:
    from hyperon import MeTTa  # type: ignore
    HAVE_HYPERON = True
except Exception:
    HAVE_HYPERON = False

app = Flask(__name__)
CORS(app)

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

# Built-in sample dataset (you can extend/replace this with MeTTa or CSV)
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
def load_metta_edges(metta_dir: str):
    """If Hyperon/MeTTa is available, load flight facts and add to graph."""
    if not HAVE_HYPERON:
        return []

    metta_files = []
    for fname in ("flight_routes.metta", "algorithms.metta"):
        fpath = os.path.join(metta_dir, fname)
        if os.path.exists(fpath):
            metta_files.append(fpath)

    if not metta_files:
        return []

    m = MeTTa()
    for f in metta_files:
        with open(f, "r", encoding="utf-8") as fh:
            code = fh.read()
        # Load code into space
        m.run(code)

    # Pull all flight-route facts
    # Returns tuples of: (src dst airline duration cost layovers)
    q = '!(match &self (flight-route $from $to $airline (duration $dur) (cost $cost) (layovers $lay)) ($from $to $airline $dur $cost $lay))'
    try:
        results = m.run(q)
    except Exception:
        # Hyperon API variants exist; if this fails, we simply skip MeTTa import
        return []

    edges = []
    # Parse the values back (Hyperon returns nested SExpr-like values).
    # We'll use a simple string-based parse for portability.
    for r in results:
        s = str(r)
        # Expect something like: (Toronto NewYork AirCanada 1.5 220 0)
        s = s.strip()
        if s.startswith("(") and s.endswith(")"):
            s = s[1:-1]
        parts = []
        token = ""
        in_quote = False
        for ch in s:
            if ch == '"':
                in_quote = not in_quote
                token += ch
            elif ch == " " and not in_quote:
                if token:
                    parts.append(token)
                    token = ""
            else:
                token += ch
        if token:
            parts.append(token)

        if len(parts) != 6:
            continue

        # Strip quotes
        def unq(x):
            return x[1:-1] if len(x) >= 2 and x[0] == '"' and x[-1] == '"' else x

        src = unq(parts[0])
        dst = unq(parts[1])
        airline = unq(parts[2])
        try:
            duration = float(unq(parts[3]))
            cost     = float(unq(parts[4]))
            lay      = int(unq(parts[5]))
        except Exception:
            continue

        edge = FlightEdge(src, dst, airline, duration, cost, lay)
        edges.append(edge)

    for e in edges:
        add_edge_to_graph(e)

    return edges

# -----------------------------
# Weighting and Dijkstra
# -----------------------------
def edge_weight(u: str, v: str, attrs: Dict[str, Any],
                w_duration: float, w_cost: float, w_layovers: float) -> float:
    # Normalize cost a bit to keep scales similar (USD/100)
    return (
        w_duration * float(attrs.get("duration", 0.0)) +
        w_cost     * (float(attrs.get("cost", 0.0)) / 100.0) +
        w_layovers * float(attrs.get("layovers", 0))
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

    # Collect details
    edges = []
    total_duration = 0.0
    total_cost = 0.0
    # Layovers are path stops minus 1 (edges count minus 1)
    total_layovers = max(0, len(path) - 2)

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
        total_cost += float(attrs.get("cost", 0.0))

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
            "score": round(score, 3)
        }
    }

# -----------------------------
# Boot
# -----------------------------
def boot():
    GRAPH.clear()
    load_sample_edges()
    # Try to load MeTTa facts
    metta_dir = os.path.join(os.path.dirname(__file__), "..", "metta")
    load_metta_edges(os.path.abspath(metta_dir))

boot()

# -----------------------------
# Routes
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
        w_cost = float(request.args.get("w_cost", "0.0"))
        w_layovers = float(request.args.get("w_layovers", "0.0"))
    except Exception:
        return jsonify({"error": "Weights must be numeric"}), 400

    res = compute_best_route(src, dst, w_duration, w_cost, w_layovers)
    if not res:
        return jsonify({"error": f"No route from {src} to {dst}"}), 404
    return jsonify(res)

if __name__ == "__main__":
    app.run(debug=True)
