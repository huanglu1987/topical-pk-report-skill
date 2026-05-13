from __future__ import annotations

import csv
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from .io_utils import ensure_dir, write_json


PUBCHEM_PROPERTIES = [
    "MolecularFormula",
    "MolecularWeight",
    "XLogP",
    "TPSA",
    "HBondDonorCount",
    "HBondAcceptorCount",
    "CanonicalSMILES",
    "IsomericSMILES",
    "InChIKey",
    "IUPACName",
]

CDE_CURATED_SOURCES = [
    {
        "title": "模型引导的创新药物剂量探索和优化技术指导原则",
        "url": "https://www.cde.org.cn/zdyz/domesticinfopage?zdyzIdCODE=aedd7891b591c77683ee7e201961c6b4",
        "keywords": "模型引导 剂量探索 剂量优化 临床药理 药代动力学",
    },
    {
        "title": "模型引导的罕见病药物研发技术指导原则（征求意见稿）",
        "url": "https://www.cde.org.cn/main/news/viewInfoCommon/258189515b8d3df9964e275b26ba901b",
        "keywords": "模型引导 罕见病 药物研发 定量药理学",
    },
    {
        "title": "ICH M10 生物分析方法验证和样品分析",
        "url": "https://www.cde.org.cn/ichWeb/guideIch/toGuideIch/4/0",
        "keywords": "M10 生物分析 方法验证 样品分析 药代动力学",
    },
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slug(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "_", value.strip())
    return clean.strip("_")[:80] or "query"


def _manifest_path(output_dir: str | Path) -> Path:
    return Path(output_dir) / "evidence_manifest.csv"


def _append_manifest(output_dir: str | Path, rows: list[dict[str, Any]]) -> None:
    ensure_dir(output_dir)
    path = _manifest_path(output_dir)
    fieldnames = [
        "retrieved_at",
        "source",
        "query",
        "source_url",
        "cache_file",
        "field",
        "value",
        "used_for_model",
        "status",
        "note",
    ]
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _get_json_with_retries(url: str, timeout: int, attempts: int = 3) -> tuple[dict[str, Any], int]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, timeout=timeout, headers={"User-Agent": "pktool/0.1"})
            status = response.status_code
            if status in {429, 500, 502, 503, 504} and attempt < attempts:
                time.sleep(0.75 * attempt)
                continue
            response.raise_for_status()
            return response.json(), status
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(0.75 * attempt)
                continue
    raise last_error or RuntimeError(f"Request failed: {url}")


def fetch_pubchem(name: str, output_dir: str | Path = "data/evidence_cache", timeout: int = 20) -> dict[str, Any]:
    ensure_dir(output_dir)
    retrieved_at = _now_iso()
    encoded_name = quote(name)
    props = ",".join(PUBCHEM_PROPERTIES)
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{encoded_name}/property/{props}/JSON"
    cache_file = Path(output_dir) / f"pubchem_{_slug(name)}.json"

    result: dict[str, Any] = {
        "source": "PubChem PUG REST",
        "query": name,
        "retrieved_at": retrieved_at,
        "url": url,
        "ok": False,
        "properties": {},
        "synonyms": [],
    }
    try:
        payload, status = _get_json_with_retries(url, timeout=timeout)
        result["http_status"] = status
        properties = payload.get("PropertyTable", {}).get("Properties", [])
        if properties:
            result["properties"] = properties[0]
            result["ok"] = True
    except Exception as exc:  # requests and JSON parsing failures should not stop the workflow.
        result["primary_error"] = str(exc)

    if not result["ok"]:
        try:
            cid_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{encoded_name}/cids/JSON"
            result["cid_lookup_url"] = cid_url
            cid_payload, cid_status = _get_json_with_retries(cid_url, timeout=timeout)
            result["cid_lookup_status"] = cid_status
            cids = cid_payload.get("IdentifierList", {}).get("CID", [])
            if cids:
                cid = cids[0]
                cid_property_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/property/{props}/JSON"
                result["fallback_url"] = cid_property_url
                payload, fallback_status = _get_json_with_retries(cid_property_url, timeout=timeout)
                result["fallback_http_status"] = fallback_status
                properties = payload.get("PropertyTable", {}).get("Properties", [])
                if properties:
                    result["properties"] = properties[0]
                    result["ok"] = True
        except Exception as exc:
            result["error"] = str(exc)

    cid = result["properties"].get("CID")
    if cid:
        synonym_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/synonyms/JSON"
        try:
            syn_payload, _ = _get_json_with_retries(synonym_url, timeout=timeout, attempts=2)
            infos = syn_payload.get("InformationList", {}).get("Information", [])
            if infos:
                result["synonyms"] = infos[0].get("Synonym", [])[:30]
            result["synonym_url"] = synonym_url
        except Exception as exc:
            result["synonym_error"] = str(exc)

    write_json(cache_file, result)
    rows: list[dict[str, Any]] = []
    if result["ok"]:
        for field, value in result["properties"].items():
            rows.append(
                {
                    "retrieved_at": retrieved_at,
                    "source": "PubChem",
                    "query": name,
                    "source_url": url,
                    "cache_file": str(cache_file),
                    "field": field,
                    "value": value,
                    "used_for_model": "candidate_input_only",
                    "status": "ok",
                    "note": "需人工确认后进入模型参数。",
                }
            )
    else:
        rows.append(
            {
                "retrieved_at": retrieved_at,
                "source": "PubChem",
                "query": name,
                "source_url": url,
                "cache_file": str(cache_file),
                "field": "",
                "value": "",
                "used_for_model": "no",
                "status": "error",
                "note": result.get("error", "No result"),
            }
        )
    _append_manifest(output_dir, rows)
    return result


def fetch_fda_label(ingredient: str, output_dir: str | Path = "data/evidence_cache", limit: int = 5, timeout: int = 20) -> dict[str, Any]:
    ensure_dir(output_dir)
    retrieved_at = _now_iso()
    query = f'openfda.generic_name:"{ingredient}"'
    url = f"https://api.fda.gov/drug/label.json?search={quote(query)}&limit={int(limit)}"
    cache_file = Path(output_dir) / f"fda_label_{_slug(ingredient)}.json"

    result: dict[str, Any] = {
        "source": "openFDA drug label",
        "query": ingredient,
        "retrieved_at": retrieved_at,
        "url": url,
        "ok": False,
        "records": [],
        "labels_found": 0,
    }
    try:
        response = requests.get(url, timeout=timeout)
        result["http_status"] = response.status_code
        if response.status_code == 404:
            result["error"] = "No matching FDA label records."
        else:
            response.raise_for_status()
            payload = response.json()
            records = payload.get("results", [])
            result["records"] = records
            result["labels_found"] = len(records)
            result["ok"] = len(records) > 0
    except Exception as exc:
        result["error"] = str(exc)

    write_json(cache_file, result)
    if result["ok"]:
        rows = []
        for idx, record in enumerate(result["records"], start=1):
            openfda = record.get("openfda", {})
            field_value = "; ".join(openfda.get("brand_name", [])[:5]) or record.get("id", "")
            rows.append(
                {
                    "retrieved_at": retrieved_at,
                    "source": "openFDA",
                    "query": ingredient,
                    "source_url": url,
                    "cache_file": str(cache_file),
                    "field": f"label_record_{idx}",
                    "value": field_value,
                    "used_for_model": "evidence_only",
                    "status": "ok",
                    "note": "标签信息仅作公开证据线索，PK 参数需人工确认。",
                }
            )
    else:
        rows = [
            {
                "retrieved_at": retrieved_at,
                "source": "openFDA",
                "query": ingredient,
                "source_url": url,
                "cache_file": str(cache_file),
                "field": "",
                "value": "",
                "used_for_model": "no",
                "status": "no_result",
                "note": result.get("error", "No result"),
            }
        ]
    _append_manifest(output_dir, rows)
    return result


def fetch_cde_sources(
    keyword: str,
    output_dir: str | Path = "data/evidence_cache",
    url: str | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    ensure_dir(output_dir)
    retrieved_at = _now_iso()
    keyword_lower = keyword.lower()
    candidates = [
        item
        for item in CDE_CURATED_SOURCES
        if keyword_lower in item["title"].lower() or keyword_lower in item["keywords"].lower()
    ]
    if url:
        candidates.append({"title": "用户登记的 CDE 官方来源", "url": url, "keywords": keyword})

    records = []
    for item in candidates:
        record = {**item, "retrieved_at": retrieved_at, "reachable": False, "page_title": ""}
        try:
            response = requests.get(item["url"], timeout=timeout, headers={"User-Agent": "pktool/0.1"})
            record["http_status"] = response.status_code
            record["reachable"] = response.ok
            if response.text:
                soup = BeautifulSoup(response.text, "html.parser")
                if soup.title and soup.title.string:
                    record["page_title"] = soup.title.string.strip()
        except requests.RequestException as exc:
            record["error"] = str(exc)
        records.append(record)

    result = {
        "source": "CDE official source registry",
        "query": keyword,
        "retrieved_at": retrieved_at,
        "ok": len(records) > 0,
        "records": records,
        "note": "CDE first version uses official URL registration rather than an assumed stable API.",
    }
    cache_file = Path(output_dir) / f"cde_{_slug(keyword)}.json"
    write_json(cache_file, result)

    rows = []
    if records:
        for record in records:
            rows.append(
                {
                    "retrieved_at": retrieved_at,
                    "source": "CDE",
                    "query": keyword,
                    "source_url": record["url"],
                    "cache_file": str(cache_file),
                    "field": "official_source",
                    "value": record["title"],
                    "used_for_model": "evidence_only",
                    "status": "ok" if record.get("reachable") else "registered",
                    "note": "官方来源线索；正文解读需人工确认。",
                }
            )
    else:
        rows.append(
            {
                "retrieved_at": retrieved_at,
                "source": "CDE",
                "query": keyword,
                "source_url": url or "",
                "cache_file": str(cache_file),
                "field": "",
                "value": "",
                "used_for_model": "no",
                "status": "no_curated_match",
                "note": "未命中内置来源，可用 --url 登记官方页面。",
            }
        )
    _append_manifest(output_dir, rows)
    return result
