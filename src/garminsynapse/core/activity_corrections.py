"""Orchestrates the outlier preview/apply workflow: download FIT -> detect ->
(optionally) correct -> back up original -> delete + re-upload corrected FIT.

This is intentionally decoupled from `core.api.GarminAPI` (duck-typed `api`
param) so it can be unit-tested with a plain mock, and reused identically
from the CLI, Web routes, and MCP tools.
"""
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from garminsynapse.core.fit_editor import load_fit
from garminsynapse.core.outlier_detectors import apply_corrections as apply_detector_corrections
from garminsynapse.core.outlier_detectors import run_all_detectors

logger = logging.getLogger(__name__)

DEFAULT_BACKUP_DIR = Path.cwd() / "garmin_files" / "backups"


def preview_corrections(api, activity_id: int) -> Dict[str, Any]:
    """Download the activity's FIT file and report detected outliers WITHOUT
    modifying or uploading anything."""
    raw = api.download_activity_fit(activity_id)
    activity = load_fit(raw)
    findings = run_all_detectors(activity.records, sport=activity.sport())
    return {
        "activity_id": activity_id,
        "sport": activity.sport(),
        "record_count": len(activity.records),
        "findings": [f.to_dict() for f in findings],
    }


def apply_corrections(
    api,
    activity_id: int,
    confirm: bool = False,
    backup_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Correct detected outliers and replace the activity on Garmin Connect.

    This is destructive: the original activity is deleted and a new one is
    uploaded in its place (new activity ID; comments/kudos on the original
    are lost). Requires `confirm=True` to be passed explicitly by the
    caller -- callers (CLI/Web/MCP) are expected to have already shown the
    user a `preview_corrections` result and obtained their consent.
    """
    if not confirm:
        raise ValueError(
            "apply_corrections requires confirm=True. Call preview_corrections "
            "first and obtain explicit user confirmation before applying."
        )

    raw = api.download_activity_fit(activity_id)
    activity = load_fit(raw)
    findings = run_all_detectors(activity.records, sport=activity.sport())

    if not findings:
        return {
            "activity_id": activity_id,
            "applied": False,
            "reason": "no outliers detected",
            "findings": [],
        }

    apply_detector_corrections(activity.records, findings)
    data, report = activity.encode()

    target_dir = Path(backup_dir) if backup_dir else DEFAULT_BACKUP_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = target_dir / f"{activity_id}_{timestamp}.fit"
    backup_path.write_bytes(raw)
    logger.info(f"Backed up original activity {activity_id} FIT to {backup_path}")

    api.delete_activity(str(activity_id))

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".fit", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        upload_result = api.upload_activity(tmp_path)
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)

    return {
        "activity_id": activity_id,
        "applied": True,
        "findings": [f.to_dict() for f in findings],
        "backup_path": str(backup_path),
        "encode_report": {
            "dropped_mesg_counts": report.dropped_mesg_counts,
            "summary": report.summary(),
        },
        "upload_result": upload_result,
    }
