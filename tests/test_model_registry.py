"""
Regression Test: Model Registration & Startup Mapper Initialization.

Verifies in a fresh subprocess (independent of test fixtures / conftest model imports)
that importing `app.main` registers all SQLAlchemy models and allows `configure_mappers()`
to resolve all model relationships without raising `sqlalchemy.exc.InvalidRequestError`.
"""

import subprocess
import sys


def test_models_registered_on_app_import_subprocess() -> None:
    """
    Spawns a clean Python subprocess that imports app.main and calls configure_mappers().
    This ensures that when the app starts in Docker/production, all relationships
    (e.g., User -> EmailVerificationToken) resolve without relying on test fixture imports.
    """
    cmd = [
        sys.executable,
        "-c",
        "import app.main; from sqlalchemy.orm import configure_mappers; configure_mappers()",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    assert result.returncode == 0, (
        f"Mapper configuration failed on app.main import in fresh subprocess:\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )
