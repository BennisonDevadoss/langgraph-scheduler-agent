import httpx

from fastapi import Body

from config.settings import SETTINGS
from schemas.chat_schema import RAGChatRequestParams, SchedulerChatRequestParams
from exceptions.custom_errors import BadRequestException


async def verify_captcha(
    params: RAGChatRequestParams | SchedulerChatRequestParams = Body(),
) -> None:
    if not params.captcha_token:
        raise BadRequestException("Captcha token missing")

    url = "https://www.google.com/recaptcha/api/siteverify"
    data = {
        "secret": SETTINGS.RECAPTCHA_SECRET_KEY,
        "response": params.captcha_token,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, data=data)
        result = resp.json()

    if not result.get("success"):
        raise BadRequestException("Invalid captcha token")
