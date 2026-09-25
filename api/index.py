"""Vercel Python entrypoint.

Vercel treats files under ``api/`` as serverless functions. This module exposes
the ASGI ``app`` object so Vercel can invoke the FastAPI application.
"""

import os
import sys

# Make the sibling ``app`` package importable when Vercel runs this file.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app  # noqa: E402,F401

__all__ = ["app"]
