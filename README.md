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

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add GROQ_API_KEY (free tier: console.groq.com)

# Process a call (audio must already exist under data/raw/audio/{TICKER}/{QUARTER}.mp3)
python pipeline.py --ticker NVDA --quarter Q1-2025

# API
uvicorn api.main:app --port 8321

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

RAG (stage 5) needs a local Postgres with the `pgvector` extension; without it, the pipeline
degrades gracefully — it logs a warning and continues without cross-quarter context rather
than failing the whole run.

## Scope — what this deliberately is not

A local demo you run yourself, not a public hosted site: this was a conscious choice, not a
shortcut. Serving strangers on the internet needs always-on hosting, concurrency handling,
and input sanitization this project doesn't have — a different, bigger project than a
portfolio piece. Candor also does not fetch new audio automatically (the 16 calls were
downloaded once from company IR pages / Castify) and does not perform speaker diarization
(every segment is unattributed text + timestamp, not "CEO says X").
