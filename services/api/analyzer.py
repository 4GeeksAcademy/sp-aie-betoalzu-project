from __future__ import annotations

import importlib.util
from pathlib import Path


_MODULE_PATH = Path(__file__).resolve().parent / "incident-analyzer" / "analyzer.py"
_SPEC = importlib.util.spec_from_file_location("services.api.incident_analyzer_analyzer", _MODULE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Unable to load incident-analyzer module from {_MODULE_PATH}")

_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


VALID_CATEGORIES = _MODULE.VALID_CATEGORIES
VALID_STATUSES = _MODULE.VALID_STATUSES
REQUIRED_HEADERS = _MODULE.REQUIRED_HEADERS
AGENT_PATTERN = _MODULE.AGENT_PATTERN
INVALID_RULE_LABELS = _MODULE.INVALID_RULE_LABELS
SCORE_LABELS = _MODULE.SCORE_LABELS
AnalysisError = _MODULE.AnalysisError
EmptyFileError = _MODULE.EmptyFileError
InvalidCsvFormatError = _MODULE.InvalidCsvFormatError
AnalysisResult = _MODULE.AnalysisResult
analyze_csv_stream = _MODULE.analyze_csv_stream
analyze_csv = _MODULE.analyze_csv
build_summary = _MODULE.build_summary
print_report = _MODULE.print_report
build_metrics_rows = _MODULE.build_metrics_rows
build_metrics_csv = _MODULE.build_metrics_csv
export_metrics = _MODULE.export_metrics
