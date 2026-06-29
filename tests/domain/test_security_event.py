import pytest

from src.domain.entities.security_event import SecurityEvent, SecurityEventStatus
from src.domain.exceptions import DomainValidationError
from src.domain.value_objects.detection_box import DetectionBox
from src.domain.value_objects.threat_level import ThreatLevel, ThreatSeverity


def _event(severity: ThreatSeverity = ThreatSeverity.HIGH) -> SecurityEvent:
    return SecurityEvent(
        camera_id="cam-1",
        threat_level=ThreatLevel(severity=severity, confidence=0.9),
        detections=[
            DetectionBox(
                label="person", confidence=0.9, x=0.1, y=0.1, width=0.2, height=0.2
            )
        ],
    )


def test_event_requires_detections():
    with pytest.raises(DomainValidationError):
        SecurityEvent(
            camera_id="cam-1",
            threat_level=ThreatLevel(severity=ThreatSeverity.LOW, confidence=0.5),
            detections=[],
        )


def test_high_threat_requires_escalation():
    assert _event(ThreatSeverity.HIGH).requires_human_escalation() is True
    assert _event(ThreatSeverity.LOW).requires_human_escalation() is False


def test_acknowledge_transition():
    event = _event()
    event.mark_alerting()
    event.acknowledge("operator-42")
    assert event.status == SecurityEventStatus.ACKNOWLEDGED
    assert event.acknowledged_by == "operator-42"


def test_resolve_from_detected_is_allowed():
    """resolve() is allowed from any active state (including freshly DETECTED)."""
    event = _event()
    event.resolve()
    assert event.status == SecurityEventStatus.RESOLVED


def test_invalid_transition_raises():
    """Resolving/dismissing an already-terminal event is the invalid transition."""
    event = _event()
    event.resolve()
    assert event.status == SecurityEventStatus.RESOLVED

    with pytest.raises(DomainValidationError):
        event.resolve()  # cannot resolve an already-resolved event

    with pytest.raises(DomainValidationError):
        event.dismiss()  # cannot dismiss an already-resolved event

    dismissed = _event()
    dismissed.dismiss()
    with pytest.raises(DomainValidationError):
        dismissed.dismiss()  # cannot dismiss an already-dismissed event
