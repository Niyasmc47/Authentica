# Authentica — Backend System Foundation (Stage 1)

> **Hackathena '26 2.0 Project**  
> **Theme:** Detection and Prevention of AI-Based Frauds  
> **Module:** Stage 1 Core Backend & Media Preprocessing Pipeline  
> **Lead Developer (Stage 1):** Member 1 (System Foundation & Ingestion Engine)

---

## 📌 Overview

This backend is the system foundation for **Authentica**, an AI-based fraud and deepfake detection platform. 

In **Stage 1**, this service provides:
1. High-throughput video ingestion and safe multipart streaming.
2. File validation (MIME types, allowed extensions, maximum duration, maximum file size).
3. Cryptographic media fingerprinting (**SHA-256**) for integrity and duplicate prevention.
4. Robust local media inspection and frame sampling (~1 FPS) using **OpenCV** and **FFmpeg/FFprobe**.
5. Safe audio stream extraction (16kHz mono WAV) for downstream speech & voice analysis.
6. Unified **Stage 1 Shared Data Contract** with modular interfaces for **Member 2** (Visual AI Detector) and **Member 3** (Audio Spoofing & Speech Transcriber).
7. Strict ephemeral processing with **Zero Data Retention** (temporary workspaces are completely deleted immediately upon request completion).

---

## 🏗️ Stage 1 Architecture & Pipeline

```
               [ User / Client ]
                       │
             POST /api/analyses (multipart)
                       ▼
           ┌───────────────────────┐
           │ Fast Validation Layer │ (MIME, Extension, Size, Header)
           └───────────┬───────────┘
                       ▼
           ┌───────────────────────┐
           │  Ephemeral Workspace  │ (temp/{analysis_id}/)
           └───────────┬───────────┘
                       ▼
           ┌───────────────────────┐
           │  SHA-256 Fingerprint  │ (hashlib streaming)
           └───────────┬───────────┘
                       ▼
           ┌───────────────────────┐
           │  Video Preprocessing  │
           │ (OpenCV + FFprobe)    │ (Duration, FPS, Resolution, Audio check)
           └───────────┬───────────┘
                       ▼
           ┌───────────────────────┐
           │  Frame Sampling (1fps)│ (Sampled frames saved to temp/frames/)
           └───────────┬───────────┘
                       ▼
           ┌───────────────────────┐
           │   Audio Extraction    │ (FFmpeg -> 16kHz mono PCM WAV)
           └───────────┬───────────┘
                       ▼
      ┌─────────────────────────────────┐
      │  Pluggable AI Model Interfaces  │
      ├────────────────┬────────────────┤
      │    Member 2    │    Member 3    │
      │ VisualDetector │ Audio / Speech │
      │ (Placeholder)  │ (Placeholder)  │
      └────────────────┴────────────────┘
                       ▼
           ┌───────────────────────┐
           │   Response Assembly   │
           └───────────┬───────────┘
                       ▼
           ┌───────────────────────┐
           │   Workspace Cleanup   │ (shutil.rmtree -> Zero Retention)
           └───────────┬───────────┘
                       ▼
             [ JSON Response ]
```

---

## 🧩 Team Member Integration Guide

### 👁️ Member 2: Visual AI Deepfake Detector (Stage 1 Implemented)
Implemented in: 📁 `app/services/detectors/visual_detector.py`

- **Model Name:** `EfficientNet-B0-FFPP-C23`
- **Source / Repository:** [Xicor9/efficientnet-b0-ffpp-c23](https://huggingface.co/Xicor9/efficientnet-b0-ffpp-c23)
- **License:** MIT License
- **Face Detector:** Google MediaPipe FaceDetector (`blaze_face_short_range.tflite`)
- **Device Support:** Auto-selects CUDA when available; automatically falls back to CPU.
- **Expected Input:** Video frame samples at ~1 FPS. MediaPipe locates faces, selects the primary face by maximum bounding box area, applies a 10% safety margin, and extracts RGB face crops.
- **Preprocessing:** Resizes face crops to (224, 224), converts to PyTorch tensor in range [0.0, 1.0].
- **Output Interpretation:**
  - `real_score`: Softmax probability score for Class 0 (Real/Authentic)
  - `fake_score`: Softmax probability score for Class 1 (Fake/Manipulated)
  - Missing faces or unreadable frames return `face_detected: false`, `real_score: null`, `fake_score: null` without crashing.

> ⚠️ **FORENSIC DISCLAIMER:**  
> *Authenitca uses a pretrained research model as one forensic signal. Its output is not a calibrated probability and does not by itself establish that media is fake.*  
> The visual detector provides evidence of facial manipulation/deepfake-style artifacts represented in its training dataset (FaceForensics++ C23: DeepFake, FaceSwap, Face2Face, NeuralTextures). Raw forensic scores are forwarded downstream for multi-modal evidence fusion.

```python
from app.services.detectors.visual_detector import VisualDeepfakeDetector

# Singleton access
detector = VisualDeepfakeDetector.get_instance()
# analyze(frames, video_info) returns VisualResult
```

### 🎙️ For Member 3 (Audio Spoofing & Speech-to-Text)
Implement `AudioDetector` and `SpeechToText` interfaces in:
📁 `app/services/detectors/base.py`

```python
from app.services.detectors.base import AudioDetector, SpeechToText
from app.schemas.analysis import AudioResult, SpeechResult, VideoInfo
from pathlib import Path

class Member3AudioDetector(AudioDetector):
    async def analyze(self, audio_path: Path | None, video_info: VideoInfo) -> AudioResult:
        # Analyzes the extracted 16kHz mono WAV file for voice synthesis / cloning artifacts
        ...

class Member3SpeechToText(SpeechToText):
    async def transcribe(self, audio_path: Path | None, video_info: VideoInfo) -> SpeechResult:
        # Transcribes audio with Whisper / open-source ASR model
        ...
```

---

## 📋 What is Implemented vs Intentionally Deferred

| Feature | Status | Responsible |
| :--- | :--- | :--- |
| **FastAPI REST Application & Health Check** | ✅ Implemented | Member 1 |
| **Video Ingestion & Multipart Validation** | ✅ Implemented | Member 1 |
| **SHA-256 Media Hashing** | ✅ Implemented | Member 1 |
| **OpenCV Frame Sampling (~1 FPS)** | ✅ Implemented | Member 1 |
| **FFmpeg Media Inspection & 16kHz Audio Extraction** | ✅ Implemented | Member 1 |
| **Ephemeral Privacy & Cleanup Manager** | ✅ Implemented | Member 1 |
| **Shared Pydantic Data Contracts** | ✅ Implemented | Member 1 |
| **MediaPipe Face Detection & Face Cropping** | ✅ Implemented | Member 2 |
| **EfficientNet-B0 FF++ C23 Deepfake Detector** | ✅ Implemented | Member 2 |
| **Batched Visual Inference & CUDA/CPU Auto-Fallback** | ✅ Implemented | Member 2 |
| **Automated Pytest Suite (21 tests)** | ✅ Implemented | Member 1 & 2 |
| **Audio Voice Spoofing AI Model** | ⏳ Stage 2 Integration | Member 3 |
| **Whisper Speech-to-Text Model** | ⏳ Stage 2 Integration | Member 3 |
| **Timeline Fusion / Aggregated Fraud Risk Score** | ⏳ Stage 3 Integration | Team |
| **Frontend UI / React Dashboard** | ⏳ Later Stage | Member 2 |


> ⚠️ **IMPORTANT:** In Stage 1, detector interfaces return explicit `status: "unavailable"` and `available: false`. **No fake or fabricated AI detection scores are generated.**

---

## 🚀 Getting Started

### 1. Prerequisites

- **Python 3.10+** (Tested on Python 3.10 - 3.14)
- **FFmpeg & FFprobe** installed on system `PATH`

#### Installing FFmpeg:
- **Ubuntu/Debian:**
  ```bash
  sudo apt-get update && sudo apt-get install -y ffmpeg
  ```
- **macOS (Homebrew):**
  ```bash
  brew install ffmpeg
  ```
- **Fedora/RHEL:**
  ```bash
  sudo dnf install -y ffmpeg ffmpeg-free-devel
  ```
- **Windows (Chocolatey/Winget):**
  ```powershell
  winget install Gyan.FFmpeg
  ```

### 2. Create Virtual Environment & Install Dependencies

From the repository root or `backend/` directory:

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
# Linux/macOS:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 3. Environment Configuration

Create a `.env` file (or copy `.env.example`):

```bash
cp .env.example .env
```

Default configurable parameters:
```env
MAX_FILE_SIZE_MB=100
MAX_DURATION_SECONDS=90.0
FRAME_SAMPLE_FPS=1.0
LOG_LEVEL=INFO
```

### 4. Run the Development Server

From inside the `backend/` directory:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The server will be available at:
- **API Base:** `http://localhost:8000`
- **Interactive Swagger Docs:** `http://localhost:8000/docs`
- **Alternative ReDoc Docs:** `http://localhost:8000/redoc`

---

## 🧪 Running Automated Tests

Run the test suite using `pytest`:

```bash
# Run all tests
pytest tests/ -v

# Run with output logging
pytest tests/ -v -s
```

---

## 📡 API Reference

### 1. Health Check
`GET /api/health`

**Sample Response:**
```json
{
  "status": "ok",
  "ffmpeg_available": true,
  "ffprobe_available": true,
  "version": "1.0.0"
}
```

---

### 2. Video Analysis Upload
`POST /api/analyses`

- **Content-Type:** `multipart/form-data`
- **Body Parameter:** `file` (Video file: `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`)
- **Limits:** Max 100 MB, Max 90 seconds duration

**Sample `curl` command:**
```bash
curl -X POST "http://localhost:8000/api/analyses" \
  -H "accept: application/json" \
  -F "file=@/path/to/sample_video.mp4;type=video/mp4"
```

**Sample Response (Stage 1):**
```json
{
  "id": "e4b6c31a-637d-41a4-9e87-5c4e47cf793a",
  "status": "completed",
  "created_at": "2026-10-05T12:15:30.123456+00:00",
  "video": {
    "filename": "sample_video.mp4",
    "sha256": "4a5e2f7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f",
    "duration_s": 15.0,
    "fps": 30.0,
    "width": 1920,
    "height": 1080,
    "frames_sampled": 15,
    "audio_available": true
  },
  "visual": {
    "available": true,
    "model": "EfficientNet-B0-FFPP-C23",
    "status": "completed",
    "frames_analyzed": 15,
    "faces_found": 14,
    "face_detection_rate": 0.9333,
    "results": [
      {
        "timestamp_s": 0.0,
        "face_detected": true,
        "real_score": 0.9124,
        "fake_score": 0.0876
      },
      {
        "timestamp_s": 1.0,
        "face_detected": true,
        "real_score": 0.8841,
        "fake_score": 0.1159
      }
    ]
  },
  "audio": {
    "available": false,
    "model": null,
    "status": "unavailable",
    "results": []
  },
  "speech": {
    "available": false,
    "model": null,
    "status": "unavailable",
    "segments": []
  }
}
```

---

## 🔒 Privacy & Local Processing Principles

1. **Local-Only Inference:** Media processing, decoding, frame sampling, and subsequent AI model evaluations run entirely within the local execution environment.
2. **No Paid/Cloud APIs:** Zero data sent to Gemini, OpenAI, Claude, or third-party cloud APIs.
3. **Strict Zero Retention:** Uploaded videos, sampled frame images (`.jpg`), and extracted audio clips (`.wav`) reside exclusively in ephemeral subdirectories (`temp/{analysis_id}/`) and are purged immediately after response delivery.
