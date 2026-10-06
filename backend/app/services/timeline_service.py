import math
from typing import List, Optional

from app.core.config import settings
from app.core.logging import logger
from app.schemas.analysis import AudioResult, SpeechResult, VisualResult
from app.schemas.fraud import FraudResult
from app.schemas.timeline import TimelineEvent


class TimelineService:
    """
    Stage 2 & Stage 3 Timeline Aggregation Service.
    Aggregates point and window observations from sensory detectors and fraud intent engine
    into structured, explainable, and timestamped timeline evidence events.
    
    Adheres strictly to timestamp fidelity: never claims more precision than underlying
    detectors provide.
    """

    def __init__(
        self,
        window_duration_s: float = settings.TIMELINE_WINDOW_DURATION_S,
        visual_low: float = settings.VISUAL_LOW_THRESHOLD,
        visual_high: float = settings.VISUAL_HIGH_THRESHOLD,
        audio_low: float = settings.AUDIO_LOW_THRESHOLD,
        audio_high: float = settings.AUDIO_HIGH_THRESHOLD,
    ):
        self.window_duration_s = window_duration_s
        self.visual_low = visual_low
        self.visual_high = visual_high
        self.audio_low = audio_low
        self.audio_high = audio_high

    def aggregate(
        self,
        visual: VisualResult,
        audio: AudioResult,
        speech: SpeechResult,
        video_duration_s: float,
        fraud: Optional[FraudResult] = None,
    ) -> List[TimelineEvent]:
        """
        Synthesizes visual, audio, speech, and fraud observations into a unified chronological timeline.
        
        Args:
            visual: Visual frame results.
            audio: Audio sliding window results.
            speech: Transcribed speech segments.
            video_duration_s: Total video duration.
            fraud: Stage 3 Fraud Intent results.
            
        Returns:
            Sorted list of TimelineEvent objects.
        """
        events: List[TimelineEvent] = []

        # 1. Visual Timeline Aggregation (~3s windows with noise filtering)
        visual_events = self._aggregate_visual_windows(visual, video_duration_s)
        events.extend(visual_events)

        # 2. Audio Timeline Aggregation
        audio_events = self._aggregate_audio_windows(audio)
        events.extend(audio_events)

        # 3. Speech Transcript Timeline Events
        speech_events = self._aggregate_speech_segments(speech)
        events.extend(speech_events)

        # 4. Stage 3 Fraud Intent Timeline Events
        if fraud:
            fraud_events = self._aggregate_fraud_events(fraud)
            events.extend(fraud_events)

        # 5. Sort chronologically by start_s, then end_s
        events.sort(key=lambda ev: (ev.start_s, ev.end_s))

        logger.info(f"Timeline Aggregation: Synthesized {len(events)} timeline events.")
        return events

    def _aggregate_visual_windows(
        self,
        visual: VisualResult,
        video_duration_s: float
    ) -> List[TimelineEvent]:
        """
        Groups ~1 FPS frame results into ~3-second windows and applies consecutive-window
        noise filtering for high-confidence visual manipulation events.
        """
        if not visual.available or not visual.results:
            return []

        # Partition frames into discrete 3-second bins
        num_windows = max(1, math.ceil(video_duration_s / self.window_duration_s))
        raw_windows = []

        for w_idx in range(num_windows):
            w_start = round(w_idx * self.window_duration_s, 2)
            w_end = round(min((w_idx + 1) * self.window_duration_s, video_duration_s), 2)

            # Collect all frames strictly belonging to this time window
            if w_idx == num_windows - 1:
                frames_in_win = [
                    f for f in visual.results
                    if w_start <= f.timestamp_s <= w_end
                ]
            else:
                frames_in_win = [
                    f for f in visual.results
                    if w_start <= f.timestamp_s < w_end
                ]

            valid_fake_scores = [
                f.fake_score for f in frames_in_win
                if f.face_detected is True and f.fake_score is not None
            ]

            if valid_fake_scores:
                n_frames = len(valid_fake_scores)
                sorted_scores = sorted(valid_fake_scores)
                max_score = round(max(valid_fake_scores), 4)
                mean_score = round(sum(valid_fake_scores) / n_frames, 4)
                median_score = round(
                    sorted_scores[n_frames // 2] if n_frames % 2 == 1 else (sorted_scores[n_frames // 2 - 1] + sorted_scores[n_frames // 2]) / 2.0,
                    4
                )
                high_count = len([s for s in valid_fake_scores if s >= self.visual_high])
                
                # Robust window level assignment:
                # A window is HIGH only if mean score is high, or multiple frames exceed threshold
                if mean_score >= self.visual_high or (high_count >= 2 and mean_score >= 0.55) or (n_frames == 1 and max_score >= self.visual_high):
                    raw_level = "HIGH"
                elif mean_score >= self.visual_low or high_count >= 1 or max_score >= self.visual_high:
                    raw_level = "MEDIUM"
                else:
                    raw_level = "LOW"

                raw_windows.append({
                    "start_s": w_start,
                    "end_s": w_end,
                    "score": mean_score,
                    "max_score": max_score,
                    "mean_score": mean_score,
                    "median_score": median_score,
                    "raw_level": raw_level,
                    "frame_count": n_frames
                })
            else:
                # No face detected in this window
                raw_windows.append({
                    "start_s": w_start,
                    "end_s": w_end,
                    "score": None,
                    "max_score": None,
                    "mean_score": None,
                    "median_score": None,
                    "raw_level": "N/A",
                    "frame_count": 0
                })

        # Apply noise reduction:
        # A single isolated HIGH window without an adjacent qualifying window (score >= visual_low)
        # is downgraded to MEDIUM to prevent isolated false positives from dominating the timeline.
        events: List[TimelineEvent] = []
        for i, win in enumerate(raw_windows):
            level = win["raw_level"]

            if level == "HIGH":
                has_prev_qualifying = (
                    i > 0 and raw_windows[i - 1]["score"] is not None and
                    raw_windows[i - 1]["score"] >= self.visual_low
                )
                has_next_qualifying = (
                    i < len(raw_windows) - 1 and raw_windows[i + 1]["score"] is not None and
                    raw_windows[i + 1]["score"] >= self.visual_low
                )
                if not (has_prev_qualifying or has_next_qualifying) and len(raw_windows) > 1:
                    # Isolated spike window: attenuate to MEDIUM
                    level = "MEDIUM"

            if level != "N/A" or win["frame_count"] > 0:
                events.append(TimelineEvent(
                    start_s=win["start_s"],
                    end_s=win["end_s"],
                    kind="visual",
                    level=level,
                    evidence_source="visual_window",
                    score=win["score"],
                    details=f"Frames evaluated: {win['frame_count']}"
                ))

        return events

    def _aggregate_audio_windows(self, audio: AudioResult) -> List[TimelineEvent]:
        """Maps Stage 1 audio windows into timeline events with evidence levels."""
        if not audio.available or not audio.results:
            return []

        events: List[TimelineEvent] = []
        for win in audio.results:
            score = win.spoof_score
            if score is not None:
                if score >= self.audio_high:
                    level = "HIGH"
                elif score >= self.audio_low:
                    level = "MEDIUM"
                else:
                    level = "LOW"
            else:
                level = "N/A"

            events.append(TimelineEvent(
                start_s=round(win.start_s, 2),
                end_s=round(win.end_s, 2),
                kind="audio",
                level=level,
                evidence_source="audio_window",
                score=score,
                details=f"AASIST voice anti-spoofing window [{win.start_s:.1f}s - {win.end_s:.1f}s]"
            ))

        return events

    def _aggregate_speech_segments(self, speech: SpeechResult) -> List[TimelineEvent]:
        """Maps Whisper timestamped transcript segments directly to the timeline."""
        if not speech.available or not speech.segments:
            return []

        events: List[TimelineEvent] = []
        for seg in speech.segments:
            events.append(TimelineEvent(
                start_s=round(seg.start_s, 2),
                end_s=round(seg.end_s, 2),
                kind="transcript",
                level="N/A",
                evidence_source="transcript_segment",
                score=None,
                details=seg.text
            ))

        return events

    def _aggregate_fraud_events(self, fraud: FraudResult) -> List[TimelineEvent]:
        """Maps detected fraud evidence spans into timeline events."""
        if not fraud or fraud.level == "NOT_ASSESSABLE":
            return []

        events: List[TimelineEvent] = []
        for cat in fraud.categories:
            for ev in cat.evidence:
                events.append(TimelineEvent(
                    start_s=round(ev.start_s, 2),
                    end_s=round(ev.end_s, 2),
                    kind="fraud",
                    level=cat.severity,
                    evidence_source="transcript_segment",
                    score=None,
                    details=f"[{cat.category}] {ev.phrase}"
                ))

        return events
