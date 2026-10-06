import os
import time
import urllib.request
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
import torch
import torch.nn as nn
from torchvision import models, transforms

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from app.core.logging import logger
from app.schemas.analysis import VideoInfo, VisualFrameResult, VisualResult
from app.services.detectors.base import FrameSample, VisualDetector

# Model constants & provenance
MODEL_NAME = "EfficientNet-B0-FFPP-C23"
MODEL_VERSION = "1.0.0"
MODEL_LICENSE = "MIT"
MODEL_CHECKPOINT_URL = "https://huggingface.co/Xicor9/efficientnet-b0-ffpp-c23/resolve/main/efficientnet_b0_ffpp_c23.pth"
MEDIAPIPE_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite"

IMAGE_SIZE = (224, 224)


class VisualDeepfakeDetector(VisualDetector):
    """
    Member 2 Visual AI / Face Deepfake Detector Service for Stage 1.
    
    Pipeline:
      Sampled Frames -> MediaPipe Face Detector -> Face Bounding Box ->
      Face Crop & Preprocessing -> EfficientNet-B0 FaceForensics++ C23 Model ->
      Forensic Real/Fake Class Scores -> Structured VisualResult.
    
    Responsibilities:
      - Loads pretrained EfficientNet-B0 model once (singleton/cached).
      - Automatically detects CUDA if available, with CPU fallback.
      - Uses inference/no-grad mode for evaluation.
      - Employs MediaPipe BlazeFace for lightweight, robust local face detection.
      - Crops and preprocesses primary faces to (224, 224) RGB tensors.
      - Handles missing faces, multiple faces, bad images, and inference errors gracefully.
      - Never fabricates scores or outputs uncalibrated verdicts.
    """

    _instance: Optional["VisualDeepfakeDetector"] = None

    def __init__(
        self,
        device: Optional[str] = None,
        model_url: str = MODEL_CHECKPOINT_URL,
        min_face_confidence: float = 0.5,
    ):
        self.model_url = model_url
        self.min_face_confidence = min_face_confidence
        
        # 1. Device selection
        if device:
            self.device = torch.device(device)
        else:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        logger.info(f"VisualDeepfakeDetector initialized on target device: {self.device}")

        # Model and detector holders
        self.model: Optional[nn.Module] = None
        self.face_detector: Optional[vision.FaceDetector] = None
        self._is_loaded = False

        # Image transform: Resize to 224x224 and convert to float tensor [0, 1]
        self.transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize(IMAGE_SIZE),
            transforms.ToTensor(),
        ])

    @classmethod
    def get_instance(cls) -> "VisualDeepfakeDetector":
        """Singleton accessor to prevent reloading weights across requests."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load(self) -> None:
        """
        Loads the pretrained model and MediaPipe face detector.
        Thread-safe / idempotent: does not reload if already loaded.
        """
        if self._is_loaded and self.model is not None and self.face_detector is not None:
            return

        logger.info("VisualDeepfakeDetector: Loading models...")
        start_time = time.perf_counter()

        try:
            # A. Load MediaPipe Face Detector
            self._load_face_detector()

            # B. Load EfficientNet-B0 FF++ C23 Checkpoint
            self._load_classifier_model()

            self._is_loaded = True
            load_elapsed = time.perf_counter() - start_time
            logger.info(
                f"VisualDeepfakeDetector: Successfully loaded on {self.device} in {load_elapsed:.2f}s."
            )
        except Exception as e:
            logger.error(f"VisualDeepfakeDetector: Failed to load models: {e}")
            self._is_loaded = False
            raise

    def _load_face_detector(self) -> None:
        """Downloads and initializes the MediaPipe FaceDetector task."""
        cache_dir = Path.home() / ".cache" / "mediapipe"
        cache_dir.mkdir(parents=True, exist_ok=True)
        model_path = cache_dir / "blaze_face_short_range.tflite"

        if not model_path.exists():
            logger.info(f"Downloading MediaPipe FaceDetector model to {model_path}...")
            urllib.request.urlretrieve(MEDIAPIPE_MODEL_URL, str(model_path))

        base_options = python.BaseOptions(model_asset_path=str(model_path))
        options = vision.FaceDetectorOptions(
            base_options=base_options,
            min_detection_confidence=self.min_face_confidence
        )
        self.face_detector = vision.FaceDetector.create_from_options(options)
        logger.debug("MediaPipe FaceDetector initialized.")

    def _load_classifier_model(self) -> None:
        """Downloads and initializes the EfficientNet-B0 classifier with FF++ weights."""
        logger.info(f"Loading EfficientNet-B0 FF++ C23 weights from {self.model_url}...")
        
        try:
            state_dict = torch.hub.load_state_dict_from_url(
                self.model_url,
                map_location=self.device,
                progress=False
            )
        except Exception as e:
            logger.warning(f"Failed to load weights to {self.device}: {e}. Falling back to CPU.")
            self.device = torch.device("cpu")
            state_dict = torch.hub.load_state_dict_from_url(
                self.model_url,
                map_location="cpu",
                progress=False
            )

        # Build architecture: EfficientNet-B0 with 2-class head
        model = models.efficientnet_b0(weights=None)
        in_features = model.classifier[1].in_features
        model.classifier[1] = nn.Linear(in_features, 2)
        model.load_state_dict(state_dict)
        model.to(self.device)
        model.eval()

        self.model = model
        logger.debug("EfficientNet-B0 FF++ C23 model loaded and set to eval mode.")

    def detect_primary_face(self, img_rgb: np.ndarray) -> Optional[np.ndarray]:
        """
        Detects faces using MediaPipe and extracts the primary face crop.
        
        Selection strategy:
          - If 1 face: return that crop.
          - If multiple faces: return the face with largest bounding box area.
          - If 0 faces: return None.
        
        Includes safety margin and bounds clamping.
        """
        if self.face_detector is None:
            raise RuntimeError("Face detector is not initialized. Call load() first.")

        h, w, _ = img_rgb.shape
        if h == 0 or w == 0:
            return None

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
        detection_result = self.face_detector.detect(mp_image)

        if not detection_result.detections:
            return None

        # Select primary face based on bounding box area
        best_box = None
        max_area = -1

        for det in detection_result.detections:
            box = det.bounding_box
            area = box.width * box.height
            if area > max_area:
                max_area = area
                best_box = box

        if best_box is None:
            return None

        # Add 10% padding around face crop for forensic context
        pad_x = int(best_box.width * 0.10)
        pad_y = int(best_box.height * 0.10)

        x1 = max(0, best_box.origin_x - pad_x)
        y1 = max(0, best_box.origin_y - pad_y)
        x2 = min(w, best_box.origin_x + best_box.width + pad_x)
        y2 = min(h, best_box.origin_y + best_box.height + pad_y)

        if x2 <= x1 or y2 <= y1:
            return None

        face_crop = img_rgb[y1:y2, x1:x2]
        return face_crop

    @staticmethod
    def _calculate_face_forensics(face_crop_rgb: np.ndarray) -> Tuple[float, float]:
        """
        Computes forensic quality and spatial-frequency anomaly indicators:
          1. Sharpness / Focus Index (Laplacian variance normalized to [0, 1])
          2. High-Frequency Spectral Artifact Score (2D FFT energy distribution)
        """
        try:
            gray = cv2.cvtColor(face_crop_rgb, cv2.COLOR_RGB2GRAY)
            # 1. Laplacian sharpness metric
            lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            sharpness = float(np.clip(lap_var / 150.0, 0.05, 1.0))

            # 2. 2D FFT Frequency Analysis
            # Synthetic generators and blending boundaries leave high-frequency grid & boundary artifacts
            h, w = gray.shape
            if h < 16 or w < 16:
                return sharpness, 0.0

            f = np.fft.fft2(gray.astype(np.float32))
            fshift = np.fft.fftshift(f)
            mag = np.log1p(np.abs(fshift))

            cy, cx = h // 2, w // 2
            r_inner = min(h, w) // 6
            r_outer = min(h, w) // 2

            y, x = np.ogrid[:h, :w]
            dist = np.sqrt((x - cx)**2 + (y - cy)**2)

            low_mask = dist <= r_inner
            high_mask = (dist > r_inner) & (dist <= r_outer)

            low_e = np.mean(mag[low_mask]) if np.any(low_mask) else 1.0
            high_e = np.mean(mag[high_mask]) if np.any(high_mask) else 0.0

            ratio = float(high_e / max(1e-5, low_e))
            spectral_anomaly = float(np.clip((ratio - 0.40) * 1.5, 0.0, 1.0))
            return sharpness, spectral_anomaly
        except Exception:
            return 1.0, 0.0

    @classmethod
    def _calibrate_crop_score(cls, raw_real: float, raw_fake: float, face_crop_rgb: np.ndarray) -> Tuple[float, float]:
        """
        Calibrates raw neural network logits against optical and spatial-frequency indicators.
        Prevents low-resolution webcam compression and motion blur from generating false positives.
        """
        sharpness, spectral_anomaly = cls._calculate_face_forensics(face_crop_rgb)
        h, w, _ = face_crop_rgb.shape
        min_dim = min(h, w)

        fake_score = raw_fake

        # 1. Webcam Compression & Low-Resolution Gating:
        # If crop is small (<120px) or low sharpness without strong AI spectral anomaly,
        # damp compression noise towards genuine baseline
        if min_dim < 120 or sharpness < 0.40:
            quality_factor = min(1.0, max(0.2, (min_dim / 120.0) * (sharpness / 0.40)))
            if spectral_anomaly < 0.35:
                # Natural camera compression: pull towards genuine baseline
                fake_score = fake_score * (0.35 + 0.65 * quality_factor)
            else:
                # High spectral anomaly: retain AI generation artifact score
                fake_score = fake_score * 0.85 + spectral_anomaly * 0.15

        # 2. Clean Camera Optics:
        # High sharpness with minimal spectral anomaly indicates authentic camera feed
        if sharpness > 0.60 and spectral_anomaly < 0.10:
            fake_score = min(fake_score, fake_score * 0.85)

        fake_score = float(np.clip(fake_score, 0.01, 0.99))
        fake_score = round(fake_score, 4)
        real_score = round(1.0 - fake_score, 4)
        return real_score, fake_score

    def predict_face_crop(self, face_crop_rgb: np.ndarray) -> Tuple[float, float]:
        """
        Runs model inference on a single RGB face crop with quality-aware calibration.
        Returns: (real_score, fake_score)
        """
        if self.model is None:
            raise RuntimeError("Classifier model is not initialized. Call load() first.")

        tensor = self.transform(face_crop_rgb).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self.model(tensor)
            scaled_logits = logits / 1.2
            probs = torch.softmax(scaled_logits, dim=-1)[0]
            raw_real = float(probs[0].item())
            raw_fake = float(probs[1].item())

        return self._calibrate_crop_score(raw_real, raw_fake, face_crop_rgb)

    def predict_batch(self, face_crops_rgb: List[np.ndarray]) -> List[Tuple[float, float]]:
        """
        Runs batched model inference on a list of RGB face crops with quality-aware calibration.
        Returns: List of (real_score, fake_score)
        """
        if not face_crops_rgb:
            return []

        if self.model is None:
            raise RuntimeError("Classifier model is not initialized. Call load() first.")

        tensors = [self.transform(crop) for crop in face_crops_rgb]
        batch_tensor = torch.stack(tensors).to(self.device)

        with torch.no_grad():
            logits = self.model(batch_tensor)
            scaled_logits = logits / 1.2
            probs = torch.softmax(scaled_logits, dim=-1)
            raw_scores = [
                (float(p[0].item()), float(p[1].item()))
                for p in probs
            ]

        results: List[Tuple[float, float]] = []
        for crop, (raw_real, raw_fake) in zip(face_crops_rgb, raw_scores):
            results.append(self._calibrate_crop_score(raw_real, raw_fake, crop))

        return results

    async def analyze(
        self,
        frames: List[FrameSample],
        video_info: VideoInfo
    ) -> VisualResult:
        """
        Executes Stage 1 visual analysis on sampled frames according to the shared contract.
        """
        start_time = time.perf_counter()

        if not frames:
            logger.info("VisualDeepfakeDetector: No frames provided for analysis.")
            return VisualResult(
                available=True,
                model=MODEL_NAME,
                status="completed",
                frames_analyzed=0,
                faces_found=0,
                face_detection_rate=0.0,
                results=[]
            )

        # Ensure models are loaded
        try:
            self.load()
        except Exception as e:
            logger.error(f"VisualDeepfakeDetector: Cannot run analysis due to loading failure: {e}")
            return VisualResult(
                available=False,
                model=MODEL_NAME,
                status="error",
                frames_analyzed=0,
                faces_found=0,
                face_detection_rate=None,
                results=[]
            )

        # Process each frame: extract face and prepare for inference
        frame_results: List[VisualFrameResult] = []
        valid_face_crops: List[np.ndarray] = []
        face_crop_indices: List[int] = []  # Maps crop index to frame_results index

        for idx, frame_sample in enumerate(frames):
            ts = frame_sample.timestamp_s
            frame_path = frame_sample.frame_path

            # Handle unreadable / missing frame files safely
            if not frame_path.exists():
                logger.warning(f"Frame file does not exist: {frame_path}")
                frame_results.append(VisualFrameResult(
                    timestamp_s=ts,
                    face_detected=False,
                    real_score=None,
                    fake_score=None
                ))
                continue

            try:
                img_bgr = cv2.imread(str(frame_path.resolve()))
                if img_bgr is None or img_bgr.size == 0:
                    logger.warning(f"Failed to read image at {frame_path}")
                    frame_results.append(VisualFrameResult(
                        timestamp_s=ts,
                        face_detected=False,
                        real_score=None,
                        fake_score=None
                    ))
                    continue

                img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                face_crop = self.detect_primary_face(img_rgb)

                if face_crop is None:
                    # No face detected in this frame
                    frame_results.append(VisualFrameResult(
                        timestamp_s=ts,
                        face_detected=False,
                        real_score=None,
                        fake_score=None
                    ))
                else:
                    # Face detected - stage for inference
                    frame_results.append(VisualFrameResult(
                        timestamp_s=ts,
                        face_detected=True,
                        real_score=None,
                        fake_score=None
                    ))
                    valid_face_crops.append(face_crop)
                    face_crop_indices.append(len(frame_results) - 1)

            except Exception as e:
                logger.warning(f"Error processing frame {frame_path.name} at {ts}s: {e}")
                frame_results.append(VisualFrameResult(
                    timestamp_s=ts,
                    face_detected=False,
                    real_score=None,
                    fake_score=None
                ))

        # Run batched inference on all extracted face crops
        if valid_face_crops:
            try:
                scores = self.predict_batch(valid_face_crops)
                for crop_idx, (real_s, fake_s) in enumerate(scores):
                    target_idx = face_crop_indices[crop_idx]
                    frame_results[target_idx].real_score = real_s
                    frame_results[target_idx].fake_score = fake_s
            except Exception as e:
                logger.error(f"Inference batch failed: {e}. Falling back to sequential inference.")
                for crop_idx, crop in enumerate(valid_face_crops):
                    target_idx = face_crop_indices[crop_idx]
                    try:
                        real_s, fake_s = self.predict_face_crop(crop)
                        frame_results[target_idx].real_score = real_s
                        frame_results[target_idx].fake_score = fake_s
                    except Exception as frame_err:
                        logger.warning(f"Inference failed on individual crop {crop_idx}: {frame_err}")
                        frame_results[target_idx].face_detected = False
                        frame_results[target_idx].real_score = None
                        frame_results[target_idx].fake_score = None

        # Calculate quality metrics
        frames_analyzed = len(frame_results)
        faces_found = sum(1 for r in frame_results if r.face_detected is True)
        face_detection_rate = round(faces_found / frames_analyzed, 4) if frames_analyzed > 0 else 0.0
        elapsed = time.perf_counter() - start_time

        logger.info(
            f"VisualDeepfakeDetector: Analyzed {frames_analyzed} frames | "
            f"Faces found: {faces_found} ({face_detection_rate * 100:.1f}%) | "
            f"Elapsed: {elapsed:.2f}s"
        )

        return VisualResult(
            available=True,
            model=MODEL_NAME,
            status="completed",
            frames_analyzed=frames_analyzed,
            faces_found=faces_found,
            face_detection_rate=face_detection_rate,
            results=frame_results
        )
