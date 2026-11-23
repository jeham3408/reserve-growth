"""Shared helpers for the reserve-growth pipeline."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"
DERIVED = ROOT / "derived"
WEB_DATA = ROOT / "web" / "data"
FIGURES = ROOT / "figures"

SM3_TO_BBL = 6.2898  # 1 Sm3 of oil = 6.2898 barrels (Sodir conversion table)


def newest(folder: str, stem: str, suffix: str = ".csv") -> Path:
    """Newest dated raw file, e.g. raw/sodir/field_reserves_2026-11-19.csv."""
    hits = sorted((RAW / folder).glob(f"{stem}_20??-??-??{suffix}"))
    if not hits:
        raise FileNotFoundError(f"no raw file {folder}/{stem}_<date>{suffix}; run pipeline/download.py")
    return hits[-1]


def sodir(table: str) -> pd.DataFrame:
    df = pd.read_csv(newest("sodir", table), encoding="utf-8-sig", low_memory=False)
    for col in df.columns:
        if df[col].dtype == object or str(df[col].dtype).startswith("str"):
            df[col] = df[col].str.strip()
    return df


def clean(obj):
    """Make numpy / NaN values JSON-safe."""
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, np.ndarray, pd.Series)):
        return [clean(v) for v in list(obj)]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        return None if (math.isnan(v) or math.isinf(v)) else round(v, 4)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if obj is pd.NA or obj is pd.NaT:
        return None
    return obj


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(obj), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size / 1024:.0f} kB)")


def boot_ci(values, stat=np.median, n_boot: int = 4000, seed: int = 1, level: float = 0.90):
    """Percentile bootstrap confidence interval for a statistic of one sample."""
    x = np.asarray([v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))], dtype=float)
    if len(x) < 3:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), size=(n_boot, len(x)))
    stats = stat(x[idx], axis=1)
    lo, hi = np.quantile(stats, [(1 - level) / 2, 1 - (1 - level) / 2])
    return (float(lo), float(hi))
