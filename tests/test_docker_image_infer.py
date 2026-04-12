import pytest

from api.services.docker_image_infer import resolve_job_image


@pytest.mark.parametrize(
    "cmd,task,nw,explicit,want",
    [
        ("python -c 'print(1)'", "", False, None, "python:3.11-slim"),
        ("npm test", "", False, None, "node:20-slim"),
        ("npx foo", "", False, None, "node:20-slim"),
        ("echo hi", "", False, None, "python:3.11-slim"),
        ("", "use playwright", False, None, "mcr.microsoft.com/playwright/python:v1.45.0-jammy"),
        ("sleep 1", "", True, None, "mcr.microsoft.com/playwright/python:v1.45.0-jammy"),
        ("apk add curl", "", False, None, "alpine:latest"),
        ("python -c 'x'", "", False, "python:3.12-slim", "python:3.12-slim"),
        ("npm x", "", False, "auto", "node:20-slim"),
        ("echo ok", "Run npm install and build my React app", False, None, "node:20-slim"),
        ("echo ok", "Take a screenshot using a headless browser", False, None, "mcr.microsoft.com/playwright/python:v1.45.0-jammy"),
        ("echo ok", "Use apk add to install curl in a minimal container", False, None, "alpine:latest"),
        ("echo ok", "Run pandas and matplotlib data analysis", False, None, "python:3.11-slim"),
    ],
)
def test_resolve_job_image(cmd, task, nw, explicit, want):
    assert resolve_job_image(cmd=cmd, task=task, network_enabled=nw, explicit_image=explicit) == want
