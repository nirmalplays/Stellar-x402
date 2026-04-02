import pytest


def _docker_available() -> bool:
    try:
        import docker

        client = docker.from_env()
        try:
            client.ping()
            return True
        finally:
            client.close()
    except Exception:
        return False


DOCKER_AVAILABLE = _docker_available()


def pytest_collection_modifyitems(config, items):
    skip = pytest.mark.skip(
        reason="Docker Engine not available (start Docker Desktop to run integration tests)."
    )
    for item in items:
        if item.get_closest_marker("docker"):
            if not DOCKER_AVAILABLE:
                item.add_marker(skip)
