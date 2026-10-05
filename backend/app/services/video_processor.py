from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
import cv2

from app.core.config import settings
from app.core.logging import logger
from app.services.detectors.base import FrameSample
from app.utils.ffmpeg import (
    MediaExtractionError,
    extract_audio_ffmpeg,
    get_media_metadata_ffprobe,
)


class VideoProcessingError(Exception):
    """Base exception for video processing failures."""
    pass


class CorruptedVideoError(VideoProcessingError):
    """Raised when the uploaded media cannot be opened or decoded."""
    pass


class VideoDurationExceededError(VideoProcessingError):
    """Raised when the video duration exceeds the configured maximum limit."""
    pass


@dataclass
class VideoProcessingResult:
    """Raw processing and extraction results produced by VideoProcessor."""
    duration_s: float
    fps: float
    width: int
    height: int
    frame_count: int
    frames_sampled: int
    audio_available: bool
    frame_samples: List[FrameSample]
    audio_path: Optional[Path] = None

    def to_metadata_dict(self) -> dict:
        return {
            "duration_s": self.duration_s,
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "frames_sampled": self.frames_sampled,
            "audio_available": self.audio_available,
        }


class VideoProcessor:
    """
    Core video inspection, frame sampling, and audio extraction service.
    Implements real media processing using OpenCV and FFmpeg/FFprobe.
    """

    def __init__(
        self,
        max_duration_s: float = settings.MAX_DURATION_SECONDS,
        sample_fps: float = settings.FRAME_SAMPLE_FPS
    ):
        self.max_duration_s = max_duration_s
        self.sample_fps = sample_fps

    def process(
        self,
        video_path: Path,
        frames_dir: Path,
        audio_dir: Path
    ) -> VideoProcessingResult:
        """
        Validates, extracts metadata, samples frames (~1 FPS), and prepares audio.
        
        Args:
            video_path: Path to the local video file.
            frames_dir: Directory where sampled frame images will be written.
            audio_dir: Directory where extracted WAV audio will be written.
            
        Returns:
            VideoProcessingResult with full metadata and artifact paths.
        """
        logger.info(f"Starting video processing for: {video_path.name}")

        # 1. Inspect container & streams with ffprobe
        has_video_stream, has_audio_stream, ffprobe_duration, ffprobe_fps, ffprobe_dims = (
            self._probe_media_streams(video_path)
        )

        if not has_video_stream:
            raise CorruptedVideoError("No valid video stream detected in uploaded file.")

        # 2. Open video stream using OpenCV
        cap = cv2.VideoCapture(str(video_path.resolve()))
        if not cap.isOpened():
            raise CorruptedVideoError("Failed to open video file with OpenCV decoder.")

        try:
            cv_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cv_fps = float(cap.get(cv2.CAP_PROP_FPS))
            cv_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            cv_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            # Combine ffprobe and OpenCV metadata for maximum accuracy
            width = cv_width if cv_width > 0 else (ffprobe_dims[0] if ffprobe_dims else 0)
            height = cv_height if cv_height > 0 else (ffprobe_dims[1] if ffprobe_dims else 0)
            fps = cv_fps if cv_fps > 0 else (ffprobe_fps or 30.0)

            if cv_frame_count > 0 and fps > 0:
                duration_s = cv_frame_count / fps
            elif ffprobe_duration is not None and ffprobe_duration > 0:
                duration_s = ffprobe_duration
            else:
                duration_s = 0.0

            if ffprobe_duration is not None and ffprobe_duration > 0:
                duration_s = ffprobe_duration

            if width <= 0 or height <= 0:
                raise CorruptedVideoError("Invalid video dimensions (0x0). Video may be corrupted.")

            if duration_s <= 0.0 and cv_frame_count <= 0:
                raise CorruptedVideoError("Unable to determine video length or read frames.")

            # Validate maximum duration
            if duration_s > self.max_duration_s:
                raise VideoDurationExceededError(
                    f"Video duration ({duration_s:.1f}s) exceeds maximum allowed limit of {self.max_duration_s:.1f}s."
                )

            logger.info(
                f"Video inspection: {width}x{height} @ {fps:.2f} FPS | "
                f"Duration: {duration_s:.2f}s | Audio stream: {has_audio_stream}"
            )

            # 3. Sample frames at ~1 FPS
            frame_samples = self._sample_frames(
                cap=cap,
                fps=fps,
                total_frames=cv_frame_count,
                frames_dir=frames_dir
            )

            if not frame_samples:
                raise CorruptedVideoError("Failed to extract any readable frames from video stream.")

            logger.info(f"Extracted {len(frame_samples)} frame samples at ~{self.sample_fps} FPS.")

        finally:
            cap.release()

        # 4. Extract audio if audio stream is present
        extracted_audio_path: Optional[Path] = None
        if has_audio_stream:
            target_wav = audio_dir / "audio.wav"
            success = extract_audio_ffmpeg(video_path, target_wav, sample_rate_hz=16000)
            if success:
                extracted_audio_path = target_wav
                logger.info(f"Audio extracted successfully to {target_wav}")
            else:
                logger.warning("Audio stream was detected by ffprobe, but ffmpeg extraction failed.")
                has_audio_stream = False

        return VideoProcessingResult(
            duration_s=round(duration_s, 2),
            fps=round(fps, 2),
            width=width,
            height=height,
            frame_count=cv_frame_count if cv_frame_count > 0 else len(frame_samples),
            frames_sampled=len(frame_samples),
            audio_available=has_audio_stream,
            frame_samples=frame_samples,
            audio_path=extracted_audio_path
        )

    def _probe_media_streams(
        self,
        video_path: Path
    ) -> Tuple[bool, bool, Optional[float], Optional[float], Optional[Tuple[int, int]]]:
        """Runs ffprobe to inspect container streams and formats."""
        try:
            probe_data = get_media_metadata_ffprobe(video_path)
        except MediaExtractionError as e:
            logger.warning(f"ffprobe metadata extraction failed: {e}")
            raise CorruptedVideoError(f"Media inspection failed: {str(e)}") from e

        streams = probe_data.get("streams", [])
        has_video = False
        has_audio = False
        duration_s: Optional[float] = None
        fps: Optional[float] = None
        dims: Optional[Tuple[int, int]] = None

        # Check format level duration
        fmt = probe_data.get("format", {})
        if "duration" in fmt:
            try:
                duration_s = float(fmt["duration"])
            except (ValueError, TypeError):
                pass

        for st in streams:
            codec_type = st.get("codec_type")
            if codec_type == "video" and not has_video:
                has_video = True
                w = st.get("width")
                h = st.get("height")
                if w and h:
                    dims = (int(w), int(h))
                
                # Parse r_frame_rate or avg_frame_rate e.g. "30/1" or "29.97"
                rate_str = st.get("avg_frame_rate") or st.get("r_frame_rate")
                if rate_str and "/" in rate_str:
                    num, den = rate_str.split("/", 1)
                    try:
                        num_f, den_f = float(num), float(den)
                        if den_f > 0:
                            fps = num_f / den_f
                    except (ValueError, ZeroDivisionError):
                        pass

            elif codec_type == "audio":
                has_audio = True

        return has_video, has_audio, duration_s, fps, dims

    def _sample_frames(
        self,
        cap: cv2.VideoCapture,
        fps: float,
        total_frames: int,
        frames_dir: Path
    ) -> List[FrameSample]:
        """
        Samples frames at approximately sample_fps (~1 FPS) and writes them to frames_dir.
        Preserves timestamps accurately.
        """
        samples: List[FrameSample] = []
        frame_interval = max(1, round(fps / self.sample_fps))

        frame_idx = 0
        sample_count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                # Timestamp in seconds
                pos_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
                if pos_msec > 0:
                    timestamp_s = pos_msec / 1000.0
                else:
                    timestamp_s = frame_idx / fps if fps > 0 else float(sample_count)

                frame_filename = f"frame_{sample_count:04d}_{int(timestamp_s * 1000):06d}ms.jpg"
                frame_path = frames_dir / frame_filename

                # Save frame image locally
                write_ok = cv2.imwrite(str(frame_path.resolve()), frame)
                if write_ok:
                    samples.append(FrameSample(
                        timestamp_s=round(timestamp_s, 3),
                        frame_path=frame_path
                    ))
                    sample_count += 1
                else:
                    logger.warning(f"Failed to write frame to {frame_path}")

            frame_idx += 1

        return samples
