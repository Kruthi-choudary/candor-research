"""Fail loudly when live historical retrieval or its source evidence is invalid."""
import json
from src.common.manifest import ROOT
from src.eval.audit_reports import context_issues
from src.rag.build_index import (
    CALL_DATES_PATH, _eligible_prior_quarters, _retrieve_nodes,
    build_nodes, index_identity, stored_node_ids, check_existing_index, current_call_queries,
)


def main():
    nodes = build_nodes()
    identity = index_identity(nodes)
    manifest = json.loads((ROOT / ".local/index_manifest.json").read_text())
    if not check_existing_index(identity, stored_node_ids(), manifest):
        raise RuntimeError("Index is empty; run src.rag.build_index first.")
    dates = json.loads(CALL_DATES_PATH.read_text())
    checked = []
    for ticker, calls in sorted(dates.items()):
        for quarter in sorted(calls, key=calls.get):
            eligible = _eligible_prior_quarters(ticker, quarter)
            if not eligible:
                checked.append({"ticker": ticker, "quarter": quarter, "status": "no_earlier_calls", "matches": 0})
                continue
            sentiment = json.loads((ROOT / f"data/processed/sentiment/segment/{ticker}/{quarter}.json").read_text())
            queries = current_call_queries(sentiment["segments"])
            if not queries:
                raise RuntimeError(f"No current-call evidence queries for {ticker} {quarter}")
            matches = _retrieve_nodes(ticker, eligible, 3, queries=queries)
            if not matches:
                raise RuntimeError(f"No historical evidence returned for {ticker} {quarter}")
            if any(m.node.metadata.get("ticker") != ticker or m.node.metadata.get("quarter") not in eligible for m in matches):
                raise RuntimeError("Retrieval returned an ineligible company or quarter.")
            context = [{"quarter": m.node.metadata["quarter"], "start_sec": m.node.metadata["start_sec"], "text": m.node.text} for m in matches]
            issues = context_issues(ticker, quarter, context, dates,
                                    lambda t, q: json.loads((ROOT / f"data/processed/transcripts/{t}/{q}.json").read_text()))
            if issues:
                raise RuntimeError(f"Historical source validation failed: {issues}")
            checked.append({"ticker": ticker, "quarter": quarter, "status": "source_and_date_checked", "matches": len(matches), "source_quarters": [c["quarter"] for c in context]})
    output = ROOT / ".local/retrieval_verification.json"
    output.write_text(json.dumps({"scope": "Live source/date/company isolation checks, not retrieval relevance or claim correctness evaluation.", "checks": checked}, indent=2) + "\n")
    print(f"Verified {len(nodes)} unique chunks and {len(checked)} calls. Results: {output}")


if __name__ == "__main__":
    main()
