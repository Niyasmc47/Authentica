from typing import Optional

from app.core.config import settings
from app.core.logging import logger
from app.schemas.analysis import AudioMetadata, AudioResult, VideoInfo, VisualResult
from app.schemas.evidence import (
    EvidenceMatrix,
    EvidenceMetadata,
    EvidenceModalityResult,
    ModalityStatistics,
    ModelEvidenceItem,
    ProvenanceResult,
)
from app.schemas.reliability import ReliabilityResult


class EvidenceService:
    """
    Stage 2 Evidence Synthesis Service.
    Normalizes raw sensory model outputs into discrete evidence levels (LOW / MEDIUM / HIGH / N/A)
    and constructs the unified EvidenceMatrix.
    
    All raw numeric outputs are explicitly annotated as 'model score (not a probability)'.
    """

    def __init__(
        self,
        visual_low: float = settings.VISUAL_LOW_THRESHOLD,
        visual_high: float = settings.VISUAL_HIGH_THRESHOLD,
        audio_low: float = settings.AUDIO_LOW_THRESHOLD,
        audio_high: float = settings.AUDIO_HIGH_THRESHOLD,
    ):
        self.visual_low = visual_low
        self.visual_high = visual_high
        self.audio_low = audio_low
        self.audio_high = audio_high

    def build_matrix(
        self,
        video_info: Optional[VideoInfo] = None,
        visual: Optional[VisualResult] = None,
        audio: Optional[AudioResult] = None,
        provenance: Optional[ProvenanceResult] = None,
        reliability: Optional[ReliabilityResult] = None,
        audio_metadata: Optional[AudioMetadata] = None,
        media_type: str = "VIDEO"
    ) -> EvidenceMatrix:
        """
        Constructs the comprehensive EvidenceMatrix combining all modalities and provenance.
        """
        visual_modality = self._evaluate_visual_modality(visual or VisualResult())
        audio_modality = self._evaluate_audio_modality(audio or AudioResult())
        prov = provenance or ProvenanceResult(state="NONE_FOUND", note="No provenance manifest found.")
        rel = reliability or ReliabilityResult(level="OK", reasons=[])

        if media_type == "AUDIO":
            duration = audio_metadata.duration_s if audio_metadata else (video_info.duration_s if video_info else 0.0)
            metadata = EvidenceMetadata(
                media_type="AUDIO",
                width=None,
                height=None,
                duration_s=duration,
                fps=None,
                frames_sampled=0,
                audio_available=True,
            )
        else:
            metadata = EvidenceMetadata(
                media_type="VIDEO",
                width=video_info.width if video_info else 0,
                height=video_info.height if video_info else 0,
                duration_s=video_info.duration_s if video_info else 0.0,
                fps=video_info.fps if video_info else 0.0,
                frames_sampled=video_info.frames_sampled if video_info else 0,
                audio_available=video_info.audio_available if video_info else False,
            )

        matrix = EvidenceMatrix(
            visual=visual_modality,
            audio=audio_modality,
            provenance=prov,
            metadata=metadata,
            reliability=rel,
        )

        logger.info(
            f"Evidence Matrix Built ({media_type}): visual_level={visual_modality.level} | "
            f"audio_level={audio_modality.level} | provenance_state={prov.state} | "
            f"reliability={rel.level}"
        )
        return matrix

    def _evaluate_visual_modality(self, visual: VisualResult) -> EvidenceModalityResult:
        """Evaluates visual detection results using robust statistics to prevent spike false-positives."""
        if not visual.available or visual.status != "completed" or visual.frames_analyzed == 0:
            return EvidenceModalityResult(
                level="N/A",
                models=[]
            )

        # Collect valid fake scores from frames where a face was detected
        detected_fake_scores = [
            f.fake_score for f in visual.results
            if f.face_detected is True and f.fake_score is not None
        ]

        if not detected_fake_scores:
            return EvidenceModalityResult(
                level="N/A",
                models=[
                    ModelEvidenceItem(
                        name=visual.model or "VisualDetector",
                        score=None,
                        label="model score (not a probability)"
                    )
                ]
            )

        # Robust statistics calculation
        sorted_scores = sorted(detected_fake_scores)
        n = len(detected_fake_scores)
        mean_score = round(sum(detected_fake_scores) / n, 4)
        median_score = round(
            sorted_scores[n // 2] if n % 2 == 1 else (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2.0,
            4
        )
        max_score = round(max(detected_fake_scores), 4)
        high_frames = [s for s in detected_fake_scores if s >= self.visual_high]
        high_ratio = round(len(high_frames) / n, 4)

        # Calibrated decision logic:
        # HIGH requires persistent manipulation across multiple frames or high central tendency
        if (mean_score >= self.visual_high) or (high_ratio >= 0.40 and mean_score >= 0.55):
            level = "HIGH"
        elif (mean_score >= self.visual_low) or (high_ratio >= 0.20):
            level = "MEDIUM"
        else:
            level = "LOW"

        # Representative score: use mean_score as standard summary
        rep_score = mean_score

        stats = ModalityStatistics(
            mean_score=mean_score,
            median_score=median_score,
            max_score=max_score,
            high_ratio=high_ratio,
            consecutive_high_count=0
        )

        return EvidenceModalityResult(
            level=level,
            models=[
                ModelEvidenceItem(
                    name=visual.model or "EfficientNet-B0-FFPP-C23",
                    score=rep_score,
                    label="model score (not a probability)"
                )
            ],
            statistics=stats
        )

    def _evaluate_audio_modality(self, audio: AudioResult) -> EvidenceModalityResult:
        """Evaluates audio anti-spoofing results using robust statistics to prevent spike false-positives."""
        if not audio.available or audio.status != "completed" or not audio.results:
            return EvidenceModalityResult(
                level="N/A",
                models=[]
            )

        valid_spoof_scores = [
            win.spoof_score for win in audio.results
            if win.spoof_score is not None
        ]

        if not valid_spoof_scores:
            return EvidenceModalityResult(
                level="N/A",
                models=[
                    ModelEvidenceItem(
                        name=audio.model or "AudioDetector",
                        score=None,
                        label="model score (not a probability)"
                    )
                ]
            )

        sorted_scores = sorted(valid_spoof_scores)
        n = len(valid_spoof_scores)
        mean_score = round(sum(valid_spoof_scores) / n, 4)
        median_score = round(
            sorted_scores[n // 2] if n % 2 == 1 else (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2.0,
            4
        )
        max_score = round(max(valid_spoof_scores), 4)
        high_windows = [s for s in valid_spoof_scores if s >= self.audio_high]
        high_ratio = round(len(high_windows) / n, 4)

        # Calibrated decision logic:
        # HIGH requires persistent spoofing across multiple windows or high mean
        if (mean_score >= self.audio_high) or (high_ratio >= 0.40 and mean_score >= 0.55):
            level = "HIGH"
        elif (mean_score >= self.audio_low) or (high_ratio >= 0.20):
            level = "MEDIUM"
        else:
            level = "LOW"

        rep_score = mean_score

        stats = ModalityStatistics(
            mean_score=mean_score,
            median_score=median_score,
            max_score=max_score,
            high_ratio=high_ratio,
            consecutive_high_count=0
        )

        return EvidenceModalityResult(
            level=level,
            models=[
                ModelEvidenceItem(
                    name=audio.model or "AASIST-ASVspoof2019-LA",
                    score=rep_score,
                    label="model score (not a probability)"
                )
            ],
            statistics=stats
        )
