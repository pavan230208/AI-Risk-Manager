import os

# Ensure the test suite always runs in a controlled development environment,
# regardless of what the user's local .env file contains.
# This prevents production fail-closed invariants from breaking test collection.
os.environ["ENVIRONMENT"] = os.environ.get("PYTEST_ENVIRONMENT", "test")

if os.environ["ENVIRONMENT"] == "test":
    os.environ["EVENT_BUS_BACKEND"] = "inmemory"
    os.environ["USE_FAKEREDIS"] = "1"
    os.environ["JWT_SECRET"] = "super_secret_for_tests_that_is_long_enough"
    os.environ["API_KEY"] = "test_api_key"
