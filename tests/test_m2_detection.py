
import pandas as pd
import pytest

from modules.vegetation.detection import (
    detect_negative_changes,
)


def sample_thresholds():
    return pd.DataFrame([
        {
            "vegetation_class": "Pine",
            "ndvi_threshold": -0.02,
            "ndmi_threshold": -0.03,
        }
    ])


def sample_patches():
    return pd.DataFrame([
        {
            "patch_id": "P1",
            "vegetation_class": "Pine",
            "ndvi_anomaly": -0.04,
            "ndmi_anomaly": -0.01,
            "anomaly_eligible": True,
        },
        {
            "patch_id": "P2",
            "vegetation_class": "Pine",
            "ndvi_anomaly": 0.01,
            "ndmi_anomaly": 0.02,
            "anomaly_eligible": True,
        },
        {
            "patch_id": "P3",
            "vegetation_class": "Pine",
            "ndvi_anomaly": -0.10,
            "ndmi_anomaly": -0.10,
            "anomaly_eligible": False,
        },
        {
            "patch_id": "P4",
            "vegetation_class": "Unknown",
            "ndvi_anomaly": -0.10,
            "ndmi_anomaly": -0.10,
            "anomaly_eligible": True,
        },
        {
            "patch_id": "P5",
            "vegetation_class": "Pine",
            "ndvi_anomaly": None,
            "ndmi_anomaly": -0.10,
            "anomaly_eligible": True,
        },
    ])


def test_negative_change_detected():
    result = detect_negative_changes(
        sample_patches(), sample_thresholds()
    )

    p1 = result.set_index("patch_id").loc["P1"]

    assert bool(p1["anomaly_detected"]) is True
    assert p1["detection_status"] == "negative_change_flagged"


def test_normal_patch_not_flagged():
    result = detect_negative_changes(
        sample_patches(), sample_thresholds()
    )

    p2 = result.set_index("patch_id").loc["P2"]

    assert bool(p2["anomaly_detected"]) is False
    assert p2["detection_status"] == "not_flagged"


def test_ineligible_patch_not_evaluated():
    result = detect_negative_changes(
        sample_patches(), sample_thresholds()
    )

    p3 = result.set_index("patch_id").loc["P3"]

    assert pd.isna(p3["anomaly_detected"])
    assert p3["detection_status"] == "not_evaluated"


def test_unknown_class_not_evaluated():
    result = detect_negative_changes(
        sample_patches(), sample_thresholds()
    )

    p4 = result.set_index("patch_id").loc["P4"]

    assert pd.isna(p4["anomaly_detected"])
    assert p4["detection_status"] == "not_evaluated"


def test_missing_measurement_not_evaluated():
    result = detect_negative_changes(
        sample_patches(), sample_thresholds()
    )

    p5 = result.set_index("patch_id").loc["P5"]

    assert pd.isna(p5["anomaly_detected"])
    assert p5["detection_status"] == "not_evaluated"


def test_duplicate_patch_ids_rejected():
    patches = sample_patches()
    patches.loc[1, "patch_id"] = "P1"

    with pytest.raises(ValueError):
        detect_negative_changes(
            patches, sample_thresholds()
        )


def test_duplicate_threshold_classes_rejected():
    thresholds = pd.concat(
        [sample_thresholds(), sample_thresholds()],
        ignore_index=True,
    )

    with pytest.raises(ValueError):
        detect_negative_changes(
            sample_patches(), thresholds
        )
