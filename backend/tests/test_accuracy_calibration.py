import pytest
from app.schemas.analysis import (
    AudioResult,
    AudioWindowResult,
    SpeechResult,
    SpeechSegment,
    VideoInfo,
    VisualFrameResult,
    VisualResult,
)
from app.schemas.evidence import (
    EvidenceMatrix,
    EvidenceMetadata,
    EvidenceModalityResult,
    ModelEvidenceItem,
    ProvenanceResult,
)
from app.schemas.reliability import ReliabilityResult
from app.schemas.timeline import TimelineEvent
from app.services.assessment_service import AssessmentService
from app.services.evidence_service import EvidenceService
from app.services.fraud_engine import FraudIntentEngine
from app.services.timeline_service import TimelineService


@pytest.fixture
def evidence_service():
    return EvidenceService()


@pytest.fixture
def timeline_service():
    return TimelineService()


@pytest.fixture
def assessment_service():
    return AssessmentService()


@pytest.fixture
def fraud_engine():
    return FraudIntentEngine()


# --------------------------------------------------------------------------
# 1. Visual Spike False Positive Prevention Tests
# --------------------------------------------------------------------------

def test_single_visual_frame_spike_does_not_force_high_or_likely_manipulated(evidence_service, assessment_service):
    """
    Regression Test: A real video with 15 low frames and 1 isolated high frame spike (e.g. 0.95)
    must NOT produce visual level HIGH or final verdict LIKELY_MANIPULATED.
    """
    # 15 frames at ~0.02, 1 spike frame at 0.95 (Mean = ~0.08)
    frames = [
        VisualFrameResult(timestamp_s=float(i), face_detected=True, real_score=0.98, fake_score=0.02)
        for i in range(15)
    ]
    frames.append(
        VisualFrameResult(timestamp_s=15.0, face_detected=True, real_score=0.05, fake_score=0.95)
    )

    visual = VisualResult(
        available=True,
        model="EfficientNet-B0-FFPP-C23",
        status="completed",
        frames_analyzed=16,
        faces_found=16,
        face_detection_rate=1.0,
        results=frames,
    )

    audio_clean = AudioResult(
        available=True,
        model="AASIST-ASVspoof2019-LA",
        status="completed",
        windows_analyzed=4,
        results=[
            AudioWindowResult(start_s=0.0, end_s=4.0, spoof_score=0.02),
            AudioWindowResult(start_s=4.0, end_s=8.0, spoof_score=0.03),
            AudioWindowResult(start_s=8.0, end_s=12.0, spoof_score=0.01),
            AudioWindowResult(start_s=12.0, end_s=16.0, spoof_score=0.02),
        ],
    )

    video_info = VideoInfo(
        filename="real_person_with_glitch.mp4",
        sha256="abc1234567890",
        duration_s=16.0,
        fps=30.0,
        width=1280,
        height=720,
        frames_sampled=16,
        audio_available=True,
    )

    provenance = ProvenanceResult(
        state="NONE_FOUND",
        valid=None,
        trusted=None,
        signer=None,
        note="Absence of content credentials does not indicate manipulation.",
    )

    reliability = ReliabilityResult(level="OK", reasons=[])

    matrix = evidence_service.build_matrix(video_info, visual, audio_clean, provenance, reliability)

    # Visual modality must be LOW or at most MEDIUM, never HIGH
    assert matrix.visual.level != "HIGH"
    assert matrix.visual.statistics is not None
    assert matrix.visual.statistics.mean_score < 0.15
    assert matrix.visual.statistics.max_score == 0.95

    # Final assessment: MUST NOT be LIKELY_MANIPULATED
    res, exp, lim = assessment_service.assess(matrix, [])
    assert res.media != "LIKELY_MANIPULATED"
    assert res.media in ("NO_STRONG_EVIDENCE", "SUSPICIOUS")


def test_consistent_low_evidence_produces_no_strong_evidence(evidence_service, assessment_service):
    """
    Regression Test: Real video with consistently low visual and audio scores produces NO_STRONG_EVIDENCE.
    """
    frames = [
        VisualFrameResult(timestamp_s=float(i), face_detected=True, real_score=0.99, fake_score=0.01)
        for i in range(10)
    ]
    visual = VisualResult(
        available=True,
        model="EfficientNet-B0-FFPP-C23",
        status="completed",
        frames_analyzed=10,
        faces_found=10,
        face_detection_rate=1.0,
        results=frames,
    )

    audio = AudioResult(
        available=True,
        model="AASIST-ASVspoof2019-LA",
        status="completed",
        windows_analyzed=2,
        results=[
            AudioWindowResult(start_s=0.0, end_s=4.0, spoof_score=0.02),
            AudioWindowResult(start_s=4.0, end_s=8.0, spoof_score=0.03),
        ],
    )

    video_info = VideoInfo(
        filename="authentic_clip.mp4",
        sha256="def987654321",
        duration_s=8.0,
        fps=30.0,
        width=1280,
        height=720,
        frames_sampled=10,
        audio_available=True,
    )

    provenance = ProvenanceResult(
        state="NONE_FOUND",
        valid=None,
        trusted=None,
        signer=None,
        note="Absence of content credentials does not indicate manipulation.",
    )
    reliability = ReliabilityResult(level="OK", reasons=[])

    matrix = evidence_service.build_matrix(video_info, visual, audio, provenance, reliability)
    assert matrix.visual.level == "LOW"
    assert matrix.audio.level == "LOW"

    res, exp, lim = assessment_service.assess(matrix, [])
    assert res.media == "NO_STRONG_EVIDENCE"
    assert res.media != "AUTHENTIC"


def test_consistent_high_multimodal_evidence_produces_likely_manipulated(evidence_service, assessment_service):
    """
    Regression Test: Persistent high visual and audio scores produce LIKELY_MANIPULATED.
    """
    frames = [
        VisualFrameResult(timestamp_s=float(i), face_detected=True, real_score=0.01, fake_score=0.99)
        for i in range(10)
    ]
    visual = VisualResult(
        available=True,
        model="EfficientNet-B0-FFPP-C23",
        status="completed",
        frames_analyzed=10,
        faces_found=10,
        face_detection_rate=1.0,
        results=frames,
    )

    audio = AudioResult(
        available=True,
        model="AASIST-ASVspoof2019-LA",
        status="completed",
        windows_analyzed=2,
        results=[
            AudioWindowResult(start_s=0.0, end_s=4.0, spoof_score=0.98),
            AudioWindowResult(start_s=4.0, end_s=8.0, spoof_score=0.97),
        ],
    )

    video_info = VideoInfo(
        filename="deepfake_synthetic.mp4",
        sha256="fake123456",
        duration_s=8.0,
        fps=30.0,
        width=1280,
        height=720,
        frames_sampled=10,
        audio_available=True,
    )

    provenance = ProvenanceResult(
        state="NONE_FOUND",
        valid=None,
        trusted=None,
        signer=None,
        note="Absence of content credentials does not indicate manipulation.",
    )
    reliability = ReliabilityResult(level="OK", reasons=[])

    matrix = evidence_service.build_matrix(video_info, visual, audio, provenance, reliability)
    assert matrix.visual.level == "HIGH"
    assert matrix.audio.level == "HIGH"

    res, exp, lim = assessment_service.assess(matrix, [])
    assert res.media == "LIKELY_MANIPULATED"


# --------------------------------------------------------------------------
# 2. Fraud Intent Engine Regression Tests
# --------------------------------------------------------------------------

def test_fraud_i_need_money_is_low(fraud_engine):
    """
    'I need money.' must NOT be classified as high or medium fraud.
    """
    speech = SpeechResult(
        available=True,
        model="faster-whisper-base-int8",
        status="completed",
        language="en",
        duration_s=3.0,
        text="I need money to buy groceries.",
        segments=[
            SpeechSegment(start_s=0.0, end_s=3.0, text="I need money to buy groceries.")
        ],
    )
    res = fraud_engine.analyze(speech)
    assert res.level == "LOW"
    assert len(res.requested_actions) == 0
    assert not any(c.category == "PAYMENT_CREDENTIAL" for c in res.categories)


def test_fraud_send_me_money_action(fraud_engine):
    """
    'Send me money.' contains SEND_MONEY action.
    """
    speech = SpeechResult(
        available=True,
        model="faster-whisper-base-int8",
        status="completed",
        language="en",
        duration_s=3.0,
        text="Send me money right away.",
        segments=[
            SpeechSegment(start_s=0.0, end_s=3.0, text="Send me money right away.")
        ],
    )
    res = fraud_engine.analyze(speech)
    assert any(a.action == "SEND_MONEY" for a in res.requested_actions)


def test_fraud_ceo_wire_urgent_secrecy(fraud_engine):
    """
    'I am your CEO. Send the money immediately. Don't tell anyone.' -> HIGH fraud.
    """
    speech = SpeechResult(
        available=True,
        model="faster-whisper-base-int8",
        status="completed",
        language="en",
        duration_s=5.0,
        text="I am your CEO. Send the money immediately. Don't tell anyone.",
        segments=[
            SpeechSegment(start_s=0.0, end_s=5.0, text="I am your CEO. Send the money immediately. Don't tell anyone.")
        ],
    )
    res = fraud_engine.analyze(speech)
    assert res.level == "HIGH"
    assert any(c.category == "AUTHORITY" for c in res.categories)
    assert any(c.category == "URGENCY" for c in res.categories)
    assert any(c.category == "SECRECY" for c in res.categories)
    assert any(a.action in ("SEND_MONEY", "TRANSFER_MONEY") for a in res.requested_actions)


def test_fraud_police_warned_downgrade(fraud_engine):
    """
    'Police warned that scammers ask victims to send money.' -> Not HIGH fraud.
    """
    speech = SpeechResult(
        available=True,
        model="faster-whisper-base-int8",
        status="completed",
        language="en",
        duration_s=5.0,
        text="Police warned that scammers ask victims to send money.",
        segments=[
            SpeechSegment(start_s=0.0, end_s=5.0, text="Police warned that scammers ask victims to send money.")
        ],
    )
    res = fraud_engine.analyze(speech)
    assert res.level != "HIGH"
    assert res.news_context_downgrade is True


def test_df2_morgan_freeman_harmless_ai(fraud_engine, assessment_service):
    """
    Regression Test: DF2.mp4 known transcript:
    'I am not Morgan Freeman, and what you see is not real.'
    Expected: media: LIKELY_MANIPULATED, fraud: LOW, action: CAUTION.
    """
    speech = SpeechResult(
        available=True,
        model="faster-whisper-base-int8",
        status="completed",
        language="en",
        duration_s=8.0,
        text="I am not Morgan Freeman, and what you see is not real. What would you say if I told you that my voice was generated by an AI model?",
        segments=[
            SpeechSegment(start_s=0.0, end_s=4.0, text="I am not Morgan Freeman, and what you see is not real."),
            SpeechSegment(start_s=4.0, end_s=8.0, text="What would you say if I told you that my voice was generated by an AI model?")
        ],
    )
    fraud_res = fraud_engine.analyze(speech)
    assert fraud_res.level == "LOW"

    # Simulated Stage 2 output for DF2.mp4
    matrix = EvidenceMatrix(
        visual=EvidenceModalityResult(
            level="HIGH",
            models=[ModelEvidenceItem(name="EfficientNet-B0-FFPP-C23", score=0.998)]
        ),
        audio=EvidenceModalityResult(
            level="HIGH",
            models=[ModelEvidenceItem(name="AASIST-ASVspoof2019-LA", score=0.999)]
        ),
        provenance=ProvenanceResult(
            state="NONE_FOUND",
            valid=None,
            trusted=None,
            signer=None,
            note="Absence of content credentials does not indicate manipulation."
        ),
        metadata=EvidenceMetadata(
            width=1280, height=720, duration_s=15.1, fps=30.0, frames_sampled=16, audio_available=True
        ),
        reliability=ReliabilityResult(level="OK", reasons=[]),
    )

    assessment, explanations, limitations = assessment_service.assess(matrix, [], fraud_res)
    assert assessment.media == "LIKELY_MANIPULATED"
    assert assessment.fraud == "LOW"
    assert assessment.action == "CAUTION"
