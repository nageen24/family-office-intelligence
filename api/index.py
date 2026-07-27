"""Vercel Python serverless entry — exposes the FastAPI ASGI app.

Vercel's @vercel/python builder serves the module-level `app`; vercel.json routes
every path here, so this one function serves both the UI (/) and /answer.
"""
import os
import sys

# make the repo root importable (rag/, frontend/ live one level up)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag.api import app  # noqa: E402,F401
