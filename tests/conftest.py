"""Pytest configuration and shared database fixtures."""

import os
import tempfile
import pytest

from src.database.connection import DatabaseConnectionManager


@pytest.fixture
def temp_db():
    """Provides a temporary file-backed SQLite database initialized with schema."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    
    db_manager = DatabaseConnectionManager(db_path=db_path)
    db_manager.initialize_schema()
    
    yield db_manager
    
    db_manager.close_thread_connection()
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass