# Unbreak AI

AI agent that finds the root cause of production incidents across your observability stack, and is built to fix them next.

> **Status:** design complete, implementation starting. Built spec-first: the specs below are the source of truth for every change.

## What it does

When an alert fires, Unbreak AI groups it with related alerts into one incident, investigates it on its own across logs, metrics, traces and recent deploys, and posts an evidence-backed root-cause report to Slack, email or Teams within minutes. Every claim in the report links back to the log line, metric or commit that supports it.

- **Read-only by design.** v1 investigates and recommends; humans act.
- **Pluggable.** Logs, metrics, traces, change history and notifications each sit behind a provider interface. v1 ships Elasticsearch, Elastic APM, Prometheus, GitHub, Slack and email.
- **Measured.** A replayable eval set of 30 recorded incidents scores every change against baselines.

## Roadmap

1. **v1 investigates:** root cause, timeline and evidence for each incident.
2. **v2 proposes fixes:** rollback suggestions and draft pull requests for human approval.
3. **v3 applies safe fixes:** a small allowlist of reversible actions with dry runs and automatic rollback.

## Specs

| Document | Contents |
| --- | --- |
| [specs/overview.md](specs/overview.md) | Goals, architecture, report schema, eval design, risks |
| [specs/requirements.md](specs/requirements.md) | Numbered, testable requirements (EARS form) and non-functional targets |
| [specs/design.md](specs/design.md) | Runtime topology, package layout, provider interfaces, data models, tool contracts, config |
| [specs/tasks.md](specs/tasks.md) | 39 PR-sized tasks in 5 phases, each linked to requirements and a "done when" check |

## Install

Not yet published. When released: `pip install unbreak-ai`, then `import unbreak_ai`.

## License

[Apache 2.0](LICENSE)
