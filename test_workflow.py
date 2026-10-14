"""Explicit homework tests: only fictional files and permitted commands."""
import json
import sys
from unittest.mock import patch
import agent
from app import config, tls, ROOT

# Local shell checks use only fictional files and short-lived processes.
assert agent.run_bash("printf 'alpha\\nbeta\\n' | tail -n 1")['stdout'].strip() == 'beta'
assert 'notes.txt' in agent.run_bash('ls "' + str(agent.WORK) + '"')['stdout']
assert len(agent.run_bash("printf '%15000s' x")['stdout'].split('\n',1)[-1]) == 10000
assert agent.run_bash('doesnotexist')['exit_code'] == 127
assert agent.run_bash('sleep 2', timeout=0.05)['exit_code'] == 124
assert 'Stopped' in agent.advance({'pending': [], 'rounds': 20}, {}, None)['answer']
print('PASS: shell pipes, directory paths, truncation, real timeout, and round cap.', flush=True)

def scenario(label, question, expected, approve=True):
    state = {'messages': [{'role': 'system', 'content': (ROOT / 'system_prompt.md').read_text()},
                          {'role': 'user', 'content': question}], 'pending': [], 'rounds': 0}
    commands = []
    results = []
    token_calls = 0
    while True:
        response = agent.advance(state, config, tls)
        if 'usage' in response:
            u = response['usage']
            assert isinstance(u.get('prompt_tokens'), int)
            assert isinstance(u.get('completion_tokens'), int)
            token_calls += 1
            print(label, 'tokens:', u['prompt_tokens'], 'input,', u['completion_tokens'], 'output', flush=True)
        if 'pending' not in response:
            print(label, 'answer:', response['answer'], flush=True)
            break
        pending = response['pending']
        command = pending['command']
        # Test authorizes only exactly the intended commands; never arbitrary requests.
        if command not in expected:
            raise AssertionError('Model requested an unexpected command; none executed.')
        commands.append(command)
        results.append(agent.decide(state, pending['id'], approve))
        print(label, 'command:', command, 'exit:', results[-1]['exit_code'], flush=True)
        if len(commands) > 4:
            raise AssertionError('Too many requests in the test.')
    assert commands
    assert token_calls >= 2
    return commands, results

if '--deny-only' not in sys.argv:
    commands, results = scenario('FILES', 'Your current working directory is already the practice folder. Call bash with command exactly ls, without flags or cd. Report the returned file names.', ['ls', 'ls -la', 'ls -l'])
    assert 'notes.txt' in results[0]['stdout'] and 'sample.csv' in results[0]['stdout']
    commands, results = scenario('MULTI', 'The current working directory is already the practice folder. First run exactly date with bash. After receiving its result, run exactly ls without flags in a separate bash call. Then summarize both results. Do not combine commands.', ['date', 'ls'])
    assert commands == ['date', 'ls'] and all(r['exit_code'] == 0 for r in results)
    commands, results = scenario('ERROR', 'Run doesnotexist with bash once to demonstrate a command-not-found error. Explain the result; do not retry.', ['doesnotexist'])
    assert results[0]['exit_code'] == 127
commands, results = scenario('DENY', 'Use bash date to check the current date.', ['date'], approve=False)
assert len(commands) == 1 and results[0]['exit_code'] is None
print('PASS: denial workflow and token usage.' if '--deny-only' in sys.argv else 'PASS: all four model workflow tests, token usage, and full Bash support.', flush=True)
