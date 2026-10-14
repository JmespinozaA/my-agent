"""Local web chat with conversation history and command approval."""
import json
import secrets
from agent import advance, decide
from pathlib import Path
import ssl
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent
config = {}
for line in (ROOT / '.env').read_text().splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        name, value = line.split('=', 1)
        config[name.strip()] = value.strip().strip('\"').strip("'")
certs = Path('/etc/ssl/cert.pem')
tls = ssl.create_default_context(cafile=str(certs) if certs.exists() else None)

sessions = {}

PAGE = '''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Chat</title>
<style>
*{box-sizing:border-box}body{font:16px system-ui;margin:0;background:#fff;color:#202124}main{height:100dvh;max-width:850px;margin:auto;display:flex;flex-direction:column;padding:0 24px}header{display:flex;align-items:center;justify-content:space-between;padding:18px 0;border-bottom:1px solid #eee}h1{font-size:20px;margin:0}button{font:inherit;cursor:pointer;border:0;border-radius:12px;padding:10px 16px}#new{background:#f2f2f2}#messages{flex:1;overflow-y:auto;padding:28px 0;display:flex;flex-direction:column;gap:24px}.message{max-width:90%;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.65}.user{align-self:flex-end;background:#f1f1f1;border-radius:22px;padding:12px 20px}.assistant{align-self:flex-start;padding:4px 0}.usage{font-size:12px;color:#777;margin-top:10px;white-space:normal}.empty{margin:auto;text-align:center;color:#777;font-size:22px}form{display:flex;align-items:flex-end;gap:12px;border:1px solid #ddd;background:#fafafa;border-radius:24px;padding:12px;margin:16px 0 10px}textarea{flex:1;border:0;outline:0;background:transparent;font:inherit;resize:none;padding:8px;max-height:180px}#send{background:#202124;color:white}button:disabled{opacity:.4;cursor:default}.footnote{font-size:12px;text-align:center;color:#777;margin:0 0 16px}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
</style><main><header><h1>Chat</h1><button id="new" type="button">New chat</button></header>
<section id="messages" role="log" aria-label="Conversation" aria-live="polite"><div class="empty" id="empty">How can I help?</div></section>
<form id="form"><label class="sr-only" for="question">Message</label><textarea id="question" rows="2" required placeholder="Message…" maxlength="4000"></textarea><button id="send">Send</button></form><p class="footnote">AI can make mistakes. Check important information.</p></main>
<script>
const form=document.getElementById('form'),button=document.getElementById('send'),messages=document.getElementById('messages'),input=document.getElementById('question'),newChat=document.getElementById('new');
let chatId=null;
function addMessage(role,text){document.getElementById('empty')?.remove();const el=document.createElement('div');el.className='message '+role;el.textContent=text;messages.append(el);messages.scrollTop=messages.scrollHeight;return el;}
function busy(value){button.disabled=value;input.disabled=value;newChat.disabled=value;}
function usage(u){if(!u)return;const el=addMessage('assistant',`Tokens: input ${u.prompt_tokens??'not reported'} · cached input ${u.prompt_tokens_details?.cached_tokens??'not reported'} · output ${u.completion_tokens??'not reported'}`);el.className='usage';}
async function send(path,body){const waiting=addMessage('assistant','Thinking…');try{const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await response.json();waiting.remove();if(data.chat_id)chatId=data.chat_id;usage(data.usage);if(data.tool_result){const r=data.tool_result;addMessage('assistant',`Command result\n${r.stdout}${r.stderr}\nExit code: ${r.exit_code??'not executed'}`);}if(data.error){addMessage('assistant',data.error);busy(false);return;}if(data.pending){const box=addMessage('assistant','Command requested: '+data.pending.command);const note=document.createElement('p');note.textContent='Runs only if you approve. Output will be sent to OpenRouter. This command can access or change files on your computer. Review it before approving.';box.append(note);for(const [label,approved] of [['Approve',true],['Deny',false]]){const action=document.createElement('button');action.textContent=label;action.style.marginRight='8px';box.append(action);action.addEventListener('click',async()=>{box.querySelectorAll('button').forEach(b=>b.disabled=true);await send('/decision',{chat_id:chatId,call_id:data.pending.id,approved});});}messages.scrollTop=messages.scrollHeight;return;}addMessage('assistant',data.answer);busy(false);input.focus();}catch{waiting.textContent='Could not connect. Start a new chat to retry.';busy(false);}messages.scrollTop=messages.scrollHeight;}
newChat.addEventListener('click',()=>{chatId=null;messages.replaceChildren();const empty=document.createElement('div');empty.id='empty';empty.className='empty';empty.textContent='How can I help?';messages.append(empty);input.focus();});
form.addEventListener('submit',async e=>{e.preventDefault();const question=input.value.trim();if(!question)return;busy(true);addMessage('user',question);input.value='';await send('/ask',{question,chat_id:chatId});});
</script></html>'''

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Do not log questions or credentials.

    def send(self, status, body, content_type='application/json; charset=utf-8'):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body.encode())

    def do_GET(self):
        if self.path == '/':
            self.send(200, PAGE, 'text/html; charset=utf-8')
        else:
            self.send(404, json.dumps({'error': 'Page not found.'}))

    def do_POST(self):
        if self.path not in ('/ask', '/decision'):
            return self.send(404, '{}')
        if self.headers.get('Origin') not in (None, 'http://127.0.0.1:8765'):
            return self.send(403, '{}')
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 20000:
                raise ValueError()
            body = json.loads(self.rfile.read(length))
            chat_id = body.get('chat_id')
            if chat_id is None and self.path == '/ask':
                if len(sessions) >= 100:
                    raise ValueError('Restart the server to clear old chats.')
                chat_id = secrets.token_urlsafe(24)
                sessions[chat_id] = {'messages': [{'role': 'system', 'content': (ROOT / 'system_prompt.md').read_text()}], 'pending': [], 'rounds': 0}
            if not isinstance(chat_id, str) or chat_id not in sessions:
                raise ValueError('Please start a new chat.')
            state = sessions[chat_id]
            tool_result = None
            if self.path == '/ask':
                question = body['question']
                if not isinstance(question, str) or not question.strip() or len(question) > 4000:
                    raise ValueError('Please enter a short message.')
                if state['pending']:
                    raise ValueError('Approve or deny the pending command first.')
                state['messages'].append({'role': 'user', 'content': question})
                state['rounds'] = 0
            else:
                if type(body.get('approved')) is not bool:
                    raise ValueError('Choose Approve or Deny.')
                tool_result = decide(state, body['call_id'], body['approved'])
            result = advance(state, config, tls)
            result['chat_id'] = chat_id
            if tool_result is not None:
                result['tool_result'] = tool_result
            self.send(200, json.dumps(result))
        except urllib.error.HTTPError as error:
            self.send(502, json.dumps({'error': f'OpenRouter returned error {error.code}. Please start a new chat or retry later.'}))
        except (urllib.error.URLError, TimeoutError):
            self.send(502, json.dumps({'error': 'Could not connect to OpenRouter. Please start a new chat.'}))
        except (ValueError, KeyError, TypeError, IndexError):
            self.send(400, json.dumps({'error': 'Could not process this request. Please start a new chat.'}))

if __name__ == '__main__':
    print('Open http://127.0.0.1:8765 — press Ctrl+C to stop.', flush=True)
    HTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
