from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from app.core.config import settings
from app.utils.hashing import compute_sha256


def test_post_analyses_end_to_end(test_client: TestClient, synthetic_video_path: Path):
    """
    End-to-end integration test for POST /api/analyses.
    Verifies:
      - Valid video upload processing
      - Accurate SHA-256 hashing
      - Video metadata extraction
      - Frame sampling count
      - Stage 1 contract adherence (visual/audio/speech reporting 'unavailable' without fake scores)
      - Zero artifact leakage / guaranteed temp directory cleanup
    """
    expected_hash = compute_sha256(synthetic_video_path)

    with open(synthetic_video_path, "rb") as video_file:
        response = test_client.post(
            "/api/analyses",
            files={"file": (synthetic_video_path.name, video_file, "video/mp4")}
        )

    assert response.status_code == 200
    data = response.json()

    # 1. Structure Verification
    assert "id" in data
    assert data["status"] == "completed"
    assert "created_at" in data

    # 2. Video Metadata Verification
    video = data["video"]
    assert video["filename"] == synthetic_video_path.name
    assert video["sha256"] == expected_hash
    assert video["duration_s"] == pytest.approx(3.0, rel=0.2)
    assert video["fps"] == pytest.approx(10.0, rel=0.1)
    assert video["width"] == 320
    assert video["height"] == 240
    assert video["frames_sampled"] >= 3

    # 3. Stage 1 Contract: Active VisualDetector (Member 2) + Unavailable Audio/Speech Placeholders (Member 3)
    visual = data["visual"]
    assert visual["available"] is True
    assert visual["status"] == "completed"
    assert visual["model"] == "EfficientNet-B0-FFPP-C23"
    assert visual["frames_analyzed"] >= 3
    assert len(visual["results"]) >= 3

    audio = data["audio"]
    assert audio["available"] is False
    assert audio["status"] == "unavailable"
    assert audio["results"] == []

    speech = data["speech"]
    assert speech["available"] is False
    assert speech["status"] == "unavailable"
    assert speech["segments"] == []

    # 4. Privacy & Cleanup Verification: No leftover folders in temp dir
    analysis_temp_dir = settings.TEMP_DIR / data["id"]
    assert not analysis_temp_dir.exists(), f"Temporary directory {analysis_temp_dir} was not cleaned up!"


def test_post_analyses_corrupted_file(test_client: TestClient, temp_test_dir: Path):
    """Verifies that uploading a corrupt video file returns HTTP 422 with clean error."""
    corrupt_file = temp_test_dir / "bad_video.mp4"
    corrupt_file.write_bytes(b"INVALID_HEADER_GARBAGE_DATA" * 50)

    with open(corrupt_file, "rb") as f:
        response = test_client.post(
            "/api/analyses",
            files={"file": ("bad_video.mp4", f, "video/mp4")}
        )

    assert response.status_code == 422
    assert "detail" in response.json()
    assert "corrupt" in response.json()["detail"].lower() or "inspection failed" in response.json()["detail"].lower()


def test_post_analyses_with_audio_end_to_end(test_client: TestClient, synthetic_video_with_audio_path: Path):
    """
    End-to-end integration test for POST /api/analyses with video containing audio.
    Verifies:
      - Visual detector produces real/fake frame scores
      - Local audio detector produces windowed spoof scores
      - Faster-Whisper transcriber produces speech transcription and language detection
    """
    with open(synthetic_video_with_audio_path, "rb") as video_file:
        response = test_client.post(
            "/api/analyses",
            files={"file": (synthetic_video_with_audio_path.name, video_file, "video/mp4")}
        )

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "completed"
    assert data["video"]["audio_available"] is True

    # Visual branch
    assert data["visual"]["available"] is True
    assert data["visual"]["status"] == "completed"

    # Audio branch (Member 3)
    audio = data["audio"]
    assert audio["available"] is True
    assert audio["status"] == "completed"
    assert audio["model"] == "AASIST-ASVspoof2019-LA"
    assert audio["windows_analyzed"] >= 1
    assert len(audio["results"]) >= 1
    for win in audio["results"]:
        assert win["start_s"] >= 0.0
        assert win["end_s"] > win["start_s"]
        assert win["spoof_score"] is not None
        assert 0.0 <= win["spoof_score"] <= 1.0

    # Speech branch (Member 3)
    speech = data["speech"]
    assert speech["available"] is True
    assert speech["status"] == "completed"
    assert speech["model"] == "faster-whisper-base-int8"
    assert speech["language"] is not None
    assert isinstance(speech["segments"], list)
