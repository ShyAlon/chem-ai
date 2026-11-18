# HomeChem technologies

This document records the technology choices in the current implementation. Exact dependency versions come from the [frontend lockfile](../web/package-lock.json) and [backend lockfile](../backend/uv.lock).

| Area | Technology | Role |
| --- | --- | --- |
| Web app | React, React DOM, TypeScript, Vite | Component-based notebook, type checking, local development server, and production build |
| UI and localization | CSS custom properties and logical properties, TypeScript message catalogs | Shared design tokens, English and Hebrew strings, and RTL layout |
| PWA and preferences | Web App Manifest, Service Worker and Cache APIs, `localStorage` | Installation metadata, offline static shell, and browser-local language preference |
| API | Python 3.12, FastAPI, Uvicorn, Pydantic | ASGI service, typed HTTP routes, input validation, and deterministic policy |
| Client contract | OpenAPI, `openapi-typescript`, Fetch API | Generate TypeScript types from the server schema and use them in the HTTP client |
| Integrations | MCP Python SDK, Streamable HTTP, HTTPX | Publish and call the read-only policy tool and send HTTP requests to model providers |
| LLM inference | Ollama with `qwen2.5:7b-instruct-q4_K_M` by default, DeepSeek with `deepseek-flash` by default | Structured interpretation in local and production environments respectively. A fixture provider supports deterministic tests. |
| Observability | Python logging, OpenTelemetry SDK, OTLP/HTTP | Structured logs, correlated spans, request latency, and policy outcome metrics |
| Verification | pytest, TypeScript compiler, Playwright with Chromium | Policy and provider contract tests, type and schema checks, and browser coverage for the bilingual workflow and offline shell |
| Dependencies and automation | uv, Node.js 24, npm, Bash | Locked installs and repeatable commands shared by developers and CI |
| Hosting and release | Docker, Docker Compose, Caddy, GitHub Actions, GHCR, SSH | Build, publish, and deploy two containers to the VPS and verify or roll back releases |

## Planned technologies

- **Supabase Postgres** for curated evidence and persisted application data. Postgres full-text search is the initial retrieval approach. Adoption of pgvector depends on retrieval evaluation.
- **RDKit and a supervised solubility model** for the Molecule Explorer. The model and external compound lookup provider are still to be selected.
- **Supabase Auth** is deferred until the project needs accounts or cross-device persistence.

Update this document when a core tool is adopted, replaced, or retired. The [architecture](architecture.md) describes how these tools fit together.
