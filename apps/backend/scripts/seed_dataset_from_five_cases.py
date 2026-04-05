from __future__ import annotations

import argparse
import json
import random
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = ROOT / "apps" / "backend"

sys.path.append(str(BACKEND_ROOT))

from app.db.training_store import DatasetSampleModel, SessionLocal, init_training_db  # noqa: E402
from app.schemas.training import DatasetSampleIn  # noqa: E402
from app.services.nn import get_training_status, start_training, add_dataset_sample  # noqa: E402


def _base_cases() -> list[dict]:
    return [
        {
            "name": "case_cantilever_chain",
            "nodes": [
                {"id": "n1", "x": 0.0, "y": 0.0},
                {"id": "n2", "x": 100.0, "y": 0.0},
                {"id": "n3", "x": 200.0, "y": 0.0},
                {"id": "n4", "x": 300.0, "y": 0.0},
                {"id": "n5", "x": 400.0, "y": 0.0},
                {"id": "n6", "x": 500.0, "y": 0.0},
            ],
            "rods": [
                {"id": "r1", "startNodeId": "n1", "endNodeId": "n2", "area": 0.014, "elasticModulus": 2e11},
                {"id": "r2", "startNodeId": "n2", "endNodeId": "n3", "area": 0.014, "elasticModulus": 2e11},
                {"id": "r3", "startNodeId": "n3", "endNodeId": "n4", "area": 0.013, "elasticModulus": 2e11},
                {"id": "r4", "startNodeId": "n4", "endNodeId": "n5", "area": 0.012, "elasticModulus": 2e11},
                {"id": "r5", "startNodeId": "n5", "endNodeId": "n6", "area": 0.011, "elasticModulus": 2e11},
            ],
            "constraints": [{"nodeId": "n1", "uxFixed": True, "uyFixed": True}],
            "loads": [{"nodeId": "n6", "fx": 1100.0, "fy": -180.0}],
            "hot_rods": ["r4", "r5"],
            "defect_prob": 0.58,
        },
        {
            "name": "case_triangular_truss",
            "nodes": [
                {"id": "n1", "x": 0.0, "y": 0.0},
                {"id": "n2", "x": 120.0, "y": 0.0},
                {"id": "n3", "x": 240.0, "y": 0.0},
                {"id": "n4", "x": 60.0, "y": 90.0},
                {"id": "n5", "x": 180.0, "y": 90.0},
            ],
            "rods": [
                {"id": "r1", "startNodeId": "n1", "endNodeId": "n2", "area": 0.011, "elasticModulus": 2e11},
                {"id": "r2", "startNodeId": "n2", "endNodeId": "n3", "area": 0.011, "elasticModulus": 2e11},
                {"id": "r3", "startNodeId": "n1", "endNodeId": "n4", "area": 0.010, "elasticModulus": 2e11},
                {"id": "r4", "startNodeId": "n4", "endNodeId": "n2", "area": 0.010, "elasticModulus": 2e11},
                {"id": "r5", "startNodeId": "n2", "endNodeId": "n5", "area": 0.010, "elasticModulus": 2e11},
                {"id": "r6", "startNodeId": "n5", "endNodeId": "n3", "area": 0.010, "elasticModulus": 2e11},
                {"id": "r7", "startNodeId": "n4", "endNodeId": "n5", "area": 0.009, "elasticModulus": 2e11},
            ],
            "constraints": [
                {"nodeId": "n1", "uxFixed": True, "uyFixed": True},
                {"nodeId": "n3", "uxFixed": False, "uyFixed": True},
            ],
            "loads": [{"nodeId": "n2", "fx": 400.0, "fy": -950.0}],
            "hot_rods": ["r4", "r5", "r7"],
            "defect_prob": 0.52,
        },
        {
            "name": "case_portal_frame",
            "nodes": [
                {"id": "n1", "x": 0.0, "y": 0.0},
                {"id": "n2", "x": 180.0, "y": 0.0},
                {"id": "n3", "x": 0.0, "y": 140.0},
                {"id": "n4", "x": 180.0, "y": 140.0},
                {"id": "n5", "x": 90.0, "y": 200.0},
            ],
            "rods": [
                {"id": "r1", "startNodeId": "n1", "endNodeId": "n3", "area": 0.016, "elasticModulus": 2e11},
                {"id": "r2", "startNodeId": "n2", "endNodeId": "n4", "area": 0.016, "elasticModulus": 2e11},
                {"id": "r3", "startNodeId": "n3", "endNodeId": "n4", "area": 0.013, "elasticModulus": 2e11},
                {"id": "r4", "startNodeId": "n3", "endNodeId": "n5", "area": 0.012, "elasticModulus": 2e11},
                {"id": "r5", "startNodeId": "n4", "endNodeId": "n5", "area": 0.012, "elasticModulus": 2e11},
            ],
            "constraints": [
                {"nodeId": "n1", "uxFixed": True, "uyFixed": True},
                {"nodeId": "n2", "uxFixed": True, "uyFixed": True},
            ],
            "loads": [{"nodeId": "n5", "fx": 650.0, "fy": -820.0}],
            "hot_rods": ["r3", "r4", "r5"],
            "defect_prob": 0.56,
        },
        {
            "name": "case_warren_like",
            "nodes": [
                {"id": "n1", "x": 0.0, "y": 0.0},
                {"id": "n2", "x": 100.0, "y": 0.0},
                {"id": "n3", "x": 200.0, "y": 0.0},
                {"id": "n4", "x": 300.0, "y": 0.0},
                {"id": "n5", "x": 50.0, "y": 80.0},
                {"id": "n6", "x": 150.0, "y": 80.0},
                {"id": "n7", "x": 250.0, "y": 80.0},
            ],
            "rods": [
                {"id": "r1", "startNodeId": "n1", "endNodeId": "n2", "area": 0.010, "elasticModulus": 2e11},
                {"id": "r2", "startNodeId": "n2", "endNodeId": "n3", "area": 0.010, "elasticModulus": 2e11},
                {"id": "r3", "startNodeId": "n3", "endNodeId": "n4", "area": 0.010, "elasticModulus": 2e11},
                {"id": "r4", "startNodeId": "n1", "endNodeId": "n5", "area": 0.009, "elasticModulus": 2e11},
                {"id": "r5", "startNodeId": "n5", "endNodeId": "n2", "area": 0.009, "elasticModulus": 2e11},
                {"id": "r6", "startNodeId": "n2", "endNodeId": "n6", "area": 0.009, "elasticModulus": 2e11},
                {"id": "r7", "startNodeId": "n6", "endNodeId": "n3", "area": 0.009, "elasticModulus": 2e11},
                {"id": "r8", "startNodeId": "n3", "endNodeId": "n7", "area": 0.009, "elasticModulus": 2e11},
                {"id": "r9", "startNodeId": "n7", "endNodeId": "n4", "area": 0.009, "elasticModulus": 2e11},
            ],
            "constraints": [
                {"nodeId": "n1", "uxFixed": True, "uyFixed": True},
                {"nodeId": "n4", "uxFixed": False, "uyFixed": True},
            ],
            "loads": [{"nodeId": "n6", "fx": 250.0, "fy": -1000.0}],
            "hot_rods": ["r6", "r7", "r8"],
            "defect_prob": 0.49,
        },
        {
            "name": "case_asymmetric_braced",
            "nodes": [
                {"id": "n1", "x": 0.0, "y": 0.0},
                {"id": "n2", "x": 130.0, "y": 0.0},
                {"id": "n3", "x": 260.0, "y": 0.0},
                {"id": "n4", "x": 60.0, "y": 110.0},
                {"id": "n5", "x": 200.0, "y": 95.0},
                {"id": "n6", "x": 290.0, "y": 170.0},
            ],
            "rods": [
                {"id": "r1", "startNodeId": "n1", "endNodeId": "n2", "area": 0.013, "elasticModulus": 2e11},
                {"id": "r2", "startNodeId": "n2", "endNodeId": "n3", "area": 0.013, "elasticModulus": 2e11},
                {"id": "r3", "startNodeId": "n1", "endNodeId": "n4", "area": 0.010, "elasticModulus": 2e11},
                {"id": "r4", "startNodeId": "n2", "endNodeId": "n4", "area": 0.009, "elasticModulus": 2e11},
                {"id": "r5", "startNodeId": "n2", "endNodeId": "n5", "area": 0.010, "elasticModulus": 2e11},
                {"id": "r6", "startNodeId": "n3", "endNodeId": "n5", "area": 0.009, "elasticModulus": 2e11},
                {"id": "r7", "startNodeId": "n5", "endNodeId": "n6", "area": 0.008, "elasticModulus": 2e11},
            ],
            "constraints": [
                {"nodeId": "n1", "uxFixed": True, "uyFixed": True},
                {"nodeId": "n3", "uxFixed": True, "uyFixed": True},
            ],
            "loads": [{"nodeId": "n6", "fx": 900.0, "fy": -430.0}],
            "hot_rods": ["r5", "r6", "r7"],
            "defect_prob": 0.61,
        },
    ]


def _with_jitter(base: dict, rnd: random.Random) -> dict:
    case = deepcopy(base)
    for node in case["nodes"]:
        node["x"] = round(float(node["x"]) + rnd.uniform(-6.0, 6.0), 3)
        node["y"] = round(float(node["y"]) + rnd.uniform(-6.0, 6.0), 3)
    for rod in case["rods"]:
        rod["area"] = round(max(0.006, min(0.022, float(rod["area"]) * rnd.uniform(0.88, 1.12))), 6)
    for load in case["loads"]:
        load["fx"] = round(float(load["fx"]) * rnd.uniform(0.70, 1.40), 3)
        load["fy"] = round(float(load["fy"]) * rnd.uniform(0.70, 1.40), 3)
    return case


def _build_true_defect_rods(case: dict, rnd: random.Random) -> list[str]:
    if rnd.random() > float(case["defect_prob"]):
        return []
    rod_ids = [r["id"] for r in case["rods"]]
    hot = list(case["hot_rods"])
    count = rnd.randint(1, 3)
    picked: list[str] = []
    while len(picked) < count:
        candidate = rnd.choice(hot) if hot and rnd.random() < 0.72 else rnd.choice(rod_ids)
        if candidate not in picked:
            picked.append(candidate)
    return picked


def _build_observed_defects(case: dict, true_defect_rods: list[str], rnd: random.Random) -> list[dict]:
    observed: list[str] = []
    for rid in true_defect_rods:
        if rnd.random() < 0.65:
            observed.append(rid)

    rod_ids = [r["id"] for r in case["rods"]]
    if rod_ids and rnd.random() < 0.10:
        false_pick = rnd.choice(rod_ids)
        if false_pick not in observed:
            observed.append(false_pick)

    defects = []
    for i, rid in enumerate(observed, start=1):
        defects.append(
            {
                "id": f"d{i}",
                "rodId": rid,
                "defectType": rnd.choice(["crack", "corrosion", "fatigue"]),
                "params": {
                    "position": round(rnd.uniform(0.12, 0.88), 3),
                    "depth": round(rnd.uniform(0.35, 3.8), 3),
                },
            }
        )
    return defects


def _build_sensors(case: dict, true_defect_rods: list[str], rnd: random.Random) -> dict[str, dict[str, float]]:
    nodes = case["nodes"]
    max_x = max(abs(float(n["x"])) for n in nodes) or 1.0

    true_has_defect = bool(true_defect_rods)
    defect_intensity = 0.00045 if true_has_defect else 0.00025
    sensors: dict[str, dict[str, float]] = {}
    for n in nodes:
        nx = float(n["x"])
        ny = float(n["y"])
        baseline_dx = 0.0035 * (nx / max_x)
        baseline_dy = 0.0012 * (ny / max_x)
        dx = baseline_dx + rnd.uniform(-defect_intensity, defect_intensity)
        dy = baseline_dy + rnd.uniform(-defect_intensity, defect_intensity)

        if (not true_has_defect and rnd.random() < 0.22) or (true_has_defect and rnd.random() < 0.18):
            dx += rnd.uniform(-0.00035, 0.00035)
            dy += rnd.uniform(-0.00035, 0.00035)

        sensors[n["id"]] = {"dx": round(dx, 6), "dy": round(dy, 6)}
    return sensors


def generate_dataset(total: int, seed: int, reset: bool) -> dict:
    rnd = random.Random(seed)
    init_training_db()

    if reset:
        with SessionLocal() as session:
            session.query(DatasetSampleModel).delete()
            session.commit()

    bases = _base_cases()
    defect_samples = 0

    for idx in range(total):
        base = bases[idx % len(bases)]
        case = _with_jitter(base, rnd)

        true_defect_rods = _build_true_defect_rods(case, rnd)
        true_has_defect = bool(true_defect_rods)
        observed_defects = _build_observed_defects(case, true_defect_rods, rnd)
        sensors = _build_sensors(case, true_defect_rods, rnd)

        if true_has_defect:
            defect_samples += 1

        payload = {
            "request": {
                "scenario_id": f"{base['name']}-{idx // len(bases)}",
                "nodes": case["nodes"],
                "rods": case["rods"],
                "loads": case["loads"],
                "constraints": case["constraints"],
                "defects": observed_defects,
                "nodeSensors": sensors,
                "analysisType": "quasi_static",
            }
        }

        add_dataset_sample(
            DatasetSampleIn(
                name=f"{base['name']}-{idx:04d}",
                payload=payload,
                label="defect" if true_has_defect else "ok",
                note="generated from 5 manual cases with noisy supervision",
            )
        )

    return {
        "generated": total,
        "defect_samples": defect_samples,
        "ok_samples": total - defect_samples,
        "seed": seed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate training dataset from 5 manual seed-cases")
    parser.add_argument("--count", type=int, default=320, help="Total samples to generate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--reset", action="store_true", help="Clear dataset before generating")
    parser.add_argument("--train", action="store_true", help="Run training right after generation")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--lr", type=float, default=0.03)
    parser.add_argument("--family", type=str, default="sensor-driven")
    args = parser.parse_args()

    summary = generate_dataset(total=max(1, args.count), seed=args.seed, reset=args.reset)

    out = {"dataset": summary}
    if args.train:
        start = start_training(epochs=args.epochs, learning_rate=args.lr, model_family=args.family)
        out["train_start"] = start
        out["train_status"] = get_training_status()

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
