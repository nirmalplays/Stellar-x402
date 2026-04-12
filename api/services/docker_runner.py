import asyncio
import os
import queue
import threading
import time
from typing import AsyncGenerator

import docker
from docker.errors import APIError, ImageNotFound

_LOG_END = object()
_LOG_NO_CHUNK = object()

# ---------------------------------------------------------------------------
# Image allowlist — only these images can be run as jobs.
# To add more, extend this set or set DOCKER_ALLOWED_IMAGES in .env
# (comma-separated list, e.g. "python:3.11-slim,node:20-slim").
# In dev mode (REGISTRY_BYPASS_DEV=true), the allowlist is still enforced.
# To disable the allowlist entirely (NOT recommended for production),
# set DOCKER_DISABLE_ALLOWLIST=true.
# ---------------------------------------------------------------------------
_DEFAULT_ALLOWED_IMAGES = {
    "python:3.11-slim",
    "python:3.11",
    "python:3.12-slim",
    "python:3.12",
    "node:20-slim",
    "node:20",
    "alpine:latest",
    "alpine:3.19",
    "ubuntu:22.04",
    "ubuntu:24.04",
    "busybox:latest",
    "mcr.microsoft.com/playwright:v1.43.0-jammy",
    "mcr.microsoft.com/playwright:v1.44.0-jammy",
}


def _get_allowed_images() -> set[str]:
    """Returns the set of allowed images from env or defaults."""
    env_val = os.getenv("DOCKER_ALLOWED_IMAGES", "").strip()
    if env_val:
        extras = {img.strip() for img in env_val.split(",") if img.strip()}
        return _DEFAULT_ALLOWED_IMAGES | extras
    return _DEFAULT_ALLOWED_IMAGES


def _allowlist_disabled() -> bool:
    v = os.getenv("DOCKER_DISABLE_ALLOWLIST", "").strip().lower()
    return v in ("1", "true", "yes")


def _image_allowed(image: str) -> bool:
    if _allowlist_disabled():
        return True
    return image.strip() in _get_allowed_images()


def _simulation_allowed() -> bool:
    v = os.getenv("ALLOW_DOCKER_SIMULATION", "").strip().lower()
    return v in ("1", "true", "yes")


def _keep_job_container() -> bool:
    """If true, do not remove the job container after run (easier to see in Docker Desktop). Dev only."""
    v = os.getenv("DOCKER_KEEP_CONTAINERS", "").strip().lower()
    return v in ("1", "true", "yes")


def _get_agent_secrets(agent_id: str) -> dict[str, str]:
    """
    Loads secrets for an agent from `secrets/<agent_id>.env`.
    Returns a dict of key-value pairs.
    """
    secrets = {}
    if not agent_id:
        return secrets
    
    # Root dir is typically where the app runs
    secrets_dir = os.path.join(os.getcwd(), "secrets")
    secret_file = os.path.join(secrets_dir, f"{agent_id}.env")

    if os.path.exists(secret_file):
        try:
            with open(secret_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        secrets[parts[0].strip()] = parts[1].strip()
        except Exception as e:
            print(f"Error loading secrets for {agent_id}: {e}")
    return secrets


class DockerRunner:
    def __init__(self):
        # We don't store a persistent client because it's not thread-safe for many overlapping runs.
        # We only check once if Docker is available to avoid spamming errors if it's down.
        self._initial_check_done = False
        self._docker_available = False
        self._lifecycle_lock = threading.Lock()

    def _check_docker(self) -> bool:
        try:
            client = docker.from_env()
            client.ping()
            client.close()
            return True
        except Exception:
            return False

    async def run(
        self,
        image: str,
        cmd: str,
        timeout: int = 30,
        allow_network: bool = False,
        allow_browser: bool = False,
        agent_id: str = None,
    ) -> AsyncGenerator[str, None]:
        # Check image allowlist before doing anything else
        if not _image_allowed(image):
            allowed = sorted(_get_allowed_images())
            yield f"[ERROR] Image '{image}' is not in the allowlist. Allowed images: {', '.join(allowed)}"
            return

        # Try to connect.
        try:
            client = docker.from_env()
            client.ping()  # Verify actual connectivity
        except Exception as e:
            if _simulation_allowed():
                yield f"[WARN] Docker daemon not available: {e}"
                yield "> [SIMULATION] Entering mock execution environment..."
                await asyncio.sleep(1)
                yield f"> [SIMULATION] Running command: {cmd}"
                await asyncio.sleep(2)
                yield "SUCCESS: Mock execution completed."
                return
            yield f"[ERROR] Docker is required but the daemon is not reachable: {e}"
            return

        container = None
        timed_out = False
        log_q: queue.Queue[object] = queue.Queue()

        def pump_logs(iterator):
            try:
                for chunk in iterator:
                    log_q.put(chunk)
            except Exception as e:
                log_q.put(e)
            finally:
                log_q.put(_LOG_END)

        try:
            with self._lifecycle_lock:
                # Browser automation needs more resources and SHM.
                # If network is requested or browser is requested, we enable network.
                network_disabled = not (allow_network or allow_browser)
                shm_size = "1g" if allow_browser else "64m"
                mem_limit = "1g" if allow_browser else "256m"
                pids_limit = 128 if allow_browser else 64
                
                # Load agent secrets from local vault
                env_vars = _get_agent_secrets(agent_id) if agent_id else {}

                container = client.containers.create(
                    image=image,
                    command=cmd,
                    network_disabled=network_disabled,
                    mem_limit=mem_limit,
                    nano_cpus=int(0.5 * 1e9),
                    pids_limit=pids_limit,
                    read_only=True,
                    security_opt=["no-new-privileges"],
                    shm_size=shm_size,
                    environment=env_vars,
                    labels={
                        "stellar-x402.executor-job": "true",
                        "stellar-x402.kind": "docker-runner",
                    },
                )
                container.start()
            start_time = time.time()

            log_iterator = container.logs(stream=True, follow=True)
            threading.Thread(
                target=pump_logs, args=(log_iterator,), daemon=True
            ).start()

            loop = asyncio.get_event_loop()

            def dequeue() -> object:
                try:
                    return log_q.get(timeout=0.5)
                except queue.Empty:
                    return _LOG_NO_CHUNK

            while True:
                if time.time() - start_time > timeout:
                    try:
                        container.kill()
                    except Exception:
                        pass
                    timed_out = True
                    yield f"[TIMEOUT] Execution exceeded {timeout}s limit."
                    break

                try:
                    item = await asyncio.wait_for(
                        loop.run_in_executor(None, dequeue),
                        timeout=0.6,
                    )
                except asyncio.TimeoutError:
                    continue

                if item is _LOG_NO_CHUNK:
                    continue

                if item is _LOG_END:
                    break
                if isinstance(item, Exception):
                    raise item

                line_bytes = item
                text = line_bytes.decode("utf-8", errors="replace").strip()
                if text:
                    for l in text.splitlines():
                        yield l.strip()

            container.reload()
            state = container.attrs["State"]
            exit_code = state["ExitCode"]
            oom_killed = state.get("OOMKilled", False)

            if timed_out:
                pass
            elif oom_killed or exit_code == 137:
                yield "[ERROR] Container killed due to OOM (Out of Memory)."
            elif exit_code != 0 and not state.get("Running"):
                yield f"[ERROR] Process exited with code {exit_code}."

        except ImageNotFound:
            yield f"[ERROR] Image '{image}' not found."
        except APIError as e:
            yield f"[ERROR] Docker API error: {str(e)}"
        except Exception as e:
            yield f"[ERROR] Runtime error: {str(e)}"
        finally:
            if container and not _keep_job_container():
                try:
                    container.remove(force=True)
                except Exception:
                    pass
            try:
                client.close()
            except Exception:
                pass


docker_runner = DockerRunner()