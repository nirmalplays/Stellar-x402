# Stellar x402 / Stellarpay Executor

Python **FastAPI** service that streams **Docker** job output (sandboxed containers), plus **Soroban** tooling for an on-chain **agent registry** contract (Rust in `contracts/registry/`).

Use this README as the **run order**. All commands assume the **inner** project folder (the one that contains `api/`, `scripts/`, and `contracts/`):

```text
Stellar-x402-main/Stellar-x402-main/
```

If your download has an extra outer `Stellar-x402-main` wrapper, `cd` into the inner one before running anything.

---

## What each part does

| Piece | Role |
|--------|------|
| `scripts/setup_accounts.py` | Creates **DEPLOYER** and **EXECUTOR** keypairs and funds them on **Stellar testnet** via Friendbot; writes **`/.env`** in the project root. |
| `contracts/registry/` | Soroban smart contract: `register_agent`, `get_agent`, etc. You build and deploy it, then put the contract id in **`REGISTRY_CONTRACT_ID`**. |
| `scripts/registry_client.py` | Python client for that contract (RPC health check + optional `register_agent` / `get_agent`). |
| `scripts/diagnostic_docker.py` | Verifies Docker + the same runner the API uses (streaming + OOM behavior). |
| `api/` | FastAPI app: `POST /execute/stream` runs a container and streams logs as **SSE**. |
| `docker-compose.yml` | Starts **Redis** on port 6379. The current API code does **not** use Redis yet; safe to skip unless you extend the app. |
| `tests/` | **pytest** suite. Tests that need Docker are marked and **auto-skip** when Docker Engine is not running. |

---

## Prerequisites

- **Python 3.11+** (3.12 works)
- **Docker Desktop** (or Docker Engine) — required for `/execute/stream` and Docker-related tests
- **Stellar testnet** access (HTTPS) for scripts and contract work
- **Optional (registry on-chain):** [Rust](https://rustup.rs/), [Stellar CLI](https://developers.stellar.org/docs/tools/developer-tools) (`stellar`) with Soroban support, matching the contract’s `soroban-sdk` version (~22)

---

## Recommended run order

### 1) Install Python dependencies

```powershell
cd path\to\Stellar-x402-main\Stellar-x402-main
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2) Create testnet accounts and `.env`

```powershell
python scripts/setup_accounts.py
```

This writes **`Stellar-x402-main/Stellar-x402-main/.env`**. If `.env` already had `REGISTRY_CONTRACT_ID` or `GEMINI_API_KEY`, those values are **kept**; new keys are generated for deployer/executor.

**Optional:** copy `.env.example` to `.env` and fill values by hand instead.

### 3) Build and deploy the registry contract (optional but needed for `REGISTRY_CONTRACT_ID`)

From the [Stellar Soroban docs](https://developers.stellar.org/docs/tools/developer-tools), install **`stellar`**, then:

```powershell
cd contracts\registry
stellar contract build
```

Deploy using a funded account (use the **DEPLOYER** secret from `.env` or configure a `stellar` identity). The CLI prints a **contract id** (starts with `C...`). Put it in `.env`:

```env
REGISTRY_CONTRACT_ID=CXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

Exact `stellar contract deploy` flags depend on your CLI version; follow the official deploy flow and use the `.wasm` path printed after `stellar contract build`.

### 4) Verify Stellar / RPC and client wiring

```powershell
cd ..\..
python scripts\registry_client.py
```

You should see **Soroban RPC health**. If `REGISTRY_CONTRACT_ID` is set and funded, you can uncomment or add calls in that file for `register_agent` / `get_agent`.

### 5) Verify Docker (before relying on the API)

With Docker running:

```powershell
python scripts\diagnostic_docker.py
```

### 6) Optional: Redis via Compose

```powershell
docker compose up -d
```

### 7) Run the HTTP API

```powershell
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

- API root: `http://127.0.0.1:8000`
- OpenAPI: `http://127.0.0.1:8000/docs`
- Execute stream: `POST /execute/stream` with a JSON body like:

```json
{
  "task": "demo",
  "input": {},
  "agent_id": "agent-1",
  "image": "python:3.11-slim",
  "cmd": "python -c \"print('hello')\""
}
```

### 8) Tests

```powershell
python -m pytest tests/ -v
```

With Docker running, Docker-marked tests execute; without Docker they **skip** (exit code still 0).

To run **only** Docker integration tests when Docker is up:

```powershell
python -m pytest tests/ -v -m docker
```

---

## Environment variables

See **`.env.example`**. Important keys:

- **`DEPLOYER_SECRET` / `EXECUTOR_SECRET`** — set by `setup_accounts.py` or manually.
- **`REGISTRY_CONTRACT_ID`** — Soroban contract id after deploy.
- **`SOROBAN_RPC_URL` / `HORIZON_URL`** — default to public testnet endpoints.
- **`GEMINI_API_KEY`** — optional; for Google Gemini if you add LLM features (dependency: `google-generativeai`).

`scripts/registry_client.py` loads **project `.env`**, then optionally a **parent-directory `.env`** (same file name) so a wrapper folder layout still works.

---

## Troubleshooting

- **`Docker daemon not available`**: start Docker Desktop; wait until it is fully running.
- **`REGISTRY_CONTRACT_ID` missing**: deploy the contract (step 3) or leave registry calls disabled; health check still works.
- **Friendbot failures**: try again later; testnet faucets can rate-limit.
- **Import errors when running scripts**: always run from the **inner** project root, or use `python -m pytest` / `python -m uvicorn` as above so imports resolve.

---

## License / upstream

Refer to the repository you cloned for license and attribution.
