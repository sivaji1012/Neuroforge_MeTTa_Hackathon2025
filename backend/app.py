import math
import os
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from flask import Flask, request, jsonify
import networkx as nx

# (Optional) CORS if you later serve the UI from a different origin
try:
    from flask_cors import CORS  # type: ignore
except Exception:
    CORS = None  # same-origin does not need CORS

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
if CORS:
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

# City coordinates (approximate, for heuristic)
CITY_COORDS: Dict[str, Tuple[float, float]] = {
    "Toronto": (43.65107, -79.347015),
    "NewYork": (40.712776, -74.005974),
    "London": (51.507351, -0.127758),
    "Paris": (48.856613, 2.352222),
    "Frankfurt": (50.110924, 8.682127),
    "Rome": (41.902782, 12.496366),
}

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
# MeTTa helpers (load at boot + request-time)
# -----------------------------
def _load_metta_files_into(instance, metta_dir: str):
    """
    Load ONLY metta/flight_routes.metta.
    Supports multi-line S-expressions by buffering until parens are balanced.
    Emits precise line ranges on parse errors.
    """
    fpath = os.path.join(metta_dir, "flight_routes.metta")
    if not os.path.exists(fpath):
        return

    def strip_inline_comment(s: str) -> str:
        # Remove anything after an unquoted ';'
        out, in_str, esc = [], False, False
        for ch in s:
            if in_str:
                out.append(ch)
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
                out.append(ch)
            elif ch == ';':
                break  # comment starts (outside string) → ignore rest of line
            else:
                out.append(ch)
        return "".join(out)

    def paren_delta_outside_strings(s: str) -> int:
        # Count '(' and ')' outside of quoted strings
        bal, in_str, esc = 0, False, False
        for ch in s:
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            else:
                if ch == '"':
                    in_str = True
                elif ch == '(':
                    bal += 1
                elif ch == ')':
                    bal -= 1
        return bal

    buf: list[str] = []
    bal = 0
    start_line = None

    with open(fpath, "r", encoding="utf-8") as fh:
        for i, raw in enumerate(fh, start=1):
            # Strip inline comments and whitespace
            code = strip_inline_comment(raw).strip()
            if not code:
                continue  # skip blank/comment-only lines

            if bal == 0:
                start_line = i
                buf = []

            buf.append(code)
            bal += paren_delta_outside_strings(code)

            if bal == 0:
                form = " ".join(buf)
                try:
                    instance.run(form)
                except Exception as e:
                    raise RuntimeError(
                        f"MeTTa parse error in {fpath}:{start_line}-{i} -> `{form}` :: {e}"
                    )
                buf = []
                start_line = None

    if bal != 0:
        # Unclosed expression at EOF
        joined = " ".join(buf)
        raise RuntimeError(
            f"MeTTa parse error in {fpath}:{start_line}-EOF -> (unclosed form) `{joined}`"
        )


def _pull_edges_from_metta(instance) -> List[FlightEdge]:
    q = '!(match &self (flight-route $from $to $airline (duration $dur) (cost $cost) (layovers $lay)) ($from $to $airline $dur $cost $lay))'
    try:
        results = instance.run(q)
    except Exception:
        return []
    edges: List[FlightEdge] = []
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
        if len(parts) != 6:
            continue

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

# Build a temporary graph from edges (used for request-time MeTTa)
def graph_from_edges(edges: List[FlightEdge]) -> nx.DiGraph:
    g = nx.DiGraph()
    for e in edges:
        g.add_edge(
            e.src, e.dst,
            airline=e.airline,
            duration=e.duration,
            cost=e.cost,
            layovers=e.layovers
        )
    return g

# Request-time pull of edges from the *current* MeTTa space
def edges_from_metta_now() -> List[FlightEdge]:
    if not (HAVE_HYPERON and METTA_INSTANCE):
        return []
    return _pull_edges_from_metta(METTA_INSTANCE)

# -----------------------------
# Weights & Heuristic
# -----------------------------
LAYOVER_PENALTY_PER_HOP_HOURS = 1.5  # tune 0.5–3.0
CRUISE_SPEED_KMPH = 800.0
EARTH_R_KM = 6371.0088

def edge_weight(u: str, v: str, attrs: Dict[str, Any],
                w_duration: float, w_cost: float, w_layovers: float) -> float:
    return (
        w_duration * float(attrs.get("duration", 0.0)) +
        w_cost     * (float(attrs.get("cost", 0.0)) / 100.0) +
        w_layovers * LAYOVER_PENALTY_PER_HOP_HOURS
    )

def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    (lat1, lon1), (lat2, lon2) = a, b
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 2 * EARTH_R_KM * math.asin(math.sqrt(h))

def heuristic_duration_only(node: str, goal: str, w_duration: float) -> float:
    """Admissible heuristic: only duration component (cost/layovers are >= 0)."""
    a = CITY_COORDS.get(node)
    b = CITY_COORDS.get(goal)
    if not (a and b):
        return 0.0
    km = haversine_km(a, b)
    hours = km / CRUISE_SPEED_KMPH
    return w_duration * hours

# -----------------------------
# Routing
# -----------------------------
def compute_best_route_on_graph(G: nx.DiGraph, src: str, dst: str,
                                w_duration: float, w_cost: float, w_layovers: float,
                                method: str = "dijkstra"):
    if src not in G or dst not in G:
        return None

    # Build weighted projection
    H = nx.DiGraph()
    for u, v, attrs in G.edges(data=True):
        w = edge_weight(u, v, attrs, w_duration, w_cost, w_layovers)
        new_attrs = dict(attrs)
        new_attrs["weight"] = float(w)
        H.add_edge(u, v, **new_attrs)

    try:
        if method == "a_star":
            h = lambda n: heuristic_duration_only(n, dst, w_duration)
            path = nx.astar_path(H, source=src, target=dst, heuristic=h, weight="weight")
        else:
            path = nx.shortest_path(H, source=src, target=dst, weight="weight", method="dijkstra")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None

    # Collect details
    edges = []
    total_duration = 0.0
    total_cost = 0.0
    total_layovers = max(0, len(path) - 2)

    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        attrs = H[u][v]
        edges.append({
            "from": u,
            "to": v,
            "airline": attrs.get("airline"),
            "duration": attrs.get("duration"),
            "cost": attrs.get("cost"),
        })
        total_duration += float(attrs.get("duration", 0.0))
        total_cost     += float(attrs.get("cost", 0.0))

    score = sum(H[path[i]][path[i+1]]["weight"] for i in range(len(path) - 1))
    return {
        "path": path,
        "edges": edges,
        "totals": {
            "duration_hours": round(total_duration, 2),
            "cost_usd": round(total_cost, 2),
            "layovers": total_layovers,
            "score": round(float(score), 3),
            "method": method
        },
    }

# Convenience wrapper using the global in-memory graph
def compute_best_route(src: str, dst: str,
                       w_duration: float, w_cost: float, w_layovers: float,
                       method: str = "dijkstra"):
    return compute_best_route_on_graph(GRAPH, src, dst, w_duration, w_cost, w_layovers, method)

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
    method = request.args.get("method", "dijkstra").lower()
    source = request.args.get("source", "python").lower()  # python | metta

    if method not in ("dijkstra", "a_star", "astar", "a*"):
        method = "dijkstra"
    if method in ("a_star", "astar", "a*"):
        method = "a_star"

    if not src or not dst:
        return jsonify({"error": "Missing required params: from, to"}), 400
    try:
        w_duration = float(request.args.get("w_duration", "1.0"))
        w_cost     = float(request.args.get("w_cost", "0.0"))
        w_layovers = float(request.args.get("w_layovers", "0.0"))
    except Exception:
        return jsonify({"error": "Weights must be numeric"}), 400

    if source == "metta":
        if not (HAVE_HYPERON and METTA_INSTANCE):
            return jsonify({"error": "MeTTa/Hyperon not available"}), 400
        metta_edges = edges_from_metta_now()
        Gtmp = graph_from_edges(metta_edges)
        res = compute_best_route_on_graph(Gtmp, src, dst, w_duration, w_cost, w_layovers, method=method)
    else:
        res = compute_best_route(src, dst, w_duration, w_cost, w_layovers, method=method)

    if not res:
        return jsonify({"error": f"No route from {src} to {dst} (source={source})"}), 404
    return jsonify(res)

def add_fact_to_graph_and_metta(start: str, end: str, airline: str,
                                duration: float, cost: float, layovers: int = 0):
    # Update Python graph
    add_edge_to_graph(FlightEdge(start, end, airline, duration, cost, layovers))
    # Mirror into MeTTa (in-memory) if available
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

# (Optional) tiny MeTTa debug endpoint
@app.get("/api/metta/direct")
def api_metta_direct():
    if not (HAVE_HYPERON and METTA_INSTANCE):
        return jsonify({"error": "MeTTa/Hyperon not available"}), 400
    start = request.args.get("from")
    end = request.args.get("to")
    if not start or not end:
        return jsonify({"error": "Missing required params: from, to"}), 400
    q = f'!(match &self (flight-route "{start}" "{end}" $air (duration $d) (cost $c) (layovers $l)) ($air $d $c $l))'
    try:
        res = [str(x) for x in METTA_INSTANCE.run(q)]
    except Exception as e:
        return jsonify({"error": f"MeTTa query failed: {e}"}), 500
    return jsonify({"from": start, "to": end, "candidates": res})

# -----------------------------
# Frontend (same origin)
# -----------------------------
@app.route("/")
def index():
    return app.send_static_file("index.html")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5500, debug=True)
