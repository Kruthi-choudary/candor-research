# Candor

Turn an hour-long earnings call into a short, evidence-backed brief — every claim traced back
to an exact timestamp and quote in the transcript, not a summary you have to trust blind.

Built as a resume/interview project, not a startup or hackathon entry. Scope: 4 companies
(AAPL, MSFT, NVDA, META) × 4 quarters each = 16 real earnings calls, all real audio, all real
data, nothing mocked.

## Problem

Earnings call transcripts are long (45-90 minutes), dense, and hard to fact-check. Most
AI summarizer demos solve the "summarize this" problem but not the "how do I know this is
actually what was said" problem — the summary just has to be trusted. Candor's bet is that
the second problem is the one that actually matters: every claim it produces carries a
timestamp and an exact quote, and a separate verification pass checks that the quote really
exists at that timestamp before the claim ships.

## Architecture

```
React (Vite + TS)  ──HTTP──▶  FastAPI (api/main.py)  ──reads/writes──▶  data/processed/*.json
                                      │
                                      └──calls──▶  pipeline.py  ──orchestrates──▶  src/*
```

**Why Vite, not Next.js:** this is a local SPA that only ever runs on localhost for one
person — there's no SSR, SEO, or multi-route-server need for Next.js to actually solve.
Vite gets the same React/TypeScript/Tailwind stack running with less configuration and
nothing unused sitting in the project.

- **Frontend** (`frontend/`): Vite + React 19 + TypeScript + Tailwind v4. Dashboard, per-call
  report (overview / claims / transcript tabs), a claim-detail view with a WaveSurfer.js
  waveform player, and an evaluation page. Talks to the API only — no hardcoded report data.
- **API** (`api/main.py`): a small local FastAPI service — not a public-facing product (see
  "Scope" below). `/companies`, `/calls`, `/calls/{ticker}/{quarter}`, `/calls/.../claims`,
  `/calls/.../transcript`, `/calls/.../audio`, `/eval/summary`, `POST /analyze`.
- **Pipeline** (`pipeline.py` + `src/`): the actual processing. Each stage's code lives under
  `src/<stage>/`, config lives in `config/*.yaml`, and `src/common/` holds the shared
  manifest/schema/error-handling code described below.

## Pipeline

One command runs the whole thing for a single call:

```bash
python pipeline.py --ticker NVDA --quarter Q1-2025
python pipeline.py --ticker NVDA --date 2024-05-22   # alternative: look up by call date
```

Six stages, each caching its output so re-running a call skips what's already done
(`--force` to recompute):

1. **Audio** — the call recording, already present under `data/raw/audio/{TICKER}/{QUARTER}.mp3`
   (Candor does not fetch new audio automatically — see "Scope").
2. **Transcription** — `faster-whisper` (`base.en`) converts speech to timestamped segments.
3. **Sentiment** — `ProsusAI/finbert` scores every segment positive/negative/neutral.
4. **Prosody** — `librosa` extracts pitch, energy, pause length, and speaking rate per segment.
5. **RAG context** — queries a pgvector index (LlamaIndex + `BAAI/bge-small-en-v1.5`) for
   prior-quarter chunks from the *same* company, filtered server-side by ticker, to give the
   LLM cross-quarter comparison context.
6. **Verified report** — a Groq-hosted LLM (`openai/gpt-oss-120b`) drafts claims as
   JSON-schema-constrained output (every claim must carry a citation copied verbatim from a
   provided quote); a separate evaluator then re-checks every citation against the transcript
   before the final report is written.

Output is one standardized JSON per call (`src/common/schema.py` is the contract) —
`company`, `quarter`, `overall_summary`, `sentiment_distribution`, `key_claims` (claim /
evidence / timestamp / sentiment), `citation_verification`, `audio_features_summary`,
`prior_quarter_context_used`, `stage_durations_sec`. `risks` and `management_outlook` are
present but intentionally empty — the current prompt doesn't extract them yet, and an empty
honest field beats a faked one.

Bad input, missing audio, an empty transcript, a Groq API failure, or malformed LLM JSON all
raise a `PipelineError` and exit with a clean one-line message — not a raw traceback.

## Tech stack

| Layer | Tech |
|---|---|
| ASR | `faster-whisper` 1.2.1 |
| Sentiment | `transformers` 5.18 + `ProsusAI/finbert` |
| Prosody | `librosa` 1.0.0 |
| RAG | `llama-index-core` 0.14.25 + Postgres/pgvector + `BAAI/bge-small-en-v1.5` |
| LLM | Groq (`openai/gpt-oss-120b`), free tier |
| API | FastAPI 0.142 + Uvicorn |
| Frontend | React 19, Vite 8, TypeScript, Tailwind v4, WaveSurfer.js, react-router-dom |
| Config | YAML (`config/companies.yaml`, `config/pipeline.yaml`) — no hardcoded model names or thresholds |

## Evaluation methodology

Two separate, independent measurements — because "it doesn't hallucinate" and "it's actually
useful" are different claims, and conflating them is exactly the kind of thing that falls
apart under a follow-up question.

**1. Citation accuracy** (`src/eval/check_citations*.py`): for every citation an LLM output
claims, does that exact quote exist at that timestamp in the real transcript? Run across all
16 calls, comparing two generation strategies:

| Metric | Baseline (free-text citations) | Structured (JSON-schema citations) |
|---|---|---|
| Schema compliance | 81.2% | 100.0% |
| Citation accuracy | 81.4% | 100.0% |
| Total citations | 86 | 128 |
| Verified citations | 70 | 128 |

Switching from regex-parsed free-text citations (`"quote" [mm:ss]`) to a JSON-schema-constrained
response that forces every claim to carry an exact, copy-verbatim citation eliminated the
paraphrasing and malformed-timestamp failures behind the baseline's gap. (Reproduce with
`python -m src.eval.compare_runs`.)

**2. Claim-extraction coverage** (`src/eval/scaffold_labels.py` + `check_claim_coverage.py`):
citation accuracy only proves claims aren't fabricated — it says nothing about whether the
pipeline *missed* important claims or surfaced noise. This measures precision/recall/F1
against hand-labeled ground truth: a human (or, for 3 of the 4 calls, an independent AI
reading the raw transcript cold) reads the call and writes down what they'd consider the
real claims, *without* looking at the model's output, then that list is compared to what the
pipeline actually generated.

| Call | Labeled by | Precision | Recall | F1 |
|---|---|---|---|---|
| AAPL Q1 2025 | Human (fully independent) | 0.625 | 0.714 | 0.667 |
| META Q1 2025 | AI, reading transcript cold | 0.75 | 0.75 | 0.75 |
| MSFT Q1 2025 | AI, reading transcript cold | 0.875 | 0.875 | 0.875 |
| NVDA Q1 2025 | AI, reading transcript cold | 0.875 | 0.875 | 0.875 |
| **Average** | | **0.781** | **0.803** | **0.792** |

Worth stating plainly rather than burying: the one fully human-independent label set (AAPL)
scored lowest. The AI-drafted labels for the other three were written by the same system
that designed the extraction prompt, so they likely overlap with the model's own notion of
"what's a claim" more than a cold human reading would. **The AAPL number (~0.67-0.71) is the
more trustworthy figure of the four** — the average is presented for completeness, not as
the headline.

Matching for both evals is approximate (`difflib.SequenceMatcher` text similarity), which
catches "missed this entirely" / "fabricated a claim nothing supports" but isn't precise
enough to be the only signal — the per-call breakdown matters more than the aggregate.

## Results

- 16/16 calls fully processed through the standardized pipeline, 100% citation accuracy on
  every one (128/128 citations verified).
- Baseline → structured-output change: citation accuracy 81.4% → 100%, schema compliance
  81.2% → 100%.
- Claim-extraction coverage: 0.792 F1 average across 4 labeled calls (one per company);
  ~0.67 F1 on the single fully-independent human-labeled call.

## Demo

Run the API and frontend locally (see below), then:

- **Dashboard** — search across all 16 calls, each card showing real sentiment distribution
  and citation accuracy.
- **Call report** — Overview / Claims / Transcript tabs; click any transcript line to seek
  the real audio.
- **Claim detail** — the core interaction: claim → verdict badge → timestamp → exact
  transcript evidence → a waveform with the cited region highlighted, playable from that
  exact point.
- **Evaluation** — the two tables above, served live from `/eval/summary`.

## How to run

**Tier 1 — just browse the 16 already-processed calls.** `data/processed/` (transcripts,
sentiment, reports, eval results) is committed to this repo, so this works with no API key
and no audio files:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --port 8321          # terminal 1
cd frontend && npm install && npm run dev  # terminal 2
```

Open http://localhost:5173 — dashboard, reports, claims, transcripts, and the evaluation
page all work immediately. **Audio playback will 404**, though: the source mp3s
(~580MB, real earnings-call recordings) aren't in this repo — not ours to redistribute,
and too large to be worth it for a portfolio project. Everything that's just text works.

**Tier 2 — regenerate a report or re-run eval for one of the 16 calls.** Needs a Groq key
(free tier) but not audio, since transcription/sentiment/prosody are already cached:

```bash
cp .env.example .env   # add GROQ_API_KEY from console.groq.com
python pipeline.py --ticker NVDA --quarter Q1-2025 --force
```

**Tier 3 — process a brand-new call from scratch.** Drop an mp3 at
`data/raw/audio/{TICKER}/{QUARTER}.mp3` (ticker must exist in `config/companies.yaml`),
add a Groq key, then run the same `pipeline.py` command without `--force` needed. RAG
(stage 5) also needs a local Postgres with the `pgvector` extension — without it, the
pipeline degrades gracefully (logs a warning, continues without cross-quarter context)
rather than failing the whole run.

## Deploying (optional — a public, read-only demo)

This deploys **Tier 1 only** — the 16 committed calls, browsable by anyone, no audio
playback, no live processing. Deliberately not full pipeline hosting: that would need an
always-on server and would share your Groq key across all traffic. Two free services,
no server of your own:

**API, on Render:**
1. [render.com](https://render.com) → sign in with GitHub → **New → Blueprint** → select
   this repo. `render.yaml` pre-fills everything (`requirements-api.txt` only — a few MB,
   not the multi-GB Whisper/FinBERT/llama-index stack — and `READ_ONLY_MODE=true`, which
   makes `POST /analyze` return 403 without ever importing the heavy pipeline code).
2. Leave `ALLOWED_ORIGINS` blank for now — set it after step 2 below.
3. Deploy. You'll get a URL like `https://candor-api-xxxx.onrender.com`. Free tier sleeps
   after 15 minutes idle; the first request after that takes ~30s to wake it up.

**Frontend, on Vercel:**
1. [vercel.com](https://vercel.com) → sign in with GitHub → **Add New → Project** → select
   this repo.
2. Set **Root Directory** to `frontend`.
3. Add an environment variable `VITE_API_BASE_URL` = the Render URL from above.
4. Deploy. You'll get a URL like `https://candor-xxxx.vercel.app`.

**Connect them:** back on Render → your service → **Environment** → set `ALLOWED_ORIGINS`
to the Vercel URL from step 4 → save (Render redeploys automatically). Without this, the
browser blocks the frontend's requests to the API as a CORS error.

## Scope — what this deliberately is not

A local demo you run yourself, not a public hosted site: this was a conscious choice, not a
shortcut. Serving strangers on the internet needs always-on hosting, concurrency handling,
and input sanitization this project doesn't have — a different, bigger project than a
portfolio piece. Candor also does not fetch new audio automatically (the 16 calls were
downloaded once from company IR pages / Castify) and does not perform speaker diarization
(every segment is unattributed text + timestamp, not "CEO says X").
