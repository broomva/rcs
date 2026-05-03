"""Sandbox backends for the SWE-bench-Lite adapter.

Pluggable per Flue's MountableFs pattern: one backend impl ships now, future
backends slot in without changes to `swe_bench.py`.
"""
from .backend import SandboxBackend, SetupError
from .uv_venv import UvVenvBackend

__all__ = ["SandboxBackend", "SetupError", "UvVenvBackend"]
