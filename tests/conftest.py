"""Shared test fixtures for TokenMizer."""
import pytest
import tempfile
import shutil
from pathlib import Path


@pytest.fixture
def tmp_storage(tmp_path):
    """Temporary storage directory for graph databases."""
    return str(tmp_path / "storage")


@pytest.fixture
def sample_messages():
    """Sample LLM conversation messages for testing."""
    return [
        {"role": "user", "content": "Build a FastAPI authentication service with JWT"},
        {"role": "assistant", "content": "Decided: Python 3.12 runtime. Creating: api/main.py, api/auth.py. Completed: project scaffold."},
        {"role": "user", "content": "Use bcrypt for password hashing"},
        {"role": "assistant", "content": "Decided: bcrypt for password hashing. Completed: User model in api/models.py. Working on: auth endpoints."},
        {"role": "user", "content": "Login returns 422"},
        {"role": "assistant", "content": "Fixed: 422 error — missing email validation. Updated api/models.py. Need to: add rate limiting."},
    ]


@pytest.fixture
def sample_ground_truth():
    """Ground truth annotations for sample messages."""
    return {
        "completed_tasks": ["project scaffold", "user model", "fix 422 error"],
        "pending_tasks": ["auth endpoints", "rate limiting"],
        "decisions": ["python 3.12", "bcrypt"],
        "files": ["api/main.py", "api/auth.py", "api/models.py"],
    }
