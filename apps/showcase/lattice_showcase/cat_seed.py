"""Sample data for the catastrophe response story: an exposure snapshot of about 40,000
insured locations in real metro areas, the people who respond, and four events with their
footprints, exposure runs and claims. Fixed random seed: the same data every time.

None of this is real. Places, counties and coastlines are; policies, people and claims are
made up, with plausible shapes (claims spike after an event and tail off).
"""

from __future__ import annotations

import json
import math
import random
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import geoengine
from lattice.api import Db, notifications, sql_queries, urn

SQL = sql_queries(Path(__file__).parent / "sql").catseed
STATIC_MAPS = Path(__file__).parents[3] / "lattice" / "static" / "maps"
SNAPSHOT = date(2026, 10, 19)
# The story's present: Delta two days after landfall. Never ahead of the real clock, or
# claims would be reported in the future.
NOW = min(datetime(2026, 10, 20, 9, 0), datetime.now(UTC).replace(tzinfo=None))

STATES = {"48": "TX", "22": "LA", "12": "FL", "06": "CA", "28": "MS", "01": "AL"}

# (city, lon, lat, spread lon, spread lat, locations)
METROS = [
    ("Houston", -95.37, 29.76, 0.33, 0.24, 8200), ("Galveston", -94.90, 29.30, 0.10, 0.06, 900),
    ("Beaumont", -94.13, 30.08, 0.12, 0.08, 900), ("Dallas", -96.80, 32.78, 0.25, 0.18, 5200),
    ("Fort Worth", -97.33, 32.75, 0.20, 0.15, 3000), ("Austin", -97.74, 30.27, 0.18, 0.14, 2600),
    ("San Antonio", -98.49, 29.42, 0.20, 0.15, 2600), ("Corpus Christi", -97.40, 27.78, 0.12, 0.08, 900),
    ("New Orleans", -90.07, 29.95, 0.18, 0.10, 3200), ("Baton Rouge", -91.15, 30.45, 0.14, 0.10, 1400),
    ("Lafayette", -92.02, 30.22, 0.12, 0.10, 1000), ("Lake Charles", -93.22, 30.23, 0.12, 0.08, 900),
    ("Tampa", -82.46, 27.95, 0.18, 0.20, 2600), ("Miami", -80.25, 25.85, 0.10, 0.22, 2600),
    ("Pensacola", -87.21, 30.42, 0.14, 0.07, 700), ("Sacramento", -121.49, 38.58, 0.18, 0.14, 1400),
    ("Santa Rosa", -122.71, 38.44, 0.12, 0.10, 900), ("Napa", -122.29, 38.30, 0.08, 0.08, 600),
    ("Oakland", -122.20, 37.75, 0.15, 0.15, 1400),
]
FIRST = ["James", "Maria", "Robert", "Linda", "Michael", "Patricia", "David", "Jennifer",
         "Carlos", "Thanh", "Aisha", "Daniel", "Sofia", "Kevin", "Grace", "Luis", "Priya",
         "Marcus", "Hannah", "Omar", "Elena", "Tyler", "Mei", "Andre"]
LAST = ["Garcia", "Johnson", "Nguyen", "Smith", "Martinez", "Brown", "Lee", "Davis", "Patel",
        "Robinson", "Hernandez", "Walker", "Kim", "Thompson", "Lopez", "Wilson", "Clark",
        "Ramirez", "Allen", "Young", "Le", "Mitchell", "Turner", "Adams"]
BUSINESS = ["Bayou {} Grill", "{} Logistics", "{} Medical Plaza", "{} Hardware", "Gulf {} Storage",
            "{} Family Dental", "{} Auto Body", "Lone Star {} Supply", "{} Office Park",
            "{} Inn & Suites", "{} Tire & Battery", "Coastal {} Marine"]
TIERS = (["rooftop"] * 70 + ["parcel"] * 15 + ["street"] * 8 + ["zip"] * 6 + ["county"] * 1)


def weighted(rng: random.Random, options: dict) -> str:
    return rng.choices(list(options), list(options.values()))[0]


def _location(rng: random.Random, n: int, city: str) -> dict:
    line = weighted(rng, {"homeowners": 70, "commercial_property": 20, "auto": 10})
    if line == "homeowners":
        occupancy = weighted(rng, {"single_family": 82, "condo": 12, "mobile_home": 6})
        construction = ("manufactured" if occupancy == "mobile_home"
                        else weighted(rng, {"frame": 60, "masonry": 38, "steel": 2}))
        tiv = round(rng.lognormvariate(12.75, 0.45), -3)
        deductible = max(1000, round(tiv * rng.choice([0.01, 0.02]), -2))
        insured = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
    elif line == "commercial_property":
        occupancy = weighted(rng, {"retail": 30, "office": 25, "warehouse": 20,
                                    "restaurant": 15, "hotel": 10})
        construction = weighted(rng, {"masonry": 45, "steel": 40, "frame": 15})
        tiv = round(rng.lognormvariate(14.6, 0.8), -3)
        deductible = rng.choice([10000, 25000, 50000, 100000])
        insured = rng.choice(BUSINESS).format(rng.choice(LAST))
    else:
        occupancy, construction = "personal_auto", "vehicle"
        tiv = round(rng.uniform(12000, 68000), -2)
        deductible = rng.choice([500, 1000])
        insured = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
    return {"ref": f"LOC-{n:06d}", "policy_number": f"{line[:2].upper()}-{rng.randint(1000000, 9999999)}",
            "insured": insured, "line": line, "occupancy": occupancy, "construction": construction,
            "year_built": rng.randint(1955, 2024), "tiv": tiv, "deductible": deductible,
            "city": city, "snapshot_on": SNAPSHOT}


def seed_locations(db: Db, rng: random.Random) -> dict:
    """Points in each metro, kept only where they fall in a county (not in the Gulf)."""
    counties = geoengine.to_geojson(json.loads((STATIC_MAPS / "counties-10m.json").read_text()),
                                    "counties")
    names = {f["id"]: f["properties"]["name"] for f in counties["features"]}
    keep = {"type": "FeatureCollection",
            "features": [f for f in counties["features"] if f["id"][:2] in STATES]}
    layer = geoengine.create_layer(db.conn, "us-counties", "areas", "US counties")
    geoengine.put_geojson(db.conn, layer, keep)

    points, attributes, n = [], {}, 0
    for city, lon, lat, slon, slat, count in METROS:
        for _ in range(int(count * 1.12)):                 # extra, for points that land in water
            n += 1
            tier = rng.choice(TIERS)
            plon, plat = rng.gauss(lon, slon), rng.gauss(lat, slat)
            if tier in ("zip", "county"):                  # a centroid, not the house
                step = 0.05 if tier == "zip" else 0.3
                plon, plat = round(plon / step) * step, round(plat / step) * step
            ref = f"LOC-{n:06d}"
            points.append({"id": ref, "lon": plon, "lat": plat, "quality": tier})
            attributes[ref] = _location(rng, n, city)
    places = geoengine.create_layer(db.conn, "locations", "points", "Insured locations")
    geoengine.put_points(db.conn, places, points)
    county_of = {r["point_id"]: r["area_id"] for r in db.all(SQL.location_counties)}
    kept = [p for p in points if p["id"] in county_of]
    geoengine.clear_layer(db.conn, places)
    geoengine.put_points(db.conn, places, kept)
    db.run_many(SQL.add_location, [
        {**attributes[p["id"]], "state": STATES[county_of[p["id"]][:2]],
         "county_fips": county_of[p["id"]], "county": names.get(county_of[p["id"]], "")}
        for p in kept])
    return counties


STAFF = [
    ("Rosa Delgado", "lead", "Gulf Coast CAT", "Houston"), ("Marcus Bell", "lead", "Gulf Coast CAT", "Lake Charles"),
    ("Hannah Cho", "lead", "Texas Field", "Dallas"), ("Daniel Ortiz", "lead", "California Field", "Sacramento"),
    ("Grace Whitfield", "lead", "Desk Adjusting", "Austin"),
] + [(f"{first} {last}", role, team, home) for (first, last, role, team, home) in [
    ("Tom", "Reyes", "surveyor", "Gulf Coast CAT", "Houston"), ("Ana", "Pham", "surveyor", "Gulf Coast CAT", "Galveston"),
    ("Luis", "Navarro", "surveyor", "Gulf Coast CAT", "Beaumont"), ("Kim", "Haddad", "surveyor", "Gulf Coast CAT", "Lake Charles"),
    ("Ray", "Fontenot", "surveyor", "Gulf Coast CAT", "Lafayette"), ("Jo", "Boudreaux", "surveyor", "Gulf Coast CAT", "Baton Rouge"),
    ("Sam", "Okafor", "surveyor", "Texas Field", "Dallas"), ("Mia", "Larsen", "surveyor", "Texas Field", "Fort Worth"),
    ("Eli", "Grant", "surveyor", "Texas Field", "Austin"), ("Zoe", "Marsh", "surveyor", "California Field", "Santa Rosa"),
    ("Ian", "Ruiz", "surveyor", "California Field", "Napa"),
    ("Dee", "Landry", "surveyor", "Gulf Coast CAT", "Beaumont"), ("Nate", "Guidry", "surveyor", "Gulf Coast CAT", "Lake Charles"), ("Ava", "Brooks", "adjuster", "Desk Adjusting", "Austin"),
    ("Noah", "Singh", "adjuster", "Desk Adjusting", "Austin"), ("Lena", "Ford", "adjuster", "Desk Adjusting", "Houston"),
    ("Owen", "Price", "adjuster", "Desk Adjusting", "Dallas"), ("Ruth", "Kaplan", "adjuster", "Desk Adjusting", "Tampa"),
    ("Femi", "Adeyemi", "adjuster", "Desk Adjusting", "New Orleans"), ("Jade", "Moreau", "adjuster", "Desk Adjusting", "Sacramento"),
    ("Paul", "Varga", "adjuster", "Gulf Coast CAT", "Houston"), ("Nina", "Castillo", "adjuster", "Gulf Coast CAT", "Lake Charles"),
]]


def _ring(cx: float, cy: float, rx: float, ry: float, rng: random.Random, wobble: float,
          points: int = 48) -> list:
    """A closed, irregular loop around a centre: a fire perimeter."""
    ring = []
    for i in range(points):
        a = 2 * math.pi * i / points
        r = 1 + rng.uniform(-wobble, wobble)
        ring.append([cx + rx * r * math.cos(a), cy + ry * r * math.sin(a)])
    return ring + ring[:1]


def _cone(track: list[tuple[float, float]], start: float, grow: float) -> list:
    """A forecast cone: the track widened by an uncertainty that grows with time."""
    left, right = [], []
    for i, (lon, lat) in enumerate(track):
        nxt = track[min(i + 1, len(track) - 1)]
        prev = track[max(i - 1, 0)]
        dx, dy = nxt[0] - prev[0], nxt[1] - prev[1]
        norm = math.hypot(dx, dy) or 1
        w = start + grow * i
        left.append([lon - dy / norm * w, lat + dx / norm * w])
        right.append([lon + dy / norm * w, lat - dx / norm * w])
    ring = left + right[::-1]
    return ring + ring[:1]


def _area(polygon: list, name: str, **props) -> dict:
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": "area", "properties": {"name": name, **props},
         "geometry": {"type": "Polygon", "coordinates": [polygon]}}]}


def _counties(counties: dict, fips: set[str], name: str) -> dict:
    return {"type": "FeatureCollection", "features": [
        {**f, "properties": {"name": f"{f['properties']['name']} County", "group": name}}
        for f in counties["features"] if f["id"] in fips]}


SEVERITY_SHARE = {"minor": (0.01, 0.04), "moderate": (0.04, 0.12), "major": (0.12, 0.45),
                  "total": (0.6, 1.0)}
CHANNEL = {"phone": 40, "app": 30, "agent": 20, "web": 10}

EVENTS = [
    {"code": "CAT-2602", "name": "Winter Storm Uri II: Texas freeze", "peril": "freeze",
     "status": "closed", "pcs_code": "PCS 2602", "region": "Texas",
     "starts_on": date(2026, 2, 13), "landfall_on": date(2026, 2, 14), "closed_on": date(2026, 6, 30),
     "details": {"min_temp_f": 6, "hours_below_freezing": 76, "power_outages": "widespread"},
     "claims": 2400, "mean_days": 9, "causes": {"frozen_pipes": 70, "roof_collapse": 5, "power_surge": 25},
     "severity": {"minor": 45, "moderate": 40, "major": 14, "total": 1}},
    {"code": "CAT-2604", "name": "Hailstorm: Dallas–Fort Worth", "peril": "hail",
     "status": "closed", "pcs_code": "PCS 2617", "region": "North Texas",
     "starts_on": date(2026, 4, 14), "landfall_on": date(2026, 4, 14), "closed_on": date(2026, 7, 31),
     "details": {"hail_size_in": 2.75, "max_wind_mph": 70},
     "claims": 1800, "mean_days": 6, "causes": {"hail": 92, "wind": 8},
     "severity": {"minor": 40, "moderate": 42, "major": 16, "total": 2}},
    {"code": "CAT-2608", "name": "Glass Fire: Napa & Sonoma", "peril": "wildfire",
     "status": "recovery", "pcs_code": "PCS 2633", "region": "Northern California",
     "starts_on": date(2026, 8, 21), "landfall_on": date(2026, 8, 21), "closed_on": None,
     "details": {"acres_burned": 61000, "containment_pct": 100, "structures_destroyed": 1555},
     "claims": 170, "mean_days": 12, "causes": {"fire": 55, "smoke": 40, "evacuation": 5},
     "severity": {"minor": 30, "moderate": 25, "major": 20, "total": 25}},
    {"code": "CAT-2610", "name": "Hurricane Delta", "peril": "hurricane",
     "status": "response", "pcs_code": "PCS 2641", "region": "Gulf Coast",
     "starts_on": date(2026, 10, 14), "landfall_on": date(2026, 10, 18), "closed_on": None,
     "details": {"category": 3, "max_wind_mph": 120, "pressure_mb": 958,
                 "landfall": "Near Cameron, Louisiana", "storm_surge_ft": 11},
     "claims": 950, "mean_days": 1.2, "causes": {"wind": 50, "storm_surge": 15, "flood": 20, "tree_fall": 15},
     "severity": {"minor": 35, "moderate": 35, "major": 22, "total": 8}},
]

# Hurricane Delta's track from the Gulf, then three advisories as the forecast moved east.
DELTA_TRACKS = [
    ("Advisory 8, 15 Oct", datetime(2026, 10, 15, 4), [(-91.0, 24.0), (-93.0, 25.6), (-95.0, 27.2), (-96.6, 28.6), (-97.4, 30.0), (-97.6, 31.6)], 0.25, 0.32),
    ("Advisory 12, 16 Oct", datetime(2026, 10, 16, 4), [(-91.5, 25.2), (-93.2, 26.6), (-94.6, 28.0), (-95.2, 29.4), (-95.4, 30.8), (-95.3, 32.2)], 0.22, 0.25),
    ("Advisory 17, 17 Oct", datetime(2026, 10, 17, 10), [(-91.8, 26.0), (-92.8, 27.4), (-93.4, 28.8), (-93.5, 29.8), (-93.2, 31.0), (-92.6, 32.2)], 0.2, 0.18),
]
# Each event's zones: the counties in it, its lead, and the surveyors working it.
ZONES = {
    "CAT-2610": [("Galveston & Houston", {"48167", "48201", "48039", "48157", "48071"}, "Rosa Delgado", ["Tom Reyes", "Ana Pham"]),
                 ("Beaumont–Port Arthur", {"48245", "48361", "48199", "48351"}, "Rosa Delgado", ["Luis Navarro", "Dee Landry"]),
                 ("Lake Charles", {"22019", "22023", "22053", "22011"}, "Marcus Bell", ["Kim Haddad", "Nate Guidry"]),
                 ("Lafayette & Acadiana", {"22055", "22113", "22045", "22099", "22001", "22097"}, "Marcus Bell", ["Ray Fontenot", "Jo Boudreaux"])],
    "CAT-2604": [("Dallas", {"48113"}, "Hannah Cho", ["Sam Okafor"]), ("Fort Worth", {"48439"}, "Hannah Cho", ["Mia Larsen"]),
                 ("Collin & Denton", {"48085", "48121"}, "Hannah Cho", ["Eli Grant"])],
    "CAT-2602": [("Houston area", {"48201", "48157", "48339", "48039", "48167", "48071"}, "Rosa Delgado", ["Tom Reyes", "Ana Pham"]),
                 ("North Texas", {"48113", "48439", "48085", "48121"}, "Hannah Cho", ["Sam Okafor", "Mia Larsen"]),
                 ("Central Texas", {"48453", "48491", "48029", "48209", "48187"}, "Grace Whitfield", ["Eli Grant"])],
    "CAT-2608": [("Napa", {"06055"}, "Daniel Ortiz", ["Ian Ruiz"]), ("Sonoma", {"06097"}, "Daniel Ortiz", ["Zoe Marsh"])],
}


STEPS = {"assigned": 1, "inspected": 2, "settled": 3, "closed": 4}


def progress(rng: random.Random, reported: datetime, status: str) -> dict:
    """When a claim was assigned, inspected, settled and closed, as far as its status goes.
    Waits are drawn so some claims sit for days: the gaps are what the timelines show."""
    reached = STEPS.get(status, 0)
    out, at = {}, reported
    for i, (key, lo, hi) in enumerate((("assigned_at", 0.1, 3), ("inspected_at", 0.3, 6),
                                       ("settled_at", 3, 30), ("closed_at", 1, 12)), start=1):
        if i <= reached:
            step = at + timedelta(days=rng.uniform(lo, hi))
            # A step drawn past now happened somewhere between the last one and now.
            at = step if step < NOW else at + (NOW - at) * rng.uniform(0.05, 0.95)
        out[key] = at if i <= reached else None
    return out


def seed_events(db: Db, rng: random.Random, counties: dict) -> None:
    staff = {s[0]: db.value(SQL.add_staff, name=s[0], role=s[1], team=s[2], home=s[3])
             for s in STAFF}
    adjusters = [sid for (name, role, *_), sid in zip(STAFF, staff.values(), strict=True)
                 if role == "adjuster"]
    tx = {f["id"] for f in counties["features"] if f["id"].startswith("48")}
    claim_no = 0
    for spec in EVENTS:
        event_id = db.value(SQL.add_event, **{k: spec[k] for k in (
            "code", "name", "peril", "status", "pcs_code", "region", "starts_on", "landfall_on",
            "closed_on")}, details=spec["details"])
        versions: list[tuple[str, datetime, dict, str]] = []
        if spec["peril"] == "hail":
            versions.append(("Storm reports, 15 Apr", datetime(2026, 4, 15, 8),
                             _counties(counties, {"48113", "48439", "48085", "48121"}, "Hail swath"), "counties"))
        elif spec["peril"] == "freeze":
            versions.append(("Hard freeze warnings, 14 Feb", datetime(2026, 2, 14, 6),
                             _counties(counties, tx, "Hard freeze warning"), "counties"))
        elif spec["peril"] == "wildfire":
            fire_rng = random.Random(26)
            versions.append(("Perimeter, 23 Aug", datetime(2026, 8, 23, 7),
                             _area(_ring(-122.50, 38.52, 0.10, 0.07, fire_rng, 0.25), "Fire perimeter, 23 Aug"), "upload"))
            versions.append(("Perimeter, 28 Aug", datetime(2026, 8, 28, 7),
                             _area(_ring(-122.53, 38.50, 0.18, 0.12, fire_rng, 0.2), "Fire perimeter, 28 Aug"), "upload"))
        else:
            for label, at, track, start, grow in DELTA_TRACKS:
                versions.append((label, at, _area(_cone(track, start, grow), f"Forecast cone, {label}",
                                                  track=[list(p) for p in track]), "advisory"))
        run_id = None
        for version, (label, at, shapes, source) in enumerate(versions, start=1):
            key = f"{spec['code'].lower()}-v{version}"
            layer = geoengine.create_layer(db.conn, key, "areas", f"{spec['name']}: {label}")
            geoengine.put_geojson(db.conn, layer, shapes)
            footprint_id = db.value(SQL.add_footprint, event_id=event_id, version=version,
                                    label=label, source=source, layer=key, created_at=at)
            run_id = db.value(SQL.add_exposure_run, event_id=event_id, footprint_id=footprint_id,
                              layer=key, at=at + timedelta(minutes=12))
            db.run(SQL.total_exposure_run, run_id=run_id)

        zones = []
        for name, fips, lead, pool in ZONES[spec["code"]]:
            zone_id = db.value(SQL.add_zone, event_id=event_id, name=name, lead_id=staff[lead])
            zones.append((zone_id, fips, [staff[p] for p in pool]))
        exposed = db.all(SQL.exposed, run_id=run_id)
        if spec["code"] == "CAT-2610":          # hardest hit near landfall: weight by closeness
            exposed = [e for e in exposed if e["county_fips"][:2] in ("22", "48")]
        picked = rng.sample(exposed, min(spec["claims"], len(exposed)))
        landfall = datetime.combine(spec["landfall_on"], datetime.min.time())
        claims = []
        for loc in picked:
            claim_no += 1
            days = rng.expovariate(1 / spec["mean_days"])
            reported = landfall + timedelta(days=days, hours=rng.uniform(6, 20))
            if reported > NOW:
                reported = NOW - timedelta(minutes=rng.randint(5, 600))
            severity = weighted(rng, spec["severity"])
            lo, hi = SEVERITY_SHARE[severity]
            estimate = round(float(loc["tiv"]) * rng.uniform(lo, hi), -2)
            if spec["status"] == "closed":
                status = weighted(rng, {"closed": 92, "settled": 8})
            elif spec["status"] == "recovery":
                status = weighted(rng, {"closed": 55, "settled": 25, "inspected": 15, "assigned": 5})
            else:
                age = (NOW - reported).total_seconds() / 86400
                status = weighted(rng, {"new": 60, "assigned": 40} if age < 0.6 else
                                   {"new": 20, "assigned": 50, "inspected": 30})
            zone_id, _, pool = next((z for z in zones if loc["county_fips"] in z[1]),
                                    (None, None, zones[0][2]))
            paid = round(estimate * rng.uniform(0.8, 1.0), -2) if status in ("settled", "closed") else 0
            claims.append(dict(
                claim_number=f"CLM-{spec['starts_on']:%y}-{claim_no:06d}",
                event_id=event_id, location_id=loc["id"], loss_date=spec["landfall_on"],
                reported_at=reported, channel=weighted(rng, CHANNEL),
                cause=weighted(rng, spec["causes"]), severity=severity, status=status,
                priority=severity in ("major", "total") and rng.random() < 0.5,
                estimate=estimate, paid=paid, zone_id=zone_id,
                surveyor_id=rng.choice(pool) if status != "new" else None,
                adjuster_id=rng.choice(adjusters) if status in ("inspected", "settled", "closed") else None,
                updated_at=min(NOW, reported + timedelta(days=rng.uniform(0, 20))),
                **progress(rng, reported, status)))
        db.run_many(SQL.add_claim, claims)


def seed_estimates(db: Db) -> None:
    """Hurricane Delta's loss estimates at advisories 12 and 17, as they were run."""
    from lattice_showcase import losses
    for version in (2, 3):
        run = db.first(SQL.delta_estimate, version=version, simulations=1000,
                       assumptions=losses.ASSUMPTIONS)
        losses.estimate(db, {**run, "simulations": 1000})


def seed(db: Db) -> None:
    rng = random.Random(2610)
    counties = seed_locations(db, rng)
    seed_events(db, rng, counties)
    db.run(SQL.assign_handlers)
    for claim in db.all(SQL.handled):           # handlers follow their claims (ADR 0016)
        notifications.follow(db, claim["handler_id"], urn("showcase.claim", claim["id"]))
    seed_estimates(db)

