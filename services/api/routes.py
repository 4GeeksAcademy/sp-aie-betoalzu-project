"""Backwards-compatible re-exports for the old routes module.

All endpoints have been moved to their respective packages:
  - Incident-analyzer endpoints  -> services/api/incident_analyzer/routes.py
  - Supplier endpoints            -> services/api/suppliers/routes.py
"""

from __future__ import annotations

from services.api.incident_analyzer.routes import incidents_api

__all__ = ["incidents_api"]