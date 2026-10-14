# Verification — October 14, 2026

Tested against `nvidia/nemotron-3.5-lightning:free` through OpenRouter.

- File listing: `ls` returned the fictional `notes.txt` and `sample.csv` files in `practice`.
- Multiple calls: the model called `date`, received its result, then called `ls` and summarized both results. Exit codes were 0.
- Failed command: the deliberately nonexistent `doesnotexist` command returned exit code 127. The model explained the command-not-found error.
- Denial: no command ran; the model received the denial and did not retry. Initial testing found that the model sometimes asked for approval in prose. The system prompt was clarified to request the tool directly, leaving approval to the application. The targeted denial test then passed.
- Each real API call reported input and output token counts. The interface displays cached input when supplied; cache reuse was not demonstrated.
- After the user requested full Bash support, local checks passed for shell pipes, directory paths, output truncation, and the 20-call cap. The command allowlist was removed.
- Timeout handling was tested with a real `sleep 2` process and a shortened 0.05-second timeout.
- The browser interface was previously verified for message ordering, token display, and the denial buttons. The student verified an approved `date` command end to end.

Run `python3 test_workflow.py` to repeat the model tests, or add `--deny-only` for just the denial test. These consume the provider's free request allowance.

- The model workflow tests were repeated after enabling full Bash: listing, multiple calls, command failure, denial, and token reporting all passed.
- `df -h .` returned disk-space information successfully. A `du | sort | tail` pipeline worked against fictional test data. A complete home-directory size scan was not performed.

## Current scope

The user explicitly requested full shell capability to meet the assignment. The original practice allowlist has been removed. Bash now supports arbitrary commands after approval, including directory inspection and pipelines; `practice` is a working directory, not a sandbox. The command's output goes to OpenRouter. Public publication and fresh public-clone installation verification remain pending.
