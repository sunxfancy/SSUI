import unittest
import tempfile
import os
from unittest.mock import patch
from backend.resource_monitor import placement, GiB


class ResourcePolicyTests(unittest.TestCase):
    def resources(self, ram=32, vram=24):
        return {"ram": {"total": 64 * GiB, "available": ram * GiB},
                "gpus": [{"index": 0, "available": vram * GiB}]}

    def test_full_device_with_headroom(self):
        self.assertEqual(placement(20 * GiB, self.resources()), "device")

    def test_low_vram_uses_host(self):
        self.assertEqual(placement(22 * GiB, self.resources()), "cpu_offload")

    def test_host_pressure_requires_confirmation(self):
        self.assertEqual(placement(22 * GiB, self.resources(ram=8)), "disk_confirmation")

    def test_missing_gpu_is_not_unlimited(self):
        r = self.resources()
        r["gpus"] = []
        self.assertEqual(placement(4 * GiB, r), "cpu_offload")

    def test_decline_and_unavailable_server_fail_closed(self):
        from backend.disk_offload import confirm_disk_offload
        with patch('backend.disk_offload.urlopen', side_effect=OSError('offline')):
            with self.assertRaises(MemoryError):
                confirm_disk_offload('test', GiB)

    def test_real_disk_backing_preserves_output(self):
        import torch
        from backend.disk_offload import disk_back_model
        model = torch.nn.Linear(4, 3)
        x = torch.randn(2, 4)
        expected = model(x).detach().clone()
        cache = tempfile.TemporaryDirectory()
        with patch.dict(os.environ, {"SSUI_OFFLOAD_DIR": cache.name}):
            directory = disk_back_model(model, 60)
        try:
            self.assertTrue(torch.equal(expected, model(x)))
            model.load_state_dict({k: v.clone() for k, v in model.state_dict().items()}, assign=True)
        finally:
            directory.cleanup()
            cache.cleanup()

    def test_api_confirmation_is_one_shot(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from server.routes.resource_routes import router
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client:
            key = client.post('/api/resources/disk-requests', json={
                'model': 'test', 'required_bytes': GiB}).json()['id']
            self.assertIsNone(client.get('/api/resources/disk-requests/' + key).json()['approved'])
            self.assertEqual(client.post('/api/resources/disk-requests/' + key,
                                         json={'approved': False}).status_code, 200)
            self.assertFalse(client.get('/api/resources/disk-requests/' + key).json()['approved'])
            self.assertEqual(client.post('/api/resources/disk-requests/' + key,
                                         json={'approved': True}).status_code, 409)

    def test_cache_uses_disk_mapping_only_after_consent(self):
        import torch
        try:
            from backend.model_manager.load.model_cache.model_cache import ModelCache
        except RuntimeError as exc:
            if 'infer_schema(func)' in str(exc):
                self.skipTest('Installed flash-attention is incompatible with torch: ' + str(exc).splitlines()[0])
            raise
        from backend.model_manager.load.model_cache.cached_model.cached_model_with_partial_load import CachedModelWithPartialLoad
        cache_root = tempfile.TemporaryDirectory()
        resources = self.resources(ram=0, vram=0)
        with patch.object(ModelCache, '_calc_ram_available_to_model_cache', return_value=GiB), \
             patch.object(ModelCache, 'make_room'), \
             patch('backend.resource_monitor.snapshot', return_value=resources), \
             patch('backend.disk_offload.confirm_disk_offload') as confirm, \
             patch.dict(os.environ, {'SSUI_OFFLOAD_DIR': cache_root.name}):
            cache = ModelCache(3, True, True, execution_device='cuda')
            model = torch.nn.Linear(4, 3)
            expected = model.weight.detach().clone()
            cache.put('tiny-model', model)
            confirm.assert_called_once()
            wrapped = cache.get('tiny-model').cached_model
            self.assertIsInstance(wrapped, CachedModelWithPartialLoad)
            self.assertTrue(torch.equal(expected, wrapped.get_cpu_state_dict()['weight']))
            backing = wrapped._disk_backing
            model.load_state_dict({k: v.clone() for k, v in model.state_dict().items()}, assign=True)
            wrapped._cpu_state_dict = None
            backing.cleanup()
        cache_root.cleanup()

    def test_confirmation_approval_and_refusal(self):
        import io
        import json
        from backend.disk_offload import confirm_disk_offload
        for approved in (True, False):
            responses = [io.BytesIO(json.dumps({'id': 'one-shot'}).encode()),
                         io.BytesIO(json.dumps({'approved': approved}).encode())]
            with patch('backend.disk_offload.urlopen', side_effect=responses):
                if approved:
                    confirm_disk_offload('model', 1024)
                else:
                    with self.assertRaises(MemoryError):
                        confirm_disk_offload('model', 1024)

    def test_low_host_requires_disk_even_if_gpu_fits(self):
        self.assertEqual(placement(4 * GiB, self.resources(ram=1)), 'disk_confirmation')

    def test_disk_space_failure_does_not_create_backing_file(self):
        import torch
        from backend.disk_offload import disk_back_model
        with tempfile.TemporaryDirectory() as root, \
             patch.dict(os.environ, {'SSUI_OFFLOAD_DIR': root}), \
             patch('backend.disk_offload.shutil.disk_usage') as usage:
            usage.return_value.free = 0
            with self.assertRaises(MemoryError):
                disk_back_model(torch.nn.Linear(1, 1), GiB)
            self.assertEqual(os.listdir(root), [])
