# AUTHENTICA — Development Log (Stage 1 Final Integration)

**Role:** Final Integration Engineer (Member 1 Foundation + Member 2 Vision + Member 3 Audio/Speech)  
**Theme:** AI Fraud & Deepfake Detection (Hackathena '26 2.0)  
**Status:** Stage 1 Pipeline 100% Operational & Verified on Local Machine  

---

## 🚀 Unified Stage 1 Pipeline Architecture

```
                      [ Client Video Upload ]
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
                     │  SHA-256 Fingerprint  │ (Streaming crypto hash)
                     └───────────┬───────────┘
                                 ▼
                     ┌───────────────────────┐
                     │  Video Preprocessing  │
                     │ (OpenCV + FFprobe)    │ (Duration, FPS, Dims, Audio Check)
                     └───────────┬───────────┘
                                 ▼
                     ┌───────────────────────┐
                     │ Frame Sampling (1fps) │ (Extracted JPEGs + Timestamps)
                     └───────────┬───────────┘
                                 ▼
                     ┌───────────────────────┐
                     │   Audio Extraction    │ (FFmpeg -> 16kHz Mono PCM WAV)
                     └───────────┬───────────┘
                                 ▼
          ┌─────────────────────────────────────────────┐
          │      Integrated Stage 1 AI Detection        │
          ├──────────────────────┬──────────────────────┤
          │       Member 2       │       Member 3       │
          │ MediaPipe BlazeFace  │ AASIST Anti-Spoofing │
          │         +            │          +           │
          │ EfficientNet-B0 FF++ │ Faster-Whisper Base  │
          └──────────────────────┴──────────────────────┘
                                 ▼
                     ┌───────────────────────┐
                     │   Response Assembly   │
                     └───────────┬───────────┘
                                 ▼
                     ┌───────────────────────┐
                     │   Workspace Cleanup   │ (Zero Retention Purge)
                     └───────────┬───────────┘
                                 ▼
                      [ JSON Stage 1 Result ]
```

---

## 🛠️ Integrated Modules & Implementations

### 1. Member 1: System Foundation & Media Engine
- **FastAPI Application (`backend/app/main.py`):** Lifespan startup check for FFmpeg/FFprobe, CORS, and error handling.
- **Validation & Hashing:** MIME & extension checks, size/duration thresholds, and streaming SHA-256 hashing.
- **Media Preprocessing (`backend/app/services/video_processor.py`):** Metadata extraction, 1 FPS frame sampling with timestamps, and FFmpeg 16kHz WAV audio extraction.
- **Zero-Retention Privacy (`backend/app/utils/temp_manager.py`):** Automatic workspace purging after response delivery.

### 2. Member 2: Visual AI & Face Deepfake Detector
- **Face Detection:** MediaPipe BlazeFace Short Range model (`blaze_face_short_range.tflite`) extracts primary face crops.
- **Deepfake Classification (`backend/app/services/detectors/visual_detector.py`):** Pretrained Hugging Face EfficientNet-B0 model trained on FaceForensics++ C23 (`Xicor9/efficientnet-b0-ffpp-c23`).
- **Output:** Produces frame-by-frame real/fake probability scores.

### 3. Member 3: Audio Anti-Spoofing & Speech-to-Text
- **Voice Spoofing Detection (`backend/app/services/detectors/audio_detector.py`):** Pretrained Clova AI AASIST Graph Attention model on 16kHz raw waveform.
- **Speech Transcription (`backend/app/services/detectors/speech_transcriber.py`):** Faster-Whisper Base model with CTranslate2 INT8 execution, VAD silence filtering, and timestamped speech segments.

---

## 📊 Live Verification Results

- **Automated Tests:** **31 / 31 passed** in pytest.
- **Endpoints:**
  - `GET /api/health` — Server health check
  - `POST /api/analyses` — Video upload and complete Stage 1 analysis
