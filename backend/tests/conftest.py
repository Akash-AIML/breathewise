import os

import pytest

# Default unit/adversarial tests must never depend on real credentials or live
# provider availability. Live-provider checks are opt-in via RUN_LIVE_TESTS=1;
# when opted in, keys from the local .env must remain visible to those tests.
if os.getenv("RUN_LIVE_TESTS") != "1":
    os.environ["DATA_GOV_IN_API_KEY"] = ""
    os.environ["OPENAQ_API_KEY"] = ""
    os.environ["GROQ_API_KEY"] = ""
    os.environ["GEMINI_API_KEY"] = ""


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Skip live/integration checks unless the caller explicitly opts in."""
    if os.getenv("RUN_LIVE_TESTS") == "1":
        return
    skip_integration = pytest.mark.skip(
        reason="Integration tests are opt-in; set RUN_LIVE_TESTS=1 to run them."
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
