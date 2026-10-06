import datetime
import uuid
from pathlib import Path
from typing import Optional
from fastapi import UploadFile

from app.core.config import settings
from app.core.logging import logger
from app.schemas.analysis import (
    AnalysisResponse,
    AudioResult,
    SpeechResult,
    VideoInfo,
    VisualResult,
)
from app.services.assessment_service import AssessmentService
from app.services.c2pa_service import C2PAService
from app.services.detectors import (
    AudioDetector,
    FasterWhisperTranscriber,
    LocalAudioAntiSpoofDetector,
    PlaceholderAudioDetector,
    PlaceholderSpeechToText,
    PlaceholderVisualDetector,
    SpeechToText,
    VisualDeepfakeDetector,
    VisualDetector,
)
from app.services.evidence_service import EvidenceService
from app.services.fraud_engine import FraudIntentEngine
from app.services.reliability_service import ReliabilityService
from app.services.timeline_service import TimelineService
from app.services.video_processor import (
    CorruptedVideoError,
    VideoDurationExceededError,
    VideoProcessingError,
    VideoProcessor,
)
from app.utils.hashing import compute_sha256
from app.utils.temp_manager import TempWorkspace


class ValidationException(Exception):
    """Base exception for user input validation errors."""
    pass


class InvalidFileExtensionError(ValidationException):
    pass


class InvalidMimeTypeError(ValidationException):
    pass


class FileTooLargeError(ValidationException):
    pass


class AnalysisService:
    """
    Orchestration service for Authentica Media Analysis Pipeline (Stage 1, Stage 2 & Stage 3).
    
    Coordinates:
      1. Validation of upload MIME, extension, size
      2. Ephemeral workspace creation
      3. SHA-256 fingerprinting
      4. Video inspection, frame sampling, audio extraction
      5. C2PA Content Credentials / Provenance inspection
      6. Sensory deepfake detectors (Visual, Audio, Speech)
      7. Stage 3 Fraud Intent & Social-Engineering Engine
      8. Reliability Gate evaluation
      9. Multi-modal Evidence Matrix synthesis
      10. Timeline aggregation and noise reduction (Visual, Audio, Transcript, Fraud)
      11. Media Assessment, Fraud Synthesis & Final Recommended Action
      12. Assembly of standardized full-stage response
      13. Guaranteed ephemeral artifact cleanup (zero data retention)
    """

    def __init__(
        self,
        video_processor: Optional[VideoProcessor] = None,
        visual_detector: Optional[VisualDetector] = None,
        audio_detector: Optional[AudioDetector] = None,
        speech_detector: Optional[SpeechToText] = None,
        c2pa_service: Optional[C2PAService] = None,
        reliability_service: Optional[ReliabilityService] = None,
        evidence_service: Optional[EvidenceService] = None,
        timeline_service: Optional[TimelineService] = None,
        assessment_service: Optional[AssessmentService] = None,
        fraud_engine: Optional[FraudIntentEngine] = None,
    ):
        self.video_processor = video_processor or VideoProcessor()
        self.visual_detector = visual_detector or VisualDeepfakeDetector.get_instance()
        self.audio_detector = audio_detector or LocalAudioAntiSpoofDetector.get_instance()
        self.speech_detector = speech_detector or FasterWhisperTranscriber.get_instance()
        
        # Stage 2 & 3 Services
        self.c2pa_service = c2pa_service or C2PAService()
        self.reliability_service = reliability_service or ReliabilityService()
        self.evidence_service = evidence_service or EvidenceService()
        self.timeline_service = timeline_service or TimelineService()
        self.assessment_service = assessment_service or AssessmentService()
        self.fraud_engine = fraud_engine or FraudIntentEngine()

    async def analyze_video(self, file: UploadFile) -> AnalysisResponse:
        """
        Processes an uploaded video through the unified Stage 1, 2, and 3 pipeline.
        
        Args:
            file: FastAPI UploadFile object from multipart request.
            
        Returns:
            AnalysisResponse matching the shared data contract.
        """
        analysis_id = str(uuid.uuid4())
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        original_filename = file.filename or "unknown_video.mp4"

        logger.info(f"[{analysis_id}] Received analysis request for file: '{original_filename}'")

        # 1. Validate file extension and MIME type
        self._validate_file_metadata(original_filename, file.content_type)

        workspace = TempWorkspace(analysis_id=analysis_id).setup()

        try:
            # 2. Stream uploaded file safely to temporary disk and enforce size limit
            saved_video_path = workspace.video_dir / Path(original_filename).name
            await self._save_upload_file(file, saved_video_path)

            logger.info(f"[{analysis_id}] Video saved to temporary location: {saved_video_path}")

            # 3. Compute SHA-256 hash
            sha256_hash = compute_sha256(saved_video_path)
            logger.info(f"[{analysis_id}] Computed SHA-256: {sha256_hash}")

            # 4. Stage 2 C2PA / Provenance Manifest Inspection
            logger.info(f"[{analysis_id}] Inspecting C2PA provenance credentials...")
            provenance_result = self.c2pa_service.inspect(saved_video_path)
            logger.info(f"[{analysis_id}] Provenance state: {provenance_result.state}")

            # 5. Preprocess video (metadata, frame sampling, audio extraction)
            logger.info(f"[{analysis_id}] Preprocessing video...")
            proc_result = self.video_processor.process(
                video_path=saved_video_path,
                frames_dir=workspace.frames_dir,
                audio_dir=workspace.audio_dir,
            )
            logger.info(f"[{analysis_id}] Preprocessing completed successfully.")

            # Construct VideoInfo schema
            video_info = VideoInfo(
                filename=original_filename,
                sha256=sha256_hash,
                duration_s=proc_result.duration_s,
                fps=proc_result.fps,
                width=proc_result.width,
                height=proc_result.height,
                frames_sampled=proc_result.frames_sampled,
                audio_available=proc_result.audio_available,
            )

            # 6. Invoke Visual Detector (Member 2)
            visual_result = await self._run_visual_detector(
                analysis_id, proc_result.frame_samples, video_info
            )

            # 7. Invoke Audio Detector (Member 3)
            audio_result = await self._run_audio_detector(
                analysis_id, proc_result.audio_path, video_info
            )

            # 8. Invoke Speech-to-Text (Member 3)
            speech_result = await self._run_speech_transcriber(
                analysis_id, proc_result.audio_path, video_info
            )

            # 9. Stage 3: Fraud Intent & Social Engineering Engine
            logger.info(f"[{analysis_id}] Evaluating fraud intent and social engineering risks...")
            fraud_result = self.fraud_engine.evaluate(speech_result)
            logger.info(f"[{analysis_id}] Fraud Intent Evaluation: level={fraud_result.level}")

            # 10. Stage 2: Reliability Gate Assessment
            reliability_result = self.reliability_service.evaluate(
                video_info=video_info,
                visual=visual_result,
                audio=audio_result,
            )

            # 11. Stage 2: Build Evidence Matrix
            evidence_matrix = self.evidence_service.build_matrix(
                video_info=video_info,
                visual=visual_result,
                audio=audio_result,
                provenance=provenance_result,
                reliability=reliability_result,
            )

            # 12. Stage 2 & 3: Timeline Aggregation
            timeline_events = self.timeline_service.aggregate(
                visual=visual_result,
                audio=audio_result,
                speech=speech_result,
                video_duration_s=video_info.duration_s,
                fraud=fraud_result,
            )

            # 13. Stage 2 & 3: Media Assessment, Fraud Synthesis & Final Action
            assessment_result, explanations, limitations = self.assessment_service.assess(
                matrix=evidence_matrix,
                timeline=timeline_events,
                fraud=fraud_result,
            )

            # 14. Assemble Full Stage 1 + Stage 2 + Stage 3 AnalysisResponse
            response = AnalysisResponse(
                id=analysis_id,
                status="completed",
                created_at=created_at,
                video=video_info,
                visual=visual_result,
                audio=audio_result,
                speech=speech_result,
                reliability=reliability_result,
                evidence=evidence_matrix,
                timeline=timeline_events,
                assessment=assessment_result,
                explanation=explanations,
                limitations=limitations,
                fraud=fraud_result,
            )

            logger.info(
                f"[{analysis_id}] Pipeline completed: media={assessment_result.media} | "
                f"fraud={assessment_result.fraud} | action={assessment_result.action} | "
                f"reliability={reliability_result.level}"
            )
            return response

        finally:
            # 15. Guaranteed cleanup of all temporary media, frames, and audio
            workspace.cleanup()
            logger.debug(f"[{analysis_id}] Ephemeral workspace cleanup completed.")

    def _validate_file_metadata(self, filename: str, content_type: Optional[str]) -> None:
        """Validates filename extension and reported MIME type."""
        ext = Path(filename).suffix.lower()
        if not ext or ext not in settings.ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(settings.ALLOWED_EXTENSIONS))
            raise InvalidFileExtensionError(
                f"Unsupported file extension '{ext}'. Allowed extensions: {allowed}"
            )

        if content_type:
            # Clean content_type (e.g. remove parameters like charset)
            base_mime = content_type.split(";")[0].strip().lower()
            if base_mime not in settings.ALLOWED_MIME_TYPES:
                allowed_mimes = ", ".join(sorted(settings.ALLOWED_MIME_TYPES))
                raise InvalidMimeTypeError(
                    f"Unsupported MIME type '{base_mime}'. Allowed MIME types: {allowed_mimes}"
                )

    async def _save_upload_file(self, file: UploadFile, dest_path: Path) -> None:
        """Streams upload file in chunks while enforcing maximum file size limit."""
        bytes_written = 0
        chunk_size = 1024 * 1024  # 1 MB chunk

        with open(dest_path, "wb") as f:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > settings.max_file_size_bytes:
                    raise FileTooLargeError(
                        f"File size exceeds maximum allowed limit of {settings.MAX_FILE_SIZE_MB} MB."
                    )
                f.write(chunk)

        if bytes_written == 0:
            raise ValidationException("Uploaded file is empty (0 bytes).")

    async def _run_visual_detector(self, analysis_id: str, frame_samples, video_info: VideoInfo) -> VisualResult:
        try:
            return await self.visual_detector.analyze(frame_samples, video_info)
        except NotImplementedError:
            logger.info(f"[{analysis_id}] Visual detector interface not implemented.")
            return VisualResult(available=False, status="unavailable")
        except Exception as e:
            logger.error(f"[{analysis_id}] Visual detector encountered error: {e}")
            return VisualResult(available=False, status="error")

    async def _run_audio_detector(self, analysis_id: str, audio_path: Optional[Path], video_info: VideoInfo) -> AudioResult:
        try:
            return await self.audio_detector.analyze(audio_path, video_info)
        except NotImplementedError:
            logger.info(f"[{analysis_id}] Audio detector interface not implemented.")
            return AudioResult(available=False, status="unavailable")
        except Exception as e:
            logger.error(f"[{analysis_id}] Audio detector encountered error: {e}")
            return AudioResult(available=False, status="error")

    async def _run_speech_transcriber(self, analysis_id: str, audio_path: Optional[Path], video_info: VideoInfo) -> SpeechResult:
        try:
            return await self.speech_detector.transcribe(audio_path, video_info)
        except NotImplementedError:
            logger.info(f"[{analysis_id}] Speech-to-text interface not implemented.")
            return SpeechResult(available=False, status="unavailable")
        except Exception as e:
            logger.error(f"[{analysis_id}] Speech-to-text encountered error: {e}")
            return SpeechResult(available=False, status="error")
