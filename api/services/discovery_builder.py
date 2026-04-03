"""Agent discovery JSON: local file + env overrides + optional IPFS merge."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

X402_AMOUNT_XLM = "0.05"


def _metadata_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "agent_metadata.json"


def load_local_agent_metadata() -> dict:
    p = _metadata_path()
    if not p.exists():
        return {"error": "agent_metadata.json not found"}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def build_discovery_payload() -> dict:
    data = load_local_agent_metadata()
    if "error" in data:
        return data

    base = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    executor = (os.getenv("EXECUTOR_PUBLIC_KEY") or "").strip()

    out = dict(data)
    if base:
        out["endpoint"] = f"{base}/execute/stream"
        out["public_urls"] = {
            "api_docs": f"{base}/docs",
            "openapi_json": f"{base}/openapi.json",
            "prepare_x402_payment": f"{base}/api/x402/prepare-payment",
            "discovery_resolved": f"{base}/api/discovery/resolved",
        }

    fallback_base = base or "http://127.0.0.1:8000"
    out["x402"] = {
        "amount_xlm": X402_AMOUNT_XLM,
        "asset": "native",
        "destination": executor or None,
        "flow": "POST /execute/stream without payment header → 402 → pay → retry with X-Stellar-Payment-Tx",
        "prepare_unsigned_transaction": f"{fallback_base}/api/x402/prepare-payment",
    }

    return out


def ipfs_http_url(cid: str) -> str:
    cid = (cid or "").strip()
    if cid.startswith("http://") or cid.startswith("https://"):
        return cid
    if cid.startswith("ipfs://"):
        cid = cid[7:].lstrip("/")
    gateway = (os.getenv("IPFS_GATEWAY") or "https://ipfs.io").rstrip("/")
    return f"{gateway}/ipfs/{cid}"


async def fetch_json_from_ipfs(cid: str) -> dict | None:
    url = ipfs_http_url(cid)
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return None
            return r.json()
    except Exception:
        return None
