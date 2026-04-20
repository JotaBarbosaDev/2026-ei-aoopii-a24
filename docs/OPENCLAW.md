# OpenClaw Runtime Notes

This project keeps the content pipeline as a small Python tool and lets OpenClaw act as the always-on agent runtime and messaging bridge.

Official OpenClaw starting points:

- GitHub: https://github.com/openclaw/openclaw
- Docs: https://docs.openclaw.ai/

## Runtime Role

OpenClaw is responsible for:

- Telegram or other channel connection
- Receiving the user message
- Keeping the agent process available
- Calling tools or shell commands
- Returning the final document link to the user

The Python package in this repo is responsible for:

- Extracting the input
- Generating multi-format content
- Evaluating clarity, engagement, and branding
- Improving weak outputs
- Creating a PDF document
- Uploading the PDF to a demo public folder
- Logging execution history

## Local Demo

Install the package in editable mode:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Run one pipeline execution:

```bash
content-pipeline run --file examples/sample_input.txt
```

Serve generated public documents locally:

```bash
content-pipeline serve --directory data/public --port 8000
```

In another terminal, make returned links use that server:

```bash
PUBLIC_BASE_URL=http://127.0.0.1:8000 content-pipeline run --file examples/sample_input.txt
```

For a real public link, replace `PUBLIC_BASE_URL` with a public file host, Google Drive flow, or a tunnel URL.

## LLM Provider

The default provider is `demo`, which is deterministic and does not need API keys. For a real LLM call, set one of these before running the pipeline:

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_MODEL=...
```

```bash
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=...
```

For any OpenAI-compatible chat-completions endpoint:

```bash
LLM_PROVIDER=compatible
LLM_BASE_URL=...
LLM_API_KEY=...
LLM_MODEL=...
```

## Suggested OpenClaw Agent Prompt

Use this as the instruction for the OpenClaw agent:

```text
You are Agent: Content Pipeline.

Goal:
Transform one user input into a branded content package and return a document link.

Behavior:
1. Treat each Telegram message as one content input.
2. Run the repository tool:
   PYTHONPATH=src python3 -m content_pipeline run --input "<USER_MESSAGE>" --json
3. Read the JSON result.
4. If the score is below 8.5, report that the agent improved the content automatically.
5. Return only:
   - document link
   - quality score
   - improvement rounds

Constraints:
- Do not chat generally unless the user asks about the pipeline.
- Do not generate final content directly in the message.
- Always use the content pipeline tool.
- Keep the response short and practical.
```

## Tool Mapping

| Assignment tool | Python implementation |
| --- | --- |
| `generate_content(input)` | `content_pipeline.tools.generate_content` |
| `evaluate_content(content)` | `content_pipeline.tools.evaluate_content` |
| `improve_content(content)` | `content_pipeline.tools.improve_content` |
| `create_document(content)` | `content_pipeline.tools.create_document` |
| `upload_document(file)` | `content_pipeline.tools.upload_document` |

## Persistence

Execution memory is stored as JSONL:

```text
data/memory/executions.jsonl
```

Inspect recent runs:

```bash
content-pipeline history --limit 5
```
