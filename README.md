# HomeChem

HomeChem is an English/Hebrew household chemistry notebook with a React PWA and a FastAPI backend. The backend owns the catalogs, chemistry content, translations, matching rules, and calculations. React renders the content and actions returned by the API.

Cleaning questions follow an English NLP resolver, user confirmation, and deterministic assessment through a direct Python call. Reviewed procedures cover intact glass tabletops, smooth glass screens, and everyday cleaning of glazed ceramic sinks and tile floors. Mechanical sink unclogging is also supported after explicit condition checks. Each procedure includes instructions, chemistry reasoning, and sources.

Eight additional workspaces provide supported starter scenarios for stain removal, food science, limescale and corrosion, material care, water chemistry, home experiments, ingredient explanations, and chemical disposal. Water-hardness classification, experiment comparisons, and ingredient lookups run on the backend. These workspaces use explicit scenario selection; the free-text interpreter handles cleaning questions.

## Local development

Requirements are Python 3.12 through uv, Node 24, npm, and Ollama. Use an installed Ollama model or pull the model listed in `.env.example`.

```bash
scripts/bootstrap.sh
cp .env.example .env
scripts/dev.sh
```

Open [the local app](http://127.0.0.1:5173) and select **Try an example**. Hebrew questions are translated by the configured model before they enter the same English NLP resolver as English questions. Set `LLM_PROVIDER=fixture` in `.env` to use a stub for test translations and unresolved surface requests. Model names are configurable. To use dedicated machine translation, set `TRANSLATION_PROVIDER=azure`, `AZURE_TRANSLATOR_KEY`, and, for a regional resource, `AZURE_TRANSLATOR_REGION` in your local `.env` or VPS `runtime.env`. Azure only receives questions that need Hebrew translation. The default uses the configured LLM. The local smoke test was exercised with `qwen2.5:7b-instruct-q4_K_M`.

The development script starts the API on port 8000, the MCP data service on port 8002, and Vite on port 5173. Set `MCP_DATA_URL` to use another service implementing the same chemistry-data tools.

The PWA service worker runs in production builds and caches the app shell, static assets, and the most recently fetched backend presentation catalog for offline viewing. Interpretation, assessment, and scenario calculations require a connection. The locale preference is stored in versioned browser localStorage.

## Development commands

| Script | Purpose |
| --- | --- |
| `scripts/bootstrap.sh` | Install locked dependencies (including spaCy model) and fetch WordNet |
| `scripts/download-nlp-data.sh` | Fetch the WordNet corpus for the English resolver |
| `scripts/dev.sh` | Run Vite, the API, and the MCP data service |
| `scripts/serve-knowledge.sh [port]` | Run the standalone MCP chemistry-data service |
| `scripts/knowledge-smoke.sh [mcp-url]` | Verify compound, evidence, and reference lookups through MCP |
| `scripts/generate-client.sh` | Regenerate frontend types from FastAPI’s OpenAPI schema |
| `scripts/check.sh` | Check schema drift and TypeScript |
| `scripts/test.sh` | Run Python tests; optional pytest arguments are forwarded |
| `scripts/install-browser.sh` | Install Chromium for browser tests |
| `scripts/browser-test.sh` | Build the PWA and run all browser tests against an isolated API with the fixture provider |
| `scripts/test-sanity.sh` | Run the focused E2E sanity journey: review, approval, MCP trace, debug ZIP, and persisted Hebrew/RTL |
| `scripts/test-management.sh` | Check types, build, and test the management workflow |
| `scripts/test-use-cases.sh` | Check types, build, and test the scenario workspaces and calculators |
| `scripts/import-materials.sh <file>` | Validate and atomically apply a material catalog export |
| `scripts/import-procedures.sh <file>` | Validate and atomically apply a procedure catalog export |
| `scripts/provider-smoke.sh [base-url]` | Check English matching, live Hebrew translation, and the live surface fallback |
| `scripts/mcp-smoke.sh [mcp-url]` | Discover and call the policy from a standalone MCP client |
| `scripts/build.sh` | Build the React PWA. With a registry prefix and SHA, build both deployment images |

Browser tests launch their own API, fixture MCP data service, and preview server. The full suite uses API port 8011 and preview port 4173; management tests use 8012 and 4184; scenario tests use 8013 and 4183. To use an installed Chromium-compatible browser, set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` to its executable.

For a quick sanity E2E, run `./scripts/test-sanity.sh`. It checks types, builds the PWA, starts isolated API/MCP/preview services on ports 8014/8114/4186, and runs a browser journey through question review, policy approval, chemistry reasoning, correlated MCP activity, debug ZIP download, and persisted Hebrew/RTL settings. Additional sanity cases cover lowercase “how do I clean my apple watch” (external lookup without a guessed material) and “how do I unclog my sink?” (mechanical procedure after all required conditions are confirmed). External providers use fixtures, so no API credentials or running Ollama instance are needed. Failures retain Playwright traces and screenshots under `web/test-results/`. This sanity test also runs as part of the full browser suite in CI.

## Architecture

```mermaid
flowchart LR
    Web["React PWA and management UI"] -->|"Catalogs, hints, interpretation and results"| API["FastAPI"]
    Data["Validated backend JSON catalogs"] --> API
    API --> NLP["English NLP and deterministic matching"]
    API -->|"Hebrew translation"| Translation["Azure Translator or configured LLM"]
    API -->|"Unresolved surface wording"| Model["Ollama locally / DeepSeek remotely"]
    API -->|"Direct Python call"| Policy["Deterministic policy"]
    Data --> Policy
    Client["External MCP client"] --> MCP["Optional MCP tool endpoint"]
    MCP --> Policy
    API -->|"MCP client"| Knowledge["Chemistry data service"]
    Knowledge --> PubChem["PubChem API"]
    Knowledge --> References["Curated evidence and reference measurements"]
    API --> Calculations["Deterministic scenario evaluation"]
    API --> Telemetry["Structured logs, traces and metrics"]
    Policy --> Telemetry
```

- `web/src` contains presentation components, navigation, forms, keyboard interaction, language preference handling, and API types generated from OpenAPI. It renders backend-provided fields, instructions, and results.
- `backend/homechem` contains the FastAPI routes, NLP resolver, deterministic policy, scenario evaluators, MCP transport, provider adapters, and telemetry.
- `backend/homechem/data` holds the application definitions. The backend validates them at startup and derives matching rules, procedure eligibility, bilingual content, and hints from these definitions.
- `infra` contains the Dockerfiles, Caddy configuration, and Compose stack. Caddy serves the React assets and proxies the API and MCP endpoint over HTTPS.

| Backend catalog | Contents |
| --- | --- |
| `materials.json` | Specific material IDs, labels, aliases, explicit parent classes, and external IDs |
| `entities.json` | spaCy model, WordNet physical-object roots, generic heads |
| `procedures.json` | Task/object/material relationships, finishes, supplies, required checks, exclusions, bilingual steps, reasoning, sources, and hints |
| `lexicon.json` | Object/device aliases, WordNet category roots, cleaning vocabulary, supply combinations, and exclusions |
| `scenarios.json` | Scenario content, input definitions, calculation parameters, and result explanations |
| `knowledge.json`, `research.json` | Cited evidence, reference measurements, and data-lab presentation definitions |
| `labels.json`, `messages.json`, `management_messages.json` | Display labels and interface translations |
| `guide.json`, `settings.json` | Algorithm guide and default example selection |

### API flow

1. `GET /api/catalog` supplies the content for the notebook, scenarios, and algorithm guide. `GET /api/hints` filters question suggestions on the server.
2. `POST /api/interpret` translates Hebrew when needed, then runs the shared English resolver. It also searches for related evidence through MCP before any model fallback. Its response includes recognized details, resolution status, retrieved evidence status and sources, localized confirmation fields, and an assessment action when the backend finds a supported match.
3. After confirmation, `POST /api/assess` calls the instrumented Python assessment function directly. The response includes the decision, selected procedure content, sources, policy version, and a supplementary MCP evidence result.
4. `POST /api/scenarios/{id}/evaluate` validates measurements or selections against the scenario definition and returns a localized result. Classification thresholds, ratios, and ingredient lookups run on the server. Scenario exploration also calls `POST /api/scenarios/{id}/evidence`, including scenarios without calculators.

English normalization uses spaCy’s locked small English model for noun phrases, lemmas, modifiers, and grammatical targets, plus NLTK stemming and WordNet physical-object classes. Local aliases provide the application overlay rather than the complete object vocabulary. Specific materials retain their identity: porcelain is a distinct entity with a ceramic parent. Reviewed surface matching checks explicit ancestry, finish, and supply restrictions. The LLM handles translation when configured and can suggest a surface for unresolved wording. Procedure approval comes from the deterministic policy.

The existing `/mcp` endpoint also exposes the assessment function to external clients. The web app uses the direct API-to-Python path. The backend also consumes chemistry data through a separate MCP data service.

### MCP data lab and activity traces

Select **Data lab** to use five tools:

- **Object material comparison** queries the free Wikidata and DBpedia APIs in parallel, displaying candidate entities, explicit material claims, missing data, and timing/cache information. No API key is needed.
- **Chemical terminology** searches ChEBI through the official EMBL-EBI OLS MCP service and returns candidate labels, definitions, identifiers, and source links.
- **Compound lookup** resolves an English compound name or CID through PubChem and returns identity, formula, molecular weight, and provenance.
- **Chemistry evidence** searches curated bilingual summaries about surfactants, water hardness, and emulsions, with links to their sources.
- **Experiment comparison** computes water density from measured mass and volume and compares it with a USGS reference at a selected temperature. The initial reference temperatures are 10, 21, and 26.7 °C.

The API also connects directly to the official OLS MCP endpoint (`OLS_MCP_URL`, default `https://www.ebi.ac.uk/ols4/api/mcp`). Previously unknown substance modifiers can trigger a bounded five-second ChEBI lookup during interpretation. These results are candidates and never automatically set a substrate or authorize a procedure. The trace records searches and candidate IDs; the API and console summary retain the entity identities and candidates. English terms are sent to OLS, not the entire question. Run `./scripts/terminology-smoke.sh` for a live read-only check.

The standalone data service publishes `lookup_compound`, `search_evidence`, and `get_reference`. The API validates MCP responses and caches successful results for one hour, up to 256 entries. PubChem lookup is live; evidence summaries and reference measurements are bundled, cited records. A retrieval timestamp records when the data service returned the record. Results can be exported as JSON for review.

Open **Activity trace** to watch recorded server operations while a request runs. The timeline shows model/provider metadata and token usage when available, NLP, policy evaluation, calculations, MCP calls, cache hits, failures, and duration. Expand a step to inspect its metadata and use the request and trace IDs to find the server logs.

The browser polls `GET /api/activities/{key}` using an unpredictable request capability key. Traces expire after ten minutes and the API retains at most 500 traces in memory. Client-visible debug sections include normalized input tokens, unmatched terms, and MCP search queries. Server logs and exported spans contain reason codes, counts, and operation metadata. Model prompts, credentials, and private model reasoning are excluded. The existing OpenTelemetry export remains available for persistent observability.

The shared evidence stage also runs for the management resolver inspector. It reports `matched`, `no_matches`, or `unavailable`, with a four-second retrieval budget. Repeated lookups may show an MCP-data cache hit. Retrieved context supplements the catalog and does not independently approve procedures.

### Managing materials and procedures

Open **Management** at `/management` to inspect the active materials, dictionaries, procedure relationships, sources, scenario definitions, and resolution pipeline. The English resolver inspector runs the production matching logic and displays normalized tokens and extracted details.

1. Add a material with bilingual labels and English aliases, or edit an existing material in the draft JSON.
2. Validate and export the material catalog, then run `scripts/import-materials.sh <materials.json>`.
3. Edit the procedure definitions to specify the object, material, finishes, supplies, bilingual instructions, reasoning, and evidence. Validate and export, then run `scripts/import-procedures.sh <procedures.json>`.
4. Restart the API to load the catalogs. Commit the catalog files to include them in the GitHub Actions deployment.

Drafts remain in the page until exported. The import scripts validate before replacing files atomically. Materials referenced by procedures must remain in the catalog. Adding a procedure that uses existing algorithms requires catalog changes. New matching or calculation algorithms are implemented in the backend.

See the [terms and processes inventory](docs/terms-and-processes-inventory.md) for definitions, field meanings, algorithm ownership, and extension steps. See [architecture](docs/architecture.md) for more detail, [technologies used](docs/technologies.md) for the stack, [terminology](docs/terminology.md) for normalization, and the [experiments](docs/experiments.md) and [home solutions](docs/home-solutions.md) catalogs for supported activities.

### Instrumentation and rate limits

Find a request by its ID in the structured API logs. Use the corresponding trace ID to follow the provider call or the policy assessment span. Local development exports spans to the console. Set `OTEL_EXPORTER_OTLP_ENDPOINT` and, if applicable, `OTEL_EXPORTER_OTLP_HEADERS` for production OTLP/HTTP traces and metrics. Model traces capture the provider, model, prompt version, and token counts where returned. Application logs omit prompts and credentials. Question submissions have a 10-second cooldown per IP. The guest inference budget separately defaults to 12 model requests per minute per API process and is configurable through `LLM_REQUESTS_PER_MINUTE`. Local test runs can set `QUESTION_COOLDOWN_SECONDS=0`. The production IP check assumes Caddy receives traffic directly and the API stays on the private Compose network.

## Production deployment

GitHub Actions runs checks on pull requests. On a successful push to `main`, it builds both images on a hosted runner, publishes them to GHCR, and deploys both immutable digests to the VPS. Compose runs the web, API, and private MCP data services; the data service reuses the API image. The deployed revision is recorded after the HTTPS smoke check verifies the PWA, expected API release, and direct policy assessment path. If the smoke check fails, deployment attempts to restore the previous pair. Use **Deploy → Run workflow** with a previously deployed commit SHA for manual rollback.

Once the repository exists:

1. Provision the Linux VPS with Docker Compose v2, Bash, curl, and jq. Create a deploy user with Docker access and a writable deployment directory, typically `/opt/homechem`.
2. Point the app domain at the VPS and allow inbound HTTPS, HTTP, and SSH as appropriate. Set `PUBLIC_HOST=your.domain` in the deployment directory’s `.env`.
3. Create `runtime.env` in that directory with `DEEPSEEK_API_KEY` and optional model, budget, and OTLP settings. Authenticate Docker on the VPS to GHCR if the packages are private.
4. In the GitHub `production` environment, configure `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, and `DEPLOY_KNOWN_HOSTS` as secrets. Verify the VPS host key independently before setting known hosts. Set `DEPLOY_DIR` if it differs from `/opt/homechem`, or `DEPLOY_PLATFORM` if the server uses a platform besides `linux/amd64`.
5. After the first deployment, run `scripts/provider-smoke.sh https://your.domain` to exercise DeepSeek and `scripts/mcp-smoke.sh https://your.domain/mcp` to exercise the public, read-only tool.

The backend catalogs and evidence are bundled in the API image. Supabase-backed retrieval and the Molecule Explorer remain planned extensions.

### Resolution diagnostics

Interpretation responses and console summaries include normalized tokens, noun lemmas, per-category matches, unmatched terms, object/material linking, candidate surface, model-fallback eligibility, and reason codes. Final reason codes also record a model returning no catalog match and MCP evidence returning no matches or being unavailable.

Expand an activity step to inspect these diagnostics. The evidence step reports the query, search method, documents searched, source IDs, match count, timeout budget, and any failure type. Model steps report the validated surface result, allowed catalog choices, provider/model, prompt version, and token usage when supplied. Console attempts include `traceId` and a direct `activityUrl` for correlation.

### Download a debug bundle

The lower-right button in **Activity trace** downloads a ZIP for the selected completed attempt, even when the timeline is collapsed. It contains `trace.json`, `requests.json` (API input/output and outbound HTTP metadata), `logs.jsonl` (correlated structured application events), and `manifest.json` (release, IDs, scope, exclusions, and capture limits). Failed attempts can also be exported. Original question text is included; authentication headers, raw model prompts/provider bodies, and remote process logs are excluded. Payloads over 32 KiB are explicitly omitted. The export uses the same private capability and ten-minute expiry as the trace.

### Compare free object/material sources

When a grammatical cleaning target has no stated material, the backend extracts an object/product query and any explicitly attached component. For example, “the screen of my Apple Watch” searches for **Apple Watch** with **screen** retained separately. Wikidata (`P186`, with `P518` component qualifiers) and DBpedia (`material` properties) run concurrently, each with a six-second budget and its own bounded one-hour cache. Results remain separate by provider; entity ambiguity, unspecified components, missing material data, and unavailable services are explicit. Product-level claims do not establish an exposed finish or authorize a cleaning procedure.

Use **Data lab → Object material comparison**, the management resolver, or `./scripts/object-materials-smoke.sh 'Apple Watch' pencil` to compare sources. These are API integrations; OLS and the existing chemistry data service remain MCP integrations. See [source evaluation](docs/object-material-sources.md) for observed coverage.

### Sink unclogging

Ask “How do I unclog my sink?” (or “איך פותחים סתימה בכיור?”). The English resolver selects the distinct `unclog` intent and the catalog's mechanical sink-drain procedure; it does not infer a basin or pipe material. Confirm chemical-free history, a problem isolated to intact plumbing at one sink, and the required equipment/power isolation. All three checks are required by the server before instructions are returned. Chemical or plumbing-risk mentions block this offer. The procedure explains pressure-driven clearance and why acid–bicarbonate fizzing does not establish that a blockage dissolved. Definitions, conditions, instructions, evidence, and localized text remain in backend catalogs.
