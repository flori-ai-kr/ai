"""마케팅 이미지 정규화 — Bedrock 5MB/장 한도 초과 사진만 리사이즈해 전송."""

import base64
import io
import os

import httpx
from PIL import Image

from app.agents.marketing.images import (
    MAX_IMAGE_BYTES,
    normalize_image_urls,
    shrink_image_under_limit,
)


def _noise_jpeg(width: int, height: int) -> bytes:
    """랜덤 노이즈 JPEG — 잘 압축되지 않아 큰 바이트를 만든다(테스트용 '무거운 원본')."""
    img = Image.frombytes("RGB", (width, height), os.urandom(width * height * 3))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _mock_client(*, size_header: int | None, body: bytes | None, fail: bool = False) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            raise httpx.ConnectError("boom")
        if request.method == "HEAD":
            headers = {"Content-Length": str(size_header)} if size_header is not None else {}
            return httpx.Response(200, headers=headers)
        return httpx.Response(200, content=body or b"")

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_shrink_reduces_oversized_image_below_limit():
    big = _noise_jpeg(2000, 2000)
    limit = 200_000
    assert len(big) > limit  # 전제: 실제로 한도를 넘는 원본

    out = shrink_image_under_limit(big, limit)

    assert len(out) <= limit
    Image.open(io.BytesIO(out)).load()  # 여전히 디코딩 가능한 유효 이미지


async def test_normalize_passes_small_url_through_unchanged():
    small = _noise_jpeg(50, 50)
    client = _mock_client(size_header=len(small), body=small)
    try:
        out = await normalize_image_urls(["https://cdn.example.com/a.jpg"], client=client, max_bytes=5_000_000)
    finally:
        await client.aclose()
    # 한도 이하 → 원본 URL 그대로(litellm이 가져감), data URL로 바꾸지 않음
    assert out == ["https://cdn.example.com/a.jpg"]


async def test_normalize_shrinks_oversized_url_to_data_url():
    limit = 200_000
    big = _noise_jpeg(2000, 2000)
    assert len(big) > limit
    client = _mock_client(size_header=len(big), body=big)
    try:
        out = await normalize_image_urls(["https://cdn.example.com/big.jpg"], client=client, max_bytes=limit)
    finally:
        await client.aclose()

    assert len(out) == 1
    ref = out[0]
    assert ref.startswith("data:image/jpeg;base64,")
    payload = base64.b64decode(ref.split(",", 1)[1])
    assert len(payload) <= limit  # Bedrock이 보는 raw bytes가 한도 이하
    Image.open(io.BytesIO(payload)).load()


async def test_normalize_falls_back_to_original_url_on_error():
    client = _mock_client(size_header=None, body=None, fail=True)
    try:
        out = await normalize_image_urls(["https://cdn.example.com/x.jpg"], client=client, max_bytes=5_000_000)
    finally:
        await client.aclose()
    # 네트워크 실패 시 원본 URL로 폴백(현행 동작 유지 — 적극적으로 깨지 않음)
    assert out == ["https://cdn.example.com/x.jpg"]


def test_max_image_bytes_is_under_bedrock_hard_limit():
    # Bedrock Claude 하드 리밋 = 5 * 1024 * 1024 = 5,242,880 bytes. 안전 마진을 둔다.
    assert MAX_IMAGE_BYTES < 5 * 1024 * 1024
