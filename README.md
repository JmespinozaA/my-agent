# My Agent

A small local web chat for UCLA AI in Research, Week 2. Built with Python's standard library, an OpenAI-compatible Chat Completions API, and exactly one tool: `bash`. No agent framework or Python packages are required.

The interface is in English. It displays a conversation, token usage for each API call, proposed commands, Approve/Deny buttons, and command output with its exit code.

## Install

Requirements: Git, Python 3.10 or newer, and Bash. macOS and Linux are supported. On Windows, use WSL with a Linux distribution; native Windows Python is not supported because the tool uses `/bin/bash`.

```bash
git clone https://github.com/JmespinozaA/my-agent.git
cd my-agent
cp .env.example .env
```

## Configure

Open `.env` in a text editor and replace only `your_api_key_here` with your own OpenRouter key. Do not paste your key into chat or share a screenshot of it. Keep the free model selected. Its availability and request limits depend on OpenRouter; if requests are unavailable, wait or select another tool-capable free model. Do not switch to a paid model without agreeing to its cost.

Settings: `BASE_URL` is the API address, `API_KEY` is your private credential, and `MODEL` is the model ID. `.env` is ignored by Git; `.env.example` contains placeholders only.

## Run

```bash
python3 app.py
```

Open http://127.0.0.1:8765 in your browser. Press Ctrl+C in the terminal to stop the server. The server listens only on the local computer. The key stays in the Python process; it is used to authenticate API requests and is not included in the web page or model messages.

Messages and approved command results are sent to OpenRouter. Conversations stay in server memory until the server stops. New chat or reloading starts a new conversation but does not erase older server memory; stopping the server clears it. No conversation files are written.

## Bash commands and approval

The bash tool supports ordinary shell commands, folder inspection, absolute paths, pipes, and redirections. Commands start in `practice`, which contains fictional sample files, but can access other folders. This working directory is not a sandbox.

Every command is shown with Approve and Deny buttons before execution. A denial returns a tool result without execution. Approved command output is sent to OpenRouter, including file names or contents read by that command. Review each command and deny requests you do not want to run. Do not approve commands that read `.env` or other credentials. The system prompt instructs the model to avoid secrets, but instructions are not a technical access barrier.

The API key is not explicitly exported to command subprocesses. Bash has a 60-second timeout; on timeout the process group is stopped. Long output is read from temporary files and truncated before it reaches the model.

## Understand the loop

`agent.py` contains the tool and loop. `model_call` sends the whole conversation and the one-tool definition. `advance` appends the assistant response and pauses when a tool call needs approval. `decide` runs an approved permitted command or returns a denial, then appends a tool result with the matching call ID. The application calls `advance` again with that result until the model returns text. A limit of 20 model calls per question prevents indefinite loops. Commands have a 60-second timeout and output is truncated.

`app.py` serves the page and coordinates requests. `system_prompt.md` holds editable model instructions.

## Check it works

Ask `What is the current date on this computer? Use date.` Approve `date`; expect output, exit code 0, and a model response. Start a new chat and deny the same command; expect a denial without execution. Ask `What files are in the practice folder? Use ls.` Expect `notes.txt` and `sample.csv`.

Optional automated tests consume the free API request allowance:

```bash
python3 check_api.py
python3 test_workflow.py
```

See `TEST_RESULTS.md` for observed results and limitations.

## Status

The student tested approved date retrieval and explained the loop. Listing fictional files, multiple tool calls, command errors, denial, and token reporting were tested. At the student’s request the original command allowlist was removed; the bash tool now supports general shell commands with approval. The installation skill is drafted. Prepared for publication. Fresh-clone verification and the class submission pull request are the final delivery steps.

## AI assistance

OpenAI Codex wrote the code with the student, explained the API and agent loop in Spanish, helped choose a free model, and ran tests. The student initially chose practice restrictions, then explicitly requested full shell functionality, tested the chat, and described the approval and result flow.
