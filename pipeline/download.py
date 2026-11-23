#!/usr/bin/env python3
"""Download every open raw input used by the reserve-growth project.

Re-runnable: files that already exist for today's date (or, for the Wayback
cache, at all) are kept. Everything lands in raw/ and is listed in
raw/MANIFEST.tsv with URL, download date, size and md5.

Usage:
    python pipeline/download.py                # everything
    python pipeline/download.py sodir nsta     # only some sources
    python pipeline/download.py --force sodir  # re-download today's files
    python pipeline/download.py editions       # Brown Book web editions 1998-2001 (slow: one request every 4 s)

Only the Python standard library is needed.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"
TODAY = dt.date.today().isoformat()
UA = "reserve-growth-hackathon/1.0 (open-data research script)"

SODIR_URL = (
    "https://factpages.sodir.no/public?/Factpages/external/tableview/{table}"
    "&rs:Command=Render&rc:Toolbar=false&rc:Parameters=f&IpAddress=not_used"
    "&CultureCode=en&rs:Format=CSV&Top100=false"
)
SODIR_TABLES = [
    "field_reserves",
    "field_production_yearly",
    "field_production_monthly",
    "field_activity_status_hst",
    "field",
    "field_in_place_volumes",
    "field_description",
    "field_investment_yearly",
    "field_operator_hst",
    "field_owner_hst",
    "discovery",
    "discovery_reserves",
    "discovery_description",
    "facility_fixed",
    "facility_moveable",
    "wellbore_exploration_all",
    "wellbore_development_all",
    "strat_litho_wellbore",
]

NSTA_BASE = "https://services-eu1.arcgis.com/OZMfUznmLTnWccBc/arcgis/rest/services/"
NSTA_LAYERS = {
    "pprs_production": "UKCS_hydrocarbon_field_production_reports_PPRS_points_(WGS84)/FeatureServer/0",
    "offshore_fields": "Offshore_hydrocarbon_fields_(WGS84)/FeatureServer/0",
}

WATKINS_URL = "https://ceepr.mit.edu/wp-content/uploads/2023/02/2000-008.pdf"
CDX_URL = (
    "https://web.archive.org/cdx/search/cdx?url="
    "og.decc.gov.uk/information/bb_updates/appendices/fields/*"
    "&output=json&filter=statuscode:200&filter=mimetype:text/html&collapse=urlkey"
)

_last_request = 0.0


def fetch(url: str, min_interval: float = 0.0, retries: int = 4, timeout: int = 120) -> bytes:
    """GET with a generic User-Agent, optional rate limit and retries."""
    global _last_request
    for attempt in range(retries):
        wait = min_interval - (time.time() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001
            if attempt == retries - 1:
                raise
            print(f"   retry {attempt + 1} after error: {exc}", flush=True)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("unreachable")


def md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


class Manifest:
    """raw/MANIFEST.tsv: one row per file, keyed on the relative path."""

    COLS = ["path", "url", "downloaded", "bytes", "md5", "licence", "note"]

    def __init__(self) -> None:
        self.path = RAW / "MANIFEST.tsv"
        self.rows: dict[str, dict[str, str]] = {}
        if self.path.exists():
            lines = self.path.read_text(encoding="utf-8").splitlines()
            for line in lines[1:]:
                parts = line.split("\t")
                if len(parts) == len(self.COLS):
                    self.rows[parts[0]] = dict(zip(self.COLS, parts))

    def add(self, path: Path, url: str, licence: str, note: str = "", downloaded: str | None = None) -> None:
        rel = str(path.relative_to(ROOT))
        self.rows[rel] = {
            "path": rel,
            "url": url,
            "downloaded": downloaded or TODAY,
            "bytes": str(path.stat().st_size),
            "md5": md5(path),
            "licence": licence,
            "note": note,
        }

    def save(self) -> None:
        out = ["\t".join(self.COLS)]
        for rel in sorted(self.rows):
            out.append("\t".join(self.rows[rel][c] for c in self.COLS))
        self.path.write_text("\n".join(out) + "\n", encoding="utf-8")


def get_sodir(man: Manifest, force: bool) -> None:
    out_dir = RAW / "sodir"
    out_dir.mkdir(parents=True, exist_ok=True)
    for table in SODIR_TABLES:
        existing = sorted(out_dir.glob(f"{table}_20??-??-??.csv"))
        target = out_dir / f"{table}_{TODAY}.csv"
        url = SODIR_URL.format(table=table)
        if existing and not force:
            target = existing[-1]
            print(f"sodir  keep  {target.name}")
            date = target.stem[-10:]
        else:
            try:
                data = fetch(url, min_interval=1.0)
            except Exception as exc:  # noqa: BLE001
                print(f"sodir  FAIL  {table}: {exc}")
                continue
            head = data[:300].lstrip(b"\xef\xbb\xbf").lstrip()
            if not data.strip() or head.lower().startswith((b"<!doctype", b"<html")):
                print(f"sodir  FAIL  {table}: not a CSV table (wrong table name?)")
                continue
            target.write_bytes(data)
            date = TODAY
            print(f"sodir  saved {target.name} ({len(data):,} bytes)")
        man.add(target, url, "NLOD 2.0", "Sodir FactPages table", downloaded=date)
        man.save()


def get_nsta(man: Manifest, force: bool) -> None:
    out_dir = RAW / "nsta"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, layer in NSTA_LAYERS.items():
        existing = sorted(out_dir.glob(f"{name}_20??-??-??.json"))
        if existing and not force:
            print(f"nsta   keep  {existing[-1].name}")
            continue
        base = NSTA_BASE + urllib.parse.quote(layer, safe="/()")
        meta = json.loads(fetch(base + "?f=json", min_interval=0.5))
        page = int(meta.get("maxRecordCount", 1000))
        count = json.loads(fetch(base + "/query?where=1%3D1&returnCountOnly=true&f=json", min_interval=0.5))["count"]
        oid = meta.get("objectIdField") or "OBJECTID"
        rows: list[dict] = []
        offset = 0
        while True:
            q = urllib.parse.urlencode({
                "where": "1=1",
                "outFields": "*",
                "returnGeometry": "false",
                "orderByFields": oid,
                "resultOffset": offset,
                "resultRecordCount": page,
                "f": "json",
            })
            chunk = json.loads(fetch(f"{base}/query?{q}", min_interval=0.5))
            if "error" in chunk:
                raise RuntimeError(chunk["error"])
            feats = chunk.get("features", [])
            rows.extend(f["attributes"] for f in feats)
            offset += len(feats)
            print(f"nsta   {name}: {len(rows):,}/{count:,}", flush=True)
            if not feats or (len(feats) < page and not chunk.get("exceededTransferLimit")):
                break
        if len(rows) != count:
            print(f"nsta   WARNING {name}: got {len(rows)} rows, service reports {count}")
        target = out_dir / f"{name}_{TODAY}.json"
        target.write_text(json.dumps({
            "source": base,
            "downloaded": TODAY,
            "reported_count": count,
            "fields": [{k: f.get(k) for k in ("name", "alias", "type")} for f in meta.get("fields", [])],
            "rows": rows,
        }), encoding="utf-8")
        (out_dir / f"{name}_layer_metadata_{TODAY}.json").write_text(json.dumps(meta), encoding="utf-8")
        man.add(target, base, "see README (NSTA Open Data)", f"{len(rows)} rows, attributes only, paginated REST query")
        man.add(out_dir / f"{name}_layer_metadata_{TODAY}.json", base + "?f=json", "see README (NSTA Open Data)", "layer metadata incl. copyrightText")
        man.save()


def get_watkins(man: Manifest, force: bool) -> None:
    out_dir = RAW / "watkins"
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(out_dir.glob("watkins_2000_ceepr_wp00-008_20??-??-??.pdf"))
    if existing and not force:
        print(f"watkins keep {existing[-1].name}")
        return
    target = out_dir / f"watkins_2000_ceepr_wp00-008_{TODAY}.pdf"
    target.write_bytes(fetch(WATKINS_URL))
    man.add(target, WATKINS_URL, "copyright MIT CEEPR / author; cited, not redistributed",
            "Watkins (2000) Characteristics of North Sea oil reserve appreciation")
    man.save()
    print(f"watkins saved {target.name}")


def get_brownbook(man: Manifest, force: bool) -> None:
    """Brown Book per-field pages (c. 2001) from the Wayback Machine. Max 1 request/second, cached."""
    out_dir = RAW / "brownbook"
    pages = out_dir / "pages"
    pages.mkdir(parents=True, exist_ok=True)
    cdx_files = sorted(out_dir.glob("cdx_index_20??-??-??.json"))
    if cdx_files and not force:
        cdx_path = cdx_files[-1]
        cdx = json.loads(cdx_path.read_text())
    else:
        cdx_path = out_dir / f"cdx_index_{TODAY}.json"
        cdx_path.write_bytes(fetch(CDX_URL, min_interval=1.0, timeout=300))
        cdx = json.loads(cdx_path.read_text())
        man.add(cdx_path, CDX_URL, "Internet Archive CDX index", "list of archived Brown Book field pages")
    header, records = cdx[0], cdx[1:]
    idx = {k: i for i, k in enumerate(header)}
    print(f"brownbook: {len(records)} archived URLs in CDX index")
    for n, rec in enumerate(records, 1):
        original, stamp = rec[idx["original"]], rec[idx["timestamp"]]
        fname = original.rstrip("/").split("/")[-1].split("?")[0] or "index.htm"
        target = pages / f"{stamp}_{fname}"
        url = f"https://web.archive.org/web/{stamp}id_/{original}"
        if not target.exists():
            try:
                target.write_bytes(fetch(url, min_interval=1.05))
            except Exception as exc:  # noqa: BLE001
                print(f"brownbook FAIL {fname}: {exc}")
                continue
            if n % 25 == 0:
                print(f"brownbook {n}/{len(records)}", flush=True)
        if str(target.relative_to(ROOT)) not in man.rows:
            man.add(target, url, "Crown copyright (DTI/DECC Brown Book), archived copy",
                    f"Wayback capture {stamp}")
    man.save()


EDITIONS_CDX = ("https://web.archive.org/cdx/search/cdx?url=dbd-data.co.uk/*&output=json&collapse=urlkey"
                "&filter=statuscode:200&limit=6000")
EDITIONS = ("bb1998", "bb1999", "bb2000", "bbonline", "bb2001")   # bbonline = the 2000 edition at its first address


def get_brownbook_editions(man: Manifest, force: bool) -> None:
    """Annual web editions of the Brown Book 1998-2001 (dbd-data.co.uk), field pages + discovery appendix.

    Each field page gives the operator's estimate of recoverable reserves originally present, with licence
    interests "at end of <year>". Max 1 request per second, cached; oil-field pages are fetched first.
    """
    out_dir = RAW / "brownbook"
    cdx_files = sorted(out_dir.glob("cdx_dbd-data_20??-??-??.json"))
    if cdx_files and not force:
        cdx_path = cdx_files[-1]
    else:
        cdx_path = out_dir / f"cdx_dbd-data_{TODAY}.json"
        cdx_path.write_bytes(fetch(EDITIONS_CDX, min_interval=1.0, timeout=300))
    cdx = json.loads(cdx_path.read_text())
    man.add(cdx_path, EDITIONS_CDX, "Internet Archive CDX index", "list of archived Brown Book web editions 1998-2001")
    idx = {k: i for i, k in enumerate(cdx[0])}
    # Order: discovery appendix, then oil fields that started 1992 or later (their early revisions are visible in
    # these editions), then other oil fields, then the rest. "bbonline" repeats the 2000 edition and goes last.
    recent, oil = set(), set()
    for p in (out_dir / "pages").glob("*.htm*"):
        try:
            head = p.read_text(encoding="cp1252", errors="replace")
        except OSError:
            continue
        low_txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", head)).lower()
        kind = low_txt[:6000]
        if "oil" not in kind and "condensate" not in kind:
            continue
        name = p.name.split("_", 1)[1].lower()
        oil.add(name)
        m = re.search(r"production start\s*:?\s*[a-z ]*?((?:19|20)\d{2})", low_txt)
        if "under development" in kind or (m and int(m.group(1)) >= 1992):
            recent.add(name)
    jobs = []
    for rec in cdx[1:]:
        original, stamp = rec[idx["original"]], rec[idx["timestamp"]]
        low = original.lower()
        ed = next((e for e in EDITIONS if f"/{e}/" in low), None)
        if not ed:
            continue
        tail = low.split(f"/{ed}/", 1)[1]
        is_field = tail.startswith("fields/") and tail.endswith((".htm", ".html"))
        is_app = "/" not in tail and tail.startswith(("append5", "appen5_", "append3", "appen3_"))
        if not (is_field or is_app):
            continue
        fname = tail.split("/")[-1]
        prio = 0 if is_app else (1 if fname in recent else 2 if fname in oil else 3)
        if ed == "bbonline":
            prio = 4
        jobs.append((prio, ed, stamp, original, fname))
    jobs.sort()
    print(f"brownbook editions: {len(jobs)} pages listed; by priority {[sum(1 for j in jobs if j[0] == q) for q in range(5)]}")
    done = 0
    for n, (prio, ed, stamp, original, fname) in enumerate(jobs, 1):
        target = out_dir / "editions" / ed / f"{stamp}_{fname}"
        target.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://web.archive.org/web/{stamp}id_/{original}"
        if not target.exists():
            try:
                target.write_bytes(fetch(url, min_interval=4.2, retries=6))  # the archive refuses faster clients
            except Exception as exc:  # noqa: BLE001
                print(f"editions FAIL {ed}/{fname}: {exc}", flush=True)
                continue
            done += 1
            if done % 25 == 0:
                print(f"editions {n}/{len(jobs)}", flush=True)
                man.save()
        if str(target.relative_to(ROOT)) not in man.rows:
            man.add(target, url, "Crown copyright (DTI Brown Book), archived copy", f"{ed}, Wayback capture {stamp}")
    man.save()


STEPS = {"sodir": get_sodir, "nsta": get_nsta, "watkins": get_watkins, "brownbook": get_brownbook,
         "editions": get_brownbook_editions}


def main() -> None:
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        print("Steps:", ", ".join(STEPS))
        return
    unknown = [a for a in sys.argv[1:] if not a.startswith("--") and a not in STEPS]
    if unknown:
        sys.exit(f"unknown step(s): {unknown}; choose from {list(STEPS)}")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    man = Manifest()
    for name in args or list(STEPS):
        STEPS[name](man, force)
    man.save()
    print(f"manifest: {len(man.rows)} files -> {man.path}")


if __name__ == "__main__":
    main()
