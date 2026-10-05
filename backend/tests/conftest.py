import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Generator
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


@pytest.fixture(scope="session")
def test_client() -> Generator[TestClient, None, None]:
    """Provides a FastAPI TestClient instance."""
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="function")
def temp_test_dir() -> Generator[Path, None, None]:
    """Provides an isolated temporary directory for test files."""
    test_dir = Path(tempfile.mkdtemp(prefix="authentica_test_"))
    yield test_dir
    shutil.rmtree(test_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def synthetic_video_path(temp_test_dir: Path) -> Path:
    """
    Generates a small valid MP4 video for fast local testing.
    3 seconds long, 10 FPS, 320x240 resolution.
    """
    video_path = temp_test_dir / "test_synthetic.mp4"
    width, height = 320, 240
    fps = 10.0
    duration_s = 3
    total_frames = int(fps * duration_s)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_path), fourcc, fps, (width, height))

    for i in range(total_frames):
        # Create varying colored synthetic frames
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        color_val = int((i / total_frames) * 255)
        frame[:, :] = (color_val, 100, 255 - color_val)
        writer.write(frame)

    writer.release()
    return video_path


@pytest.fixture(scope="function")
def synthetic_video_with_audio_path(temp_test_dir: Path, synthetic_video_path: Path) -> Path:
    """
    Combines the synthetic video with a silent audio stream using ffmpeg.
    """
    output_path = temp_test_dir / "test_with_audio.mp4"
    
    cmd = [
        "ffmpeg",
        "-v", "error",
        "-y",
        "-i", str(synthetic_video_path),
        "-f", "lavfi",
        "-i", "anullsrc=r=16000:cl=mono",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        str(output_path)
    ]
    
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode == 0 and output_path.exists():
        return output_path
    
    # Fallback to pure video if audio synthesis command encounters any issue
    return synthetic_video_path
