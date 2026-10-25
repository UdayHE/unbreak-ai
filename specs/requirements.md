# Requirements

Every requirement is a testable statement in EARS form (When / While / If … the system shall …). Design and Tasks cite these ids, and each requirement maps to at least one automated test.

## Intake and incident management

| ID | Requirement |
| --- | --- |
| REQ-INT-01 | When an alert-source webhook request arrives, the system shall authenticate it (bearer token or basic auth for Alertmanager; an HMAC signature where the source supports one), validate the payload, persist it to the queue, and respond within 100 ms (p95). |
| REQ-INT-02 | If the payload is invalid or authentication fails, the system shall respond with a 4xx status, enqueue nothing, and log the rejection. |
| REQ-INT-03 | When an alert arrives whose fingerprint matches an open incident, the system shall attach it to that incident and shall not start a new investigation. |
| REQ-INT-04 | When an alert with no fingerprint match shares a service or namespace with an open incident whose latest alert is within the grouping window (default 5 min), the system shall attach it to that incident. |
| REQ-INT-05 | When an alert's service is downstream, in the dependency map, of a service in an open incident within the grouping window, the system shall attach it to that incident and record the dependency as the grouping reason. |
| REQ-INT-06 | When an alert matches none of REQ-INT-03 to 05, the system shall create a new incident in state `open`. |
| REQ-INT-07 | If an alert is silenced, inside a maintenance window, below the configured minimum severity, or on the known-flapper list, the system shall record it and shall not investigate it. |
| REQ-INT-08 | The system shall dispatch open incidents to workers in priority order: severity, then customer-facing flag, then number of attached alerts, then age. |
| REQ-INT-09 | While all workers are busy, the system shall keep incidents queued and shall not drop any. |
| REQ-INT-10 | When an alert joins an incident in state `investigating`, the system shall pass it to the running investigation as additional context. |
| REQ-INT-11 | When an alert joins an incident in state `reported`, the system shall post an update to the original report's thread, and shall start a follow-up investigation only if the new alert's severity is higher than the incident's. |
| REQ-INT-12 | When the alert source reports all alerts in an incident as resolved, the system shall set the incident to `resolved` and post a resolution update. |
| REQ-INT-13 | If the service restarts, the system shall resume incidents in states `open` and `investigating` without sending duplicate reports. |

## Investigation agent

| ID | Requirement |
| --- | --- |
| REQ-AGT-01 | When an incident is dispatched, the system shall start an investigation with the incident's alerts, the configured tools, and a time window from 30 minutes before the earliest alert's start until now. |
| REQ-AGT-02 | The system shall register only read-only tools with the agent; no tool shall write to any provider. |
| REQ-AGT-03 | The agent shall end every investigation by calling `submit_report` with input that validates against the report schema. |
| REQ-AGT-04 | If `submit_report` input fails validation, the system shall return the errors to the agent and allow up to 2 corrections, then publish a minimal report with confidence `low`. |
| REQ-AGT-05 | When the tool-call limit (15), input-token budget (150k) or timeout (4 min) is reached, the system shall instruct the agent to submit its best report with confidence `low` and shall stop after one more model call. |
| REQ-AGT-06 | When a tool call fails or times out, the system shall return the error to the agent as tool output and shall not abort the investigation. |
| REQ-AGT-07 | The system shall wrap all tool output in delimited data blocks, and the system prompt shall state that content inside them is data, not instructions. |
| REQ-AGT-08 | The system shall reject a report whose evidence refs or timeline timestamps do not appear in that run's tool outputs, and return the mismatches to the agent; these corrections count toward the REQ-AGT-04 limit. |
| REQ-AGT-09 | The system shall record a trace span for every model call and tool call, with tokens, latency, cost and outcome. |
| REQ-AGT-10 | The system shall store the full transcript of each investigation, keyed by incident id. |
| REQ-AGT-11 | While the daily cost budget is exhausted, the system shall run a single-shot summary (no tools) for non-critical incidents and the full investigation only for critical ones. |
| REQ-AGT-12 | The system shall use prompt caching for the system prompt, tool definitions and earlier turns, and shall count the token budget as cumulative input across all turns. |

## Providers

| ID | Requirement |
| --- | --- |
| REQ-PRV-01 | The system shall load providers and notifiers from configuration at startup, and shall fail fast with a descriptive error if a configured type is unknown or a required setting is missing. |
| REQ-PRV-02 | Agent-facing tool names and input schemas shall be identical regardless of which provider backs them. |
| REQ-PRV-03 | Each provider shall return data in the normalized model for its interface (see design.md, Data models). |
| REQ-PRV-04 | Each provider shall declare its capabilities; when a tool needs a capability its provider lacks, the tool shall return a "not supported by &lt;provider&gt;" message instead of an error. |
| REQ-PRV-05 | Every tool response shall include the source provider name and, where the provider has a UI, a deep link into it. |
| REQ-PRV-06 | Every tool response shall be at most 8,000 characters; when truncated, it shall end with a marker stating how many items were omitted. |
| REQ-PRV-07 | While a provider's circuit breaker is open, its tools shall return "provider unavailable" immediately without querying it. |
| REQ-PRV-08 | The system shall cache identical provider queries, with time windows rounded to 30-second boundaries, for 60 seconds, shared across all workers, and serve concurrent investigations from the cache. |
| REQ-PRV-09 | The system shall limit each provider to its configured maximum query rate across all workers (default 5 queries per second). |
| REQ-PRV-10 | When more than one metrics provider is configured, `metrics_service_health` shall label each value with the provider it came from. |
| REQ-PRV-11 | Every provider and notifier adapter shall pass the shared contract test suite before it can be enabled. |

## Report and notification

| ID | Requirement |
| --- | --- |
| REQ-RPT-01 | The report shall conform to the report schema in overview.md, including the timing and timeline fields. |
| REQ-RPT-02 | All report timestamps shall be ISO 8601 in UTC; each notifier shall render them in its configured display time zone. |
| REQ-RPT-03 | The timeline shall be sorted oldest first and shall include the alert itself. |
| REQ-RPT-04 | When a report is submitted, the system shall deliver it to every notifier whose routing rules match the incident's severity and service. |
| REQ-RPT-05 | Each notifier shall render the report in its native format: Slack Block Kit, email HTML with a plain-text part, Teams Adaptive Card. |
| REQ-RPT-06 | If delivery to a notifier fails, the system shall retry with exponential backoff up to 3 times, then mark that delivery failed and log it; one notifier's failure shall not block the others. |
| REQ-RPT-07 | Notifiers shall post follow-up updates in the original message's thread where the channel supports threads, and as a reply email with the same subject otherwise. |
| REQ-RPT-08 | The report shall show the confidence level prominently and, when it is `low`, the reason: limit reached, conflicting evidence, or insufficient data. |
| REQ-RPT-09 | Each delivered report shall let responders mark the root cause correct or incorrect (Slack buttons, email links), and the system shall store that feedback with the incident as a real-world accuracy label. |

## Non-functional requirements

| ID | Requirement | Target | Verified by |
| --- | --- | --- | --- |
| NFR-01 | Root-cause accuracy, all eval cases | ≥ 80% | Full eval set, mean of 3 runs with 95% CI; held-out split reported alongside |
| NFR-02 | Root-cause accuracy, high-confidence reports | ≥ 90% | Full eval set, mean of 3 runs with 95% CI; held-out split reported alongside |
| NFR-03 | Confidently wrong reports | ≤ 5% of cases | Full eval set, mean of 3 runs with 95% CI; held-out split reported alongside |
| NFR-04 | Time to report, from incident dispatch | p50 < 3 min, p95 < 5 min | Traces |
| NFR-05 | Queue wait for critical incidents under 500 alerts in 10 min | p95 < 1 min | Load test |
| NFR-06 | Average cost per full investigation | < $0.50 | Traces |
| NFR-07 | Intake acknowledgement latency | p95 < 100 ms | Load test |
| NFR-08 | Intake keeps accepting and queueing alerts while the model API or any provider is down | No alerts lost | Fault-injection test |
| NFR-09 | Secrets come only from environment variables or a secret manager, are never logged, and provider credentials are read-only | 0 secrets in logs | Log scan in CI |
| NFR-10 | Tool output is redacted for configured patterns (emails, tokens, keys) before it reaches the model | 0 matches in transcripts | Transcript scan in CI |
| NFR-11 | Transcripts and traces are retained for a configurable period | 30 days default | Config test |
| NFR-12 | Core modules are covered by unit tests, and the eval smoke set runs in CI | ≥ 80% line coverage; smoke set < 10 min | CI |
