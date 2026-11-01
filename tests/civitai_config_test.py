import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from server.routes.model_routes import civitai_models


class FakeResponse:
    status_code = 200

    def json(self):
        return {"items": []}


class FakeAsyncClient:
    def __init__(self):
        self.get_args = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, *args, **kwargs):
        self.get_args = (args, kwargs)
        return FakeResponse()


class TestCivitaiConfig(unittest.IsolatedAsyncioTestCase):
    async def test_configured_token_is_forwarded(self):
        config_service = MagicMock()
        config_service.get_config.return_value = {
            "ui": {"civitai_token": "secret-token"}
        }
        request = SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(config_service=config_service)
            )
        )
        client = FakeAsyncClient()

        with patch(
            "server.routes.model_routes.httpx.AsyncClient",
            return_value=client,
        ):
            result = await civitai_models(request, query="flux")

        self.assertEqual(result, {"items": []})
        self.assertEqual(
            client.get_args[1]["headers"],
            {"Authorization": "Bearer secret-token"},
        )
        self.assertEqual(client.get_args[1]["params"]["query"], "flux")

    async def test_empty_token_does_not_add_authorization_header(self):
        config_service = MagicMock()
        config_service.get_config.return_value = {"ui": {"civitai_token": ""}}
        request = SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(config_service=config_service)
            )
        )
        client = FakeAsyncClient()

        with patch(
            "server.routes.model_routes.httpx.AsyncClient",
            return_value=client,
        ):
            await civitai_models(request)

        self.assertIsNone(client.get_args[1]["headers"])


if __name__ == "__main__":
    unittest.main()
