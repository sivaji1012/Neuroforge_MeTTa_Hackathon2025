import math
import os
import re
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from flask import Flask, request, jsonify
import networkx as nx

# ---------- Optional MeTTa/Hyperon integration ----------
HAVE_HYPERON = False
METTA = None
try:
    from hyperon import MeTTa  # type: ignore
    METTA = MeTTa()
    HAVE_HYPERON = True
except Exception:
    HAVE_HYPERON = False
    METTA = None

# ---------- Flask (serving frontend too) ----------
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")

# ---------- Data types ----------
@dataclass
class FlightEdge:
    src: str
    dst: str
    airline: str
    duration: float
    cost: float
    layovers: int

# Built-in dataset (kept for demo & as fallback if MeTTa not loaded)
BUILTIN_EDGES: List[FlightEdge] = [
    FlightEdge("Toronto",   "NewYork",   "AirCanada", 1.5, 220, 0),
    FlightEdge("Toronto",   "London",    "AirCanada", 7.2, 520, 0),
    FlightEdge("Toronto",   "Frankfurt", "Lufthansa", 7.5, 540, 0),
    FlightEdge("NewYork",   "London",    "Delta",     6.8, 480, 0),
    FlightEdge("NewYork",   "Paris",     "Delta",     7.1, 510, 0),
    FlightEdge("London",    "Paris",     "BA",        1.1, 120, 0),
    FlightEdge("London",    "Frankfurt", "Lufthansa", 1.4, 140, 0),
    FlightEdge("London",    "NewYork",   "Delta",     7.0, 500, 0),
    FlightEdge("London",    "Toronto",   "AirCanada", 7.2, 520, 0),
    FlightEdge("Frankfurt", "Paris",     "Lufthansa", 1.2, 130, 0),
    FlightEdge("Frankfurt", "Rome",      "Lufthansa", 2.0, 150, 0),
    FlightEdge("Frankfurt", "Toronto",   "Lufthansa", 7.6, 540, 0),
    FlightEdge("Frankfurt", "London",    "Lufthansa", 1.4, 140, 0),
    FlightEdge("Paris",     "Rome",      "AirFrance", 2.0, 160, 0),
    FlightEdge("Paris",     "NewYork",   "Delta",     7.3, 520, 0),
    FlightEdge("Paris",     "London",    "BA",        1.1, 120, 0),
    FlightEdge("Paris",     "Frankfurt", "Lufthansa", 1.2, 130, 0),
    FlightEdge("Rome",      "Frankfurt", "Lufthansa", 2.0, 150, 0),
    FlightEdge("Rome",      "Paris",     "AirFrance", 2.0, 160, 0),
]

GRAPH = nx.DiGraph()

# Minimal coordinates for A* duration-only heuristic
CITY_COORDS: Dict[str, Tuple[float, float]] = {
    "Toronto":   (43.65107, -79.347015),
    "NewYork":   (40.712776, -74.005974),
    "London":    (51.507351, -0.127758),
    "Paris":     (48.856613,  2.352222),
    "Frankfurt": (50.110924,  8.682127),
    "Rome":      (41.902782, 12.496366),
}
CRUISE_SPEED_KMPH = 800.0
EARTH_R_KM = 6371.0088

# ---------- Helpers ----------
def add_edge_to_graph(e: FlightEdge) -> None:
    GRAPH.add_edge(
        e.src, e.dst,
        airline=e.airline,
        duration=float(e.duration),
        cost=float(e.cost),
        layovers=int(e.layovers),
    )

def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    (lat1, lon1), (lat2, lon2) = a, b
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 2 * EARTH_R_KM * math.asin(math.sqrt(h))

def heuristic_duration_only(node: str, goal: str, w_duration: float) -> float:
    a = CITY_COORDS.get(node)
    b = CITY_COORDS.get(goal)
    if not (a and b):
        return 0.0
    return w_duration * (haversine_km(a, b) / CRUISE_SPEED_KMPH)

LAYOVER_PENALTY_PER_HOP_HOURS = 1.5

def edge_weight(attrs: Dict[str, Any], w_d: float, w_c: float, w_l: float) -> float:
    return (
        w_d * float(attrs.get("duration", 0.0)) +
        w_c * (float(attrs.get("cost", 0.0)) / 100.0) +
        w_l * LAYOVER_PENALTY_PER_HOP_HOURS
    )

def make_weighted_graph(w_d: float, w_c: float, w_l: float) -> nx.DiGraph:
    H = nx.DiGraph()
    for u, v, attrs in GRAPH.edges(data=True):
        wt = edge_weight(attrs, w_d, w_c, w_l)
        data = dict(attrs)
        data["weight"] = float(wt)
        H.add_edge(u, v, **data)
    return H

def compute_single_leg(src: str, dst: str, method: str,
                       w_d: float, w_c: float, w_l: float,
                       max_layovers: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Compute a single leg using Dijkstra or A* (for 'metta' we currently reuse these)."""
    if src not in GRAPH or dst not in GRAPH:
        return None

    H = make_weighted_graph(w_d, w_c, w_l)

    try:
        if method == "a_star":
            h = lambda n: heuristic_duration_only(n, dst, w_d)
            path = nx.astar_path(H, source=src, target=dst, heuristic=h, weight="weight")
        else:
            path = nx.shortest_path(H, source=src, target=dst, weight="weight", method="dijkstra")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None

    if max_layovers is not None:
        # layovers = edges-1 = (len(path)-2)
        if max(0, len(path)-2) > max_layovers:
            return None

    edges = []
    tot_d, tot_c = 0.0, 0.0
    for i in range(len(path)-1):
        u, v = path[i], path[i+1]
        attrs = H[u][v]
        edges.append({
            "from": u, "to": v,
            "airline": attrs.get("airline"),
            "duration": float(attrs.get("duration", 0.0)),
            "cost": float(attrs.get("cost", 0.0)),
        })
        tot_d += float(attrs.get("duration", 0.0))
        tot_c += float(attrs.get("cost", 0.0))

    score = sum(H[path[i]][path[i+1]]["weight"] for i in range(len(path)-1))
    return {
        "path": path,
        "edges": edges,
        "totals": {
            "duration_hours": round(tot_d, 2),
            "cost_usd": round(tot_c, 2),
            "layovers": max(0, len(path)-2),
            "score": round(float(score), 3),
        },
    }

def aggregate_itinerary(legs: List[Dict[str, Any]], tag: str) -> Dict[str, Any]:
    """Stitch multiple legs into one result."""
    agg = {
        "method": tag,
        "path": [],
        "edges": [],
        "totals": {"duration_hours": 0.0, "cost_usd": 0.0, "layovers": 0, "score": 0.0},
    }
    for i, leg in enumerate(legs):
        agg["edges"].extend(leg["edges"])
        agg["totals"]["duration_hours"] += leg["totals"]["duration_hours"]
        agg["totals"]["cost_usd"] += leg["totals"]["cost_usd"]
        agg["totals"]["layovers"] += leg["totals"]["layovers"]
        agg["totals"]["score"] += leg["totals"]["score"]
        if i == 0:
            agg["path"] = leg["path"][:]
        else:
            # avoid duplicating the connecting node
            agg["path"].extend(leg["path"][1:])
    agg["totals"]["duration_hours"] = round(agg["totals"]["duration_hours"], 2)
    agg["totals"]["cost_usd"] = round(agg["totals"]["cost_usd"], 2)
    agg["totals"]["score"] = round(agg["totals"]["score"], 3)
    return agg

# ---------- MeTTa file loading ----------
_AIRPORT_RE = re.compile(
    r'\(flight-route\s+"([^"]+)"\s+"([^"]+)"\s+"([^"]+)"\s+\(duration\s+([0-9.]+)\)\s+\(cost\s+([0-9.]+)\)\s+\(layovers\s+([0-9]+)\)\)'
)

def _metta_dir() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "metta"))

def _load_metta_files_into(instance, metta_dir: str) -> None:
    for fname in ("flight_routes.metta", "algorithms.metta"):
        fpath = os.path.join(metta_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as fh:
                instance.run(fh.read())

def boot() -> None:
    GRAPH.clear()

    # Prefer MeTTa files for data; if Hyperon fails, parse text directly.
    metta_dir = _metta_dir()
    fr = os.path.join(metta_dir, "flight_routes.metta")
    alg = os.path.join(metta_dir, "algorithms.metta")
    print(f"[boot] will-load file='{fr}' exists={os.path.exists(fr)} size={os.path.getsize(fr) if os.path.exists(fr) else 0}")
    print(f"[boot] will-load file='{alg}' exists={os.path.exists(alg)} size={os.path.getsize(alg) if os.path.exists(alg) else 0}")

    parsed_edges = 0
    if HAVE_HYPERON and METTA:
        try:
            _load_metta_files_into(METTA, metta_dir)
            # Query facts
            rows = METTA.run('!(match &self (flight-route $f $t $a (duration $d) (cost $c) (layovers $l)) ($f $t $a $d $c $l))')
            # If it yielded, parse rows; else fall back to regex parse below.
            for r in rows:
                s = str(r).strip()
                if s.startswith("(") and s.endswith(")"):
                    s = s[1:-1]
                parts = re.findall(r'"[^"]+"|[^\s]+', s)
                if len(parts) != 6:
                    continue
                def uq(x): return x[1:-1] if x.startswith('"') and x.endswith('"') else x
                e = FlightEdge(
                    uq(parts[0]), uq(parts[1]), uq(parts[2]),
                    float(uq(parts[3])), float(uq(parts[4])), int(uq(parts[5]))
                )
                add_edge_to_graph(e)
                parsed_edges += 1
        except Exception:
            parsed_edges = 0

    if parsed_edges == 0:
        # Regex fallback on the flights file
        if os.path.exists(fr):
            with open(fr, "r", encoding="utf-8") as fh:
                txt = fh.read()
            for m in _AIRPORT_RE.finditer(txt):
                src, dst, airline, d, c, l = m.groups()
                add_edge_to_graph(FlightEdge(src, dst, airline, float(d), float(c), int(l)))
                parsed_edges += 1

    if parsed_edges == 0:
        # Last resort: built-in list
        for e in BUILTIN_EDGES:
            add_edge_to_graph(e)
        parsed_edges = len(BUILTIN_EDGES)

    print(f"[boot] source=metta-file file_exists={os.path.exists(fr)} parsed={parsed_edges} nodes={GRAPH.number_of_nodes()} edges={GRAPH.number_of_edges()}")

boot()

# ---------- API ----------
@app.get("/api/health")
def api_health():
    return jsonify({
        "hyperon": bool(HAVE_HYPERON and METTA),
        "nodes": GRAPH.number_of_nodes(),
        "edges": GRAPH.number_of_edges(),
        "metta_facts": GRAPH.number_of_edges(),  # simple proxy
    })

@app.get("/api/routes")
def api_routes():
    routes = []
    for u, v, attrs in GRAPH.edges(data=True):
        routes.append({
            "from": u, "to": v,
            "airline": attrs.get("airline"),
            "duration": float(attrs.get("duration", 0.0)),
            "cost": float(attrs.get("cost", 0.0)),
            "layovers": int(attrs.get("layovers", 0)),
        })
    return jsonify({"routes": routes, "nodes": list(GRAPH.nodes)})

@app.get("/api/route")
def api_route():
    src = (request.args.get("from") or "").strip()
    dst = (request.args.get("to") or "").strip()
    method = (request.args.get("method") or "dijkstra").lower()
    if method in ("a*", "astar"): method = "a_star"
    if method not in ("dijkstra", "a_star", "metta"):
        method = "dijkstra"

    trip = (request.args.get("trip") or "oneway").lower()
    stops_raw = (request.args.get("stops") or "").strip()
    try:
        w_d = float(request.args.get("w_duration", "1.0"))
        w_c = float(request.args.get("w_cost", "0.0"))
        w_l = float(request.args.get("w_layovers", "0.0"))
        max_layovers = request.args.get("max_layovers")
        max_layovers = int(max_layovers) if max_layovers not in (None, "",) else None
    except Exception:
        return jsonify({"error": "Invalid weight/constraint values"}), 400

    if trip == "oneway":
        if not src or not dst:
            return jsonify({"error": "Missing from/to"}), 400
        leg = compute_single_leg(src, dst, method if method != "metta" else "dijkstra", w_d, w_c, w_l, max_layovers)
        if not leg:
            return jsonify({"error": f"No operating route in one direction."}), 404
        res = aggregate_itinerary([leg], tag=method.upper())
        return jsonify(res)

    elif trip == "return":
        if not src or not dst:
            return jsonify({"error": "Missing from/to"}), 400
        fwd = compute_single_leg(src, dst, method if method != "metta" else "dijkstra", w_d, w_c, w_l, max_layovers)
        back = compute_single_leg(dst, src, method if method != "metta" else "dijkstra", w_d, w_c, w_l, max_layovers)
        if not fwd or not back:
            return jsonify({"error": "No operating route in one direction."}), 404
        res = aggregate_itinerary([fwd, back], tag=f"{method.lower()} (return)".upper())
        return jsonify(res)

    elif trip == "multicity":
        # Build legs: src -> s1 -> s2 -> ... -> dst
        if not src or not dst:
            return jsonify({"error": "Missing from/to"}), 400
        stops = [s.strip() for s in stops_raw.split(",") if s.strip()]
        sequence = [src] + stops + [dst]
        legs = []
        for a, b in zip(sequence, sequence[1:]):
            leg = compute_single_leg(a, b, method if method != "metta" else "dijkstra", w_d, w_c, w_l, max_layovers)
            if not leg:
                return jsonify({"error": f"No operating route for segment {a} → {b}."}), 404
            legs.append(leg)
        res = aggregate_itinerary(legs, tag=f"{method.lower()} (multi)".upper())
        return jsonify(res)

    return jsonify({"error": "Unknown trip type"}), 400

# ---------- Frontend ----------
@app.route("/")
def index():
    return app.send_static_file("index.html")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5500, debug=True)
