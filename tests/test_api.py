"""Contract and regression checks with all external dependencies mocked."""
import importlib
import sys
from pathlib import Path
from unittest.mock import Mock

import docker
import pytest
import requests
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

OPERATIONS = {
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


@pytest.fixture
def api(monkeypatch):
    for name, value in {
        'PROMETHEUS_URL': 'http://metrics.example.invalid',
        'PROMETHEUS_INSTANCE': 'exporter.example.invalid:9100',
        'PVE_URL': 'https://hypervisor.example.invalid',
        'PVE_TOKEN_ID': 'test-only-identity',
        'PVE_TOKEN': 'test-only-placeholder',
        'EMBEDDING_URL': 'http://embedding.example.invalid/embed',
        'QDRANT_URL': 'http://vectors.example.invalid',
        'AI_WORKER_LAN_HOST': 'worker.example.invalid',
        'AI_WORKER_OVERLAY_HOST': 'overlay.example.invalid',
        'AI_WORKER_EMBEDDING_URL': 'http://worker.example.invalid',
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv('PVE_CA_BUNDLE', raising=False)
    monkeypatch.setattr(docker, 'from_env', lambda: Mock())
    def no_network(*args, **kwargs):
        raise AssertionError('Unexpected external request')
    monkeypatch.setattr(requests, 'get', no_network)
    monkeypatch.setattr(requests, 'post', no_network)
    sys.modules.pop('app', None)
    return importlib.import_module('app')


def response(payload):
    value = Mock()
    value.json.return_value = payload
    value.status_code = 200
    value.ok = True
    return value


def test_openapi_contract(api):
    paths = api.app.openapi()['paths']
    assert set(paths) == set(OPERATIONS)
    for path, operation in OPERATIONS.items():
        assert set(paths[path]) == {'get'}
        assert paths[path]['get']['operationId'] == operation
    assert '/health' not in paths


@pytest.mark.parametrize('url', [
    '/knowledge/search.json',
    '/knowledge/search.json?query=test&limit=0',
    '/knowledge/search.json?query=test&limit=11',
    '/history/cpu.json?range=bad',
    '/history/memory.json?range=bad',
])
def test_invalid_requests_do_not_reach_dependencies(api, url):
    with TestClient(api.app) as client:
        assert client.get(url).status_code == 422


def test_search_preserves_provenance_and_limit(api, monkeypatch):
    vector = [0.25] * 2560
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        if url == api.EMBEDDING_URL:
            return response([vector])
        return response({'result': {'points': [{
            'id': 'example-point', 'score': 0.912345,
            'payload': {'source': 'example.md', 'section': 'Recovery',
                        'text': 'Example evidence', 'file_type': 'md',
                        'chunk': 1, 'total_chunks': 2},
        }]}})
    monkeypatch.setattr(requests, 'post', post)
    result = api.search_homelab_knowledge('recovery question', 3)
    assert calls[0][1]['json']['inputs'] == 'recovery question'
    assert calls[1][1]['json'] == {'query': vector, 'limit': 3, 'with_payload': True}
    assert result['results'][0]['source'] == 'example.md'
    assert result['results'][0]['section'] == 'Recovery'
    assert result['results'][0]['score'] == 0.9123


def test_missing_image_metadata_does_not_hide_container(api):
    class Container:
        name = 'example'
        status = 'running'
        attrs = {'Config': {'Image': 'example:recorded'}}
        @property
        def image(self):
            raise RuntimeError('Image metadata unavailable')
    api.client.containers.list.return_value = [Container()]
    result = api.docker_status()
    assert result['container_count'] == 1
    assert result['containers'][0]['image'] == 'example:recorded'
    assert 'image_metadata_warning' in result['containers'][0]


def test_pipeline_reports_embedding_failure(api, monkeypatch):
    def failed_embedding(text):
        raise requests.Timeout('Embedding request timed out')
    monkeypatch.setattr(api, 'embed_text', failed_embedding)
    monkeypatch.setattr(requests, 'get', lambda *a, **k: response({'result': {'status': 'green', 'points_count': 101, 'indexed_vectors_count': 0}}))
    result = api.knowledge_pipeline_health()
    assert result['healthy'] is False
    assert result['checks']['embedding']['ok'] is False
    assert result['checks']['semantic_query']['ok'] is False


def test_audit_retains_partial_results_and_avoids_false_index_alarm(api, monkeypatch):
    def fail():
        raise RuntimeError('One dependency unavailable')
    monkeypatch.setattr(api, 'basecamp_status', fail)
    monkeypatch.setattr(api, 'basecamp_guests', lambda: {'guests': [
        {'vmid': 100, 'name': 'core-services', 'status': 'running'},
        {'vmid': 101, 'name': 'pihole', 'status': 'running'},
        {'vmid': 102, 'name': 'ai-worker', 'status': 'running', 'memory': {'used_percent': 102}},
    ]})
    monkeypatch.setattr(api, 'basecamp_storage', lambda: {'storage': []})
    monkeypatch.setattr(api, 'host_status', lambda: {'host': 'core-services'})
    monkeypatch.setattr(api, 'docker_status', lambda: {'containers': []})
    monkeypatch.setattr(api, 'ai_worker_status', lambda: {})
    monkeypatch.setattr(api, 'knowledge_pipeline_health', lambda: {'healthy': True, 'checks': {
        'embedding': {'ok': True, 'dimensions': 2560},
        'qdrant': {'ok': True, 'status': 'green', 'points_count': 101, 'indexed_vectors_count': 0},
        'semantic_query': {'ok': True, 'results_returned': 1},
    }})
    result = api.full_homelab_audit()
    assert result['complete'] is False
    assert result['components_retrieved'] == 6
    assert result['checks']['basecamp']['retrieved'] is False
    facts = result['derived_facts']
    assert facts['knowledge_pipeline']['current_pipeline_operational'] is True
    assert facts['knowledge_pipeline']['reindex_requirement_state'] == 'not_established'
    assert facts['ai_worker_memory']['memory_exhaustion_state'] == 'not_established'


def test_public_proxmox_copy_verifies_certificates(api, monkeypatch):
    get = Mock(return_value=response({'data': []}))
    monkeypatch.setattr(requests, 'get', get)
    api.proxmox_get('nodes')
    assert get.call_args.kwargs['verify'] is True
    monkeypatch.setenv('PVE_CA_BUNDLE', '/example/ca.pem')
    api.proxmox_get('nodes')
    assert get.call_args.kwargs['verify'] == '/example/ca.pem'
