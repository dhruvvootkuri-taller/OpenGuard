"""Domain tests — pure, no infrastructure required."""

from src.domain.services.threat_assessment_service import ThreatAssessmentService
from src.domain.value_objects.detection_box import DetectionBox
from src.domain.value_objects.threat_level import ThreatSeverity


def _box(label: str, confidence: float = 0.9) -> DetectionBox:
    return DetectionBox(
        label=label, confidence=confidence, x=0.1, y=0.1, width=0.2, height=0.3
    )


def test_no_detections_is_info_level():
    service = ThreatAssessmentService()
    level = service.assess(detections=[], is_armed_zone=False)
    assert level.severity == ThreatSeverity.INFO


def test_weapon_is_always_critical():
    service = ThreatAssessmentService()
    level = service.assess(detections=[_box("knife")], is_armed_zone=False)
    assert level.severity == ThreatSeverity.CRITICAL


def test_armed_zone_amplifies_person():
    service = ThreatAssessmentService()
    base = service.assess(detections=[_box("person")], is_armed_zone=False)
    armed = service.assess(detections=[_box("person")], is_armed_zone=True)
    assert armed.severity >= base.severity
