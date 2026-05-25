"""백엔드 REST 읽기 도구 레지스트리 (A 데이터 분석).

도구 = 검증된 백엔드 엔드포인트의 얇은 래퍼. 핸들러는 ``BackendClient`` + ``RequestContext``로
호출하며 JWT를 그대로 패스스루한다(격리는 백엔드가 강제). LLM 인자는 Pydantic으로 검증·캐스팅하고,
실패 시 예외 대신 구조화 에러를 돌려 에이전트의 self-correction을 가능케 한다.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from app.backend.auth import RequestContext
from app.backend.client import BackendClient

Handler = Callable[[BackendClient, RequestContext, BaseModel], Awaitable[Any]]


# --- 인자 스키마 ---
class MonthArg(BaseModel):
    month: str | None = None  # YYYY-MM (생략 시 이번 달)


class NoArgs(BaseModel):
    pass


# --- 핸들러 (읽기전용) ---
async def _get_month_dashboard(client: BackendClient, ctx: RequestContext, args: MonthArg) -> Any:
    params = {"month": args.month} if args.month else None
    return await client.get("/dashboard/month", jwt=ctx.jwt, params=params)


async def _get_today_dashboard(client: BackendClient, ctx: RequestContext, args: NoArgs) -> Any:
    return await client.get("/dashboard/today", jwt=ctx.jwt)


async def _list_sales(client: BackendClient, ctx: RequestContext, args: MonthArg) -> Any:
    params = {"month": args.month} if args.month else None
    return await client.get("/sales", jwt=ctx.jwt, params=params)


async def _list_customers(client: BackendClient, ctx: RequestContext, args: NoArgs) -> Any:
    return await client.get("/customers", jwt=ctx.jwt)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args_schema: type[BaseModel]
    handler: Handler
    is_write: bool = False


REGISTRY: dict[str, ToolSpec] = {
    "get_month_dashboard": ToolSpec(
        name="get_month_dashboard",
        description=(
            "해당 월의 매출/지출/카테고리·결제수단·채널·고객 통계 요약을 조회. month는 'YYYY-MM'(생략 시 이번 달)."
        ),
        args_schema=MonthArg,
        handler=_get_month_dashboard,
    ),
    "get_today_dashboard": ToolSpec(
        name="get_today_dashboard",
        description="오늘의 요약, 다가오는 예약, 발동된 리마인더를 조회.",
        args_schema=NoArgs,
        handler=_get_today_dashboard,
    ),
    "list_sales": ToolSpec(
        name="list_sales",
        description="해당 월의 매출 목록을 조회. month는 'YYYY-MM'(생략 시 이번 달).",
        args_schema=MonthArg,
        handler=_list_sales,
    ),
    "list_customers": ToolSpec(
        name="list_customers",
        description="고객 목록을 구매 통계(총액 내림차순)와 함께 조회.",
        args_schema=NoArgs,
        handler=_list_customers,
    ),
}


def tool_schemas() -> list[dict]:
    """REGISTRY를 OpenAI 함수-툴 스키마로 직렬화(ChatOpenAI.bind_tools 입력)."""
    schemas: list[dict] = []
    for spec in REGISTRY.values():
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.args_schema.model_json_schema(),
                },
            }
        )
    return schemas


async def dispatch(client: BackendClient, ctx: RequestContext, name: str, args: dict[str, Any] | None) -> Any:
    """도구 1건 실행. 미등록/인자 오류는 예외 대신 에러 dict(self-correction)."""
    spec = REGISTRY.get(name)
    if spec is None:
        return {"error": f"unknown tool: {name}"}
    try:
        validated = spec.args_schema(**(args or {}))
    except ValidationError as exc:
        return {"error": f"invalid args for {name}: {exc.errors(include_url=False)}"}
    return await spec.handler(client, ctx, validated)
