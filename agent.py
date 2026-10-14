"""The model call, the bash tool, and the agent loop."""
import json
import os
import signal
import tempfile
import subprocess
import urllib.request
from pathlib import Path

WORK = Path(__file__).resolve().parent / 'practice'
WORK.mkdir(exist_ok=True)
TOOLS = [{'type': 'function', 'function': {
    'name': 'bash',
    'description': 'Run a Bash shell command on the user’s computer after explicit approval. Supports files, directories, pipes, and other shell operations. The working directory is the project practice folder; paths may refer to other folders. Commands have a 60-second timeout, output is truncated, and results are returned with an exit code.',
    'parameters': {'type': 'object', 'properties': {'command': {'type': 'string'}}, 'required': ['command'], 'additionalProperties': False},
}}]

def run_bash(command, timeout=60):
    """Execute only after approval; avoid exporting the API key to commands."""
    if not isinstance(command, str) or not command.strip():
        return {'stdout': '', 'stderr': 'Empty command.', 'exit_code': 2}
    env = {name: value for name, value in os.environ.items()
           if not any(secret in name.upper() for secret in ('KEY', 'TOKEN', 'SECRET', 'PASSWORD'))}
    env.pop('BASH_ENV', None)
    env.pop('ENV', None)
    env.setdefault('PATH', '/usr/bin:/bin')
    # Temporary files keep large command output out of memory.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(['/bin/bash', '--noprofile', '--norc', '-c', command],
            cwd=WORK, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
        timed_out = False
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            code = 124
        def tail(file):
            size = file.seek(0, 2)
            file.seek(max(0, size - 40000))
            text = file.read().decode('utf-8', errors='replace')
            return ('[Earlier output truncated]\n' if size > 40000 or len(text) > 10000 else '') + text[-10000:]
        out, err = tail(stdout), tail(stderr)
        if timed_out:
            err += f'\nCommand timed out after {timeout} seconds.'
        return {'stdout': out, 'stderr': err, 'exit_code': code}


def model_call(messages, config, tls):
    payload = {'model': config['MODEL'], 'messages': messages, 'tools': TOOLS, 'max_tokens': 2048}
    req = urllib.request.Request(config['BASE_URL'].rstrip('/') + '/chat/completions',
        data=json.dumps(payload).encode(),
        headers={'Authorization': 'Bearer ' + config['API_KEY'], 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, context=tls, timeout=60) as response:
        result = json.load(response)
    raw = result['choices'][0]['message']
    message = {'role': 'assistant', 'content': raw.get('content')}
    if raw.get('tool_calls'):
        message['tool_calls'] = raw['tool_calls']
    return message, result.get('usage', {})

def advance(state, config, tls):
    """Call the model again after every tool result; pause for each approval."""
    if state['pending']:
        call = state['pending'][0]
        try:
            command = json.loads(call['function']['arguments'])['command']
            if not isinstance(command, str):
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            command = '[Invalid command arguments]'
        return {'pending': {'id': call['id'], 'command': command}}
    if state['rounds'] >= 20:
        return {'answer': 'Stopped after 20 model calls. Please start a new question.'}

    message, usage = model_call(state['messages'], config, tls)
    state['rounds'] += 1
    state['messages'].append(message)
    if message.get('tool_calls'):
        state['pending'] = list(message['tool_calls'])
        return dict(advance(state, config, tls), usage=usage)
    return {'answer': message.get('content') or 'The model returned no text. Please try again.', 'usage': usage}

def decide(state, call_id, approved):
    if not state['pending'] or state['pending'][0]['id'] != call_id:
        raise ValueError('This command is no longer pending.')
    call = state['pending'][0]
    if not approved:
        result = {'stdout': '', 'stderr': 'The user declined to run this command.', 'exit_code': None}
    elif call['function']['name'] != 'bash':
        result = {'stdout': '', 'stderr': 'Unknown tool.', 'exit_code': 127}
    else:
        try:
            command = json.loads(call['function']['arguments'])['command']
            if not isinstance(command, str):
                raise ValueError()
            result = run_bash(command)
        except (ValueError, KeyError, TypeError):
            result = {'stdout': '', 'stderr': 'Invalid command arguments.', 'exit_code': 2}
    state['pending'].pop(0)
    state['messages'].append({'role': 'tool', 'tool_call_id': call['id'], 'content': json.dumps(result)})
    return result
