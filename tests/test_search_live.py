import urllib.request
import json

def run_tests():
    # Test 1: Blocked by offline mode
    req_setting = urllib.request.Request(
        'http://127.0.0.1:8000/api/settings',
        data=json.dumps({'air_gap_mode': True}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    urllib.request.urlopen(req_setting)

    payload_blocked = json.dumps({'tool_name': 'search_web', 'arguments': {'query': 'latest python release'}}).encode()
    req = urllib.request.Request(
        'http://127.0.0.1:8000/api/tools/execute',
        data=payload_blocked,
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode())
        print('TEST 1 (Air-gap ON):', res.get('status'), '|', res.get('summary'))

    # Test 2: Enabled (air_gap_mode: False)
    req_setting = urllib.request.Request(
        'http://127.0.0.1:8000/api/settings',
        data=json.dumps({'air_gap_mode': False}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    urllib.request.urlopen(req_setting)

    payload_active = json.dumps({
        'tool_name': 'search_web',
        'arguments': {'query': 'can you please search online for python programming language official site'}
    }).encode()
    req2 = urllib.request.Request(
        'http://127.0.0.1:8000/api/tools/execute',
        data=payload_active,
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req2) as resp:
        res2 = json.loads(resp.read().decode())
        print('\nTEST 2 (Search Active): status =', res2.get('status'))
        results = res2.get('results', [])
        print(f'Retrieved {len(results)} sources:')
        for r in results:
            print(f'  [{r.get("index")}] {r.get("title")} ({r.get("domain")})')
            print(f'      URL: {r.get("url")}')
            deep = r.get("deep_content", "").replace("\n", " ")
            print(f'      Deep preview: {deep[:120]}...')

if __name__ == '__main__':
    run_tests()
