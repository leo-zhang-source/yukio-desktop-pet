"""Own Unix socket only; rejects any protocol action beyond the test answer."""
import argparse
import json
from pathlib import Path
import socket
import struct

p = argparse.ArgumentParser()
p.add_argument('--root', type=Path, required=True)
p.add_argument('--canonical', action='store_true')
p.add_argument('--completed', action='store_true')
p.add_argument('--index', type=int, default=0)
p.add_argument('--patch-first', action='store_true')
p.add_argument('--answered', action='store_true')
p.add_argument('--tail-complete', action='store_true')
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
loads = 0

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
        if method in ('thread-stream-following-changed','thread-follower-load-complete-history'):
            assert message['params']['conversationId'] == 'fixture-session'
            if method=='thread-stream-following-changed' and not message['params']['following']:
                break
            turn = dict(status='completed' if args.completed else 'inProgress', turnId='turn', items=[dict(
                type='agentMessage', id='fixture-call', questions=([dict(title='Earlier question',options=['First','Second'])] if args.index else [])+[dict(title=question, options=['A', 'B'])])])
            state = dict(id='fixture-session', cwd='/tmp', turns=[turn], requests=[])
            if method=='thread-follower-load-complete-history':
                assert not args.tail_complete, 'A complete current tail must not fetch older unrelated history'
                loads+=1
                # A buffered old snapshot must not bypass the matching revision.
                send(dict(type='broadcast',method='thread-stream-state-changed',sourceClientId='owner',version=11,
                          params=dict(conversationId='fixture-session',change=dict(type='snapshot',revision=0,conversationState=state))))
            if args.answered and (method=='thread-follower-load-complete-history' or args.tail_complete):
                reply=json.dumps([dict(questionItemId=json.dumps(['request_user_input_async','fixture-call',args.index]),answer='Already answered')])
                turn['items'].append(dict(type='userMessage',content=[dict(type='text',text='<send_user_message_question_reply>'+reply+'</send_user_message_question_reply>')]))
            if args.canonical:
                state['turnHistory'] = dict(kind='canonical', history=dict(
                    entitiesByKey={'turn': turn}, islands=[dict(entries=[dict(key='index', value='turn')])]))
                state['turns'] = []
                if args.tail_complete:
                    state['turnHistory']['history']['islands'][0].update(olderBoundary=dict(status='available'),newerBoundary=dict(status='exhausted'))
            change=(dict(type='patches',baseRevision=1,revision=loads+1,patches=[]) if args.patch_first and loads==1
                    else dict(type='snapshot',revision=loads+1,conversationState=state))
            send(dict(type='broadcast', method='thread-stream-state-changed', sourceClientId='owner', version=11,
                      params=dict(conversationId='fixture-session', change=change)))
            if method=='thread-follower-load-complete-history':
                send(dict(type='response',requestId=message['requestId'],resultType='success',handledByClientId='owner',result={'revision':loads+1}))
            continue
        if method == 'initialize':
            result = {'clientId': 'fixture-client'}
        elif method == 'thread-owner-discovery':
            result = {'ownerClientId': 'owner'}
        elif method in ('thread-follower-steer-turn','thread-follower-start-turn'):
            assert not args.answered, 'An already answered question must never be sent again'
            if args.patch_first:assert loads==2
            params = message['params']
            assert params['conversationId'] == 'fixture-session'
            assert method==('thread-follower-start-turn' if args.completed else 'thread-follower-steer-turn')
            if args.completed:
                assert message['version']==2
                assert params['turnStart']['context']['inheritThreadSettings'] is True
            text = (params['turnStart']['request']['input'] if args.completed else params['input'])[0]['text']
            reply = json.loads(text.split('>\n', 1)[1].rsplit('\n<', 1)[0])[0]
            assert json.loads(reply['questionItemId']) == ['request_user_input_async', 'fixture-call', args.index]
            assert reply['question'] == question and reply['answer'] == answer
            (root / 'receipt.json').write_text(json.dumps(dict(
                accepted=True, answer=reply['answer'], session=params['conversationId'],
                call='fixture-call', methods=methods), ensure_ascii=False), encoding='utf-8')
            result = {'result': {'turn': {'id': 'new-turn'}} if args.completed else {'turnId': 'turn'}}
        else:
            raise AssertionError('Unexpected protocol method: ' + str(method))
        send(dict(type='response', requestId=message['requestId'], resultType='success',
                  handledByClientId='owner', result=result))
finally:
    connection.close()
    server.close()
