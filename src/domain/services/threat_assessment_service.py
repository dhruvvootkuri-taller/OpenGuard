"""Domain Service: ThreatAssessmentService.

Holds threat-evaluation logic that does not naturally belong to a single
entity. Pure business rules — no I/O, no external dependencies.
"""

from __future__ import annotations

from src.domain.value_objects.detection_box import DetectionBox
from src.domain.value_objects.threat_level import ThreatLevel


class ThreatAssessmentService:
    """Computes a ThreatLevel from a set of raw detections.

    This is deliberately framework-free: it takes value objects in and
    produces a value object out.
    """

    # Labels that the business considers inherently concerning.
    HIGH_RISK_LABELS = {"person", "weapon", "knife", "gun"}

    def assess(self, detections: list[DetectionBox], is_armed_zone: bool) -> ThreatLevel:
        if not detections:
            return ThreatLevel.from_score(0.0, confidence=1.0)

        max_confidence = max(d.confidence for d in detections)
        risk_hits = [d for d in detections if d.label.lower() in self.HIGH_RISK_LABELS]

        # Base score driven by how many high-risk objects were detected.
        score = 0.1
        if risk_hits:
            best = max(d.confidence for d in risk_hits)
            score = 0.4 + 0.4 * best

        # An armed/restricted zone amplifies the perceived threat.
        if is_armed_zone and risk_hits:
            score = min(1.0, score + 0.2)

        # A detected weapon is always critical.
        if any(d.label.lower() in {"weapon", "knife", "gun"} for d in detections):
            score = max(score, 0.95)

        return ThreatLevel.from_score(score=min(score, 1.0), confidence=max_confidence)
