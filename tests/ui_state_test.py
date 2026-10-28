import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.routes.ui_state_routes import router, state_paths


class UIStateTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        # Match the canonical project paths returned by the server (Windows 8.3 aliases
        # and macOS /var symlinks can otherwise name the same directory differently).
        self.root = Path(self.temporary.name).resolve() / 'project'
        self.root.mkdir()
        (self.root / 'ssproject.yaml').write_text('name: test')
        self.script = self.root / 'scripts' / 'example.py'
        self.script.parent.mkdir()
        self.script.touch()
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def load(self, script=None, view='functional'):
        return self.client.get('/api/ui_state_load', params={'script_path': str(script or self.script), 'view': view})

    def save(self, data, script=None, view='functional'):
        return self.client.post('/api/ui_state_store', params={'script_path': str(script or self.script), 'view': view}, json={'state_data': data})

    def test_missing_state_does_not_create_files(self):
        self.assertEqual(self.load().json(), {})
        self.assertFalse((self.root / '.ssui').exists())

    def test_internal_marker_names_in_user_json_are_preserved(self):
        state = {'literal': {'__ssui_project_path__': '../../user text'},
                 'nested': {'__ssui_literal__': {'__ssui_project_path__': 'not a file'}}}
        self.assertEqual(self.save(state).status_code, 200)
        self.assertEqual(self.load().json(), state)

    def test_roundtrip_and_isolation(self):
        state = {'prompt': '森林 🌳', 'enabled': False, 'count': 0, 'items': [1, 2]}
        self.assertEqual(self.save(state).status_code, 200)
        self.assertEqual(self.load().json(), state)
        self.assertEqual(self.load(view='workflow').json(), {})
        other = self.script.with_name('other.py')
        other.touch()
        self.assertEqual(self.load(script=other).json(), {})
        self.save({'graph': {}}, view='workflow')
        self.assertEqual(self.load().json(), state)

    def test_copied_project_restores_state_and_asset_paths(self):
        uploaded = self.client.post('/api/ui_state_asset', params={'script_path': str(self.script)},
                                    files={'file': ('../../mask.png', b'mask data', 'image/png')})
        self.assertEqual(uploaded.status_code, 200)
        asset = Path(uploaded.json()['path'])
        self.assertEqual(asset.parent, self.root / '.ssui' / 'assets')
        self.save({'image': str(asset), 'text': 'prompt', 'nested': [str(self.script)]})
        moved = self.root.with_name('copied')
        shutil.copytree(self.root, moved)
        restored = self.load(moved / 'scripts' / 'example.py').json()
        self.assertEqual(restored['image'], str(moved / '.ssui' / 'assets' / asset.name))
        self.assertEqual(Path(restored['image']).read_bytes(), b'mask data')
        self.assertEqual(restored['nested'], [str(moved / 'scripts' / 'example.py')])

    def test_same_script_spelling_uses_same_state(self):
        self.save({'prompt': 'saved'})
        alias = str(self.script.parent / '..' / 'scripts' / self.script.name)
        self.assertEqual(self.load(alias).json(), {'prompt': 'saved'})

    def test_failed_replace_keeps_previous_state_and_cleans_temporary(self):
        self.save({'prompt': 'original'})
        with patch('server.routes.ui_state_routes.os.replace', side_effect=OSError('disk full')):
            self.assertEqual(self.save({'prompt': 'replacement'}).status_code, 500)
        self.assertEqual(self.load().json(), {'prompt': 'original'})
        self.assertEqual(list((self.root / '.ssui' / 'ui_states').glob('*.tmp')), [])

    def test_corrupt_state_is_an_error(self):
        self.save({'prompt': 'saved'})
        path, _, _ = state_paths(str(self.script), 'functional')
        path.write_text('{incomplete')
        self.assertEqual(self.load().status_code, 500)

    def test_legacy_default_view_is_readable(self):
        directory = self.root / '.ssui' / 'ui_states'
        directory.mkdir(parents=True)
        legacy = directory / (hashlib.md5(str(self.script).encode()).hexdigest() + '.json')
        legacy.write_text(json.dumps({'legacy': True}))
        self.assertEqual(self.load(view='').json(), {'legacy': True})

    def test_view_cannot_escape_state_directory(self):
        self.assertEqual(self.save({'ok': True}, view='../../outside').status_code, 200)
        self.assertEqual(len(list((self.root / '.ssui' / 'ui_states').iterdir())), 1)

    def test_older_autosave_cannot_overwrite_unload_snapshot(self):
        def request(revision, prompt):
            return self.client.post('/api/ui_state_store',
                params={'script_path': str(self.script), 'view': 'functional'},
                json={'state_data': {'prompt': prompt}, 'client_id': 'editor-session', 'revision': revision})
        self.assertEqual(request(2, 'latest').status_code, 200)
        self.assertEqual(request(1, 'stale').status_code, 200)
        self.assertEqual(self.load().json(), {'prompt': 'latest'})

    def test_unknown_version_does_not_load_as_empty_state(self):
        self.save({'prompt': 'saved'})
        path, _, _ = state_paths(str(self.script), 'functional')
        path.write_text(json.dumps({'version': 2, 'state': {'prompt': 'future'}}))
        self.assertEqual(self.load().status_code, 500)

    def test_project_required(self):
        self.assertEqual(self.load(Path(self.temporary.name) / 'outside.py').status_code, 404)
