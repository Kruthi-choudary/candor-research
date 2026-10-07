import { Link } from "react-router-dom";
import { ArrowRight, Layers, AudioLines, FileText, Gauge, Mic2, Search, ShieldCheck } from "lucide-react";
import { Logo } from "../components/Logo";
import { Reveal } from "../components/Reveal";
import { VerdictBadge } from "../components/VerdictBadge";

const PIPELINE_STEPS = [
  { icon: AudioLines, title: "Audio", body: "The earnings call recording, per ticker and quarter." },
  { icon: FileText, title: "Transcription", body: "Whisper ASR converts speech to timestamped text." },
  { icon: Gauge, title: "Sentiment", body: "FinBERT scores every segment positive, negative, or neutral." },
  { icon: Mic2, title: "Prosody", body: "Librosa extracts pitch, energy, pause, and speaking rate." },
  { icon: Search, title: "RAG context", body: "Retrieves prior-quarter chunks for the same company." },
  { icon: ShieldCheck, title: "Verified report", body: "The LLM drafts claims; every citation is checked against the transcript before it ships." },
];

export function Landing() {
  return (
    <div className="relative min-h-screen bg-base">
      {/* Diagonal light-beam backdrop, confined to the hero area so it doesn't bleed into
          the sections below — a soft glowing wedge with rays spilling up-left. */}
      <div className="relative flex min-h-screen flex-col overflow-hidden">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-[78%] overflow-hidden">
          <div
            className="absolute inset-0"
            style={{
              background:
                "linear-gradient(108deg, transparent 38%, rgba(62,207,142,0.05) 44%, rgba(62,207,142,0.35) 48%, rgba(78,230,165,0.9) 49.5%, rgba(62,207,142,0.35) 51%, rgba(62,207,142,0.05) 55%, transparent 62%)",
              filter: "blur(6px)",
            }}
          />
          <div
            className="absolute inset-0 opacity-90 mix-blend-screen"
            style={{
              background:
                "radial-gradient(1100px 900px at 68% 72%, rgba(62,207,142,0.32), transparent 62%)," +
                "radial-gradient(600px 1000px at 72% 10%, rgba(62,207,142,0.16), transparent 70%)",
              filter: "blur(10px)",
            }}
          />
        </div>
        <div
          className="pointer-events-none absolute inset-x-0 bottom-0 h-[30%]"
          style={{
            background: "radial-gradient(55% 100% at 62% 0%, rgba(62,207,142,0.14), transparent 75%)",
          }}
        />

        <header className="relative z-10 flex items-center justify-between px-10 py-6">
          <Logo />
          <Link
            to="/app"
            className="flex items-center gap-2 rounded-full border border-border bg-raised/60 px-4 py-2 text-sm text-text backdrop-blur transition-colors hover:border-mint/40"
          >
            Open dashboard <ArrowRight size={14} />
          </Link>
        </header>

        <div className="relative z-10 flex flex-1 flex-col justify-center px-10">
          <span className="text-xs font-medium tracking-[0.2em] text-mint">
            EARNINGS CALLS, WITH EVIDENCE.
          </span>
          <h1 className="mt-6 max-w-2xl text-6xl font-medium leading-[1.05] tracking-tight text-text">
            From earnings calls to <span className="text-mint">verified</span> insights.
          </h1>
          <p className="mt-6 max-w-lg text-lg text-text-muted">
            Turn hours of earnings call audio into structured insights, grounded in the actual
            transcript. Transcribed, analyzed, and cross-checked by an evaluation layer built to
            catch its own mistakes.
          </p>

          <div className="mt-10 flex items-center gap-6">
            <Link
              to="/app"
              className="rounded-full bg-mint px-6 py-3 text-sm font-medium text-[#06120c] transition-opacity hover:opacity-90"
            >
              View the 16 processed calls <ArrowRight size={14} className="ml-1 inline" />
            </Link>
            <a href="#how-it-works" className="text-sm text-text-muted underline underline-offset-4 hover:text-text">
              Learn how it works
            </a>
          </div>
        </div>

        <div className="relative z-10 border-t border-border px-10 py-8">
          <div className="flex items-center justify-between text-xs uppercase tracking-wide text-text-faint">
            <span>Built on real data. Verified by evidence.</span>
            <span className="flex items-center gap-2">
              <span className="h-px w-6 bg-border" /> Evaluation layer
            </span>
          </div>
          <div className="mt-6 grid grid-cols-3 divide-x divide-border">
            <div className="pr-8">
              <div className="text-4xl font-medium text-mint">16</div>
              <div className="mt-1 text-sm text-text">Calls processed</div>
              <div className="text-xs text-text-faint">4 companies · 4 quarters each</div>
            </div>
            <div className="px-8">
              <div className="text-4xl font-medium text-mint">4</div>
              <div className="mt-1 text-sm text-text">Companies</div>
              <div className="text-xs text-text-faint">AAPL · MSFT · NVDA · META</div>
            </div>
            <div className="flex items-start gap-3 pl-8">
              <Layers className="mt-0.5 shrink-0 text-mint" size={20} />
              <div>
                <div className="text-sm text-text">Evidence-backed claims</div>
                <div className="text-xs text-text-faint">
                  Every key insight linked to a timestamp and source from the actual transcript.
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* How it works — the real 6-stage pipeline, revealed as you scroll */}
      <section id="how-it-works" className="mx-auto max-w-6xl px-10 py-28">
        <Reveal>
          <span className="text-xs font-medium tracking-[0.2em] text-mint">THE PIPELINE</span>
          <h2 className="mt-4 max-w-xl text-3xl font-medium tracking-tight text-text">
            Six real stages, not a black box.
          </h2>
          <p className="mt-3 max-w-lg text-text-muted">
            This is the actual sequence <code className="text-text">pipeline.py</code> runs for
            every call — no step is skipped or mocked.
          </p>
        </Reveal>

        <div className="mt-14 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {PIPELINE_STEPS.map((step, i) => (
            <Reveal key={step.title} delay={i * 80}>
              <div className="flex h-full flex-col gap-3 rounded-xl border border-border bg-raised p-6">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-mint/10 text-mint">
                    <step.icon size={18} />
                  </div>
                  <span className="text-xs text-text-faint">Stage {i + 1}</span>
                </div>
                <div className="text-base font-medium text-text">{step.title}</div>
                <p className="text-sm text-text-muted">{step.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* Evidence-backed claims — a real example, not a mockup */}
      <section className="mx-auto max-w-4xl px-10 pb-28">
        <Reveal>
          <span className="text-xs font-medium tracking-[0.2em] text-mint">A REAL CLAIM</span>
          <h2 className="mt-4 text-3xl font-medium tracking-tight text-text">
            Every claim, traced back to the transcript.
          </h2>
        </Reveal>

        <Reveal delay={120} className="mt-10">
          <div className="rounded-2xl border border-border bg-raised p-8">
            <div className="flex items-start justify-between gap-4">
              <blockquote className="text-xl font-medium leading-snug text-text">
                "The iPhone 16 family performed stronger than models lacking Apple intelligence."
              </blockquote>
              <VerdictBadge verdict="VERIFIED" />
            </div>
            <div className="mt-6 grid grid-cols-2 gap-4 text-sm">
              <div className="rounded-lg border border-border bg-base px-4 py-3">
                <div className="text-xs uppercase tracking-wide text-text-faint">Timestamp</div>
                <div className="mt-1 text-text">1376s (22:56)</div>
              </div>
              <div className="rounded-lg border border-border bg-base px-4 py-3">
                <div className="text-xs uppercase tracking-wide text-text-faint">Source text</div>
                <div className="mt-1 text-text">
                  "performance on the iPhone 16 family was stronger than those where Apple
                  intelligence was not"
                </div>
              </div>
            </div>
            <div className="mt-4 text-xs text-text-faint">Apple · Q1 2025 earnings call</div>
          </div>
        </Reveal>
      </section>

      {/* Final CTA */}
      <section className="border-t border-border px-10 py-20 text-center">
        <Reveal>
          <h2 className="text-2xl font-medium text-text">See it on a real call.</h2>
          <p className="mt-2 text-text-muted">16 calls, already processed, waiting in the dashboard.</p>
          <Link
            to="/app"
            className="mt-8 inline-flex items-center gap-2 rounded-full bg-mint px-6 py-3 text-sm font-medium text-[#06120c] transition-opacity hover:opacity-90"
          >
            Open the dashboard <ArrowRight size={14} />
          </Link>
        </Reveal>
      </section>
    </div>
  );
}
