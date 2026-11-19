# HomeChem architecture

HomeChem is a bilingual household chemistry notebook. The current implementation covers intact glass tabletops, smooth glass screens, and everyday cleaning of glazed ceramic sinks and tile floors. Python resolves common terms through the [terminology dictionary](terminology.md). The user confirms the inputs, and Python determines whether the procedure applies.

The UI also includes eight bilingual scenario workspaces for stains, food science, limescale and corrosion, material care, water chemistry, home experiments, ingredient functions, and chemical disposal. Their supported starter scenarios, chemistry explanations, sources, input definitions, and calculation parameters live in `backend/homechem/data/scenarios.json`. They are selected explicitly from the navigation. FastAPI validates and evaluates measurements deterministically, and the client renders the returned result.

## Components

```mermaid
flowchart LR
    Browser["React notebook"] -->|"REST API"| API["FastAPI"]
    API --> Dictionary["English NLP and terminology dictionary"]
    API -->|"Hebrew translation"| Translation["Configured LLM or Azure Translator"]
    API -->|"Unresolved surface wording"| LLM["Ollama locally or DeepSeek on the VPS"]
    API -->|"Direct Python call"| Policy["Deterministic policy and bundled source"]
    MCP["MCP endpoint in FastAPI"]
    Client["Standalone MCP client"] --> MCP
    MCP --> Policy
    API -->|"MCP client"| Knowledge["Dedicated chemistry data service"]
    Knowledge --> PubChem["PubChem API"]
    Knowledge --> Evidence["Curated evidence and reference measurements"]
    API --> Telemetry["Structured logs and OpenTelemetry"]
    MCP --> Telemetry
```

- The [React client](../web/src) owns the notebook workflow, shared components, and presentation of backend-provided translations. It sets the document direction for Hebrew RTL and stores the language preference in versioned `localStorage`. The [service worker](../web/service-worker.js) caches the app shell, static assets, and the most recently fetched backend presentation catalog for offline viewing. Assessments and scenario calculations require a connection.
- The [FastAPI service](../backend/homechem/main.py) validates REST requests and exposes the read-only `assess_cleaning` MCP tool. The REST assessment route calls the instrumented Python assessment function directly. Other MCP clients can call the same tool through `/mcp`.
- The [provider adapters](../backend/homechem/providers.py) share typed translation and surface suggestion contracts. Backend settings select local Ollama, hosted DeepSeek, or the fixture provider used in tests.
- The [policy module](../backend/homechem/policy.py) owns the decision, rule ID, policy version, and source. The browser renders the corresponding reviewed instructions and the chemistry or physical mechanism from the backend response.

## Fix-It request flow

1. `POST /api/interpret` translates Hebrew questions into English with the configured provider. It then resolves object, substrate, finish, and cleaning materials in Python using the same English rules for every request. English questions with recognizable terms or exclusions bypass inference. For unfamiliar surface wording, the configured provider can suggest a surface. Materials stay unverified on that path.
2. When the inputs match the reviewed scope, the notebook asks the user to confirm the surface and materials. Confirmation sends the structured inputs to `POST /api/assess`.
3. The API calls the instrumented `assess_cleaning` Python function directly. The policy returns `approved` only for confirmed inputs matching the reviewed material, finish, use context, and cleaning supplies. Device names appear as recognized context and are absent from the policy inputs. Other inputs yield `unverified`.
4. The notebook shows the result and supporting evidence. Interpretation and assessment each have a request ID. The browser console logs a structured summary for each API attempt with the original question, timing, outcome, and request ID. The assessment request contains a policy evaluation span. The optional MCP endpoint calls the same instrumented function for external clients.

## Runtime and deployment

Locally, [the development script](../scripts/dev.sh) starts Vite, the API, and the dedicated MCP data service on port 8002. Vite proxies API calls to the backend, which defaults to Ollama at `127.0.0.1:11434`.

The [production stack](../infra/compose.yaml) targets a single 4 GB VPS. Caddy serves the built PWA and proxies `/api/*` and `/mcp` to one FastAPI worker. A private `knowledge` service reuses the API image and exposes the chemistry-data MCP tools to the API. DeepSeek generates structured interpretations remotely. The [deployment workflow](../.github/workflows/deploy.yml) builds the web and API images on GitHub-hosted runners, publishes them to GHCR, and deploys the paired image digests over SSH. The deploy script verifies the HTTPS app shell, release SHA, and assessment flow before recording the release. A failed smoke check triggers an attempt to restore the previous pair.

The API writes structured logs with request IDs, trace IDs, and the deployed release SHA. Local development exports spans to the console. The production service can export traces and metrics over OTLP/HTTP. Server telemetry records timings and decision metadata and omits raw prompts and credentials.

The API accepts one new question per IP every 10 seconds. The cooldown applies to `POST /api/interpret` before dictionary resolution or inference. Confirmation, health checks, and MCP tool calls use their own routes. Caddy overwrites the upstream client-IP header with the address of its direct peer, and the production API accepts that header on the private Compose network. The per-IP cooldown and the separate process-wide LLM budget use in-memory state in the single API worker. Both limits respond with HTTP 429 and `Retry-After`.

## Planned extensions

Supabase Postgres is planned for evidence retrieval, inventory, and compound lookup caching. The current procedures use bundled evidence. The Molecule Explorer is planned to use a model trained offline for aqueous solubility prediction, with its own evaluation and display. User preferences are browser-local in the current phase.

Update this document when request flow, component boundaries, persistence, or deployment changes. See [technologies used](technologies.md) for the implementation stack.

## Catalog management

Open `/management` through the Management link. The bilingual page reads the active backend catalog, shows procedure relationships and sources, exposes runtime dictionaries and the resolution pipeline, and runs English examples through the production deterministic resolver. The additional scenario catalog is visible in the same page.

Surface material definitions live in `backend/homechem/data/materials.json`. Each entry contains a stable ID, English and Hebrew labels, and English aliases. The backend validates and compiles these entries at startup. The consumer UI reads their labels from the API, so adding a recognized material does not require a frontend label change.

To add a material, use the form or edit the draft JSON, then choose Validate & export catalog. Apply the downloaded file with `./scripts/import-materials.sh <materials.json>`, restart the local API, and commit the catalog change for GitHub Actions deployment. Deployment rebuilds the API image with the catalog. Drafts remain in browser memory until export. The management API exposes read, validation, and deterministic inspection endpoints. Application of catalog changes happens through the repository script.

Validation rejects duplicate IDs, conflicting normalized aliases, empty labels, and malformed entries. The validation endpoint and import script also protect materials referenced by reviewed procedures. The importer validates before replacing the file atomically. Recognizing a new material does not introduce a procedure. Procedures are also catalog data. Add an object/material relationship, finishes, supply combination, bilingual confirmation and instructions, chemistry reasoning, and evidence in `procedures.json`. Matching, provider options, approval, hints, and UI content derive from that definition. New algorithm types are implemented in the backend.

Run `./scripts/test-management.sh` for the browser workflow and `./scripts/test.sh tests` for backend checks. The browser script uses separate API and preview ports to coexist with local development.

## Backend-owned application definitions

The frontend handles rendering, navigation, keyboard interaction, network requests, and user preferences. Chemistry content and decisions come from the backend.

| Backend file | Owns |
| --- | --- |
| `data/materials.json` | Surface-material IDs, bilingual labels, English aliases |
| `data/procedures.json` | Object/material relationships, finishes, supplies, bilingual steps and confirmations, reasoning, sources, hints |
| `data/lexicon.json` | Object and device aliases, WordNet category roots, cleaning supplies, supply combinations, exclusions and question vocabulary |
| `data/scenarios.json` | Scenario content, input schemas, calculator parameters and result explanations |
| `data/knowledge.json`, `data/research.json` | Curated evidence, reference measurements, and data-lab interface definitions |
| `data/labels.json`, `data/messages.json`, `data/management_messages.json` | Display labels and interface translations |
| `data/guide.json`, `data/settings.json` | Algorithm guide and default example selection |

The backend validates these definitions at startup. `GET /api/catalog` supplies the presentation content, and `GET /api/hints` selects matching suggestions. Interpretation responses include localized fields and an optional assessment action selected by the backend. Assessment responses include the selected procedure content. React renders these without maintaining a surface-to-procedure map.

`POST /api/scenarios/{id}/evaluate` validates values against the scenario's input definitions and evaluates the configured classification, ratio, or lookup algorithm. Numeric inputs must be finite and meet their declared minimum. The API returns the localized result and the normal request instrumentation applies.

Management exposes procedure JSON editing with backend validation and export. Apply with `./scripts/import-procedures.sh <procedures.json>`, restart the API, and commit the data for deployment. Material and procedure imports replace their files atomically after validation. A backend integration test adds a surface through JSON alone and verifies recognition, confirmation, assessment, and returned instructions.

The public API keeps its existing interpretation and assessment fields and adds presentation content. Surface and supply IDs are strings so catalog additions can flow through the existing API and generic React components.

## MCP data consumption

The Data lab uses the backend as an MCP client. `knowledge_client.py` calls a standalone service selected through `MCP_DATA_URL`. The default local service runs on port 8002; production uses `http://knowledge:8000/mcp` on the private Compose network.

| MCP tool | Data source and result |
| --- | --- |
| `lookup_compound` | Live PubChem PUG REST lookup by English name or CID; identity, formula, molecular weight, source URL |
| `search_evidence` | Keyword search over curated bilingual source summaries about surfactants, water hardness, and emulsions |
| `get_reference` | Cited USGS water-density values at 10, 21, and 26.7 °C, with units and conditions |

Typed responses carry provenance, retrieval time, and a live/curated/fixture marker. The timestamp refers to retrieval through the service. It does not imply that a curated source was fetched or reviewed live. Successful MCP responses are validated and cached for an hour, with a limit of 256 entries. Errors are not cached. Calls have a 25-second overall deadline.

The experiment comparison validates mass and volume in the API, retrieves the selected temperature-specific reference through MCP, and calculates measured density and signed relative difference. The UI renders the result and source. There is no interpolation or statistical-significance claim.

The data service is independently runnable with `scripts/serve-knowledge.sh` and testable with `scripts/knowledge-smoke.sh`. Browser tests launch it in fixture mode, which explicitly marks compound test records and does not contact PubChem. The existing public assessment MCP endpoint remains available separately.

## Client-visible activity traces

`activities.py` maintains request-scoped operation records using context variables. The same operation context creates the OpenTelemetry span and updates the client-visible record, avoiding duplicate instrumentation. Model calls, Azure translation, NLP, policy evaluation, scenario calculations, MCP retrieval, reference comparison, and cache hits are instrumented.

The client assigns an unpredictable capability key to each tracked request through `X-Activity-Key`. The API registers the collection before processing, returns the key through `X-Activity-ID`, and serves live snapshots from `GET /api/activities/{key}`. The timeline polls every 450 ms while the request is pending and fetches a final snapshot on completion. Each record has an ID, optional parent ID, kind, status, start offset, duration, and operation metadata.

Snapshots include the request ID and the corresponding OpenTelemetry trace ID. They omit raw prompts, credentials, and private model reasoning. Completed and running traces expire after ten minutes; storage is bounded to 500 traces and 100 recorded operations per request. Server telemetry export can provide longer retention.

## Shared implementation boundaries

`presentation.py` defines the input and display-field schemas used by both scenarios and research tools. Reference choices are derived from the reference dataset; numeric and text constraints for research forms come from the backend input models. Management uses an explicit OpenAPI response model and the active in-memory catalog snapshot.

The React `InputFields` component renders those definitions. `api.ts` centralizes JSON response parsing, request errors, retry metadata, and attempt logging. `download.ts` owns JSON exports. Client code contains presentation and interaction behavior.

Both catalog-import Bash commands delegate to `catalog_import.py`, which shares reference validation and atomic writes. Existing procedure objects are indexed for assessment and presentation instead of being copied into parallel tuple/content maps. TypeScript checks reject unused local declarations and parameters.
