import { Link } from "react-router-dom";
import { ArrowRight, Layers } from "lucide-react";
import { Logo } from "../components/Logo";

export function Landing() {
  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-base">
      {/* Diagonal light-beam backdrop, confined to the hero area so it doesn't bleed into the
          footer band below — a soft glowing wedge with rays spilling up-left. */}
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

      <div id="how-it-works" className="relative z-10 border-t border-border px-10 py-8">
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
  );
}
