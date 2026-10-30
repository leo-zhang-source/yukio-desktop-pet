"""Own Unix socket only; rejects any protocol action beyond the test answer."""
import argparse
import json
from pathlib import Path
import socket
import struct

p = argparse.ArgumentParser()
p.add_argument('--root', type=Path, required=True)
p.add_argument('--canonical', action='store_true')
args = p.parse_args()
root = args.root
assert root.is_dir() and not (root / 'ipc.sock').exists()
question = '人工协议测试：请选择'
answer = '中文测试答案\n第二行'
server = socket.socket(socket.AF_UNIX)
server.bind(str(root / 'ipc.sock'))
server.listen(1)
server.settimeout(10)
(root / 'ready').write_text('ready', encoding='utf-8')
connection, _ = server.accept()
connection.settimeout(5)
methods = []

def read(size):
    data = b''
    while len(data) < size:
        chunk = connection.recv(size - len(data))
        if not chunk:
            raise EOFError()
        data += chunk
    return data

def send(obj):
    data = json.dumps(obj).encode()
    connection.sendall(struct.pack('<I', len(data)) + data)

try:
    while True:
        try:
            length = struct.unpack('<I', read(4))[0]
            assert length <= 1024 * 1024
            message = json.loads(read(length))
        except EOFError:
            break
        method = message.get('method')
        methods.append(method)
        if method == 'thread-stream-following-changed':
            assert message['params']['conversationId'] == 'fixture-session'
            if not message['params']['following']:
                break
            turn = dict(status='inProgress', turnId='turn', items=[dict(
                type='agentMessage', id='fixture-call', questions=[dict(title=question, options=['A', 'B'])])])
            state = dict(id='fixture-session', cwd='/tmp', turns=[turn], requests=[])
            if args.canonical:
                state['turnHistory'] = dict(kind='canonical', history=dict(
                    entitiesByKey={'turn': turn}, islands=[dict(entries=[dict(key='index', value='turn')])]))
                state['turns'] = []
            send(dict(type='broadcast', method='thread-stream-state-changed', sourceClientId='owner', version=11,
                      params=dict(conversationId='fixture-session', change=dict(type='snapshot', conversationState=state))))
            continue
        if method == 'initialize':
            result = {'clientId': 'fixture-client'}
        elif method == 'thread-owner-discovery':
            result = {'ownerClientId': 'owner'}
        elif method == 'thread-follower-steer-turn':
            params = message['params']
            assert params['conversationId'] == 'fixture-session'
            text = params['input'][0]['text']
            reply = json.loads(text.split('>\n', 1)[1].rsplit('\n<', 1)[0])[0]
            assert json.loads(reply['questionItemId']) == ['request_user_input_async', 'fixture-call', 0]
            assert reply['question'] == question and reply['answer'] == answer
            (root / 'receipt.json').write_text(json.dumps(dict(
                accepted=True, answer=reply['answer'], session=params['conversationId'],
                call='fixture-call', methods=methods), ensure_ascii=False), encoding='utf-8')
            result = {'result': {'turnId': 'turn'}}
        else:
            raise AssertionError('Unexpected protocol method: ' + str(method))
        send(dict(type='response', requestId=message['requestId'], resultType='success',
                  handledByClientId='owner', result=result))
finally:
    connection.close()
    server.close()
