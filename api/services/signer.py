import base64
import hashlib
import json
import os
from typing import Any

from nacl.encoding import HexEncoder
from nacl.signing import SigningKey


class ResultSigner:
    def __init__(self) -> None:
        seed_source = os.getenv("RESULT_SIGNING_SEED") or os.getenv("EXECUTOR_SECRET") or "stellar-x402-dev-signer"
        seed_bytes = hashlib.sha256(seed_source.encode("utf-8")).digest()
        self._signing_key = SigningKey(seed_bytes)

    @property
    def public_key(self) -> str:
        return self._signing_key.verify_key.encode(encoder=HexEncoder).decode("utf-8")

    def sign_payload(self, payload: dict[str, Any]) -> str:
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signed = self._signing_key.sign(serialized)
        return base64.b64encode(signed.signature).decode("utf-8")


result_signer = ResultSigner()
