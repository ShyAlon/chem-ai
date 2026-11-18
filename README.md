# HomeChem

HomeChem is a bilingual household chemistry notebook. This first slice interprets a cleaning question, asks the user to confirm the surface and materials, and runs a deterministic policy through MCP. The notebook shows the reviewed procedure, its source, and the policy version. The first case is standard-glass Apple Studio Display cleaning with water and a microfiber cloth.

## Local development

Requirements are Python 3.12 through uv, Node 24, npm, and Ollama. Use an installed Ollama model or pull the model listed in `.env.example`.

```bash
scripts/bootstrap.sh
cp .env.example .env
scripts/dev.sh
```

Open http://127.0.0.1:5173 and select **Try an example**. Set `LLM_PROVIDER=fixture` in `.env` to run the two built-in examples without Ollama. Model names are configurable. The local smoke test was exercised with `qwen2.5:7b-instruct-q4_K_M`.

The PWA service worker runs in production builds and caches the app shell. Assessment requests require a connection. The locale setting is stored in the browser under a versioned key.

## Development commands

| Script | Purpose |
| --- | --- |
| `scripts/bootstrap.sh` | Install dependencies from the lockfiles |
| `scripts/dev.sh` | Run Vite and the API |
| `scripts/generate-client.sh` | Regenerate frontend types from FastAPI’s OpenAPI schema |
| `scripts/check.sh` | Check schema drift and TypeScript |
| `scripts/test.sh` | Run Python tests |
| `scripts/install-browser.sh` | Install Chromium for browser tests |
| `scripts/browser-test.sh` | Build the PWA and test it with the fixture provider |
| `scripts/provider-smoke.sh [base-url]` | Check English and Hebrew extraction against a live provider |
| `scripts/mcp-smoke.sh [mcp-url]` | Discover and call the policy from a standalone MCP client |
| `scripts/build.sh` | Build the React PWA. With a registry prefix and SHA, build both deployment images |

Stop the dev servers before running browser tests, which launch their own servers on ports 8000 and 4173.

## Architecture

- `web/src` contains the notebook screen, shared components and tokens, English and Hebrew catalogs, and the typed API client. The UI renders only reviewed procedure text for an approved policy decision.
- `backend/homechem` contains the FastAPI routes, MCP transport, policy, LLM adapters, and telemetry. The LLM classifies inputs. Python independently evaluates the confirmed values and provides the rule and source.
- `infra` contains the Dockerfiles, Caddy configuration, and Compose stack. Caddy serves the React assets and proxies the API and MCP endpoint over HTTPS.

Find a request by its ID in the structured API logs. Use the corresponding trace ID to follow the provider call or the nested MCP and policy spans. Local development exports spans to the console. Set `OTEL_EXPORTER_OTLP_ENDPOINT` and, if applicable, `OTEL_EXPORTER_OTLP_HEADERS` for production OTLP/HTTP traces and metrics. Model traces capture the provider, model, prompt version, and token counts where returned. Application logs omit prompts and credentials. The guest inference budget defaults to 12 requests per minute per API process and is configurable through `LLM_REQUESTS_PER_MINUTE`.

## Production deployment

GitHub Actions runs checks on pull requests. On a successful push to `main`, it builds both images on a hosted runner, publishes them to GHCR, and deploys both immutable digests to the VPS. The deployed revision is recorded after the HTTPS smoke check verifies the PWA, expected API release, and policy path through MCP. If the smoke check fails, deployment attempts to restore the previous pair. Use **Deploy → Run workflow** with a previously deployed commit SHA for manual rollback.

Once the repository exists:

1. Provision the Linux VPS with Docker Compose v2, Bash, curl, and jq. Create a deploy user with Docker access and a writable deployment directory, typically `/opt/homechem`.
2. Point the app domain at the VPS and allow inbound HTTPS, HTTP, and SSH as appropriate. Set `PUBLIC_HOST=your.domain` in the deployment directory’s `.env`.
3. Create `runtime.env` in that directory with `DEEPSEEK_API_KEY` and optional model, budget, and OTLP settings. Authenticate Docker on the VPS to GHCR if the packages are private.
4. In the GitHub `production` environment, configure `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, and `DEPLOY_KNOWN_HOSTS` as secrets. Verify the VPS host key independently before setting known hosts. Set `DEPLOY_DIR` if it differs from `/opt/homechem`, or `DEPLOY_PLATFORM` if the server uses a platform besides `linux/amd64`.
5. After the first deployment, run `scripts/provider-smoke.sh https://your.domain` to exercise DeepSeek and `scripts/mcp-smoke.sh https://your.domain/mcp` to exercise the public, read-only tool.

Supabase-backed retrieval, additional Fix-It cases, and the Molecule Explorer are subsequent slices. This first source and policy are bundled with the application.
