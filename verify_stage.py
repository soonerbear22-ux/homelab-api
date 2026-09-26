"""Read-only integration checks against an explicitly chosen deployment."""
import argparse
import requests

EXPECTED = {
    '/docker/status.json': 'get_docker_status',
    '/host/status.json': 'get_host_status',
    '/processes/top.json': 'get_top_processes',
    '/history/memory.json': 'get_memory_history',
    '/history/cpu.json': 'get_cpu_history',
    '/disk/io.json': 'get_disk_io_status',
    '/knowledge/search.json': 'search_homelab_knowledge',
    '/ai-worker/status.json': 'get_ai_worker_status',
    '/knowledge/health.json': 'get_knowledge_pipeline_health',
    '/basecamp/status.json': 'get_basecamp_status',
    '/basecamp/guests.json': 'get_basecamp_guests',
    '/basecamp/storage.json': 'get_basecamp_storage',
    '/audit/full.json': 'get_full_homelab_audit',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base_url')
    parser.add_argument('--host', default='core-services')
    parser.add_argument('--query', default='What is the purpose of ai-worker?')
    parser.add_argument('--expected-source')
    args = parser.parse_args()
    base = args.base_url.rstrip('/')

    def get(path, params=None):
        response = requests.get(base + path, params=params, timeout=(5, 180))
        response.raise_for_status()
        return response.json()

    schema = get('/openapi.json')
    assert set(schema['paths']) == set(EXPECTED), 'Unexpected operation set'
    for path, operation_id in EXPECTED.items():
        operations = schema['paths'][path]
        assert set(operations) == {'get'}, f'Unexpected methods: {path}'
        assert operations['get']['operationId'] == operation_id, f'Operation mismatch: {path}'
        params = {'query': args.query, 'limit': 5} if path == '/knowledge/search.json' else None
        result = get(path, params)
        if path in {'/host/status.json', '/docker/status.json', '/processes/top.json', '/disk/io.json'} or path.startswith('/history/'):
            assert result['host'] == args.host, f'Unexpected host label: {path}'
        if path.startswith('/history/'):
            assert result['range'] == '1h' and result['points'], f'Missing history: {path}'
        if path == '/disk/io.json':
            assert result['metrics_device'] and 'bottleneck_detected' in result, 'Missing disk result'
        if path == '/knowledge/search.json':
            assert result['results'], 'Search returned no knowledge'
            if args.expected_source:
                assert any(r['source'] == args.expected_source for r in result['results']), 'Expected source absent'
        if path == '/knowledge/health.json':
            assert result['healthy'], 'Knowledge dependency check failed'
        if path == '/ai-worker/status.json':
            assert result['embedding_service']['reachable'], 'Embedding HTTP health unavailable'
        if path == '/audit/full.json':
            assert result['complete'] and result['components_retrieved'] == 7, 'Audit incomplete'
            assert result['derived_facts']['knowledge_pipeline']['current_pipeline_operational'], 'Audit pipeline check failed'
        print(f'OK {path}: {operation_id}')

    for path, params in [
        ('/history/cpu.json', {'range': 'bad'}),
        ('/knowledge/search.json', {}),
        ('/knowledge/search.json', {'query': 'test', 'limit': 11}),
    ]:
        assert requests.get(base + path, params=params, timeout=5).status_code == 422, 'Invalid input was accepted'
    print('OK invalid query parameters rejected')


if __name__ == '__main__':
    main()
