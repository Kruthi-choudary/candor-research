"""The official Candor report contract. Every pipeline run produces a dict matching this shape
— this is what a future frontend/API is expected to depend on, not the intermediate per-stage
JSON files in data/processed/.
"""

REQUIRED_TOP_LEVEL_FIELDS = [
    "schema_version", "ticker", "company", "quarter", "overall_summary",
    "key_claims", "sentiment_distribution", "citation_verification",
]
REQUIRED_CLAIM_FIELDS = ("claim", "evidence", "timestamp_sec", "sentiment")


def build_report(call_ref, structured_claims: dict, sentiment_distribution: dict,
                  citation_eval: dict, audio_feature_summary: dict,
                  prior_quarter_context: list, stage_durations_sec: dict) -> dict:
    report = {
        "schema_version": "1.0",
        "ticker": call_ref.ticker,
        "company": call_ref.company_name,
        "quarter": call_ref.quarter.replace("_", " "),
        "call_date": call_ref.call_date,
        "overall_summary": structured_claims["overall_summary"],
        "evidence_policy": structured_claims.get("evidence_policy", "legacy_segments_v1"),
        "sentiment_distribution": sentiment_distribution,
        "key_claims": [
            {
                "claim": c["claim"],
                "evidence": c["citation"]["source_text"],
                "timestamp_sec": c["citation"]["timestamp_sec"],
                "sentiment": c["sentiment"],
            }
            for c in structured_claims["claims"]
        ],
        # Reserved for a future prompt revision — the current LLM prompt doesn't extract
        # these separately yet, so they're honestly empty rather than faked.
        "risks": [],
        "management_outlook": [],
        "citation_verification": {
            "total_citations": citation_eval["total_citations"],
            "verified": citation_eval["verified"],
            "accuracy": citation_eval["accuracy"],
        },
        "audio_features_summary": audio_feature_summary,
        "prior_quarter_context_used": prior_quarter_context,
        "pipeline_version": "1.0",
        "stage_durations_sec": stage_durations_sec,
    }
    validate_report(report)
    return report


def validate_report(report: dict) -> None:
    missing = [f for f in REQUIRED_TOP_LEVEL_FIELDS if f not in report]
    if missing:
        raise ValueError(f"Pipeline output missing required fields: {missing}")
    for i, claim in enumerate(report["key_claims"]):
        missing_claim_fields = [f for f in REQUIRED_CLAIM_FIELDS if f not in claim]
        if missing_claim_fields:
            raise ValueError(f"key_claims[{i}] missing fields: {missing_claim_fields}")
