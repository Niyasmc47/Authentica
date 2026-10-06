from typing import Optional

from app.core.config import settings
from app.core.logging import logger
from app.schemas.analysis import AudioResult, VideoInfo, VisualResult
from app.schemas.evidence import (
    EvidenceMatrix,
    EvidenceMetadata,
    EvidenceModalityResult,
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
        video_info: VideoInfo,
        visual: VisualResult,
        audio: AudioResult,
        provenance: ProvenanceResult,
        reliability: ReliabilityResult,
    ) -> EvidenceMatrix:
        """
        Constructs the comprehensive EvidenceMatrix combining all modalities and provenance.
        """
        visual_modality = self._evaluate_visual_modality(visual)
        audio_modality = self._evaluate_audio_modality(audio)

        metadata = EvidenceMetadata(
            width=video_info.width,
            height=video_info.height,
            duration_s=video_info.duration_s,
            fps=video_info.fps,
            frames_sampled=video_info.frames_sampled,
            audio_available=video_info.audio_available,
        )

        matrix = EvidenceMatrix(
            visual=visual_modality,
            audio=audio_modality,
            provenance=provenance,
            metadata=metadata,
            reliability=reliability,
        )

        logger.info(
            f"Evidence Matrix Built: visual_level={visual_modality.level} | "
            f"audio_level={audio_modality.level} | provenance_state={provenance.state} | "
            f"reliability={reliability.level}"
        )
        return matrix

    def _evaluate_visual_modality(self, visual: VisualResult) -> EvidenceModalityResult:
        """Evaluates visual detection results and maps them to normalized evidence level."""
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

        # Aggregate score: representative maximum across valid frames
        rep_score = round(max(detected_fake_scores), 4)

        if rep_score >= self.visual_high:
            level = "HIGH"
        elif rep_score >= self.visual_low:
            level = "MEDIUM"
        else:
            level = "LOW"

        return EvidenceModalityResult(
            level=level,
            models=[
                ModelEvidenceItem(
                    name=visual.model or "EfficientNet-B0-FFPP-C23",
                    score=rep_score,
                    label="model score (not a probability)"
                )
            ]
        )

    def _evaluate_audio_modality(self, audio: AudioResult) -> EvidenceModalityResult:
        """Evaluates audio anti-spoofing results and maps them to normalized evidence level."""
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

        rep_score = round(max(valid_spoof_scores), 4)

        if rep_score >= self.audio_high:
            level = "HIGH"
        elif rep_score >= self.audio_low:
            level = "MEDIUM"
        else:
            level = "LOW"

        return EvidenceModalityResult(
            level=level,
            models=[
                ModelEvidenceItem(
                    name=audio.model or "AASIST-ASVspoof2019-LA",
                    score=rep_score,
                    label="model score (not a probability)"
                )
            ]
        )
