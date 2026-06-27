"""Composition root / DI container.

Infrastructure knows about every concrete class and wires them into the
application use cases. This is the ONLY place where concrete infrastructure
implementations are bound to the application/domain abstractions.
"""

from __future__ import annotations

from functools import cached_property

import redis.asyncio as redis

from src.application.use_cases.acknowledge_event_use_case import (
    AcknowledgeEventUseCase,
)
from src.application.use_cases.analyze_feed_frame_use_case import (
    AnalyzeFeedFrameUseCase,
)
from src.application.use_cases.escalate_event_use_case import (
    EscalateEventUseCase,
)
from src.application.use_cases.list_recent_events_use_case import (
    ListRecentEventsUseCase,
)
from src.application.use_cases.place_emergency_call_use_case import (
    PlaceEmergencyCallUseCase,
)
from src.application.use_cases.process_detection_use_case import (
    ProcessDetectionUseCase,
)
from src.domain.services.threat_assessment_service import ThreatAssessmentService
from src.infrastructure.config.settings import Settings
from src.infrastructure.llm.claude_haiku_client import ClaudeHaikuClient
from src.infrastructure.messaging.redis_event_publisher import RedisEventPublisher
from src.infrastructure.persistence.redis_active_emergency_tracker import (
    RedisActiveEmergencyTracker,
)
from src.infrastructure.persistence.redis_call_record_repository import (
    RedisCallRecordRepository,
)
from src.infrastructure.persistence.redis_emergency_service_repository import (
    RedisEmergencyServiceRepository,
)
from src.infrastructure.persistence.in_memory_detection_confirmation_tracker import (
    InMemoryDetectionConfirmationTracker,
)
from src.infrastructure.persistence.redis_feed_clip_repository import (
    RedisFeedClipRepository,
)
from src.infrastructure.persistence.redis_security_event_repository import (
    RedisSecurityEventRepository,
)
from src.infrastructure.tasks.celery_app import create_celery_app
from src.infrastructure.vision.claude_vision_analyzer import ClaudeVisionAnalyzer
from src.infrastructure.tasks.celery_task_queue import CeleryTaskQueue
from src.infrastructure.telephony.twilio_telephony_client import (
    TwilioTelephonyClient,
)
from src.infrastructure.voice.elevenlabs_conversational_agent import (
    ElevenLabsConversationalAgent,
)
from src.infrastructure.voice.elevenlabs_voice_client import ElevenLabsVoiceClient


class Container:
    """Lazily builds and caches singletons."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()

    @cached_property
    def redis(self) -> "redis.Redis":
        return redis.from_url(self.settings.redis_url)

    @cached_property
    def repository(self) -> RedisSecurityEventRepository:
        return RedisSecurityEventRepository(self.redis)

    @cached_property
    def emergency_service_repository(self) -> RedisEmergencyServiceRepository:
        return RedisEmergencyServiceRepository(self.redis)

    @cached_property
    def feed_clip_repository(self) -> RedisFeedClipRepository:
        return RedisFeedClipRepository(self.redis)

    @cached_property
    def call_record_repository(self) -> RedisCallRecordRepository:
        return RedisCallRecordRepository(self.redis)

    @cached_property
    def active_emergency_tracker(self) -> RedisActiveEmergencyTracker:
        return RedisActiveEmergencyTracker(
            self.redis,
            window_seconds=self.settings.emergency_dedup_window_seconds,
        )

    @cached_property
    def publisher(self) -> RedisEventPublisher:
        return RedisEventPublisher(self.redis)

    @cached_property
    def threat_service(self) -> ThreatAssessmentService:
        return ThreatAssessmentService()

    @cached_property
    def detection_confirmation(self) -> InMemoryDetectionConfirmationTracker:
        return InMemoryDetectionConfirmationTracker(
            window=self.settings.detection_confirmation_window,
            required=self.settings.detection_confirmation_required,
        )

    @cached_property
    def llm(self) -> ClaudeHaikuClient:
        return ClaudeHaikuClient(
            api_key=self.settings.anthropic_api_key,
            model=self.settings.anthropic_model,
        )

    @cached_property
    def vision_analyzer(self) -> ClaudeVisionAnalyzer:
        return ClaudeVisionAnalyzer(
            api_key=self.settings.anthropic_api_key,
            model=self.settings.anthropic_vision_model,
        )

    @cached_property
    def voice(self) -> ElevenLabsVoiceClient:
        return ElevenLabsVoiceClient(
            api_key=self.settings.elevenlabs_api_key,
            voice_id=self.settings.elevenlabs_voice_id,
        )

    @cached_property
    def voice_agent(self) -> ElevenLabsConversationalAgent:
        return ElevenLabsConversationalAgent(
            api_key=self.settings.elevenlabs_api_key,
            agent_id=self.settings.elevenlabs_agent_id,
            phone_number_id=self.settings.elevenlabs_phone_number_id,
        )

    @cached_property
    def telephony(self) -> TwilioTelephonyClient:
        return TwilioTelephonyClient(
            account_sid=self.settings.twilio_account_sid,
            auth_token=self.settings.twilio_auth_token,
            from_number=self.settings.twilio_from_number,
        )

    @cached_property
    def celery_app(self):
        return create_celery_app(self.settings)

    @cached_property
    def task_queue(self) -> CeleryTaskQueue:
        return CeleryTaskQueue(self.celery_app)

    # --- use cases --------------------------------------------------------

    def process_detection_use_case(self) -> ProcessDetectionUseCase:
        return ProcessDetectionUseCase(
            repository=self.repository,
            threat_service=self.threat_service,
            publisher=self.publisher,
            task_queue=self.task_queue,
            active_tracker=self.active_emergency_tracker,
        )

    def analyze_feed_frame_use_case(self) -> AnalyzeFeedFrameUseCase:
        return AnalyzeFeedFrameUseCase(
            vision_analyzer=self.vision_analyzer,
            repository=self.repository,
            threat_service=self.threat_service,
            publisher=self.publisher,
            task_queue=self.task_queue,
            confirmation=self.detection_confirmation,
            min_confidence=self.settings.detection_min_confidence,
            min_threat_score=self.settings.detection_min_threat_score,
            active_tracker=self.active_emergency_tracker,
        )

    def escalate_event_use_case(self) -> EscalateEventUseCase:
        return EscalateEventUseCase(
            repository=self.repository,
            llm=self.llm,
            voice=self.voice,
            telephony=self.telephony,
            publisher=self.publisher,
            on_call_number=self.settings.on_call_number,
        )

    def place_emergency_call_use_case(self) -> PlaceEmergencyCallUseCase:
        return PlaceEmergencyCallUseCase(
            voice_agent=self.voice_agent,
            default_to_number=self.settings.on_call_number,
        )

    def acknowledge_event_use_case(self) -> AcknowledgeEventUseCase:
        return AcknowledgeEventUseCase(
            repository=self.repository,
            active_tracker=self.active_emergency_tracker,
        )

    def list_recent_events_use_case(self) -> ListRecentEventsUseCase:
        return ListRecentEventsUseCase(repository=self.repository)