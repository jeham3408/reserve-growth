"""Parsers for the three UK sources: Watkins (2000) tables, Brown Book field pages, NSTA production."""
from __future__ import annotations

import html
import json
import re

import numpy as np
import pandas as pd

from common import DERIVED, RAW, newest

ROW = re.compile(
    r"^\s*(\d{1,3})\s+(.+?)\s{2,}(\d{4})\s+(\d{4})\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(\S+)\s+(\S+)\s+(\d+)\s*(.*)$")


def watkins_tables() -> pd.DataFrame:
    """Table D-1 (UK, rows 1-96) and D-2 (Norway, rows 97-126) of Watkins (2000), via `pdftotext -layout`.

    Columns used: (3) initial reserves at start-up, (4) initial reserves at last observation year,
    (6) remaining reserves at last observation year, all in million barrels of oil.
    """
    txt_path = DERIVED / "watkins_2000.txt"
    if not txt_path.exists():
        import subprocess
        subprocess.run(["pdftotext", "-layout", str(newest("watkins", "watkins_2000_ceepr_wp00-008", ".pdf")), str(txt_path)], check=True)
    lines = txt_path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(i for i, l in enumerate(lines) if "Various Field Characteristics: UK Sector" in l and "...." not in l)
    rows = []
    for line in lines[start:]:
        if "Data Sources" in line:
            break
        m = ROW.match(line)
        if not m:
            continue
        no = int(m.group(1))
        rows.append({"no": no, "sector": "UK" if no <= 96 else "Norway", "name": m.group(2).strip(),
                     "discovery_year": int(m.group(3)), "start_year": int(m.group(4)),
                     "initial_mmbbl": float(m.group(5)), "last_mmbbl": float(m.group(6)),
                     "prod_last_year_mmbbl": float(m.group(7)), "remaining_mmbbl": float(m.group(8)),
                     "api": m.group(10), "water_depth": m.group(11), "years_on_production": int(m.group(12)),
                     "formation": m.group(13).strip()})
    df = pd.DataFrame(rows).drop_duplicates("no").sort_values("no").reset_index(drop=True)
    df["af_1996"] = df.last_mmbbl / df.initial_mmbbl
    df["cum_prod_last_mmbbl"] = df.last_mmbbl - df.remaining_mmbbl
    return df


def _page_text(raw: str) -> str:
    t = re.sub(r"(?is)<(script|style|head|xml)[^>]*>.*?</\1>", " ", raw)
    t = re.sub(r"(?is)<!--.*?-->", " ", t)
    t = re.sub(r"<[^>]+>", "|", t)
    t = html.unescape(t).replace("\xa0", " ").replace("’", "'")
    t = re.sub(r"\s+", " ", t)
    return re.sub(r"(\|\s*)+", "|", t)


def _num(s: str) -> float:
    m = re.search(r"\d[\d,]*\.?\d*", s or "")
    return float(m.group(0).replace(",", "")) if m else np.nan


def _parse_field_page(path) -> dict | None:
    """One Brown Book field page -> name, kind, estimate (oil in million tonnes, gas in billion m3), dates."""
    t = _page_text(path.read_text(encoding="cp1252", errors="replace"))
    parts = [p.strip() for p in t.split("|") if p.strip()]
    kind = next((p for p in parts[:12] if re.match(r"(?i)(offshore|onshore)\b", p)), "")
    if not kind:
        return None  # index or non-field page
    k_i = parts.index(kind)
    title = parts[0] if k_i >= 1 else ""
    title = next((p for p in parts[:k_i] if len(p) < 80 and not re.match(r"^\(", p)), title)
    operator = next((p.strip("() ") for p in parts[:k_i] if p.startswith("(")), "")
    seg = re.search(r"(?i)Recoverable\s+reserves\s+originally\s+present(.*?)(?:First year of peak|Peak production|Water depth|Gravity|Transport system|$)", t)
    s = seg.group(1) if seg else ""
    oil = gas = np.nan
    flat = re.sub(r"\s+", " ", s.replace("|", " "))
    MT, BCM, NUM = r"\(\s*million tonnes\s*\)", r"\(\s*billion cubic metres\s*\)", r"([\d.,]*\d)"
    multi = len(re.findall(r"(?i)million tonnes", flat)) + len(re.findall(r"(?i)billion cubic metres", flat))
    several_fields = (re.search(r"(?i)\b[A-Z][a-z]+ [A-Z]\b.*\b[A-Z][a-z]+ [A-Z]\b", flat) and multi >= 3 and not re.search(r"(?i)\boil\s*:", flat)) \
        or re.search(r"(?i)accumulation", flat)
    if not several_fields:
        # labelled forms, in the three orders used by the different editions
        mo = (re.search(rf"(?i)\boil\s*:?\s*{MT}\s*:?\s*{NUM}", flat) or re.search(rf"(?i){MT}\s*:?\s*oil\s*:?\s*{NUM}", flat)
              or re.search(rf"(?i)\boil\s*:?\s*{NUM}\s*{MT}", flat))
        mg = (re.search(rf"(?i)\bgas\s*:?\s*{BCM}\s*:?\s*{NUM}", flat) or re.search(rf"(?i){BCM}\s*:?\s*gas\s*:?\s*{NUM}", flat)
              or re.search(rf"(?i)\bgas\s*:?\s*{NUM}\s*{BCM}", flat) or re.search(rf"(?i)\bgas\s*{BCM}\s*:\s*{NUM}", flat))
        # unlabelled forms: "(million tonnes): 61.40" at the start, "(billion cubic metres): 7.58" anywhere
        if not mo and not re.search(r"(?i)\boil\s*:", flat):
            mo = re.match(rf"(?i)\s*:?\s*{MT}\s*:?\s*{NUM}", flat) or re.match(rf"(?i)\s*:?\s*\(\s*million tonnes\s*\)?\s*:?\s*{NUM}", flat)
        if not mg:
            mg = re.search(rf"(?i){BCM}\s*:?\s*{NUM}", flat) or re.search(rf"(?i)\(\s*billion cubic metres\s*\)?\s*:\s*{NUM}", flat)
        oil = _num(mo.group(1)) if mo else np.nan
        gas = _num(mg.group(1)) if mg else np.nan
    start = re.search(r"(?i)Production start\s*:?\s*\|\s*([^|]*)", t)
    disc = re.search(r"(?i)Date of discovery\s*:?\s*\|\s*([^|]*)", t)
    asof = re.search(r"(?i)at (end of [A-Za-z ]*\d{4})", t)
    wd = re.search(r"(?i)Water depth\s*:?\s*\|\s*([^|]*)", t)
    yr = re.search(r"(19|20)\d{2}", start.group(1)) if start else None
    dyr = re.search(r"(19|20)\d{2}", disc.group(1)) if disc else None
    return {"name": title.strip(), "operator": operator, "kind": kind.rstrip("."),
            "offshore": kind.lower().startswith("offshore"), "is_oil": "oil" in kind.lower(),
            "under_development": "under development" in kind.lower(),
            "oil_mt": oil, "gas_bcm": gas, "start_text": start.group(1).strip() if start else "",
            "start_year": int(yr.group(0)) if yr else np.nan, "discovery_year": int(dyr.group(0)) if dyr else np.nan,
            "discovery_text": disc.group(1).strip() if disc else "", "water_depth_m": _num(wd.group(1)) if wd else np.nan,
            "licence_interest_date": asof.group(1) if asof else "", "reserves_text": s.strip("| :")[:160]}


def brown_book_pages() -> pd.DataFrame:
    """One row per archived Brown Book field page, last web update (licence interests 'at end of February 2002')."""
    rows = []
    for path in sorted((RAW / "brownbook" / "pages").glob("*.htm*")):
        stamp, fname = path.name.split("_", 1)
        rec = _parse_field_page(path)
        if rec:
            rows.append({"file": fname, "wayback_timestamp": stamp, **rec})
    return pd.DataFrame(rows)


EDITION_YEAR = {"bb1998": 1997, "bb1999": 1998, "bb2000": 1999, "bbonline": 1999, "bb2001": 2000}


def brown_book_editions() -> pd.DataFrame:
    """Long table: one row per field page and edition. `year` = the year-end the edition describes.

    bb1998 -> end 1997, bb1999 -> end 1998, bb2000 (= bbonline) -> end 1999, bb2001 -> end 2000 (dbd-data.co.uk).
    The last web update on og.dti.gov.uk / og.decc.gov.uk (interests at end of February 2002) repeats the 2001 figures.
    """
    rows = []
    for ed, year in EDITION_YEAR.items():
        for path in sorted((RAW / "brownbook" / "editions" / ed).glob("*.htm*")):
            stamp, fname = path.name.split("_", 1)
            if fname.startswith("app"):
                continue
            rec = _parse_field_page(path)
            if rec:
                rows.append({"file": fname, "edition": ed, "year": year, "wayback_timestamp": stamp, **rec})
    last = brown_book_pages()
    if len(last):
        # The 2002 web update changed licence interests but repeated the reserve figures of the 2001 edition
        # (checked below), so it counts as the same year-end (2000), and is used only where the 2001 page is missing.
        last = last.assign(edition="update2002", year=2000)
        rows.extend(last.to_dict("records"))
    df = pd.DataFrame(rows)
    order = {"bb1998": 0, "bb1999": 1, "bb2000": 2, "bbonline": 3, "bb2001": 4, "update2002": 5}
    df["o"] = df.edition.map(order)
    both = df[df.edition.isin(["bb2001", "update2002"]) & df.oil_mt.notna()].pivot_table(index="file", columns="edition", values="oil_mt", aggfunc="first").dropna()
    df.attrs["update2002_check"] = {"n_compared": int(len(both)),
                                    "n_identical": int((np.abs(both["bb2001"] - both["update2002"]) < 0.005).sum()) if len(both) else 0}
    attrs = df.attrs
    df = df.sort_values(["file", "year", "o"]).drop_duplicates(["file", "year"], keep="first").drop(columns="o")
    df.attrs = attrs
    return df.reset_index(drop=True)


def nsta_production() -> tuple[pd.DataFrame, pd.DataFrame]:
    """NSTA PPRS: yearly production per field (oil in tonnes and m3, gas in ksm3)."""
    d = json.loads(newest("nsta", "pprs_production", ".json").read_text())
    p = pd.DataFrame(d["rows"])
    num = ["OILPRODMAS", "OILPRODM3", "AGASPROKSM", "DGASPROKSM", "GCONDVOL", "GCONDMASS"]
    p[num] = p[num].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    yearly = p.groupby(["FIELDNAME", "PERIODYR"], as_index=False)[num].sum()
    info = p.groupby("FIELDNAME").agg(location=("LOCATION", "first"), area=("FIELDAREA", "first"),
                                      unit_type=("UNITTYPDES", lambda s: s.mode().iat[0]),
                                      first_period=("PERIODYRMN", "min"), last_period=("PERIODYRMN", "max"),
                                      oil_t=("OILPRODMAS", "sum"), oil_m3=("OILPRODM3", "sum"),
                                      gas_ksm3=("DGASPROKSM", "sum"), agas_ksm3=("AGASPROKSM", "sum"),
                                      cond_m3=("GCONDVOL", "sum"), cond_t=("GCONDMASS", "sum"))
    info["density"] = np.where(info.oil_m3 > 0, info.oil_t / info.oil_m3, np.nan)  # tonnes per m3
    return yearly, info.reset_index()


def nsta_fields() -> pd.DataFrame:
    d = json.loads(newest("nsta", "offshore_fields", ".json").read_text())
    f = pd.DataFrame(d["rows"])[["FIELDNAME", "FIELDTYPE", "STATUS", "DISC_DATE", "PROD_DATE", "DEPTH_M", "ORIG_OP", "CURR_OPER"]]
    return f.drop_duplicates("FIELDNAME")
