import argparse
import csv
import json
import pickle
import re
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import roc_curve, roc_auc_score, det_curve

from app.services.photo_conversion import extract_face_encoding
from app.services.recognition_service import (
    cosine_distance,
    INSIGHTFACE_COSINE_DISTANCE_AUTO_ALLOW,
    INSIGHTFACE_COSINE_DISTANCE_REVIEW,
)

FRONTAL_RE = re.compile(r"^(?P<sid>\d{3})_frontal\.(jpg|jpeg|png)$", re.IGNORECASE)
SURV_RE = re.compile(
    r"^(?P<sid>\d{3})_cam(?P<cam>[1-8])_(?P<dist>[1-3])\.(jpg|jpeg|png)$",
    re.IGNORECASE,
)
POSE_RE = re.compile(
    r"^(?P<sid>\d{3})_(?P<angle>L4|L3|L2|L1|F|R1|R2|R3|R4)\.(jpg|jpeg|png)$",
    re.IGNORECASE,
)


class EmbeddingCache:
    def __init__(self, cache_path: Path):
        self.cache_path = cache_path
        self.data = {}
        if self.cache_path.exists():
            try:
                with self.cache_path.open("rb") as f:
                    self.data = pickle.load(f)
            except Exception:
                self.data = {}

    def get(self, path: Path):
        key = str(path.resolve())
        stat = path.stat()
        meta = (stat.st_size, int(stat.st_mtime))
        item = self.data.get(key)
        if not item:
            return None
        if item.get("meta") != meta:
            return None
        emb = item.get("embedding")
        if emb is None:
            return None
        return np.asarray(emb, dtype=np.float32)

    def set(self, path: Path, emb: np.ndarray):
        key = str(path.resolve())
        stat = path.stat()
        meta = (stat.st_size, int(stat.st_mtime))
        self.data[key] = {
            "meta": meta,
            "embedding": emb.tolist(),
        }

    def save(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self.cache_path.open("wb") as f:
            pickle.dump(self.data, f)


def get_embedding(path: Path, cache: EmbeddingCache) -> np.ndarray | None:
    cached = cache.get(path)
    if cached is not None:
        return cached

    try:
        image_bytes = path.read_bytes()
        emb = extract_face_encoding(image_bytes)
        emb = np.asarray(emb, dtype=np.float32)
        cache.set(path, emb)
        return emb
    except Exception:
        return None


def collect_frontal(root: Path) -> dict[str, Path]:
    folder = root / "mugshot_frontal_original_all"
    if not folder.exists():
        raise FileNotFoundError(f"Не найдена папка: {folder}")

    result = {}
    for path in folder.iterdir():
        if not path.is_file():
            continue
        m = FRONTAL_RE.match(path.name)
        if m:
            result[m.group("sid")] = path
    return result


def collect_surveillance(root: Path, include_ir: bool = False) -> list[dict]:
    folder = root / "surveillance_cameras_all"
    if not folder.exists():
        raise FileNotFoundError(f"Не найдена папка: {folder}")

    result = []
    for path in folder.iterdir():
        if not path.is_file():
            continue
        m = SURV_RE.match(path.name)
        if not m:
            continue

        sid = m.group("sid")
        cam = int(m.group("cam"))
        dist = int(m.group("dist"))

        if not include_ir and cam >= 6:
            continue

        result.append({
            "person_id": sid,
            "path": path,
            "camera": cam,
            "distance": dist,
            "bucket": f"cam{cam}_dist{dist}",
        })

    result.sort(key=lambda x: (x["person_id"], x["camera"], x["distance"], x["path"].name))
    return result


def collect_pose(root: Path) -> list[dict]:
    folder = root / "mugshot_rotation_all"
    if not folder.exists():
        raise FileNotFoundError(f"Не найдена папка: {folder}")

    result = []
    for path in folder.iterdir():
        if not path.is_file():
            continue
        m = POSE_RE.match(path.name)
        if not m:
            continue

        angle = m.group("angle").upper()
        if angle == "F":
            continue

        result.append({
            "person_id": m.group("sid"),
            "path": path,
            "angle": angle,
            "bucket": f"pose_{angle}",
        })

    result.sort(key=lambda x: (x["person_id"], x["bucket"], x["path"].name))
    return result


def choose_authorized(subject_ids: list[str], authorized_count: int) -> set[str]:
    subject_ids = sorted(subject_ids)
    if authorized_count >= len(subject_ids):
        return set(subject_ids)
    return set(subject_ids[:authorized_count])


def build_gallery(frontal_map: dict[str, Path], authorized_ids: set[str], cache: EmbeddingCache):
    gallery = defaultdict(list)

    for sid in sorted(authorized_ids):
        path = frontal_map.get(sid)
        if path is None:
            continue

        emb = get_embedding(path, cache)
        if emb is None:
            continue

        gallery[sid].append(emb)

    return dict(gallery)


def evaluate_probes(probes: list[dict], gallery: dict[str, list[np.ndarray]], authorized_ids: set[str], cache: EmbeddingCache):
    results = []

    for probe in probes:
        sid = probe["person_id"]
        bucket = probe["bucket"]
        path = probe["path"]
        authorized = sid in authorized_ids

        probe_emb = get_embedding(path, cache)

        row = {
            "person_id": sid,
            "image_path": str(path),
            "bucket": bucket,
            "authorized": authorized,
            "embed_ok": probe_emb is not None,
            "best_person_id": None,
            "best_distance": None,
            "same_person_distance": None,
        }

        if probe_emb is None or not gallery:
            results.append(row)
            continue

        if authorized and sid in gallery:
            same_dists = [cosine_distance(probe_emb, enroll_emb) for enroll_emb in gallery[sid]]
            row["same_person_distance"] = float(min(same_dists))

        best_person_id = None
        best_distance = float("inf")

        for g_sid, enroll_list in gallery.items():
            d = min(cosine_distance(probe_emb, enroll_emb) for enroll_emb in enroll_list)
            if d < best_distance:
                best_distance = d
                best_person_id = g_sid

        row["best_person_id"] = best_person_id
        row["best_distance"] = float(best_distance)
        results.append(row)

    return results


def summarize(results: list[dict], threshold: float) -> dict:
    auth = [r for r in results if r["authorized"]]
    unknown = [r for r in results if not r["authorized"]]

    correct_accept = 0
    false_reject = 0

    for r in auth:
        ok = (
            r["embed_ok"]
            and r["best_person_id"] == r["person_id"]
            and r["best_distance"] is not None
            and r["best_distance"] <= threshold
        )
        if ok:
            correct_accept += 1
        else:
            false_reject += 1

    false_accept = 0
    true_reject = 0

    for r in unknown:
        accepted = (
            r["embed_ok"]
            and r["best_distance"] is not None
            and r["best_distance"] <= threshold
        )
        if accepted:
            false_accept += 1
        else:
            true_reject += 1

    genuine_scores = [
        r["same_person_distance"]
        for r in auth
        if r["same_person_distance"] is not None
    ]
    impostor_scores = [
        r["best_distance"]
        for r in unknown
        if r["best_distance"] is not None
    ]

    fnmr = (
        sum(score > threshold for score in genuine_scores) / len(genuine_scores)
        if genuine_scores else None
    )
    fmr = (
        sum(score <= threshold for score in impostor_scores) / len(impostor_scores)
        if impostor_scores else None
    )

    return {
        "threshold": threshold,
        "authorized_count": len(auth),
        "unknown_count": len(unknown),
        "correct_accept": correct_accept,
        "false_reject": false_reject,
        "false_accept": false_accept,
        "true_reject": true_reject,
        "authorized_accept_rate": (correct_accept / len(auth)) if auth else None,
        "unknown_false_accept_rate": (false_accept / len(unknown)) if unknown else None,
        "fnmr": fnmr,
        "fmr": fmr,
    }


def summarize_by_bucket(results: list[dict], threshold: float) -> dict[str, dict]:
    groups = defaultdict(list)
    for r in results:
        groups[r["bucket"]].append(r)
    return {bucket: summarize(rows, threshold) for bucket, rows in sorted(groups.items())}


def save_results_csv(results: list[dict], out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "person_id",
        "image_path",
        "bucket",
        "authorized",
        "embed_ok",
        "best_person_id",
        "best_distance",
        "same_person_distance",
    ]

    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow(row)


def save_summary_csv(summary_rows: list[dict], out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not summary_rows:
        return

    fieldnames = list(summary_rows[0].keys())
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in summary_rows:
            writer.writerow(row)


def build_binary_curve_data(results: list[dict]):
    y_true = []
    y_score = []

    # genuine pairs: positive class = "свой человек"
    for r in results:
        if r["authorized"] and r["same_person_distance"] is not None:
            y_true.append(1)
            y_score.append(-r["same_person_distance"])  # больше score = лучше совпадение

    # impostor pairs: negative class = "чужой человек"
    for r in results:
        if (not r["authorized"]) and r["best_distance"] is not None:
            y_true.append(0)
            y_score.append(-r["best_distance"])

    return np.asarray(y_true, dtype=np.int32), np.asarray(y_score, dtype=np.float32)


def save_curve_points_csv(x, y, thresholds, out_path: Path, x_name: str, y_name: str):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([x_name, y_name, "threshold"])
        for xv, yv, tv in zip(x, y, thresholds):
            writer.writerow([xv, yv, tv])


def plot_roc_det(results: list[dict], out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

    y_true, y_score = build_binary_curve_data(results)
    if len(np.unique(y_true)) < 2:
        print("Недостаточно данных для ROC/DET: нужен хотя бы один genuine и один impostor набор.")
        return

    fpr, tpr, roc_thresholds = roc_curve(y_true, y_score)
    auc = roc_auc_score(y_true, y_score)

    det_fpr, det_fnr, det_thresholds = det_curve(y_true, y_score)

    save_curve_points_csv(fpr, tpr, roc_thresholds, out_dir / "roc_points.csv", "fpr", "tpr")
    save_curve_points_csv(det_fpr, det_fnr, det_thresholds, out_dir / "det_points.csv", "fpr", "fnr")

    # ROC
    plt.figure(figsize=(7, 6))
    plt.plot(fpr, tpr, label=f"ROC (AUC = {auc:.4f})")
    plt.plot([0, 1], [0, 1], linestyle="--")
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title("ROC curve")
    plt.legend(loc="lower right")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_dir / "roc_global.png", dpi=180)
    plt.close()

    # DET
    plt.figure(figsize=(7, 6))
    plt.plot(det_fpr, det_fnr, label="DET")
    plt.xlabel("False Positive Rate")
    plt.ylabel("False Negative Rate")
    plt.title("DET curve")
    plt.legend(loc="upper right")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_dir / "det_global.png", dpi=180)
    plt.close()

    # Гистограмма расстояний
    genuine_distances = [
        r["same_person_distance"]
        for r in results
        if r["authorized"] and r["same_person_distance"] is not None
    ]
    impostor_distances = [
        r["best_distance"]
        for r in results
        if (not r["authorized"]) and r["best_distance"] is not None
    ]

    plt.figure(figsize=(8, 6))
    if genuine_distances:
        plt.hist(genuine_distances, bins=50, alpha=0.6, density=True, label="Genuine")
    if impostor_distances:
        plt.hist(impostor_distances, bins=50, alpha=0.6, density=True, label="Impostor")

    plt.axvline(INSIGHTFACE_COSINE_DISTANCE_AUTO_ALLOW, linestyle="--", label=f"auto_allow={INSIGHTFACE_COSINE_DISTANCE_AUTO_ALLOW}")
    plt.axvline(INSIGHTFACE_COSINE_DISTANCE_REVIEW, linestyle="--", label=f"review={INSIGHTFACE_COSINE_DISTANCE_REVIEW}")

    plt.xlabel("Cosine distance")
    plt.ylabel("Density")
    plt.title("Distance distributions")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_dir / "score_histogram.png", dpi=180)
    plt.close()

    metrics_json = {
        "roc_auc": float(auc),
        "roc_points_count": int(len(fpr)),
        "det_points_count": int(len(det_fpr)),
    }
    with (out_dir / "curve_metrics.json").open("w", encoding="utf-8") as f:
        json.dump(metrics_json, f, ensure_ascii=False, indent=2)


def run_eval(root: Path, mode: str, authorized_count: int, include_ir: bool, out_dir: Path):
    cache = EmbeddingCache(out_dir / "embedding_cache.pkl")

    frontal_map = collect_frontal(root)
    subject_ids = sorted(frontal_map.keys())
    authorized_ids = choose_authorized(subject_ids, authorized_count)
    gallery = build_gallery(frontal_map, authorized_ids, cache)

    if mode == "cctv":
        probes = collect_surveillance(root, include_ir=include_ir)
    elif mode == "pose":
        probes = collect_pose(root)
    else:
        raise ValueError(f"Неизвестный режим: {mode}")

    results = evaluate_probes(probes, gallery, authorized_ids, cache)
    cache.save()

    results_csv = out_dir / f"results_{mode}.csv"
    save_results_csv(results, results_csv)

    summary_rows = []

    for thr_name, thr in [
        ("auto_allow", INSIGHTFACE_COSINE_DISTANCE_AUTO_ALLOW),
        ("review", INSIGHTFACE_COSINE_DISTANCE_REVIEW),
    ]:
        global_summary = summarize(results, thr)
        print(f"\n=== GLOBAL | mode={mode} | threshold={thr_name} ({thr}) ===")
        for k, v in global_summary.items():
            print(f"{k}: {v}")

        summary_rows.append({
            "mode": mode,
            "level": "global",
            "bucket": "ALL",
            "threshold_name": thr_name,
            **global_summary,
        })

        bucket_stats = summarize_by_bucket(results, thr)
        for bucket, bucket_summary in bucket_stats.items():
            summary_rows.append({
                "mode": mode,
                "level": "bucket",
                "bucket": bucket,
                "threshold_name": thr_name,
                **bucket_summary,
            })

    summary_csv = out_dir / f"summary_{mode}.csv"
    save_summary_csv(summary_rows, summary_csv)

    plot_roc_det(results, out_dir / f"plots_{mode}")

    meta = {
        "root": str(root),
        "mode": mode,
        "authorized_count": authorized_count,
        "total_subjects_with_frontal": len(subject_ids),
        "authorized_subject_ids": sorted(authorized_ids),
        "gallery_subjects_with_valid_embedding": sorted(gallery.keys()),
        "results_csv": str(results_csv),
        "summary_csv": str(summary_csv),
        "include_ir": include_ir,
    }

    with (out_dir / f"meta_{mode}.json").open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\nГотово:")
    print(results_csv)
    print(summary_csv)
    print(out_dir / f"plots_{mode}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, help="Путь к папке SCface_database")
    parser.add_argument("--mode", choices=["cctv", "pose"], default="cctv")
    parser.add_argument("--authorized-count", type=int, default=80)
    parser.add_argument("--include-ir", action="store_true")
    parser.add_argument("--out", default="scface_eval_output")
    args = parser.parse_args()

    run_eval(
        root=Path(args.root),
        mode=args.mode,
        authorized_count=args.authorized_count,
        include_ir=args.include_ir,
        out_dir=Path(args.out),
    )


if __name__ == "__main__":
    main()