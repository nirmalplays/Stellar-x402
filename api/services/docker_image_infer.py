"""Pick an allowlisted Docker image from the task description + command when image is ``auto``."""

from __future__ import annotations

import re

# Natural-language hints in TASK_DESCRIPTION (checked first), then command.
_BROWSER_TASK = (
    "playwright",
    "puppeteer",
    "selenium",
    "headless browser",
    "browser automation",
    "headless chrome",
    "chromium",
    "open a browser",
    "in the browser",
    "using a browser",
    "take a screenshot",
    "screenshot of",
    "visit the url",
    "visit this url",
    "navigate to",
    "load the page",
    "web page",
    "scrape the site",
    "scrape this",
)

_NODE_TASK = (
    "node.js",
    "javascript",
    "typescript",
    "npm install",
    "npm run",
    "npx ",
    "yarn ",
    "pnpm ",
    "bun ",
    "react app",
    "react ",
    "next.js",
    "vite",
    "webpack",
    "express",
    "nestjs",
    "jest",
    "mocha",
)

_PYTHON_TASK = (
    "python script",
    "python ",
    "pip install",
    "django",
    "flask",
    "fastapi",
    "pandas",
    "jupyter",
    "pytest",
    "numpy",
)

_ALPINE_TASK = (
    "apk add",
    "alpine linux",
    "minimal image with apk",
    "only apk",
)


def _is_auto_image(explicit: str | None) -> bool:
    s = (explicit or "").strip().lower()
    return not s or s in ("auto", "automatic", "infer", "default")


def _contains_any(hay: str, needles: tuple[str, ...]) -> bool:
    return any(n in hay for n in needles)


def resolve_job_image(
    *,
    cmd: str,
    task: str = "",
    network_enabled: bool = False,
    explicit_image: str | None = None,
) -> str:
    """
    If ``explicit_image`` is a concrete image tag (not auto), return it unchanged.

    Otherwise choose from **allowlisted** images using, in order:
    1. **Task description** (what you are trying to do)
    2. **Command** (how you run it)
    3. ``network_enabled`` (browser / outbound stacks)
    """
    if not _is_auto_image(explicit_image):
        return (explicit_image or "").strip()

    task_l = (task or "").lower()
    cmd_l = (cmd or "").lower()
    # Task first for semantics; command adds technical signals.
    hay = f"{task_l}\n{cmd_l}"

    if network_enabled or _contains_any(hay, _BROWSER_TASK) or any(
        k in hay
        for k in (
            "async_playwright",
            "chromium.launch",
            "webdriver",
        )
    ):
        return "mcr.microsoft.com/playwright/python:v1.45.0-jammy"

    # Prefer task wording for Node vs inferring only from cmd
    if _contains_any(task_l, _NODE_TASK) or re.search(
        r"\b(npx|npm|yarn|pnpm|bun)\b", hay
    ) or re.search(r"(^|\s)node(\s|$)", hay):
        return "node:20-slim"

    if _contains_any(task_l, _ALPINE_TASK) or " apk " in hay or hay.lstrip().startswith(
        "apk "
    ):
        return "alpine:latest"

    if _contains_any(task_l, _PYTHON_TASK) or "pip " in hay or re.search(
        r"\bpython\d?\b", hay
    ):
        return "python:3.11-slim"

    return "python:3.11-slim"
