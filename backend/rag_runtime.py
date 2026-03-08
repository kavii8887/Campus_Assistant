"""
rag_runtime.py — Compatibility shim
=====================================
All logic has moved to the runtime/ package:

  runtime/routing.py              — query classification
  runtime/structured_handlers.py — deterministic answers
  runtime/semantic_engine.py     — LLM-backed answers
  runtime/department_router.py   — dept resource management
  runtime/runtime_engine.py      — AcademicRAGSystem (orchestrator)
  runtime/cli_interface.py        — InteractiveInterface + main()

This file re-exports AcademicRAGSystem and InteractiveInterface so that
any existing code doing:

    from rag_runtime import AcademicRAGSystem

continues to work without changes.

Version: 5.0 (modular refactor)
"""

# Re-export primary classes
from runtime_engine import AcademicRAGSystem
from cli_interface import InteractiveInterface, main


__all__ = ["AcademicRAGSystem", "InteractiveInterface", "main"]