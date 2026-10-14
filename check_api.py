"""Comprueba la conexión; no ejecuta comandos ni muestra la clave."""
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
        print(f'La API respondió HTTP {error.code}.')
        raise SystemExit(1)
    except (urllib.error.URLError, TimeoutError):
        print('No se pudo conectar a la API dentro del tiempo permitido.')
        raise SystemExit(1)
    usage = result.get('usage', {})
    print('Tokens de entrada:', usage.get('prompt_tokens', 'no informado'))
    print('Tokens en caché:', (usage.get('prompt_tokens_details') or {}).get('cached_tokens', 'no informado'))
    print('Tokens de salida:', usage.get('completion_tokens', 'no informado'))
    return result['choices'][0]['message']

print('Prueba 1: ¿Cuánto es 2 + 2?')
reply = request([{'role': 'user', 'content': '¿Cuánto es 2 + 2? Responde brevemente en español.'}])
print('Respuesta:', reply.get('content'))

print('\nPrueba 2: pedir la herramienta bash, SIN ejecutar el comando.')
tool = {'type': 'function', 'function': {'name': 'bash', 'description': 'Solicita ejecutar un comando de shell, sujeto a permiso del usuario.', 'parameters': {'type': 'object', 'properties': {'command': {'type': 'string'}}, 'required': ['command']}}}
reply = request([{'role': 'user', 'content': 'Usa bash para ejecutar echo prueba.'}], tools=[tool], tool_choice={'type': 'function', 'function': {'name': 'bash'}})
calls = reply.get('tool_calls', [])
print('El modelo pidió bash:', bool(calls) and all(c.get('function', {}).get('name') == 'bash' for c in calls))
print('No se ejecutó ningún comando solicitado por el modelo.')
