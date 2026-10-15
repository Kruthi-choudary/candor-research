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
import { resources, useAnalysisResource } from "../hooks/useAnalysis";
import { ConnectionStatus, DataSourceNote } from "../components/DataStatus";
import { demo } from "../data/demo";
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
    title: "The research workspace",
    subtitle: "Inspect signals and their sources",
  },
];

export function Landing() {
  const library = useAnalysisResource(resources.calls);
  const example = demo.calls[0]!;
  const exampleClaims = useAnalysisResource(
    resources.claims(example.ticker, example.quarter),
  );
  const calls = library.data?.calls ?? [];
  const claim =
    exampleClaims.data?.claims.find((c) => c.evidence.split(" ").length > 12) ??
    exampleClaims.data?.claims[0] ??
    null;
  const exampleUrl = `/app/calls/${example.ticker}/${example.quarter}`;
  const companyCount = new Set(calls.map((c) => c.ticker)).size;

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
          <span className="header-note">Language. Voice. Context.</span>
        </header>
      </div>
      <ConnectionStatus />
      <main id="main-content" tabIndex={-1}>
        <div className="dark">
          <section className="hero container" aria-labelledby="hero-heading">
            <div className="reveal">
              <p className="eyebrow text-brass">
                Earnings-call communication research.
              </p>
              <h1 className="hero-title editorial" id="hero-heading">
                The story behind
                <br />
                the <em>numbers.</em>
              </h1>
              <p className="hero-copy">
                What executives say. How they say it. What changes over time.
                Candor’s goal is to compare each executive with their own
                earlier calls and explain the differences with evidence.
              </p>
              <p className="caption muted mt-4 max-w-lg">
                Current prototype: transcript sentiment, vocal measurements and
                inspectable claims. Comparisons against an executive’s
                historical baseline are still in development.
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
              aria-label="An example from the research library"
            >
              <div className="preview-masthead">
                <span className="eyebrow">
                  {exampleClaims.source === "demo"
                    ? "Demo evidence brief"
                    : "The evidence brief"}
                </span>
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
                      {formatTimestamp(claim.timestamp_sec)} /{" "}
                      {exampleClaims.source === "demo"
                        ? "transcript preview"
                        : "source audio"}
                    </Link>
                    <Link to={exampleUrl} className="claim-action-link">
                      Read brief <ArrowUpRight size={14} aria-hidden="true" />
                    </Link>
                  </div>
                </>
              ) : (
                <div className="py-8">
                  <p className="muted text-sm" role="status">
                    No claims were returned for this example. Explore another
                    call in the research library.
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
              <p className="eyebrow muted">The research question</p>
              <h2 className="editorial editorial-heading" id="research-heading">
                Their own history.
                <br />A meaningful reference.
              </h2>
            </div>
            <div>
              <p className="muted leading-8">
                Some executives naturally speak slowly or pause often. The
                question is whether their language and vocal patterns change
                compared with their own earlier calls, and what they were
                discussing when that happened.
              </p>
              <p className="muted leading-8 mt-4">
                Today’s workspace lets you inspect individual calls: their
                sentiment, descriptive vocal measurements and quoted evidence.
                Speaker identification and historical change detection are the
                next research steps. A change alone would not establish
                nervousness, dishonesty or future stock performance.
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
              <p className="metric-label">
                {library.source === "demo"
                  ? "Sample earnings calls"
                  : "Processed earnings calls"}
              </p>
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
          <DataSourceNote
            sources={{
              library: library.source,
              "example claim": exampleClaims.source,
            }}
          />
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
                What the prototype
                <br />
                can do today.
              </h2>
            </div>
            <p className="muted leading-8">
              These tools provide the foundation for studying communication
              changes. The current pipeline measures signals and makes their
              sources inspectable; it does not yet calculate executive-specific
              communication anomalies.
            </p>
          </div>
          <div className="method-list">
            {[
              [
                "Capture the language",
                "Whisper turns the recording into timestamped transcript segments. FinBERT classifies their financial sentiment.",
              ],
              [
                "Measure vocal patterns",
                "Pitch, energy, pauses and speaking rate are measured from the recording. These describe the audio; they are not yet compared against the same executive’s historical baseline.",
              ],
              [
                "Trace every citation",
                "Selected positive and negative passages inform a short brief. Each generated claim includes a quote and timestamp that a separate checker compares with the transcript.",
              ],
              [
                "Build toward comparison",
                "The next stage is to identify the same executive across calls, establish an earlier-call baseline and explain differences using relevant historical passages. Existing citation scores do not evaluate that future capability.",
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
            Earnings-call communication research. Evidence you can inspect.
          </p>
        </div>
      </footer>
    </>
  );
}
