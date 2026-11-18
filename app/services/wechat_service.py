import logging

import httpx

from app.core.config import get_settings
from app.core.exceptions import WechatConfigurationError, WechatLoginError


logger = logging.getLogger(__name__)


class WechatClient:
    async def exchange_code(self, code: str) -> str:
        settings = get_settings()
        if not settings.wechat_app_id or not settings.wechat_app_secret:
            raise WechatConfigurationError()

        try:
            async with httpx.AsyncClient(
                timeout=settings.wechat_api_timeout_seconds
            ) as client:
                response = await client.get(
                    "https://api.weixin.qq.com/sns/jscode2session",
                    params={
                        "appid": settings.wechat_app_id,
                        "secret": settings.wechat_app_secret.get_secret_value(),
                        "js_code": code,
                        "grant_type": "authorization_code",
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            logger.warning(
                "微信 code2Session 请求失败，错误类型：%s",
                type(error).__name__,
            )
            raise WechatLoginError() from error

        if not isinstance(payload, dict):
            logger.warning("微信 code2Session 返回了非对象响应")
            raise WechatLoginError()
        openid = payload.get("openid")
        error_code = payload.get("errcode")
        if error_code:
            logger.warning(
                "微信 code2Session 拒绝登录，错误码：%s，错误说明：%s",
                error_code,
                payload.get("errmsg", ""),
            )
            raise WechatLoginError()
        if not isinstance(openid, str) or not openid:
            logger.warning("微信 code2Session 响应缺少有效的 openid")
            raise WechatLoginError()
        return openid
