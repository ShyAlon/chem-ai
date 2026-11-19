# HomeChem technologies

This document records the technology choices in the current implementation. Exact dependency versions come from the [frontend lockfile](../web/package-lock.json) and [backend lockfile](../backend/uv.lock).

| Area | Technology | Role |
| --- | --- | --- |
| Web app | React, React DOM, TypeScript, Vite | Component-based notebook, type checking, local development server, and production build |
| UI and localization | CSS custom properties and logical properties, backend JSON message catalogs | Shared design tokens, English and Hebrew strings, and RTL layout |
| PWA and preferences | Web App Manifest, Service Worker and Cache APIs, `localStorage` | Installation metadata, offline static shell, and browser-local language preference |
| API | Python 3.12, FastAPI, Uvicorn, Pydantic | ASGI service, typed HTTP routes, input validation, and deterministic policy |
| English normalization | NLTK Snowball and WordNet | Normalize inflections and use selected synonym sets in the deterministic resolver |
| Client contract | OpenAPI, `openapi-typescript`, Fetch API | Generate TypeScript types from the server schema and use them in the HTTP client |
| Integrations | MCP Python SDK, Streamable HTTP, HTTPX | Consume compound, evidence, and measurement data through a dedicated MCP service; expose an optional assessment tool; call model providers through HTTPX |
| LLM inference | Ollama with `qwen2.5:7b-instruct-q4_K_M` by default, DeepSeek with `deepseek-flash` by default | Hebrew-to-English translation and surface suggestions for unfamiliar wording in local and production environments respectively. A fixture provider supports deterministic tests. |
| Optional dedicated translation | Azure Translator Text API | Hebrew-to-English translation with the same downstream English resolver |
| Observability | Python logging, OpenTelemetry SDK, OTLP/HTTP | Structured logs, correlated spans, request latency, and policy outcome metrics |
| Verification | pytest, TypeScript compiler, Playwright with Chromium | Policy and provider contract tests, type and schema checks, and browser coverage for the bilingual workflow and offline shell |
| Dependencies and automation | uv, Node.js 24, npm, Bash | Locked installs and repeatable commands shared by developers and CI |
| Hosting and release | Docker, Docker Compose, Caddy, GitHub Actions, GHCR, SSH | Build, publish, and deploy two containers to the VPS and verify or roll back releases |

## Planned technologies

- **Supabase Postgres** for curated evidence and persisted application data. Postgres full-text search is the initial retrieval approach. Adoption of pgvector depends on retrieval evaluation.
- **RDKit and a supervised solubility model** for the Molecule Explorer. The model and external compound lookup provider are still to be selected.
- **Supabase Auth** is deferred until the project needs accounts or cross-device persistence.

Update this document when a core tool is adopted, replaced, or retired. The [architecture](architecture.md) describes how these tools fit together.

## Material catalog management

Pydantic validates the JSON material catalog and rejects collisions after the same NLTK normalization used by the resolver. FastAPI exposes the active catalog, draft validation, and deterministic inspection. React provides the bilingual management workspace at `/management`. Catalog imports use an atomic file replacement through `scripts/import-materials.sh`; deployed changes are bundled in the API image.

## Backend-driven presentation

FastAPI and Pydantic supply validated application definitions through `/api/catalog`, localized cleaning presentation in interpretation/assessment responses, server-selected autocomplete hints, and deterministic scenario evaluation. OpenAPI generates the React client types. Scientific content, translations, calculator thresholds, and procedure eligibility are maintained in backend JSON catalogs. React renders generic fields and results.

## MCP data and activity display

A dedicated FastMCP service wraps PubChem PUG REST and curated evidence/reference records. The API's MCP client validates typed results, applies bounded caching and timeouts, and records operation spans. React displays live activity snapshots in an expandable timeline. The data service reuses the API deployment image.

Shared Pydantic presentation models generate form types through OpenAPI. React reuses the same field renderer, JSON request client, and export utility across the notebook, scenarios, research, and management interfaces.
