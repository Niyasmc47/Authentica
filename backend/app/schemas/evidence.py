from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.reliability import ReliabilityResult


class ModelEvidenceItem(BaseModel):
    """
    Representation of an individual model score.
    Explicitly annotated to prevent misinterpreting raw outputs as calibrated probabilities.
    """
    name: str = Field(..., description="Unique model name and version")
    score: Optional[float] = Field(None, description="Raw model score (not a probability)")
    label: str = Field(
        "model score (not a probability)",
        description="Explicit provenance annotation for consumer interfaces"
    )


class EvidenceModalityResult(BaseModel):
    """Normalized evidence for an individual sensory modality (visual or audio)."""
    level: str = Field(
        "N/A",
        description="Derived modality level: 'LOW' | 'MEDIUM' | 'HIGH' | 'N/A'"
    )
    models: List[ModelEvidenceItem] = Field(
        default_factory=list,
        description="List of model outputs contributing to this modality"
    )


class ProvenanceResult(BaseModel):
    """
    C2PA / Content Credentials inspection findings.
    Distinguishes presence, signature validity, and signer trustworthiness.
    """
    state: str = Field(
        ...,
        description="Provenance state: 'NONE_FOUND' | 'FOUND' | 'UNAVAILABLE' | 'ERROR'"
    )
    valid: Optional[bool] = Field(
        None,
        description="True if cryptographic manifest signature is verified and intact, False if invalid/tampered"
    )
    trusted: Optional[bool] = Field(
        None,
        description="True if signing certificate is on the configured trusted root list"
    )
    signer: Optional[str] = Field(
        None,
        description="Common Name or Organization of the signing identity"
    )
    note: str = Field(
        ...,
        description="Human-readable explanation of provenance state and implications"
    )


class EvidenceMetadata(BaseModel):
    """Normalized media quality and container metrics."""
    width: int
    height: int
    duration_s: float
    fps: float
    frames_sampled: int
    audio_available: bool


class EvidenceMatrix(BaseModel):
    """
    Unified evidence synthesis matrix combining sensory evidence, provenance,
    media quality, and reliability status.
    """
    visual: EvidenceModalityResult = Field(default_factory=EvidenceModalityResult)
    audio: EvidenceModalityResult = Field(default_factory=EvidenceModalityResult)
    provenance: ProvenanceResult
    metadata: EvidenceMetadata
    reliability: ReliabilityResult


class MediaAssessment(BaseModel):
    """
    Stage 2 & Stage 3 Media Assessment verdict and recommended action.
    Explicitly avoids unsupported 'AUTHENTIC' claims.
    """
    media: str = Field(
        ...,
        description="Media verdict: 'LIKELY_MANIPULATED' | 'SUSPICIOUS' | 'NO_STRONG_EVIDENCE' | 'UNCERTAIN'"
    )
    fraud: Optional[str] = Field(
        None,
        description="Fraud intent risk: 'LOW' | 'MEDIUM' | 'HIGH' | 'NOT_ASSESSABLE'"
    )
    action: Optional[str] = Field(
        None,
        description="Recommended action: 'STOP_AND_VERIFY' | 'VERIFY' | 'CAUTION' | 'NO_ACTION_FLAGGED'"
    )
