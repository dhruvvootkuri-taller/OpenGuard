"""Use Case: Analyze a single MP4 camera-feed frame.

Frames arrive one at a time as a simulated live feed plays in the browser.
Each frame is assessed *independently and in real time* — we never wait for
the whole clip. The "is this an emergency?" verdict is delegated to the
``VisionAnalyzerPort`` (Claude vision underneath). Only when an emergency is
confirmed do we create, persist, publish and possibly escalate a
``SecurityEvent``.

Severity remains a domain decision: the vision model's threat score is fed
through ``ThreatAssessmentService`` / ``ThreatLevel.from_score`` and we take
the **max** of the score-derived severity and any severity implied by the
flagged detection box, so a confidently-flagged weapon is never under-rated.

**False-alarm gating.** Vision verdicts on ambiguous frames are stochastic, so
a single flagged frame is *not* trusted. Two gates run before anything becomes
an event:

  1. *Threshold gate* — the model's ``confidence`` and ``threat_score`` must
     both clear configurable minimums. A weaker flag is surfaced as a
     low-severity **candidate** only (never an event, never a call).
  2. *Confirmation gate* — the same emergency label on the same camera must
     recur across a confirmation window (M of the last K flagged frames) via
     ``DetectionConfirmationPort`` before a ``SecurityEvent`` is created and
     escalation is enqueued. Until then it stays a candidate.
"""

from __future__ import annotations

from src.application.dtos.detection_dtos import (
    AnalyzeFrameInputDTO,
    AnalyzeFrameOutputDTO,
)
from src.application.mappers.security_event_mapper import SecurityEventMapper
from src.application.ports.detection_confirmation_port import (
    DetectionConfirmationPort,
)
from src.application.ports.event_publisher_port import EventPublisherPort
from src.application.ports.task_queue_port import TaskQueuePort
from src.application.ports.vision_analyzer_port import VisionAnalyzerPort
from src.domain.entities.security_event import SecurityEvent
from src.domain.repositories.security_event_repository import (
    SecurityEventRepository,
)
from src.domain.services.threat_assessment_service import ThreatAssessmentService
from src.domain.value_objects.detection_box import DetectionBox
from src.domain.value_objects.threat_level import ThreatLevel


class AnalyzeFeedFrameUseCase:
    """Assess one camera frame; raise a SecurityEvent on a confirmed emergency."""

    def __init__(
        self,
        vision_analyzer: VisionAnalyzerPort,
        repository: SecurityEventRepository,
        threat_service: ThreatAssessmentService,
        publisher: EventPublisherPort,
        task_queue: TaskQueuePort,
        confirmation: DetectionConfirmationPort,
        min_confidence: float = 0.6,
        min_threat_score: float = 0.4,
    ) -> None:
        self._vision = vision_analyzer
        self._repository = repository
        self._threat_service = threat_service
        self._publisher = publisher
        self._task_queue = task_queue
        self._confirmation = confirmation
        self._min_confidence = min_confidence
        self._min_threat_score = min_threat_score

    async def execute(self, dto: AnalyzeFrameInputDTO) -> AnalyzeFrameOutputDTO:
        # 1. Delegate the emergency verdict to the vision model. A provider
        #    failure (bad key / retired model) raises VisionAnalyzerError and
        #    propagates — it is never silently treated as "all clear".
        assessment = await self._vision.assess_frame(
            image_base64=dto.image_base64,
            media_type=dto.media_type,
            is_armed_zone=dto.is_armed_zone,
            zone=dto.zone,
        )

        # 2. No emergency -> nothing is persisted; playback continues uninterrupted.
        if not assessment.is_emergency:
            return AnalyzeFrameOutputDTO(
                camera_id=dto.camera_id,
                is_emergency=False,
                label=assessment.label,
                summary=assessment.summary,
                event=None,
            )

        # 2a. THRESHOLD GATE. A single ambiguous frame must clear BOTH the
        #     confidence and threat-score minimums before it counts. A weaker
        #     flag is a low-severity *candidate* only — no event, no call.
        if (
            assessment.confidence < self._min_confidence
            or assessment.threat_score < self._min_threat_score
        ):
            return AnalyzeFrameOutputDTO(
                camera_id=dto.camera_id,
                is_emergency=False,
                label=assessment.label,
                summary=assessment.summary,
                event=None,
                is_candidate=True,
                candidate_reason=(
                    "below threshold "
                    f"(confidence {assessment.confidence:.2f} < "
                    f"{self._min_confidence:.2f} or "
                    f"threat_score {assessment.threat_score:.2f} < "
                    f"{self._min_threat_score:.2f})"
                ),
            )

        # 2b. CONFIRMATION GATE. Record this above-threshold hit and require the
        #     same emergency to persist across the window before we treat it as
        #     real. Until confirmed it stays a candidate — never an event/call.
        confirmed = self._confirmation.record_and_check(
            camera_id=dto.camera_id, label=assessment.label
        )
        if not confirmed:
            return AnalyzeFrameOutputDTO(
                camera_id=dto.camera_id,
                is_emergency=False,
                label=assessment.label,
                summary=assessment.summary,
                event=None,
                is_candidate=True,
                candidate_reason=(
                    "awaiting multi-frame confirmation "
                    f"({assessment.label!r} not yet sustained on "
                    f"{dto.camera_id})"
                ),
            )

        # 3. Build the detection box(es) the model flagged. Fall back to a
        #    full-frame box so a SecurityEvent always has at least one box.
        box = assessment.box or DetectionBox(
            label=assessment.label,
            confidence=assessment.confidence,
            x=0.0,
            y=0.0,
            width=1.0,
            height=1.0,
        )
        detections = [box]

        # 4. Severity is a domain decision: take the max of the score-derived
        #    severity and any severity the domain service derives from the box.
        score_level = ThreatLevel.from_score(
            score=assessment.threat_score, confidence=assessment.confidence
        )
        domain_level = self._threat_service.assess(
            detections=detections, is_armed_zone=dto.is_armed_zone
        )
        threat_level = max(
            (score_level, domain_level), key=lambda level: level.severity
        )

        # 5. Create + persist the event before any slow escalation work.
        event = SecurityEvent(
            camera_id=dto.camera_id,
            threat_level=threat_level,
            detections=detections,
            description=assessment.summary,
        )
        event.mark_analyzing()
        await self._repository.save(event)
        event_dto = SecurityEventMapper.to_dto(event)
        await self._publisher.publish_event(event_dto)

        # 6. Offload escalation when the domain decides a human must be alerted.
        if event.requires_human_escalation():
            self._task_queue.enqueue_escalation(event.id)

        # 7. Clear the confirmation window now an event exists for this camera,
        #    so a future incident must independently re-confirm.
        self._confirmation.reset(dto.camera_id)

        return AnalyzeFrameOutputDTO(
            camera_id=dto.camera_id,
            is_emergency=True,
            label=assessment.label,
            summary=assessment.summary,
            event=event_dto,
        )
