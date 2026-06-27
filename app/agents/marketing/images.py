"""마케팅 사진 정규화 — Bedrock Claude의 '이미지 1장당 5MB' 하드 리밋 방어.

블로그 생성은 사장님 매장 사진(원본 풀사이즈)을 그대로 Bedrock에 보낸다. 폰 사진은
쉽게 5MB를 넘어 ``image.source.bytes: image exceeds 5 MB maximum`` 400으로 전체 생성이
실패한다. 여기서 **한도를 넘는 사진만** 긴 변 축소 + JPEG 재인코딩으로 줄여 data URL로
교체한다. 한도 이하 사진은 원본 URL을 그대로 통과시켜(litellm이 가져감) 현행 동작·화질을 유지한다.
"""

import asyncio
import base64
import io
import logging

import httpx
from PIL import Image

_log = logging.getLogger("flori.marketing")

# Bedrock Claude 하드 리밋(이미지 1장당) = 5 * 1024 * 1024 = 5,242,880 bytes.
_BEDROCK_HARD_LIMIT = 5 * 1024 * 1024
# 실제 트리거/타깃 임계값 — 하드 리밋 아래로 안전 마진(~242KB)을 둔다. Content-Length 오차·
# 인코딩 편차로 한도에 아슬아슬하게 다시 걸리는 일을 막는다.
MAX_IMAGE_BYTES = 5_000_000

# 축소 시 긴 변 상한(px). Claude 권장 해상도와 정합 — 비용·품질에도 유리하고,
# 대부분의 무거운 폰 사진은 이 단계만으로 5MB 한참 아래로 떨어진다.
_MAX_LONG_EDGE = 1568
_JPEG_QUALITIES = (85, 75, 65, 55, 45)


def shrink_image_under_limit(data: bytes, max_bytes: int = MAX_IMAGE_BYTES) -> bytes:
    """이미지 바이트를 ``max_bytes`` 이하 JPEG로 축소한다(긴 변 캡 → 품질 하강 → 추가 다운스케일)."""
    img = Image.open(io.BytesIO(data))
    img = img.convert("RGB")  # PNG/RGBA/CMYK·EXIF 회전 무시하고 JPEG 인코딩 가능하게

    if max(img.size) > _MAX_LONG_EDGE:
        img.thumbnail((_MAX_LONG_EDGE, _MAX_LONG_EDGE))

    best = _encode_jpeg(img, _JPEG_QUALITIES[-1])
    for quality in _JPEG_QUALITIES:
        encoded = _encode_jpeg(img, quality)
        if len(encoded) <= max_bytes:
            return encoded
        best = encoded

    # 품질을 낮춰도 안 되면 해상도를 절반씩 줄여가며 재시도(노이즈 많은 사진 대비).
    while max(img.size) > 256:
        img.thumbnail((img.size[0] // 2, img.size[1] // 2))
        encoded = _encode_jpeg(img, 60)
        best = encoded
        if len(encoded) <= max_bytes:
            return encoded
    return best  # 최선의 노력(여기까지 오면 이미 매우 작음)


def _encode_jpeg(img: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def _to_data_url(data: bytes) -> str:
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


async def normalize_image_urls(
    urls: list[str], *, client: httpx.AsyncClient, max_bytes: int = MAX_IMAGE_BYTES
) -> list[str]:
    """사진 URL 목록을 Bedrock 안전 형태로 정규화한다.

    - 한도 이하: 원본 URL 그대로(litellm이 가져감) — 현행 동작·화질 유지.
    - 한도 초과: 다운로드 → 축소 → ``data:image/jpeg;base64,...`` 로 교체.
    - 실패: 원본 URL로 폴백(적극적으로 깨뜨리지 않음).
    """
    if not urls:
        return []
    return list(await asyncio.gather(*(_normalize_one(u, client=client, max_bytes=max_bytes) for u in urls)))


async def _normalize_one(url: str, *, client: httpx.AsyncClient, max_bytes: int) -> str:
    try:
        size = await _probe_size(client, url)
        if size is not None and size <= max_bytes:
            return url
        data = (await client.get(url)).raise_for_status().content
        if len(data) <= max_bytes:
            return url
        shrunk = shrink_image_under_limit(data, max_bytes)
        _log.info(
            "🖼️ 사진 리사이즈 | 원본=%.1fMB → 축소=%.1fMB (한도 %.1fMB 초과분만)",
            len(data) / 1_000_000,
            len(shrunk) / 1_000_000,
            max_bytes / 1_000_000,
        )
        return _to_data_url(shrunk)
    except Exception:  # noqa: BLE001 — 정규화 실패가 생성 전체를 막지 않게 폴백
        _log.warning("이미지 정규화 실패 — 원본 URL로 폴백", exc_info=True)
        return url


async def _probe_size(client: httpx.AsyncClient, url: str) -> int | None:
    """HEAD로 Content-Length를 본다(작은 사진을 다운로드 없이 통과시키기 위함). 실패 시 None."""
    try:
        resp = await client.head(url)
        resp.raise_for_status()
        length = resp.headers.get("Content-Length")
        return int(length) if length is not None else None
    except (httpx.HTTPError, ValueError):
        return None
