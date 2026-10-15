# Candor

### The story behind the numbers.

When a company announces its quarterly results, its leaders discuss how the business performed and answer questions in an earnings call. Their words may sound positive even when their language becomes more cautious or their speaking patterns change. Candor's research goal is to help readers investigate those changes by comparing what an executive says and how they say it with that same executive's earlier calls, then tracing the differences back to evidence.

The current prototype builds part of that workflow: it transcribes recordings, classifies financial sentiment, measures vocal features and generates short briefs from selected quotes. Readers can inspect each claim's source text, surrounding conversation and, when audio is available, the original recording. **Executive-specific historical baselines and communication-anomaly detection are not yet implemented.**

The included dataset covers **16 calls across Apple, Microsoft, Nvidia and Meta**, with four quarters per company. Reports, transcripts and evaluation outputs are committed so the research library can run without model downloads, API keys or a vector database.

**A citation match confirms similar source text near a timestamp. It does not independently verify that the source supports the generated claim.**

[Quick start](#quick-start) · [How it works](#how-it-works) · [Evaluation](#evaluation) · [Known limitations](#known-limitations) · [Deployment](#deployment)

## Research question and current scope

The central question is: **Does an executive communicate differently from their own usual pattern, and where does that change appear?** Someone who naturally speaks slowly should not be treated as unusual simply because another executive speaks faster. A meaningful comparison needs the same person's historical baseline, comparable passages and evidence a reader can inspect. A detected change would be a reason to investigate, not proof of nervousness, dishonesty or future stock performance.

| Part of the intended workflow | Current implementation |
|---|---|
| Analyse what was said | Segment-level financial sentiment and claims generated from selected quotes; no dedicated hedging or uncertainty detector |
| Analyse how it was said | Descriptive pitch, energy, pause and speaking-rate measurements |
| Compare the same executive across calls | Not implemented; speakers are not identified |
| Detect unusual changes against a historical baseline | Not implemented; no calibrated communication-anomaly score |
| Retrieve relevant historical evidence | New retrieval uses the same company and strictly earlier recorded call dates; older saved reports still need regeneration and topic-specific comparisons need work |
| Explain findings with inspectable evidence | Claim-to-quote, transcript and audio navigation exists; explanations of historical communication changes are future work |

The current interface demonstrates the available analysis and evidence trail. The longer-term research direction is to connect language and vocal measurements through speaker-aware historical comparisons.

## Research workflow

- **Research desk:** browse reports, filter by company and search by company, ticker or quarter. Library figures come from the API.
- **Earnings brief:** read the summary, inspect transcript sentiment and view descriptive vocal measurements.
- **Claims and evidence:** follow a claim to its citation-match verdict, source quote and surrounding transcript passages.
- **Audio navigation:** select a timestamp to seek the source player; the evidence view highlights the cited passage in a waveform.
- **Methodology and evaluation:** inspect recorded baseline/structured results and per-call claim-coverage scores, with incomplete human review clearly labelled.

The frontend includes responsive layouts, keyboard-operated report tabs and reduced-motion support. It opens immediately with a clearly labelled bundled demo, then replaces each resource with validated FastAPI responses as they arrive.

### Instant demo and backend connection

The frontend bundles curated copies of four existing reports (one per company), their claims, 109 transcript excerpts and a recorded evaluation snapshot. This is demonstration data from project outputs, not invented metrics or a live benchmark run. Full recordings and full transcripts are not bundled. Reports outside the sample set offer a link to an available example while their live response is pending.

A shared client checks the existing `/companies` endpoint in the background. The header shows **Connecting to live analysis…**, **Live data** after a valid response, or **Interactive demo** after all automatic connection attempts fail. It stays in the connecting state during cold-start retries while the bundled demo remains usable. Every content section separately identifies demo versus live data, including partial availability. The connection label describes backend availability; it does not imply that all visible sections have already switched to live data.

Requests time out after twelve seconds. Failed connections retry up to five times with delays of 2, 4, 8, 16 and 30 seconds; a manual retry remains available afterward. Failed content requests retain their bundled sample or previous live response. Shared caching, cancellation and request revisions prevent duplicate or stale requests from replacing newer data. Demo timestamps preview transcript passages without pretending to play audio. Optional web fonts load without blocking the first render.

To refresh the curated snapshot from the current stored outputs, run `npm run demo:build` in `frontend/`. This only updates the frontend's demo file; it does not alter API responses or rerun evaluation.

Audio playback requires the source MP3 to be available on the API server. A fresh clone and the public read-only deployment provide text-based research without those recordings.

## Quick start

Prerequisites: Python with `venv`, and Node.js **20.19+ within the 20.x series, or 22.12+** as required by the current Vite package. The existing local Python environment uses Python 3.13.

Clone the repository:

```bash
git clone https://github.com/Kruthi-choudary/candor-research.git
cd candor-research
```

**Terminal 1 — API serving the included reports:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-api.txt
READ_ONLY_MODE=true python -m uvicorn api.main:app --host 127.0.0.1 --port 8321 --reload
```

**Terminal 2 — frontend, starting from the repository root:**

```bash
cd frontend
npm ci
npm run dev
```

Open the URL Vite prints, normally **http://localhost:5173**. API documentation is at **http://127.0.0.1:8321/docs**. Vite proxies frontend `/api` requests to the backend on port `8321`. The frontend also works on its own: skip Terminal 1 to explore the bundled demo, with the connection status showing that live analysis is unavailable.

This path does not install Whisper, FinBERT, the embedding model or Groq dependencies. `POST /analyze` returns `403` in read-only mode. Missing audio is reported in the interface while reports and transcripts remain usable.

## How it works

```mermaid
flowchart TD
    Audio[Manually supplied MP3] --> Whisper[Whisper: timestamped transcript]
    Whisper --> FinBERT[FinBERT: segment sentiment]
    FinBERT --> Selection[Select positive and negative quotes]
    Selection --> LLM[Groq-hosted LLM: claims and summary]
    Index[Same-company vector retrieval] --> LLM
    LLM --> Check[Compare citation text and timestamp]
    Check --> Report[Save standardized JSON report]
    Audio --> Features[Librosa: vocal measurements]
    Whisper --> Features
    Features --> Report
    Report --> API[FastAPI]
    API --> UI[React research workspace]
```

[`pipeline.py`](pipeline.py) coordinates the processing stages:

1. **Transcription:** `faster-whisper`, configured with `base.en`, converts the recording into text segments with start and end times.
2. **Sentiment:** `ProsusAI/finbert` classifies each non-empty segment as positive, negative or neutral. The reported distribution is the percentage of segments in each class, not a measure of investor opinion.
3. **Vocal measurements:** `librosa` extracts pitch, energy, pauses and speaking rate. These are summarized alongside the report; they are not inputs to claim generation.
4. **Retrieval:** LlamaIndex queries PostgreSQL/pgvector using `BAAI/bge-small-en-v1.5` embeddings. Before vector search, metadata filters restrict candidates to the same company and quarters with recorded call dates strictly earlier than the target call. Returned results are checked against that eligibility list again. Missing or invalid target dates yield no context, and the earliest call needs no search. Ordering depends on the dates in `data/processed/call_dates.json`, which were collected from feed metadata and still need independent source verification. If retrieval fails, processing continues without it. **Older saved reports have not yet been regenerated with this fix.**
5. **Generation:** the configured Groq-hosted model, `openai/gpt-oss-120b`, receives sentiment percentages, up to four positive and four negative source quotes, and optional retrieved context. It is asked to return one claim per quote and a short summary in a JSON-schema-constrained response. **It does not receive the full current-call transcript.**
6. **Citation matching:** a separate checker finds transcript segments starting within two seconds of each citation and checks normalized text similarity against a `0.6` threshold. Match results are recorded before the standardized report is saved; a failed match does not automatically remove the claim.

The final output contains claims, evidence, timestamps, sentiment distribution, citation-match counts, audio-feature summaries, retrieved context and stage durations. See an [included Apple report](data/processed/pipeline_runs/AAPL/Q1_2025.json) and the [report contract](src/common/schema.py). `risks` and `management_outlook` are reserved fields and currently empty.

### Architecture and storage

The React SPA initially renders a bundled sample and requests live data from FastAPI in the background. The API reads saved JSON reports and intermediate outputs from `data/processed/`. In local processing mode, it can also invoke the pipeline. PostgreSQL/pgvector holds the optional retrieval index; it is not the main report store.

Vite suits the existing client-rendered research interface: report selection, evidence navigation and playback happen in the browser. The hosted frontend uses a rewrite to `index.html` so direct links and refreshes work with React Router.

| Layer | Implementation |
|---|---|
| Frontend | React 19, TypeScript, Vite 8, Tailwind CSS 4, React Router |
| Audio interface | Native audio controls and WaveSurfer.js |
| API | FastAPI and Uvicorn |
| Speech recognition | faster-whisper / `base.en` |
| Financial sentiment | Transformers / `ProsusAI/finbert` |
| Vocal measurements | librosa |
| Retrieval | LlamaIndex, PostgreSQL/pgvector, Hugging Face embeddings |
| Generation | Groq API with structured JSON output |
| Configuration | YAML files in `config/` |

These are integrations with existing models; the project does not train or fine-tune them. Dependency versions are recorded in the requirements files and frontend lockfile.

## Evaluation

### Citation matching

Recorded results from [`data/processed/eval/`](data/processed/eval/):

| Measure | Free-text baseline | Structured JSON |
|---|---:|---:|
| Citation-match rate | 81.4% | 100.0% |
| Citations matched | 70 / 86 | 128 / 128 |
| Recorded format-compliance value | 81.2% | 100.0% |

These results describe the included dataset under the implemented checkers. They do **not** establish 100% factual accuracy, complete claim support or the absence of hallucinations.

The comparison changes both generation format and checking procedure: the baseline uses regex parsing and a one-second timestamp tolerance; the structured checker uses a two-second tolerance and selects the most text-similar nearby segment. This is not a controlled experiment isolating the effect of JSON schema. The structured checker's format-compliance field counts processed report files against an expected 16; it is not an independent schema-validation score.

### Claim coverage

The coverage script greedily matches generated claims to reference claims using normalized text similarity with a `0.5` threshold.

| Call | Reference-label provenance | Precision | Recall | F1 |
|---|---|---:|---:|---:|
| AAPL Q1 2025 | Documented as human-labelled | 0.625 | 0.714 | 0.667 |
| META Q1 2025 | AI-drafted; human review pending | 0.750 | 0.750 | 0.750 |
| MSFT Q1 2025 | AI-drafted; human review pending | 0.875 | 0.875 | 0.875 |
| NVDA Q1 2025 | AI-drafted; human review pending | 0.875 | 0.875 | 0.875 |
| **Mean across four calls** | **Mixed provenance** | **0.781** | **0.803** | **0.792** |

The Apple provenance follows the repository's existing documentation; the other three [reference files](data/eval_labels/) explicitly carry `ai_drafted_pending_human_review`. The mean is not an independently human-validated quality score. Text similarity can also miss equivalent paraphrases or accept similar wording with different meaning.

### Recompute checks on saved outputs

With the API dependencies installed and the virtual environment active, run from the repository root:

```bash
python -m src.eval.check_citations_structured
python -m src.eval.check_claim_coverage
python -m src.eval.compare_runs
```

The first two commands recompute evaluation summaries from existing files without model calls or audio. They overwrite their corresponding saved summaries. `compare_runs` formats the saved baseline and structured results into `comparison.md`; it does not regenerate reports or rerun the original experiment. Per-call citation files served by the claims endpoint are written separately by `pipeline.py`.

### Historical-retrieval regression checks

```bash
python -m unittest discover -s tests -v
```

The tests cover strictly earlier dates, same-day exclusion, company isolation, missing dates, unavailable retrieval, result limits and the included dataset's chronology. They require no audio, model downloads or live database. An additional adapter test checks the installed LlamaIndex filter types with model and database operations substituted; it is skipped when those optional dependencies are unavailable.

### Frontend connection and fallback tests

With Node.js 24, run from `frontend/`:

```bash
npm test
npm run build
npm run lint
```

The dependency-free Node tests check immediate demo state, timeout and bounded retries, automatic recovery, partial failures, cache sharing, stale-response cancellation, response validation and sample-data shapes. They substitute transport responses rather than making calls to Render. They do not test browser audio decoding or visual layout.

## Run the processing pipeline locally

Full processing requires the heavier dependencies, source audio and a Groq key whenever new claims are generated. Models may download on first use.

From the repository root, with the virtual environment active:

```bash
python -m pip install -r requirements.txt
cp .env.example .env
```

Set `GROQ_API_KEY` in `.env`. Supply a recording at `data/raw/audio/{TICKER}/{QUARTER}.mp3`, for example `data/raw/audio/NVDA/Q1_2025.mp3`, then run:

```bash
python pipeline.py --ticker NVDA --quarter Q1-2025
```

**The pipeline checks for the MP3 before using cached outputs. Audio is required even when transcripts and features already exist.** Existing transcript, sentiment, audio-feature and claim files are reused by default. Retrieval and citation matching still run. Use `--force` only when you intend to recompute all cached stages, including transcription and audio features:

```bash
python pipeline.py --ticker NVDA --quarter Q1-2025 --force
```

To enable the local processing API after installing the full dependencies:

```bash
READ_ONLY_MODE=false python -m uvicorn api.main:app --host 127.0.0.1 --port 8321 --reload
```

The frontend currently browses saved reports; there is no upload or analysis-submission interface. The processing endpoint is synchronous and has no authentication, so the public deployment disables it.

For optional retrieval, configure a PostgreSQL database with the `vector` extension, update the connection settings in `config/pipeline.yaml`, and build the index:

```bash
python -m src.rag.build_index
```

The index is built from the saved transcripts. The current indexing script does not explicitly clear existing nodes, so repeated indexing should not be assumed to replace the index cleanly. Historical filtering uses the existing ticker and quarter metadata; an existing index does not need to be rebuilt just to apply that fix.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/companies` | Configured company names and tickers |
| GET | `/calls` | Saved report summaries |
| GET | `/calls/{ticker}/{quarter}` | Standardized report |
| GET | `/calls/{ticker}/{quarter}/claims` | Claims with citation-match verdicts |
| GET | `/calls/{ticker}/{quarter}/transcript` | Timestamped transcript |
| GET | `/calls/{ticker}/{quarter}/audio` | MP3 when available; otherwise `404` |
| GET | `/eval/summary` | Saved citation and coverage results |
| POST | `/analyze?ticker=NVDA&quarter=Q1-2025` | Run the local pipeline; `403` in read-only mode |

Quarter inputs accept forms such as `Q1-2025` and `Q1_2025`. Interactive documentation is available at `/docs`.

## Project structure

```text
api/                    FastAPI routes and deployment-mode handling
config/                 Company registry and pipeline settings
src/
  common/               Call paths, configuration, report shape and errors
  data/                 Transcription and supporting data-collection scripts
  nlp/                  FinBERT sentiment classification
  audio/                Vocal-feature extraction
  rag/                  Vector indexing and historical retrieval
  report/               Free-text baseline and structured generation
  eval/                 Citation checks and claim-coverage evaluation
  analysis/             Separate stock-price reaction analysis
pipeline.py             Single-call processing coordinator
data/
  processed/            Included transcripts, reports, features and evaluations
  eval_labels/          Reference claims and available provenance metadata
  raw/                  Local source recordings and downloads; gitignored
frontend/               React interface, shared connection client and bundled demo
tests/                  Historical-retrieval regression checks
render.yaml             Read-only API deployment configuration
```

### Exploratory stock-price comparison

The separate price-reaction script compares a closing price on or before the recorded call date with the next available trading day's close, alongside transcript sentiment. Its current flag uses an absolute price-move threshold of 5%; it does not estimate what return should be expected from the call's tone. This price reference is not an executive's communication baseline, and the flag is not a statistically validated anomaly or a causal explanation of market movement.

The price-reaction and SEC-filing scripts are supporting experiments. They are not part of the main claim-generation workflow or currently exposed as frontend research features. Price-window alignment with the actual call time needs validation before drawing event-study conclusions.

## Deployment

The repository supports a **read-only public demo**: the frontend browses included results while the API serves JSON files. No model inference or audio hosting is required for that mode.

| Setting | Render API | Vercel frontend |
|---|---|---|
| Repository | `Kruthi-choudary/candor-research` | `Kruthi-choudary/candor-research` |
| Branch | `main` | `main` |
| Root directory | Repository root | `frontend` |
| Build command | `pip install -r requirements-api.txt` | `npm run build` |
| Start / output | `uvicorn api.main:app --host 0.0.0.0 --port $PORT` | Output directory: `dist` |

Set `READ_ONLY_MODE=true` on the API and `ALLOWED_ORIGINS` to the exact frontend origin, without a trailing slash. Multiple origins can be comma-separated. Set the frontend's build-time `VITE_API_BASE_URL` to the API origin, without a trailing slash or `/api` suffix. For example, an API hosted at `https://your-api.onrender.com` serves `/calls` directly.

`READ_ONLY_MODE` and `ALLOWED_ORIGINS` are read from the API process environment; the API does not automatically load them from `.env`. `render.yaml` defines the read-only setting. `frontend/vercel.json` contains the SPA rewrite. Backend hosts that suspend idle services can make the first request slower.

## Known limitations

- **Incomplete evidence:** transcription segments can end mid-sentence. Selecting isolated fragments can change or obscure a claim's meaning.
- **Selection bias:** generation sees sentiment-selected quotes, not a comprehensive selection of financial facts or the full transcript.
- **Older saved context:** new retrieval enforces historical eligibility, but 10 included reports still contain 21 later-quarter context passages from earlier runs. These reports and their generated claims need review and regeneration; removing context fields alone would not undo its possible influence on generation.
- **Date provenance:** historical ordering follows recorded feed dates, not independently verified event timestamps. Incorrect date metadata can still produce an incorrect historical comparison.
- **Limited verification:** citation matching checks text and time, not whether the evidence entails the claim. Failed matches remain in the saved report.
- **Limited reference labels:** only four calls have reference claims, three sets await human review, and provenance has not been independently audited.
- **No speaker identification:** transcript segments do not distinguish management, analysts or individual speakers.
- **No historical communication baseline:** whole-call features mix speakers and passages; they cannot currently establish that a particular executive behaved unusually compared with their own history.
- **Descriptive audio only:** vocal measurements are not validated indicators of confidence, deception or financial performance.
- **File-based caching:** cache reuse depends on file existence, without automatic invalidation when prompts, models or configuration change.

## Planned improvements

These are outstanding work, not completed features.

### Reliability of the existing pipeline

1. Construct complete evidence passages from adjacent transcript segments.
2. Verify call-date sources and regenerate reports produced before historical filtering was fixed.
3. Add an independent claim-support review alongside citation matching.
4. Expand independently human-reviewed reference claims and record reviewer provenance.
5. Extend the historical-retrieval regression suite to cover misleading citations, other missing data and API failure cases.

### Communication-change research

1. Identify speakers and consistently associate the same executive across calls.
2. Compare like-for-like passages, accounting for recording quality, speaker turns and prepared remarks versus questions and answers.
3. Build historical language and vocal-feature baselines using only earlier calls, with explicit minimum-history requirements.
4. Evaluate changes in sentiment, uncertainty language, pauses, pitch, energy and speaking rate against those baselines.
5. Retrieve relevant earlier passages and explain observed differences with timestamps, uncertainty and human-reviewable evidence.
