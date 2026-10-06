from typing import List, Optional
from app.core.config import settings
from app.core.logging import logger
from app.schemas.analysis import AudioMetadata, AudioResult, VideoInfo, VisualResult
from app.schemas.reliability import ReliabilityResult


class ReliabilityService:
    """
    Stage 2 Reliability Gate.
    Evaluates whether input media quality and evidence signals are reliable enough
    to support an informed media authenticity assessment.
    
    The Reliability Gate NEVER declares media authentic; it strictly determines
    whether the evidence is sufficient (OK) or degraded/insufficient (LOW).
    """

    def __init__(
        self,
        min_width: int = settings.RELIABILITY_MIN_WIDTH,
        min_height: int = settings.RELIABILITY_MIN_HEIGHT,
        min_face_rate: float = settings.MIN_FACE_DETECTION_RATE,
        min_audio_dur: float = settings.MIN_AUDIO_DURATION,
    ):
        self.min_width = min_width
        self.min_height = min_height
        self.min_face_rate = min_face_rate
        self.min_audio_dur = min_audio_dur

    def evaluate(
        self,
        video_info: Optional[VideoInfo] = None,
        visual: Optional[VisualResult] = None,
        audio: Optional[AudioResult] = None,
        audio_metadata: Optional[AudioMetadata] = None,
        media_type: str = "VIDEO"
    ) -> ReliabilityResult:
        """
        Runs comprehensive reliability checks against media metadata and detector results.
        
        Args:
            video_info: Extracted container and video stream metrics (if VIDEO).
            visual: Visual deepfake detector result.
            audio: Audio anti-spoofing detector result.
            audio_metadata: Extracted audio metadata (if AUDIO).
            media_type: "VIDEO" | "AUDIO"
            
        Returns:
            ReliabilityResult with level ('OK' or 'LOW') and diagnostic reasons.
        """
        reasons: List[str] = []
        visual_res = visual or VisualResult()
        audio_res = audio or AudioResult()

        if media_type == "AUDIO":
            # Standalone audio checks
            duration_s = audio_metadata.duration_s if audio_metadata else (video_info.duration_s if video_info else 0.0)
            if duration_s < self.min_audio_dur:
                reasons.append(
                    f"Audio track duration ({duration_s:.1f}s) is shorter than recommended "
                    f"minimum ({self.min_audio_dur:.1f}s) for sliding-window voice analysis."
                )

            if audio_res.status == "error":
                reasons.append("Audio anti-spoofing detector encountered an execution error during analysis.")

            if not audio_res.available and audio_res.status == "unavailable":
                reasons.append("Audio anti-spoofing detector was unavailable for this analysis.")

        else:
            # Video checks
            if video_info:
                # 1. Video Resolution Check
                if video_info.width < self.min_width or video_info.height < self.min_height:
                    reasons.append(
                        f"Video resolution ({video_info.width}x{video_info.height}) is below recommended "
                        f"threshold ({self.min_width}x{self.min_height}). Compression artifacts may impair detection."
                    )

                # 2. Face Detection Coverage Check
                if visual_res.available and visual_res.status == "completed":
                    if visual_res.frames_analyzed > 0:
                        rate = visual_res.face_detection_rate if visual_res.face_detection_rate is not None else 0.0
                        if visual_res.faces_found == 0:
                            reasons.append(
                                "No detectable faces found in sampled frames. Visual face forensic model cannot be evaluated."
                            )
                        elif rate < self.min_face_rate:
                            reasons.append(
                                f"Face detection coverage is low ({rate * 100:.1f}% of frames with faces; "
                                f"recommended minimum is {self.min_face_rate * 100:.0f}%)."
                            )

                # 3. Audio Track Usability Check
                if video_info.audio_available:
                    if video_info.duration_s < self.min_audio_dur:
                        reasons.append(
                            f"Audio track duration ({video_info.duration_s:.1f}s) is shorter than recommended "
                            f"minimum ({self.min_audio_dur:.1f}s) for sliding-window voice analysis."
                        )

            # 4. Model Failure / Execution Error Checks
            if visual_res.status == "error":
                reasons.append("Visual deepfake detector encountered an execution error during analysis.")

            if audio_res.status == "error":
                reasons.append("Audio anti-spoofing detector encountered an execution error during analysis.")

            # 5. Missing Core Modalities
            if not visual_res.available and visual_res.status == "unavailable":
                reasons.append("Visual deepfake detector was unavailable for this analysis.")

        level = "LOW" if len(reasons) > 0 else "OK"

        logger.info(f"Reliability Gate Assessment ({media_type}): level={level} | reasons_count={len(reasons)}")
        return ReliabilityResult(level=level, reasons=reasons)
