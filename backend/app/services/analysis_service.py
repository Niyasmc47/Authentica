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
    Orchestration service for Stage 1 media processing pipeline.
    
    Coordinates:
      1. Validation of upload MIME, extension, size
      2. Ephemeral workspace creation
      3. SHA-256 fingerprinting
      4. Video inspection, frame sampling, audio extraction
      5. Invocation of pluggable detector interfaces
      6. Assembly of standardized Stage 1 response
      7. Guaranteed ephemeral artifact cleanup (zero data retention)
    """

    def __init__(
        self,
        video_processor: Optional[VideoProcessor] = None,
        visual_detector: Optional[VisualDetector] = None,
        audio_detector: Optional[AudioDetector] = None,
        speech_detector: Optional[SpeechToText] = None,
    ):
        self.video_processor = video_processor or VideoProcessor()
        self.visual_detector = visual_detector or VisualDeepfakeDetector.get_instance()
        self.audio_detector = audio_detector or LocalAudioAntiSpoofDetector.get_instance()
        self.speech_detector = speech_detector or FasterWhisperTranscriber.get_instance()

    async def analyze_video(self, file: UploadFile) -> AnalysisResponse:
        """
        Processes an uploaded video through the Stage 1 pipeline.
        
        Args:
            file: FastAPI UploadFile object from multipart request.
            
        Returns:
            AnalysisResponse matching the Stage 1 shared data contract.
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

            # 4. Preprocess video (metadata, frame sampling, audio extraction)
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

            # 5. Invoke Visual Detector (Member 2 integration hook)
            visual_result = await self._run_visual_detector(
                analysis_id, proc_result.frame_samples, video_info
            )

            # 6. Invoke Audio Detector (Member 3 integration hook)
            audio_result = await self._run_audio_detector(
                analysis_id, proc_result.audio_path, video_info
            )

            # 7. Invoke Speech-to-Text (Member 3 integration hook)
            speech_result = await self._run_speech_transcriber(
                analysis_id, proc_result.audio_path, video_info
            )

            # 8. Assemble Stage 1 AnalysisResponse
            response = AnalysisResponse(
                id=analysis_id,
                status="completed",
                created_at=created_at,
                video=video_info,
                visual=visual_result,
                audio=audio_result,
                speech=speech_result,
            )

            logger.info(f"[{analysis_id}] Analysis pipeline completed successfully.")
            return response

        finally:
            # 9. Guaranteed cleanup of all temporary media, frames, and audio
            workspace.cleanup()
            logger.debug(f"[{analysis_id}] Cleanup completed.")

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
            logger.info(f"[{analysis_id}] Visual detector interface not implemented (Member 2 hook).")
            return VisualResult(available=False, status="unavailable")
        except Exception as e:
            logger.error(f"[{analysis_id}] Visual detector encountered error: {e}")
            return VisualResult(available=False, status="error")

    async def _run_audio_detector(self, analysis_id: str, audio_path: Optional[Path], video_info: VideoInfo) -> AudioResult:
        try:
            return await self.audio_detector.analyze(audio_path, video_info)
        except NotImplementedError:
            logger.info(f"[{analysis_id}] Audio detector interface not implemented (Member 3 hook).")
            return AudioResult(available=False, status="unavailable")
        except Exception as e:
            logger.error(f"[{analysis_id}] Audio detector encountered error: {e}")
            return AudioResult(available=False, status="error")

    async def _run_speech_transcriber(self, analysis_id: str, audio_path: Optional[Path], video_info: VideoInfo) -> SpeechResult:
        try:
            return await self.speech_detector.transcribe(audio_path, video_info)
        except NotImplementedError:
            logger.info(f"[{analysis_id}] Speech-to-text interface not implemented (Member 3 hook).")
            return SpeechResult(available=False, status="unavailable")
        except Exception as e:
            logger.error(f"[{analysis_id}] Speech-to-text encountered error: {e}")
            return SpeechResult(available=False, status="error")
