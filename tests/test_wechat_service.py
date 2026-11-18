import asyncio

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.core.exceptions import WechatLoginError
from app.services.wechat_service import WechatClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeAsyncClient:
    def __init__(self, payload, calls):
        self.payload = payload
        self.calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return None

    async def get(self, url, params):
        self.calls.append((url, params))
        return FakeResponse(self.payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"errcode": 40029, "errmsg": "invalid code"},
        {"session_key": "present-without-openid"},
        [],
    ],
)
def test_wechat_exchange_rejects_invalid_provider_responses(
    monkeypatch,
    payload,
    caplog,
):
    settings = Settings(
        wechat_app_id="test-app-id",
        wechat_app_secret=SecretStr("test-app-secret"),
    )
    monkeypatch.setattr(
        "app.services.wechat_service.get_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        "app.services.wechat_service.httpx.AsyncClient",
        lambda **kwargs: FakeAsyncClient(payload, []),
    )

    with pytest.raises(WechatLoginError):
        asyncio.run(WechatClient().exchange_code("single-use-code"))

    if isinstance(payload, dict) and payload.get("errcode"):
        assert str(payload["errcode"]) in caplog.text
        assert "single-use-code" not in caplog.text
        assert "test-app-secret" not in caplog.text


def test_wechat_exchange_uses_server_credentials_and_returns_only_openid(
    monkeypatch,
):
    settings = Settings(
        wechat_app_id="test-app-id",
        wechat_app_secret=SecretStr("test-app-secret"),
    )
    calls = []
    monkeypatch.setattr(
        "app.services.wechat_service.get_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        "app.services.wechat_service.httpx.AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            {"openid": "test-openid", "session_key": "never-return-this"},
            calls,
        ),
    )

    openid = asyncio.run(WechatClient().exchange_code("single-use-code"))

    assert openid == "test-openid"
    assert calls[0][0] == "https://api.weixin.qq.com/sns/jscode2session"
    assert calls[0][1]["appid"] == "test-app-id"
    assert calls[0][1]["secret"] == "test-app-secret"
    assert calls[0][1]["js_code"] == "single-use-code"
