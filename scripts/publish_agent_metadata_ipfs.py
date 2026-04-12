#!/usr/bin/env python3
"""
Upload agent_metadata.json to IPFS via Pinata (JWT) and print the CID.

Usage:
  set PINATA_JWT in .env (https://app.pinata.cloud/developers/api-keys)
  python scripts/publish_agent_metadata_ipfs.py

Then register or update the agent on-chain with the printed CID (see README).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def main() -> int:
    jwt = (os.getenv("PINATA_JWT") or "").strip()
    if not jwt:
        print("Set PINATA_JWT in .env (Pinata API JWT).", file=sys.stderr)
        print("Alternative: upload agent_metadata.json manually at https://app.pinata.cloud/ and use the CID.", file=sys.stderr)
        return 1

    meta_path = ROOT / "agent_metadata.json"
    if not meta_path.exists():
        print(f"Missing {meta_path}", file=sys.stderr)
        return 1

    with open(meta_path, encoding="utf-8") as f:
        body = json.load(f)

    url = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
    headers = {"Authorization": f"Bearer {jwt}"}
    payload = {
        "pinataContent": body,
        "pinataMetadata": {"name": "stellar-x402-agent-metadata"},
    }

    with httpx.Client(timeout=60.0) as client:
        r = client.post(url, json=payload, headers=headers)

    if r.status_code != 200:
        print(f"Pinata error {r.status_code}: {r.text}", file=sys.stderr)
        return 1

    data = r.json()
    cid = data.get("IpfsHash")
    if not cid:
        print(data, file=sys.stderr)
        return 1

    print("IPFS CID:", cid)
    print("Gateway URL:", f"https://ipfs.io/ipfs/{cid}")
    print("\nNext: pass this CID as metadata_cid when calling register_agent on the Soroban registry.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
