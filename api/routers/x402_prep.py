"""Unsigned payment transactions so any Stellar account can fund x402 authorization."""

from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from stellar_sdk import Asset, Keypair, Network, Server, TransactionBuilder

router = APIRouter(prefix="/api/x402", tags=["x402"])


class PreparePaymentBody(BaseModel):
    source_public_key: str = Field(..., min_length=3, description="Account G... that will sign and submit the payment")


@router.post("/prepare-payment")
async def prepare_payment(body: PreparePaymentBody):
    source = body.source_public_key.strip()
    executor_pk = (os.getenv("EXECUTOR_PUBLIC_KEY") or "").strip()
    if not executor_pk:
        raise HTTPException(status_code=503, detail="EXECUTOR_PUBLIC_KEY is not configured")

    try:
        Keypair.from_public_key(source)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid source_public_key (expect Stellar G-address)")

    horizon_url = os.getenv("HORIZON_URL", "https://horizon-testnet.stellar.org")
    passphrase = Network.TESTNET_NETWORK_PASSPHRASE

    def _build() -> str:
        server = Server(horizon_url)
        source_account = server.load_account(source)
        return (
            TransactionBuilder(source_account, passphrase)
            .append_payment_op(executor_pk, Asset.native(), "0.05")
            .set_timeout(60)
            .build()
            .to_xdr()
        )

    try:
        xdr_b64 = await asyncio.to_thread(_build)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot build payment transaction: {e}") from e

    return {
        "transaction_xdr": xdr_b64,
        "network": "TESTNET",
        "network_passphrase": passphrase,
        "horizon_url": horizon_url,
        "payment": {
            "amount": "0.05",
            "asset": "native",
            "destination": executor_pk,
        },
        "next_steps": [
            "Sign `transaction_xdr` with the source account (Freighter, Albedo, or stellar-cli).",
            "Submit the signed transaction to Horizon.",
            "Call POST /execute/stream with header X-Stellar-Payment-Tx set to the submitted transaction hash.",
        ],
    }
