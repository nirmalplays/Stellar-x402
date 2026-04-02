import asyncio
import queue
import queue as queue_module
import threading
import time
from typing import AsyncGenerator

import docker
from docker.errors import APIError, ImageNotFound

_LOG_END = object()
_LOG_NO_CHUNK = object()


class DockerRunner:
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception as e:
            print(f"Failed to connect to Docker daemon: {e}")
            self.client = None
        self._lifecycle_lock = threading.Lock()

    async def run(self, image: str, cmd: str, timeout: int = 30) -> AsyncGenerator[str, None]:
        if not self.client:
            yield "[ERROR] Docker daemon not available."
            return

        # Fresh client per run avoids thread-safety issues when many runs overlap (asyncio.gather).
        client = docker.from_env()

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
                container = client.containers.create(
                    image=image,
                    command=cmd,
                    network_disabled=True,
                    mem_limit="256m",
                    nano_cpus=int(0.5 * 1e9),
                    pids_limit=64,
                    read_only=True,
                    security_opt=["no-new-privileges"],
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
                except queue_module.Empty:
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
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass
            try:
                client.close()
            except Exception:
                pass


docker_runner = DockerRunner()
