# Tasks

Ordered, PR-sized tasks. Each lists the requirements it satisfies and a "done when" check that a reviewer or CI can verify.

## How to use this list

1. Keep `specs/requirements.md`, `specs/design.md` and `specs/tasks.md` in the repo, so the coding agent and reviewers read the same source of truth.
2. Give Claude Code one task at a time: "Implement T-xx only. Context: specs/requirements.md, specs/design.md."
3. Tests first. Tests for each cited requirement carry a marker such as `@pytest.mark.req("REQ-INT-03")`, so traceability can be checked automatically (T-11).
4. One PR per task. Tick the box only when its "done when" check passes in CI.
5. If implementation exposes a gap or contradiction in the spec, fix the spec first in its own commit, then the code.

## Phase 1: Foundations and logs provider (weeks 1–2)

- [ ] **T-01 Repo scaffold.** uv project with the design.md package layout, ruff, mypy, pytest, import-linter and GitHub Actions. *Reqs:* NFR-12. *Done when:* CI is green, and a deliberate `providers` → `agent` import fails the build.
- [ ] **T-02 Config schema and loader.** Pydantic model per design.md, `${VAR}` interpolation, startup validation. *Reqs:* REQ-PRV-01, NFR-09. *Done when:* tests cover a valid config, an unknown type, a missing setting and a secret read from env.
- [ ] **T-03 Core models.** `Alert`, `Incident`, `TimeWindow`, `Scope`, log models and `Report`, plus JSON Schema export for `Report`. *Reqs:* REQ-PRV-03, REQ-RPT-01. *Done when:* round-trip tests pass and the exported schema validates the example report in overview.md.
- [ ] **T-04 Provider Protocols, errors and registry.** *Reqs:* REQ-PRV-01, 04. *Done when:* the registry builds a fake provider from config and rejects an unknown type with a clear error.
- [ ] **T-05 Provider middleware.** Rate limit, 60 s TTL cache with time-window rounding, circuit breaker, redaction; state kept in memory behind an interface so Redis can replace it in T-31. *Reqs:* REQ-PRV-07..09, NFR-10. *Done when:* unit tests with a fake clock cover breaker open, half-open and close, cache hits and redaction of each default pattern.
- [ ] **T-06 Elasticsearch logs adapter.** Port elk_mcp-server logic into `providers/logs/elasticsearch.py` implementing `LogsProvider`. *Reqs:* REQ-PRV-03, 05. *Done when:* the existing elk_mcp-server tests pass and recorded Elasticsearch responses map to normalized models with links.
- [ ] **T-07 Logs contract test suite.** Shared tests any `LogsProvider` must pass, run against the Elasticsearch adapter with recorded fixtures. *Reqs:* REQ-PRV-11. *Done when:* the suite runs in CI and a broken fake adapter fails it.
- [ ] **T-08 Logs MCP server.** `logs_*` tools over the provider, served over MCP streamable HTTP: TSV output, 8,000-char cap, truncation marker, `source` and `link`. *Reqs:* REQ-PRV-02, 05, 06. *Done when:* snapshot tests of each tool's output pass, including a truncation case.
- [ ] **T-09 Local demo environment.** Docker Compose for the OpenTelemetry Demo, Elasticsearch with APM, Kibana and Prometheus. *Done when:* one command brings it up and `logs_overview` returns demo logs.
- [ ] **T-10 Incident recorder.** Script that turns on a failure flag, makes the scripted commit, waits, snapshots fixtures and writes a label file. *Done when:* 5 labeled incidents are recorded and replayable.
- [ ] **T-11 Traceability check.** Script that lists every REQ and NFR id from `specs/requirements.md` and fails if any has no test marked with it (allowlist for not-yet-implemented ids, shrinking per phase). *Done when:* it runs in CI and reports coverage per requirement.

## Phase 2: Agent and eval harness (weeks 3–4)

- [ ] **T-12 Agent loop.** Hand-written tool-use loop behind a model-client interface (`agent/llm.py`), read-only tool registry, prompt caching, limits and forced final report. *Reqs:* REQ-AGT-01, 02, 05, 06, 12. *Done when:* tests with a scripted fake model cover each limit, a tool timeout and a tool error without aborting, and the token budget counts cumulative input across turns.
- [ ] **T-13 Prompt and data blocks.** System prompt, delimited data blocks for tool output, tool descriptions in `tools/descriptions.py`. *Reqs:* REQ-AGT-07. *Done when:* a prompt snapshot test passes and an injected log line arrives inside a data block.
- [ ] **T-14 Report submission.** `submit_report` schema validation and the correction loop. *Reqs:* REQ-AGT-03, 04, REQ-RPT-01, 03, 08. *Done when:* fake-model tests cover valid, invalid-then-fixed and invalid three times (minimal `low` report).
- [ ] **T-15 Evidence verification.** Check every evidence ref and timeline timestamp against the run's tool outputs. *Reqs:* REQ-AGT-08. *Done when:* tests reject a fabricated ref and a fabricated timestamp, and accept a grounded report.
- [ ] **T-16 Tracing and transcripts.** OpenTelemetry spans for model and tool calls, JSONL transcript per incident. *Reqs:* REQ-AGT-09, 10. *Done when:* one run produces spans with token, latency and cost attributes, and a transcript file.
- [ ] **T-17 Eval runner.** Replay by restoring each case's Elasticsearch and Prometheus snapshots into throwaway containers with the clock frozen at the incident time; 3 runs per case; development and held-out splits; results with 95% confidence intervals as Markdown and JSON. *Done when:* the 5 recorded cases run offline end to end.
- [ ] **T-18 Graders.** Category match, rubric-based LLM judge, grounded-evidence check, onset within ± 60 s, injection check. *Reqs:* NFR-01..03. *Done when:* each grader has unit tests with known pass and fail examples.
- [ ] **T-19 Baselines.** Single-shot runner and CLI-only agent. *Done when:* both are scored on the current set and appear as rows in the results table.
- [ ] **T-20 Eval set to 15.** Record 10 more incidents across the buckets in overview.md. *Done when:* 15 labeled cases replay and are scored.

## Phase 3: Metrics, traces and changes providers (weeks 5–6)

- [ ] **T-21 Elastic APM metrics adapter.** `service_health`, `alert_context`, `top_movers` from APM data streams, with Kibana links. *Reqs:* REQ-PRV-03, 05. *Done when:* the metrics contract suite (written in this task) passes with recorded responses.
- [ ] **T-22 Prometheus metrics adapter.** Same interface over the Prometheus HTTP API, with Grafana or Prometheus links. *Reqs:* REQ-PRV-03, 05, 11. *Done when:* it passes the same metrics contract suite.
- [ ] **T-23 Metrics MCP tools.** `metrics_*` tools, merging values from several providers with per-value source labels; raw `prom_query` fallback tool. *Reqs:* REQ-PRV-02, 06, 10. *Done when:* snapshot tests pass for APM only, Prometheus only and both.
- [ ] **T-24 Traces adapter and tools.** Elastic APM `TracesProvider`, `traces_get` and `traces_errors`, and "not supported" behavior when no traces provider exists. *Reqs:* REQ-PRV-03, 04, 11. *Done when:* contract tests pass and the not-supported message is tested.
- [ ] **T-25 GitHub changes adapter and tools.** `recent_deploys`, `diff_summary`, `config_changes`. *Reqs:* REQ-PRV-03, 05, 11. *Done when:* contract tests pass with recorded GitHub API responses, covering repos with and without the Deployments API.
- [ ] **T-26 Eval set to 30.** Add red herrings, no-clear-cause and injection cases, fix the 20/10 development and held-out split, and record 5 alert-storm scenarios as a separate set; calibrate the LLM judge against 20 hand-graded cases. *Reqs:* NFR-01..03. *Done when:* 30 cases replay and judge agreement is reported.
- [ ] **T-27 Eval iteration.** One change per run (tool descriptions, hypothesis step, each new tool group), plus runs per metrics backend. *Done when:* each change is a row in the results table with accuracy, cost and tool calls.

## Phase 4: Intake, scale and notifiers (week 7)

- [ ] **T-28 Webhook intake.** FastAPI receiver with source-specific authentication, Alertmanager normalization and a Redis Streams queue. *Reqs:* REQ-INT-01, 02, NFR-07. *Done when:* tests cover valid, unauthenticated and malformed requests, and a load test shows p95 ack under 100 ms at 500 alerts in 10 minutes.
- [ ] **T-29 Incident store and state machine.** Postgres tables and allowed transitions (open → investigating → reported → resolved). *Reqs:* REQ-INT-06, 12, 13. *Done when:* transition tests pass and illegal transitions are rejected.
- [ ] **T-30 Dedupe and grouping.** Fingerprint, scope-in-window and dependency-map rules, plus ignore rules, each storing its reason. *Reqs:* REQ-INT-03..07. *Done when:* table-driven tests pass for every rule and its recorded reason.
- [ ] **T-31 Dispatcher and workers.** Priority ordering, fixed worker pool, follow-up handling and budget fallback; move cache, rate-limit and circuit-breaker state to Redis so all workers share it; run the dispatcher as a single leader via a Postgres advisory lock. *Reqs:* REQ-INT-08..11, REQ-AGT-11, REQ-PRV-08, 09. *Done when:* tests show correct ordering, no dropped incidents with all workers busy, and the switch to single-shot when the budget is spent.
- [ ] **T-32 Notifiers.** `Notifier` interface, router, Slack and email adapters, retries, threaded updates and correct/incorrect feedback capture. *Reqs:* REQ-RPT-02, 04..07, 09. *Done when:* the notifier contract suite passes with mocked APIs, including time-zone rendering and one notifier failing while the other delivers.
- [ ] **T-33 Storm evals and load test.** *Reqs:* NFR-04, 05. *Done when:* each storm case yields one report naming the upstream cause, and load-test results are recorded against the targets.

## Phase 5: Hardening and shipping (week 8)

- [ ] **T-34 Security checks in CI.** Scan logs for secrets and transcripts for redaction-pattern matches. *Reqs:* NFR-09, 10. *Done when:* both scans run in CI and fail on a planted secret.
- [ ] **T-35 Fault-injection test.** Take the model API and one provider down during a storm replay. *Reqs:* NFR-08. *Done when:* no alerts are lost and incidents complete after recovery.
- [ ] **T-36 Retention.** Scheduled cleanup of transcripts and traces past `retention_days`. *Reqs:* NFR-11. *Done when:* a test with a fake clock shows old records removed.
- [ ] **T-37 One-command run.** Docker Compose for the full system plus a README quickstart. *Done when:* a fresh clone reaches a first report on a recorded incident by following the README.
- [ ] **T-38 CI eval smoke set.** 5 representative cases on every PR. *Reqs:* NFR-12. *Done when:* the job finishes in under 10 minutes and posts its results table to the PR.
- [ ] **T-39 Ship the story.** README with architecture diagram, results vs. baselines and a demo GIF; blog post; résumé bullet with real numbers. *Reqs:* NFR-01..06 reported. *Done when:* the traceability check (T-11) shows every requirement covered, with no allowlist left.
