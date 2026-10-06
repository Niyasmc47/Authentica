import logging
import re
from typing import List, Optional, Tuple

from app.schemas.analysis import SpeechResult, SpeechSegment
from app.schemas.fraud import (
    FraudCategoryEvidence,
    FraudEvidenceItem,
    FraudRequestedAction,
    FraudResult,
)

logger = logging.getLogger("authentica")


class FraudIntentEngine:
    """
    Stage 3 — Fraud Intent Engine.
    Performs deterministic, rule-based social-engineering and fraud signal extraction
    from timestamped Whisper transcript segments.
    """

    # Category regex patterns
    CATEGORY_PATTERNS = {
        "AUTHORITY": [
            r"\b(?:i am|this is|speaking as)\s+(?:the\s+)?(?:project\s+|senior\s+|general\s+|regional\s+)?(?:ceo|cfo|executive|director|manager|boss|chief|president)\b",
            r"\b(?:police|fbi|cia|interpol|sheriff|detective|officer|marshal|law enforcement|federal agent)\b",
            r"\b(?:irs|tax department|revenue service|customs|court|judge|legal department|attorney general)\b",
            r"\b(?:bank manager|security department|fraud department|technical support|it support|helpdesk)\b",
        ],
        "URGENCY": [
            r"\b(?:immediately|right now|urgently|hurry|asap|without delay|at once)\b",
            r"\b(?:within\s+\d+\s+(?:minutes?|hours?)|before\s+it(?:'s|\s+is)\s+too\s+late|time\s+is\s+running\s+out)\b",
            r"\b(?:account\s+will\s+be\s+blocked|funds\s+frozen|suspended\s+today|critical\s+deadline)\b",
        ],
        "PAYMENT_CREDENTIAL": [
            r"\b(?:wire\s+transfer|send\s+(?:the\s+)?money|transfer\s+funds|bitcoin|crypto|usdt|ethereum|gift\s*cards?)\b",
            r"\b(?:otp|one[- ]time\s+pass(?:code|word)?|verification\s+code|2fa\s+code|security\s+code)\b",
            r"\b(?:cvv|card\s+number|pin\s+number|bank\s+account|routing\s+number|credentials|password)\b",
            r"\b(?:western\s+union|moneygram|apple\s+gift\s*cards?|google\s+play\s*cards?|vanilla\s*visa)\b",
        ],
        "SECRECY": [
            r"\b(?:don'?t\s+tell|do\s+not\s+tell|keep\s+this\s+(?:between\s+us|confidential|secret|private|quiet))\b",
            r"\b(?:do\s+not\s+(?:call|contact|mention|discuss)\s+(?:anyone|the\s+office|colleagues|family|boss))\b",
            r"\b(?:off\s+the\s+record|strictly\s+confidential|top\s+secret|between\s+you\s+and\s+me)\b",
        ],
        "CHANNEL_IDENTITY_CHANGE": [
            r"\b(?:lost\s+(?:my\s+)?(?:phone|access)|new\s+(?:temporary\s+)?(?:number|phone)|using\s+a\s+different\s+phone)\b",
            r"\b(?:text\s+me\s+on\s+whatsapp|message\s+me\s+on\s+telegram|this\s+is\s+my\s+personal\s+(?:number|cell))\b",
            r"\b(?:changed\s+my\s+number|reach\s+me\s+here\s+instead)\b",
        ],
        "THREAT_PRESSURE": [
            r"\b(?:arrest\s+warrant|face\s+arrest|police\s+will\s+arrive|lawsuit|legal\s+action)\b",
            r"\b(?:penalty|fine|disciplinary\s+action|terminated|fired|suspended\s+permanently)\b",
            r"\b(?:your\s+account\s+has\s+been\s+compromised|illegal\s+activities\s+detected)\b",
        ],
        "TOO_GOOD_TO_BE_TRUE": [
            r"\b(?:guaranteed\s+(?:returns?|profit|income)|100x|double\s+your\s+money|lottery\s+winner)\b",
            r"\b(?:exclusive\s+investment|claim\s+your\s+prize|free\s+crypto|risk[- ]free\s+opportunity)\b",
        ],
        "REMOTE_ACCESS_LINKS": [
            r"\b(?:anydesk|teamviewer|quicksupport|ultraviewer|zoho\s+assist|remote\s+desktop)\b",
            r"\b(?:install\s+(?:this\s+)?(?:app|software|tool|file)|download\s+the\s+attached)\b",
            r"\b(?:click\s+(?:the\s+)?(?:link|button)|go\s+to\s+this\s+(?:website|url)|share\s+your\s+screen)\b",
        ],
    }

    # Action directive patterns (action_name, pattern)
    ACTION_PATTERNS = [
        ("SEND_MONEY", r"\b(?:send|pay|deposit|remit)\s+(?:me|the|us|\$|\d+)?\s*(?:money|funds|cash|crypto|bitcoin|amount|cards?)\b"),
        ("TRANSFER_MONEY", r"\b(?:transfer|wire)\s+(?:the\s+)?(?:funds?|money|balance|amount|sum)\b"),
        ("SHARE_OTP", r"\b(?:give|send|tell|share|read\s+out|provide)\s+(?:me\s+)?(?:the\s+|your\s+|that\s+)?(?:otp\s+verification\s+code|otp\s+code|otp|one[- ]time\s+pass(?:code|word)?|verification\s+code|2fa\s+code)\b"),
        ("SHARE_PASSWORD", r"\b(?:give|send|tell|share|provide)\s+(?:me\s+)?(?:your\s+|the\s+)?(?:password|pin|credentials|login)\b"),
        ("SHARE_BANK_DETAILS", r"\b(?:share|give|send|provide)\s+(?:your\s+|the\s+)?(?:bank\s+details|account\s+details|card\s+number|cvv)\b"),
        ("CLICK_LINK", r"\b(?:click\s+(?:on\s+)?(?:this|the)\s+link|open\s+(?:this|the)\s+link|follow\s+this\s+link)\b"),
        ("INSTALL_REMOTE_ACCESS", r"\b(?:install|download|run)\s+(?:anydesk|teamviewer|quicksupport|remote\s+access|the\s+app|the\s+file)\b"),
        ("SHARE_SCREEN", r"\b(?:share\s+your\s+screen|grant\s+access|give\s+control)\b"),
        ("CHANGE_PAYMENT_ACCOUNT", r"\b(?:update|change)\s+(?:the\s+)?(?:bank|invoice|payment|beneficiary|account)\s+(?:details|number|destination)\b"),
        ("KEEP_SECRET", r"\b(?:don'?t\s+tell|do\s+not\s+inform|keep\s+this\s+(?:secret|confidential|between\s+us))\b"),
        ("CONTACT_NEW_NUMBER", r"\b(?:message|text|contact|call)\s+(?:me\s+)?(?:on|at)\s+(?:this\s+new\s+number|whatsapp|telegram|my\s+cell)\b"),
    ]

    # Patterns indicating educational / news / awareness context
    NEWS_AWARENESS_PATTERNS = [
        r"\b(?:beware\s+of|be\s+careful\s+of|watch\s+out\s+for|scammers?\s+(?:are|often|use|try|will|trick|ask))\b",
        r"\b(?:in\s+this\s+(?:report|video|news|segment)|news\s+anchor|reporting\s+live|documentary)\b",
        r"\b(?:cybersecurity\s+tip|safety\s+warning|fraud\s+awareness|psa|public\s+service\s+announcement)\b",
        r"\b(?:police\s+warn|officials\s+caution|fbi\s+warns|victims\s+were\s+targeted|how\s+scams?\s+work)\b",
    ]

    def analyze(self, speech_result: Optional[SpeechResult]) -> FraudResult:
        """
        Analyze transcript segments to detect fraud intent and social engineering tactics.
        """
        return self.evaluate(speech_result)

    def evaluate(self, speech_result: Optional[SpeechResult]) -> FraudResult:
        """
        Evaluate transcript segments to detect fraud intent and social engineering tactics.
        """
        if not speech_result or not speech_result.available or not speech_result.segments:
            logger.info("FraudIntentEngine: No speech transcript segments available to analyze.")
            return FraudResult(
                level="NOT_ASSESSABLE",
                categories=[],
                requested_actions=[],
                news_context_downgrade=False,
            )

        segments = speech_result.segments
        full_transcript = " ".join(seg.text for seg in segments).lower()

        # 1. Detect educational / news / reported-speech context
        is_news_context = self._detect_news_context(full_transcript)

        # 2. Match Categories across segments
        categories_found: List[FraudCategoryEvidence] = []
        for cat_name, patterns in self.CATEGORY_PATTERNS.items():
            evidence_items: List[FraudEvidenceItem] = []
            for seg in segments:
                text_clean = seg.text.strip()
                for pat in patterns:
                    matches = list(re.finditer(pat, text_clean, re.IGNORECASE))
                    for m in matches:
                        evidence_items.append(
                            FraudEvidenceItem(
                                phrase=m.group(0),
                                start_s=seg.start_s,
                                end_s=seg.end_s,
                            )
                        )
            if evidence_items:
                # Severity determination per category
                severity = "HIGH" if cat_name in ("PAYMENT_CREDENTIAL", "THREAT_PRESSURE", "REMOTE_ACCESS_LINKS") else "MEDIUM"
                categories_found.append(
                    FraudCategoryEvidence(
                        category=cat_name,
                        severity=severity,
                        evidence=evidence_items,
                    )
                )

        # 3. Detect Directed Action Requests
        requested_actions: List[FraudRequestedAction] = []
        for seg in segments:
            text_clean = seg.text.strip()
            for action_name, pat in self.ACTION_PATTERNS:
                matches = list(re.finditer(pat, text_clean, re.IGNORECASE))
                for m in matches:
                    requested_actions.append(
                        FraudRequestedAction(
                            action=action_name,
                            phrase=m.group(0),
                            start_s=seg.start_s,
                            end_s=seg.end_s,
                        )
                    )

        # 4. Multi-signal scoring & determination of raw risk level
        raw_level = self._compute_fraud_level(categories_found, requested_actions)

        # 5. Apply News/Awareness Downgrade if applicable
        final_level = raw_level
        downgraded = False
        if is_news_context and raw_level in ("HIGH", "MEDIUM"):
            downgraded = True
            if raw_level == "HIGH":
                final_level = "MEDIUM"
            elif raw_level == "MEDIUM":
                final_level = "LOW"
            logger.info(f"FraudIntentEngine: Downgraded fraud risk {raw_level} -> {final_level} due to news/educational context.")

        logger.info(
            f"FraudIntentEngine Analysis: level={final_level} (raw={raw_level}, downgraded={downgraded}) | "
            f"categories={[c.category for c in categories_found]} | actions={[a.action for a in requested_actions]}"
        )

        return FraudResult(
            level=final_level,
            categories=categories_found,
            requested_actions=requested_actions,
            news_context_downgrade=downgraded,
        )

    def _detect_news_context(self, full_transcript: str) -> bool:
        for pat in self.NEWS_AWARENESS_PATTERNS:
            if re.search(pat, full_transcript, re.IGNORECASE):
                return True
        return False

    def _compute_fraud_level(
        self,
        categories: List[FraudCategoryEvidence],
        requested_actions: List[FraudRequestedAction],
    ) -> str:
        cat_names = {c.category for c in categories}
        action_names = {a.action for a in requested_actions}

        has_direct_action = len(requested_actions) > 0
        has_payment_creds = "PAYMENT_CREDENTIAL" in cat_names
        has_authority = "AUTHORITY" in cat_names
        has_urgency = "URGENCY" in cat_names
        has_threat = "THREAT_PRESSURE" in cat_names
        has_secrecy = "SECRECY" in cat_names
        has_remote = "REMOTE_ACCESS_LINKS" in cat_names
        has_too_good = "TOO_GOOD_TO_BE_TRUE" in cat_names

        # Critical Direct Action combinations -> HIGH
        # Any direct extraction action (Send money, share OTP, remote install) combined with pressure or authority
        if has_direct_action:
            if has_payment_creds or has_remote:
                return "HIGH"
            if has_authority or has_urgency or has_threat or has_secrecy:
                return "HIGH"
            # Explicit high-risk actions alone
            if action_names & {"SEND_MONEY", "TRANSFER_MONEY", "SHARE_OTP", "SHARE_PASSWORD", "SHARE_BANK_DETAILS", "INSTALL_REMOTE_ACCESS"}:
                return "HIGH"

        # Strong Social Engineering combos without explicit action regex trigger -> HIGH
        if has_threat and (has_payment_creds or has_urgency):
            return "HIGH"
        if has_authority and has_urgency and has_payment_creds:
            return "HIGH"
        if has_remote and has_urgency:
            return "HIGH"

        # Medium Risk indicators
        # Multi-category suspicious combinations without direct action demands
        if len(cat_names) >= 2:
            return "MEDIUM"
        if has_payment_creds or has_too_good or has_remote or has_threat:
            return "MEDIUM"
        if has_authority or has_urgency or has_secrecy or "CHANNEL_IDENTITY_CHANGE" in cat_names:
            return "MEDIUM"

        return "LOW"
