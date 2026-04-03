"""Parse Soroban `Agent` struct returned from registry `get_agent` simulation."""

from __future__ import annotations

from typing import Any

from stellar_sdk import Keypair, xdr
from stellar_sdk.xdr.public_key_type import PublicKeyType
from stellar_sdk.xdr.sc_address import SCAddress
from stellar_sdk.xdr.sc_address_type import SCAddressType


def sc_agent_map_to_dict(sc_val: xdr.SCVal) -> dict[str, Any] | None:
    if sc_val.type == xdr.SCValType.SCV_VOID:
        return None
    if sc_val.type != xdr.SCValType.SCV_MAP or sc_val.map is None or not sc_val.map.sc_map:
        return None

    out: dict[str, Any] = {}
    for entry in sc_val.map.sc_map:
        if entry.key.type != xdr.SCValType.SCV_SYMBOL or entry.key.sym is None:
            continue
        key = entry.key.sym.sc_symbol.decode()
        v = entry.val

        if v.type == xdr.SCValType.SCV_BOOL:
            out[key] = bool(v.b)
        elif v.type == xdr.SCValType.SCV_I64 and v.i64 is not None:
            out[key] = int(v.i64.int64)
        elif v.type == xdr.SCValType.SCV_STRING and v.str is not None:
            out[key] = v.str.sc_string.decode()
        elif v.type == xdr.SCValType.SCV_ADDRESS and v.address is not None:
            out[key] = _sc_address_to_g_address(v.address)
        else:
            out[key] = None

    return out if out else None


def _sc_address_to_g_address(addr: SCAddress) -> str | None:
    if addr.type != SCAddressType.SC_ADDRESS_TYPE_ACCOUNT:
        return None
    if addr.account_id is None or addr.account_id.account_id is None:
        return None
    pk = addr.account_id.account_id
    if pk.type != PublicKeyType.PUBLIC_KEY_TYPE_ED25519 or pk.ed25519 is None:
        return None
    raw = pk.ed25519.uint256
    return Keypair.from_raw_ed25519_public_key(raw).public_key
