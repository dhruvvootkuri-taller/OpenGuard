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
from src.application.use_cases.list_recent_events_use_case import (
    ListRecentEventsUseCase,
)
from src.application.use_cases.process_detection_use_case import (
    ProcessDetectionUseCase,
)
from src.domain.services.threat_assessment_service import ThreatAssessmentService
from src.infrastructure.config.settings import Settings
from src.infrastructure.llm.claude_haiku_client import ClaudeHaikuClient
from src.infrastructure.messaging.redis_event_publisher import RedisEventPublisher
from src.infrastructure.persistence.redis_security_event_repository import (
    RedisSecurityEventRepository,
)
from src.infrastructure.telephony.twilio_telephony_client import (
    TwilioTelephonyClient,
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
    def publisher(self) -> RedisEventPublisher:
        return RedisEventPublisher(self.redis)

    @cached_property
    def threat_service(self) -> ThreatAssessmentService:
        return ThreatAssessmentService()

    @cached_property
    def llm(self) -> ClaudeHaikuClient:
        return ClaudeHaikuClient(
            api_key=self.settings.anthropic_api_key,
            model=self.settings.anthropic_model,
        )

    @cached_property
    def voice(self) -> ElevenLabsVoiceClient:
        return ElevenLabsVoiceClient(
            api_key=self.settings.elevenlabs_api_key,
            voice_id=self.settings.elevenlabs_voice_id,
        )

    @cached_property
    def telephony(self) -> TwilioTelephonyClient:
        return TwilioTelephonyClient(
            account_sid=self.settings.twilio_account_sid,
            auth_token=self.settings.twilio_auth_token,
            from_number=self.settings.twilio_from_number,
        )

    # --- use cases --------------------------------------------------------

    def process_detection_use_case(self) -> ProcessDetectionUseCase:
        return ProcessDetectionUseCase(
            repository=self.repository,
            threat_service=self.threat_service,
            llm=self.llm,
            voice=self.voice,
            telephony=self.telephony,
            publisher=self.publisher,
            on_call_number=self.settings.on_call_number,
        )

    def acknowledge_event_use_case(self) -> AcknowledgeEventUseCase:
        return AcknowledgeEventUseCase(repository=self.repository)

    def list_recent_events_use_case(self) -> ListRecentEventsUseCase:
        return ListRecentEventsUseCase(repository=self.repository)
