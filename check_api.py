"""Check the API connection without executing commands or displaying the key."""
import json
import ssl
from pathlib import Path
import urllib.request
import urllib.error

config = {}
system_certs = Path('/etc/ssl/cert.pem')
tls = ssl.create_default_context(cafile=str(system_certs) if system_certs.exists() else None)
for line in Path(__file__).with_name('.env').read_text().splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        name, value = line.split('=', 1)
        config[name.strip()] = value.strip().strip('\"').strip("'")

def request(messages, **options):
    payload = dict(model=config['MODEL'], messages=messages, max_tokens=512, **options)
    req = urllib.request.Request(
        config['BASE_URL'].rstrip('/') + '/chat/completions',
        data=json.dumps(payload).encode(),
        headers={'Authorization': 'Bearer ' + config['API_KEY'], 'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=60, context=tls) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        print(f'The API returned HTTP {error.code}.')
        raise SystemExit(1)
    except (urllib.error.URLError, TimeoutError):
        print('Could not connect to the API within the time limit.')
        raise SystemExit(1)
    usage = result.get('usage', {})
    print('Input tokens:', usage.get('prompt_tokens', 'not reported'))
    print('Cached input tokens:', (usage.get('prompt_tokens_details') or {}).get('cached_tokens', 'not reported'))
    print('Output tokens:', usage.get('completion_tokens', 'not reported'))
    return result['choices'][0]['message']

print('Test 1: What is 2 + 2?')
reply = request([{'role': 'user', 'content': 'What is 2 + 2? Reply briefly in English.'}])
print('Answer:', reply.get('content'))

print('\nTest 2: request the bash tool WITHOUT executing the command.')
tool = {'type': 'function', 'function': {'name': 'bash', 'description': 'Request a shell command, subject to user approval.', 'parameters': {'type': 'object', 'properties': {'command': {'type': 'string'}}, 'required': ['command']}}}
reply = request([{'role': 'user', 'content': 'Use bash to run echo test.'}], tools=[tool], tool_choice={'type': 'function', 'function': {'name': 'bash'}})
calls = reply.get('tool_calls', [])
print('The model requested bash:', bool(calls) and all(c.get('function', {}).get('name') == 'bash' for c in calls))
print('No model-requested commands were executed.')
