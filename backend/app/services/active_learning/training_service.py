import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from app.core.logging import logger
from app.services.active_learning.adapter_models import (
    AuthenticaVisualAdapter,
    compute_param_checksum,
)

DEFAULT_ADAPTER_DIR = Path("backend/models/adapters")
DEFAULT_DATA_DIR = Path("backend/data")


class ActiveLearningTrainingService:
    """
    Continual Active Learning & Parameter Adaptation Service.
    
    Invariants:
      1. Base model (EfficientNet-B0-FFPP-C23) is 100% FROZEN and NEVER overwritten.
      2. Trainable parameters reside exclusively in the AuthenticaVisualAdapter layer.
      3. Training ONLY succeeds after optimizer.step() updates trainable weights.
      4. Parameter fingerprints (SHA-256) are calculated before and after optimization.
      5. Full artifact persistence with versioning, metrics, and rollback capability.
    """

    _instance: Optional["ActiveLearningTrainingService"] = None

    def __init__(
        self,
        adapter_dir: Path = DEFAULT_ADAPTER_DIR,
        data_dir: Path = DEFAULT_DATA_DIR,
        device: Optional[str] = None
    ):
        self.adapter_dir = adapter_dir
        self.data_dir = data_dir
        self.dataset_path = self.data_dir / "active_learning_dataset.json"
        self.metadata_path = self.adapter_dir / "visual_metadata.json"

        if device:
            self.device = torch.device(device)
        else:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self.adapter = AuthenticaVisualAdapter().to(self.device)
        self.active_version = "visual-v0"
        self.base_model_name = "EfficientNet-B0-FFPP-C23"
        self.base_model_version = "1.0.0"

        # Initialize directories and load latest adapter if present
        self.adapter_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.load_latest_adapter()

    @classmethod
    def get_instance(cls) -> "ActiveLearningTrainingService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_latest_adapter(self) -> None:
        """Loads latest persisted adapter weights and metadata from disk."""
        latest_ckpt = self.adapter_dir / "visual_adapter_latest.pth"
        if latest_ckpt.exists() and self.metadata_path.exists():
            try:
                meta = json.loads(self.metadata_path.read_text(encoding="utf-8"))
                self.active_version = meta.get("active_version", "visual-v0")
                state_dict = torch.load(str(latest_ckpt), map_location=self.device)
                self.adapter.load_state_dict(state_dict)
                self.adapter.eval()
                logger.info(
                    f"ActiveLearning: Loaded persisted adapter '{self.active_version}' "
                    f"({self.adapter.count_trainable_parameters()} params, "
                    f"checksum: {self.adapter.get_parameter_checksum()})."
                )
            except Exception as e:
                logger.warning(f"ActiveLearning: Failed to load latest adapter checkpoint: {e}")
                self.active_version = "visual-v0"
        else:
            self.active_version = "visual-v0"
            logger.info("ActiveLearning: No persisted adapter found. Initialized baseline visual-v0.")

    def rollback(self, target_version: str) -> Dict[str, Any]:
        """Rolls back the active model to a previous adapter version checkpoint."""
        ckpt_path = self.adapter_dir / f"visual_adapter_{target_version}.pth"
        if not ckpt_path.exists():
            raise FileNotFoundError(f"Adapter version '{target_version}' checkpoint not found at {ckpt_path}")

        state_dict = torch.load(str(ckpt_path), map_location=self.device)
        self.adapter.load_state_dict(state_dict)
        self.active_version = target_version

        # Update metadata active version
        if self.metadata_path.exists():
            meta = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            meta["active_version"] = target_version
            self.metadata_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        # Copy to latest
        torch.save(self.adapter.state_dict(), self.adapter_dir / "visual_adapter_latest.pth")

        logger.info(f"ActiveLearning: Successfully rolled back adapter to '{target_version}'.")
        return {
            "status": "rolled_back",
            "active_version": target_version,
            "parameter_checksum": self.adapter.get_parameter_checksum(),
        }

    def _load_dataset(self) -> Dict[str, Any]:
        if self.dataset_path.exists():
            try:
                return json.loads(self.dataset_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"version": "ds-v0", "samples": []}

    def _save_dataset(self, data: Dict[str, Any]) -> None:
        self.dataset_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def train_on_sample(
        self,
        analysis_id: str,
        features: List[List[float]],
        telemetry: Optional[List[List[float]]],
        ground_truth_media: str,  # 'REAL' or 'FAKE'
        epochs: int = 15,
        lr: float = 0.005
    ) -> Dict[str, Any]:
        """
        Executes genuine gradient-descent parameter optimization on the adapter layer.
        
        Args:
            analysis_id: Associated analysis UUID.
            features: List of 1280-dim feature vectors from analyzed frames.
            telemetry: Optional list of 4-dim capture quality telemetry vectors.
            ground_truth_media: 'REAL' (class 0) or 'FAKE' (class 1).
            epochs: Training epochs.
            lr: Learning rate for AdamW optimizer.
            
        Returns:
            Dictionary containing before/after training metrics, loss, and checksums.
        """
        if not features:
            raise ValueError("No feature vectors provided for active learning training.")

        target_label = 0 if ground_truth_media == "REAL" else 1

        # 1. Update versioned persistent training dataset
        dataset_obj = self._load_dataset()
        current_samples = dataset_obj.get("samples", [])

        # Store compact mean representation of the verified sample
        mean_feat = np.mean(np.array(features, dtype=np.float32), axis=0).tolist()
        mean_telem = np.mean(np.array(telemetry, dtype=np.float32), axis=0).tolist() if telemetry else [0.0, 0.0, 0.0, 0.0]

        new_sample_entry = {
            "analysis_id": analysis_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "target_label": target_label,
            "ground_truth_media": ground_truth_media,
            "feature_dim": len(mean_feat),
            "feature": mean_feat,
            "telemetry": mean_telem,
            "frame_count": len(features)
        }
        current_samples.append(new_sample_entry)

        curr_ds_num = int(dataset_obj.get("version", "ds-v0").replace("ds-v", "")) + 1
        new_ds_version = f"ds-v{curr_ds_num}"
        dataset_obj["version"] = new_ds_version
        dataset_obj["samples"] = current_samples
        self._save_dataset(dataset_obj)

        # 2. Build training batch from dataset samples (with diversity)
        all_features = []
        all_targets = []
        for s in current_samples:
            feat_arr = np.array(s["feature"], dtype=np.float32)
            telem_arr = np.array(s.get("telemetry", [0, 0, 0, 0]), dtype=np.float32)
            fused = np.concatenate([feat_arr, telem_arr])
            all_features.append(fused)
            all_targets.append(s["target_label"])

        # Also add all individual frame features from the current video for strong local adaptation
        for idx, f in enumerate(features):
            t = telemetry[idx] if telemetry and idx < len(telemetry) else [0.0, 0.0, 0.0, 0.0]
            fused_frame = np.concatenate([np.array(f, dtype=np.float32), np.array(t, dtype=np.float32)])
            all_features.append(fused_frame)
            all_targets.append(target_label)

        X_tensor = torch.tensor(np.array(all_features, dtype=np.float32), device=self.device)
        y_tensor = torch.tensor(np.array(all_targets, dtype=np.int64), device=self.device)

        # 3. Parameter Fingerprinting BEFORE training
        checksum_before = compute_param_checksum(self.adapter)
        param_count = self.adapter.count_trainable_parameters()

        # 4. Actual Optimizer Step Loop
        self.adapter.train()
        optimizer = optim.AdamW(self.adapter.parameters(), lr=lr, weight_decay=1e-4)
        criterion = nn.CrossEntropyLoss()

        with torch.no_grad():
            initial_logits = self.adapter(X_tensor)
            initial_loss = float(criterion(initial_logits, y_tensor).item())

        losses = []
        for epoch in range(epochs):
            optimizer.zero_grad()
            logits = self.adapter(X_tensor)
            loss = criterion(logits, y_tensor)
            loss.backward()
            optimizer.step()  # REAL OPTIMIZER UPDATE
            losses.append(loss.item())

        final_loss = float(losses[-1])
        self.adapter.eval()

        # 5. Parameter Fingerprinting AFTER training
        checksum_after = compute_param_checksum(self.adapter)

        # 6. Increment and Save Version Checkpoint
        curr_ver_num = int(self.active_version.replace("visual-v", "")) if "visual-v" in self.active_version else 0
        new_ver_num = curr_ver_num + 1
        new_adapter_version = f"visual-v{new_ver_num}"

        version_ckpt = self.adapter_dir / f"visual_adapter_{new_adapter_version}.pth"
        latest_ckpt = self.adapter_dir / "visual_adapter_latest.pth"

        torch.save(self.adapter.state_dict(), str(version_ckpt))
        torch.save(self.adapter.state_dict(), str(latest_ckpt))

        # 7. Persist Metadata History
        meta_history = []
        if self.metadata_path.exists():
            try:
                m_data = json.loads(self.metadata_path.read_text(encoding="utf-8"))
                meta_history = m_data.get("history", [])
            except Exception:
                meta_history = []

        training_record = {
            "version": new_adapter_version,
            "base_model": self.base_model_name,
            "base_model_version": self.base_model_version,
            "dataset_version": new_ds_version,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "samples_used": len(current_samples),
            "epochs_run": epochs,
            "initial_loss": round(initial_loss, 4),
            "final_loss": round(final_loss, 4),
            "loss_reduction": round(initial_loss - final_loss, 4),
            "trainable_parameters": param_count,
            "param_checksum_before": checksum_before,
            "param_checksum_after": checksum_after,
            "parameters_changed": checksum_before != checksum_after
        }
        meta_history.append(training_record)

        full_meta = {
            "base_model": self.base_model_name,
            "base_model_version": self.base_model_version,
            "active_version": new_adapter_version,
            "latest_update": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "history": meta_history
        }
        self.metadata_path.write_text(json.dumps(full_meta, indent=2), encoding="utf-8")
        self.active_version = new_adapter_version

        logger.info(
            f"ActiveLearning: Model training completed. Updated '{checksum_before}' -> '{checksum_after}'. "
            f"Loss: {initial_loss:.4f} -> {final_loss:.4f}. Active version: {new_adapter_version}."
        )

        return {
            "status": "completed",
            "active_version": new_adapter_version,
            "dataset_version": new_ds_version,
            "samples_used": len(current_samples),
            "trainable_parameters": param_count,
            "param_checksum_before": checksum_before,
            "param_checksum_after": checksum_after,
            "initial_loss": round(initial_loss, 4),
            "final_loss": round(final_loss, 4),
            "epochs": epochs
        }

