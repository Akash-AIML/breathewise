import os

# Default unit/adversarial tests must never depend on real credentials or live
# provider availability. Live-provider checks are opt-in via RUN_LIVE_TESTS=1;
# when opted in, keys from the local .env must remain visible to those tests.
if os.getenv("RUN_LIVE_TESTS") != "1":
    os.environ["DATA_GOV_IN_API_KEY"] = ""
    os.environ["OPENAQ_API_KEY"] = ""
    os.environ["GROQ_API_KEY"] = ""
    os.environ["GEMINI_API_KEY"] = ""
