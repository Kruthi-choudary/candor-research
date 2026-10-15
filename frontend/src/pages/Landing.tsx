import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  AudioLines,
  FileText,
  ScanLine,
  ShieldCheck,
} from "lucide-react";
import { Logo } from "../components/Logo";
import { VerdictBadge } from "../components/VerdictBadge";
import { api, type CallSummary, type KeyClaim } from "../lib/api";
import { formatTimestamp } from "../lib/format";

const WORKFLOW = [
  { icon: AudioLines, title: "The recording", subtitle: "Earnings-call audio" },
  {
    icon: ScanLine,
    title: "The signals",
    subtitle: "Language, tone & vocal patterns",
  },
  {
    icon: ShieldCheck,
    title: "The source check",
    subtitle: "Quotes paired with timestamps",
  },
  {
    icon: FileText,
    title: "The intelligence",
    subtitle: "An evidence-backed brief",
  },
];

export function Landing() {
  const [calls, setCalls] = useState<CallSummary[] | null>(null);
  const [claim, setClaim] = useState<KeyClaim | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let cancelled = false;
    api
      .listCalls()
      .then(async ({ calls: data }) => {
        if (cancelled) return;
        setCalls(data);
        const example = data.find((c) => c.ticker === "AAPL") ?? data[0];
        if (example) {
          const result = await api.getClaims(example.ticker, example.quarter);
          if (!cancelled)
            setClaim(
              result.claims.find((c) => c.evidence.split(" ").length > 12) ??
                result.claims[0] ??
                null,
            );
        }
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);
  const example = calls?.find((c) => c.ticker === "AAPL") ?? calls?.[0];
  const exampleUrl = example
    ? `/app/calls/${example.ticker}/${example.quarter}`
    : "/app";
  const companyCount = calls ? new Set(calls.map((c) => c.ticker)).size : null;

  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <div className="dark">
        <header className="site-header container">
          <Link to="/" aria-label="Candor home">
            <Logo />
          </Link>
          <nav className="header-nav" aria-label="Main navigation">
            <a href="#methodology">Our methodology</a>
            <Link to="/app">
              Research desk{" "}
              <ArrowUpRight size={13} className="inline" aria-hidden="true" />
            </Link>
          </nav>
          <span className="header-note">Earnings, in perspective</span>
        </header>
      </div>
      <main id="main-content" tabIndex={-1}>
        <div className="dark">
          <section className="hero container" aria-labelledby="hero-heading">
            <div className="reveal">
              <p className="eyebrow text-brass">
                Financial intelligence. With a source.
              </p>
              <h1 className="hero-title editorial" id="hero-heading">
                The story behind
                <br />
                the <em>numbers.</em>
              </h1>
              <p className="hero-copy">
                Turn earnings-call audio into evidence-backed intelligence.
                Explore executive sentiment, vocal patterns, verified claims,
                and the exact moments behind every conclusion.
              </p>
              <div className="hero-actions">
                <Link className="btn btn-brass" to="/app">
                  Explore the Analysis{" "}
                  <ArrowRight size={16} aria-hidden="true" />
                </Link>
                <a className="text-link" href="#methodology">
                  View Methodology <ArrowUpRight size={14} aria-hidden="true" />
                </a>
              </div>
              <div className="hero-index">
                <span>01 / THE RESEARCH DESK</span>
                <span>Listen closer. See further.</span>
              </div>
            </div>
            <article
              className="research-preview reveal"
              aria-label="A live-fetched example from the research library"
            >
              <div className="preview-masthead">
                <span className="eyebrow">The evidence brief</span>
                <FileText size={17} color="#82662e" aria-hidden="true" />
              </div>
              <p className="caption muted mt-6">
                {example
                  ? `${example.ticker} / ${example.quarter.replace("-", " ")}`
                  : "FROM THE RESEARCH LIBRARY"}
              </p>
              <h2 className="preview-title editorial">Beyond the headline.</h2>
              {claim ? (
                <>
                  <p className="preview-quote">{claim.claim}</p>
                  <VerdictBadge verdict={claim.verdict} />
                  <div className="preview-source mt-6">
                    <p className="eyebrow muted">The supporting words</p>
                    <blockquote>“{claim.evidence}”</blockquote>
                  </div>
                  <div className="preview-footer">
                    <Link
                      className="timestamp"
                      to={`${exampleUrl}?t=${claim.timestamp_sec}`}
                    >
                      <AudioLines size={14} aria-hidden="true" />
                      {formatTimestamp(claim.timestamp_sec)} / source audio
                    </Link>
                    <Link to={exampleUrl} className="claim-action-link">
                      Read brief <ArrowUpRight size={14} aria-hidden="true" />
                    </Link>
                  </div>
                </>
              ) : (
                <div className="py-8">
                  <p className="muted text-sm" role="status">
                    {error
                      ? "The research preview is unavailable. Open the desk to retry."
                      : calls?.length === 0
                        ? "The library is ready for its first processed call."
                        : "Opening a real claim from the library…"}
                  </p>
                </div>
              )}
            </article>
          </section>
          <div className="container workflow" aria-label="Candor workflow">
            {WORKFLOW.map((step, i) => (
              <div className="workflow-step" key={step.title}>
                <span className="tabular">0{i + 1}</span>
                <step.icon size={20} strokeWidth={1.25} aria-hidden="true" />
                <div>
                  <p>{step.title}</p>
                  <small>{step.subtitle}</small>
                </div>
              </div>
            ))}
          </div>
        </div>
        <section
          className="container landing-section"
          aria-labelledby="research-heading"
        >
          <div className="intro-grid">
            <div>
              <p className="eyebrow muted">Less noise. More context.</p>
              <h2 className="editorial editorial-heading" id="research-heading">
                A conclusion is only as
                <br />
                good as its evidence.
              </h2>
            </div>
            <div>
              <p className="muted leading-8">
                Move past the summary. Follow an extracted claim to its original
                words, see where it appears in the transcript, and listen to the
                moment yourself.
              </p>
              <Link to="/app" className="text-link mt-5">
                Inside the research library{" "}
                <ArrowRight size={15} aria-hidden="true" />
              </Link>
            </div>
          </div>
          <div className="metric-row">
            <div className="metric">
              <div className="metric-value">{calls?.length ?? "—"}</div>
              <p className="metric-label">Processed earnings calls</p>
            </div>
            <div className="metric">
              <div className="metric-value">{companyCount ?? "—"}</div>
              <p className="metric-label">Companies in the library</p>
            </div>
            <div className="metric">
              <div className="metric-value editorial">Source first.</div>
              <p className="metric-label">
                Claims linked to transcript evidence
              </p>
            </div>
          </div>
          {error && (
            <p className="caption muted mt-3">
              Library figures are unavailable until the research service
              reconnects.
            </p>
          )}
        </section>
        <section
          className="container landing-section rule-top"
          id="methodology"
          aria-labelledby="method-heading"
        >
          <div className="intro-grid">
            <div>
              <p className="eyebrow muted">02 / The methodology</p>
              <h2 className="editorial editorial-heading" id="method-heading">
                From spoken words
                <br />
                to inspectable insight.
              </h2>
            </div>
            <p className="muted leading-8">
              A transparent processing pipeline, with a clear distinction
              between what the model concludes and what the source actually
              says.
            </p>
          </div>
          <div className="method-list">
            {[
              [
                "Capture the language",
                "Whisper turns the recording into timestamped transcript segments. FinBERT classifies their financial sentiment.",
              ],
              [
                "Extract the signals",
                "Selected positive and negative passages inform the brief. Pitch, energy and speaking rate are measured separately as audio context.",
              ],
              [
                "Trace every citation",
                "The model returns structured claims with quotes and timestamps. A separate checker compares each citation with the transcript.",
              ],
              [
                "Keep the limits visible",
                "A matching citation confirms a source-text match, not the truth of an interpretation. Review the evidence and benchmark methodology yourself.",
              ],
            ].map(([title, body], i) => (
              <div className="method-row" key={title}>
                <span className="caption muted tabular">0{i + 1}</span>
                <h3>{title}</h3>
                <p>{body}</p>
              </div>
            ))}
          </div>
          <Link to="/app/evaluation" className="text-link mt-5">
            Explore the actual benchmark results{" "}
            <ArrowUpRight size={15} aria-hidden="true" />
          </Link>
        </section>
      </main>
      <footer className="dark">
        <div className="container footer-inner py-8">
          <Logo size="sm" />
          <p className="caption muted">
            Independent research tooling. Evidence you can inspect.
          </p>
        </div>
      </footer>
    </>
  );
}
