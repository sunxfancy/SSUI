import hashlib
import time
import unittest
from fastapi.testclient import TestClient
from server.generation_bridge import create_demo_app


class GenerationBridgeTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_demo_app())
        self.client.__enter__()
        self.base = '/api/generation/v1'
        self.body = {'recipe': 'mock.checker@1', 'clientId': 'demo', 'context': {'documentId': 'drawing', 'revision': 2}, 'idempotencyKey': 'one'}

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def submit(self):
        return self.client.post(self.base+'/jobs', json=self.body)

    def test_generation_download_and_idempotency(self):
        response = self.submit()
        self.assertEqual(response.status_code, 202)
        job = response.json()
        self.assertEqual(self.submit().json()['jobId'], job['jobId'])
        for _ in range(50):
            job = self.client.get(self.base+'/jobs/'+job['jobId']).json()
            if job['state'] == 'succeeded':
                break
            time.sleep(.03)
        self.assertEqual(job['state'], 'succeeded')
        self.assertEqual(job['context']['revision'], 2)
        artifact = job['artifacts'][0]
        data = self.client.get(artifact['url'])
        self.assertEqual(data.headers['content-type'], 'image/png')
        self.assertTrue(data.content.startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertEqual(hashlib.sha256(data.content).hexdigest(), artifact['sha256'])
        self.body['inputs'] = {'prompt': 'changed'}
        self.assertEqual(self.submit().status_code, 409)

    def test_cancel(self):
        job = self.submit().json()
        url = self.base+'/jobs/'+job['jobId']
        self.assertEqual(self.client.post(url+'/cancel').json()['state'], 'cancelled')
        time.sleep(.7)
        result = self.client.get(url).json()
        self.assertEqual(result['state'], 'cancelled')
        self.assertEqual(result['artifacts'], [])

    def test_validation_and_missing_resources(self):
        self.body['inputs'] = {'size': 9999}
        self.assertEqual(self.submit().status_code, 422)
        self.assertEqual(self.client.get(self.base+'/jobs/missing').status_code, 404)
        self.assertEqual(self.client.get(self.base+'/artifacts/missing').status_code, 404)
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertTrue(self.client.get(self.base+'/recipes').json()['mock'])

    def test_generic_clients_and_recipe_validation(self):
        self.body.pop('context')
        first = self.submit().json()
        self.assertEqual(first['context'], {})
        self.assertNotIn('target', first)
        self.body['clientId'] = 'another-client'
        self.body['context'] = {'timeline': {'track': 3}, 'tags': ['draft']}
        second = self.submit().json()
        self.assertNotEqual(first['jobId'], second['jobId'])
        self.assertEqual(second['context'], self.body['context'])
        self.body['recipe'] = 'unknown@1'
        self.assertEqual(self.submit().status_code, 404)
        schema = self.client.get('/openapi.json').json()
        fields = schema['components']['schemas']['Generate']['properties']
        self.assertNotIn('target', fields)
        self.assertNotIn('const', fields['recipe'])
        self.assertEqual(self.client.get(self.base+'/capabilities').json()['protocol'], 'ssui-generation')
