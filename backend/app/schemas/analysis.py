from typing import List, Optional
from pydantic import BaseModel, Field


class VideoInfo(BaseModel):
    """Metadata extracted from the uploaded video."""
    filename: str = Field(..., description="Original filename of the uploaded video")
    sha256: str = Field(..., description="SHA-256 hash of the video file")
    duration_s: float = Field(..., description="Total duration in seconds")
    fps: float = Field(..., description="Frame rate (frames per second)")
    width: int = Field(..., description="Video width in pixels")
    height: int = Field(..., description="Video height in pixels")
    frames_sampled: int = Field(..., description="Number of sampled frames extracted for analysis")
    audio_available: bool = Field(..., description="True if an audio stream exists in the video")


class VisualFrameResult(BaseModel):
    """Result for an individual sampled video frame."""
    timestamp_s: float = Field(..., description="Timestamp of the frame in seconds")
    face_detected: Optional[bool] = Field(None, description="Whether a face was detected in this frame")
    real_score: Optional[float] = Field(None, description="Confidence score for real/authentic face (0.0 to 1.0)")
    fake_score: Optional[float] = Field(None, description="Confidence score for synthetic/deepfake face (0.0 to 1.0)")


class VisualResult(BaseModel):
    """Aggregated visual / facial deepfake detection results (Member 2)."""
    available: bool = Field(False, description="Whether the visual detector is active and executed")
    model: Optional[str] = Field(None, description="Name and version of the visual detector model")
    status: str = Field("unavailable", description="Status of the visual detector (e.g., unavailable, completed, error)")
    frames_analyzed: int = Field(0, description="Total number of frames analyzed")
    faces_found: int = Field(0, description="Total number of frames where faces were detected")
    face_detection_rate: Optional[float] = Field(None, description="Proportion of sampled frames containing faces")
    results: List[VisualFrameResult] = Field(default_factory=list, description="Per-frame detection results")


class AudioWindowResult(BaseModel):
    """Result for a time window in the audio stream."""
    start_s: float = Field(..., description="Start timestamp in seconds")
    end_s: float = Field(..., description="End timestamp in seconds")
    spoof_score: Optional[float] = Field(None, description="Voice spoofing / synthetic voice confidence score (0.0 to 1.0)")


class AudioResult(BaseModel):
    """Audio deepfake / voice spoofing detection results (Member 3)."""
    available: bool = Field(False, description="Whether the audio detector is active and executed")
    model: Optional[str] = Field(None, description="Name and version of the audio detector model")
    status: str = Field("unavailable", description="Status of the audio detector (e.g., unavailable, completed, error)")
    windows_analyzed: Optional[int] = Field(None, description="Number of sliding audio windows analyzed")
    processing_time_s: Optional[float] = Field(None, description="Inference processing time in seconds")
    results: List[AudioWindowResult] = Field(default_factory=list, description="Time-windowed audio detection results")


class SpeechSegment(BaseModel):
    """Transcribed speech segment."""
    start_s: float = Field(..., description="Start timestamp in seconds")
    end_s: float = Field(..., description="End timestamp in seconds")
    text: str = Field(..., description="Transcribed text content")


class SpeechResult(BaseModel):
    """Speech-to-text transcription results (Member 3)."""
    available: bool = Field(False, description="Whether speech-to-text is active and executed")
    model: Optional[str] = Field(None, description="Name and version of the speech-to-text model")
    status: str = Field("unavailable", description="Status of the speech transcriber")
    language: Optional[str] = Field(None, description="Detected or configured spoken language code (e.g., 'en')")
    processing_time_s: Optional[float] = Field(None, description="Transcription processing time in seconds")
    segments: List[SpeechSegment] = Field(default_factory=list, description="Transcribed speech segments")


class AnalysisResponse(BaseModel):
    """Structured Stage 1 Analysis Result shared data contract."""
    id: str = Field(..., description="Unique UUID for this analysis request")
    status: str = Field(..., description="Overall analysis status: completed | partial | error")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    video: VideoInfo = Field(..., description="Extracted video metadata")
    visual: VisualResult = Field(default_factory=VisualResult, description="Visual deepfake detector output")
    audio: AudioResult = Field(default_factory=AudioResult, description="Audio deepfake detector output")
    speech: SpeechResult = Field(default_factory=SpeechResult, description="Speech-to-text output")


class HealthResponse(BaseModel):
    """Health check endpoint response model."""
    status: str = Field("ok", description="Server status")
    ffmpeg_available: bool = Field(..., description="Whether ffmpeg CLI is accessible")
    ffprobe_available: bool = Field(..., description="Whether ffprobe CLI is accessible")
    version: str = Field(..., description="Application version")


class ErrorResponse(BaseModel):
    """Standard sanitized API error response."""
    detail: str = Field(..., description="Human-readable error description")
    error_code: Optional[str] = Field(None, description="Machine-readable error code")
