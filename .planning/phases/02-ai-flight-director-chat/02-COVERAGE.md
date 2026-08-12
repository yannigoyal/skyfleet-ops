# Phase 2 — API Coverage Matrix

**Integration:** LiteLLM → OpenRouter → Cerebras (`openrouter/openai/gpt-oss-120b`)
**Generated:** 2026-08-12 during `/gsd-plan-phase 2`
**Policy:** Full API coverage by default — every capability starts at INTEGRATE; an OPT-OUT requires
a stated reason grounded in a project artifact, never "not needed yet".

The automated detector (`api-coverage.cjs`) returned `detected: false` on the phase-scope sample, but
this phase unambiguously integrates an external inference API, so the matrix is authored explicitly
rather than skipped.

## Capability Matrix

| # | Capability | Decision | Plan | Reason |
|---|------------|----------|------|--------|
| 1 | `chat_completion` — `litellm.acompletion` single-turn call | **INTEGRATE** | 02-01, 02-02 | The core of the phase: one completion per operator message (CHAT-01) |
| 2 | `structured_output` — `response_format` with `type: json_schema`, `strict: true` | **INTEGRATE** | 02-02 | CHAT-08's explicit requirement; nested inside `extra_body` so LiteLLM's OpenRouter parameter mapping cannot drop it |
| 3 | `provider_routing` — OpenRouter `provider: {"only": [...]}` | **INTEGRATE** | 02-02 | CHAT-08 requires Cerebras inference to be forced rather than auto-selected |
| 4 | `model_selection` — the `openrouter/<vendor>/<model>` routing prefix | **INTEGRATE** | 02-01, 02-02 | Model fixed to `openrouter/openai/gpt-oss-120b` by PLAN.md §9 |
| 5 | `generation_params` — `temperature`, `max_tokens` | **INTEGRATE** | 02-02 | AI-SPEC §4 fixes `temperature=0.2` / `max_tokens=800`; guardrail G4 makes the token cap load-bearing |
| 6 | `api_key_auth` — per-call bearer credential from the environment | **INTEGRATE** | 02-02 | `OPENROUTER_API_KEY` from the project `.env`; guardrail G5 forbids logging or echoing it |
| 7 | `error_surface` — transport and provider errors mapped to a typed domain error | **INTEGRATE** | 02-02 | Every provider failure becomes `LLMError` → HTTP 502 `llm_unavailable`, never an unhandled 500 (CHAT-07) |
| 8 | `usage_accounting` — `response.usage` prompt/completion token counts | **INTEGRATE** | 02-04 | AI-SPEC §7 metric 5 and dimension D9; recorded in the per-turn structured log line |
| 9 | `mock_transport` — deterministic offline substitution for the provider | **INTEGRATE** | 02-01, 02-04 | `LLM_MOCK=true` is a shipped feature (CHAT-06) and the default for the E2E suite per PLAN.md §12 |
| 10 | `streaming` — token-by-token `stream=True` completions | OPT-OUT | — | PLAN.md §9 specifies one complete JSON response per turn with a loading indicator; a schema-constrained object cannot be validated until the final token arrives, so streaming buys nothing (AI-SPEC §4b) |
| 11 | `tool_calling` / native function-calling loop | OPT-OUT | — | AI-SPEC §4 "Tool Use": the model returns structured JSON and the *backend* decides what to execute; a model-driven tool loop would compete with the CHAT-02..04 service-layer delegation requirement |
| 12 | `vision` / multimodal image input | OPT-OUT | — | The chat surface is text-only; no requirement in CHAT-01..08 or FE-08/FE-09 involves image input |
| 13 | `embeddings` | OPT-OUT | — | No retrieval anywhere in the system — fleet context is a live struct read from `TelemetryCache` and SQLite, not retrieved documents (AI-SPEC §5 rules out RAGAS on the same grounds) |
| 14 | `image_generation` | OPT-OUT | — | Outside the product surface; nothing in PLAN.md §10 renders model-generated imagery |
| 15 | `audio` / transcription / text-to-speech | OPT-OUT | — | The console has no audio surface; input is a text field (FE-08) |
| 16 | `prompt_caching` | OPT-OUT | — | The fleet-context system message changes on essentially every call (telemetry updates at ~500ms), so exact-match caching would never hit; AI-SPEC §4b rules it out explicitly |
| 17 | `provider_fallbacks` — OpenRouter fallback ordering / LiteLLM `fallbacks` | OPT-OUT | — | Directly contradicts capability 3: a silent fallback to a non-Cerebras provider is the failure mode CHAT-08's pinning exists to prevent, and AI-SPEC §7 names it as the usual cause of a latency alert |
| 18 | `retries` — LiteLLM `num_retries` / automatic retry on parse failure | OPT-OUT | — | AI-SPEC §4b fixes retries at zero for this phase: a parse failure surfaces as a readable 502 rather than a silent second attempt with different content |
| 19 | `reasoning_effort` / thinking-token parameters | OPT-OUT | — | This is a low-temperature structured-extraction task, not a reasoning benchmark; extra reasoning tokens raise cost and latency without improving schema adherence |
| 20 | `logprobs` / `top_logprobs` | OPT-OUT | — | No confidence-scoring or reranking consumer exists; grounding is validated by the service layer, not by token probability |
| 21 | `seed` — deterministic sampling | OPT-OUT | — | Determinism for tests comes from `LLM_MOCK=true` and the canned fixture corpus (AI-SPEC §5), which is stronger and free; provider-side seeding would still cost a network call |
| 22 | `batch` / async job completions | OPT-OUT | — | One call per operator turn, interactive latency budget under ~5s; batching is meaningless for a single interactive request |
| 23 | `web_search` / provider plugins | OPT-OUT | — | The model reasons only over the fleet snapshot the backend supplies; external browsing would introduce ungrounded facts into dispatch decisions |
| 24 | `credits` / rate-limit / key-inspection endpoints | OPT-OUT | — | Single-operator demo with sub-cent per-turn cost (AI-SPEC §4b); no quota management surface exists in the product |
| 25 | `callbacks` / observability integrations (Langfuse, Phoenix, OTel exporters) | OPT-OUT | — | AI-SPEC §5 keeps Arize Phoenix opt-in, localhost-only, and out of `[project].dependencies` and the Dockerfile; production monitoring is the structured per-turn log line (AI-SPEC §7) |

## Rollup

- **INTEGRATE:** 9 capabilities, all assigned to a plan
- **OPT-OUT:** 16 capabilities, each with a reason traced to `PLAN.md`, `REQUIREMENTS.md`,
  `02-AI-SPEC.md`, or `02-RESEARCH.md`
- **Unreviewed:** 0
