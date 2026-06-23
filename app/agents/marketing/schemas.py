"""마케팅 생성 입출력 스키마 (Pydantic v2)."""

from pydantic import BaseModel, Field


class StoreContext(BaseModel):
    """게이트웨이가 코드로 조립해 주입하는 매장 실데이터 (1인칭 신호·해자)."""

    shop_name: str | None = None
    avg_order_value: int | None = None  # 객단가(원)
    upcoming_season: str | None = None  # 예: "어버이날 (D-7)"
    top_products: list[str] = Field(default_factory=list)


class BlogGenInput(BaseModel):
    """블로그 초안 생성 입력. 사용자 텍스트는 생성기에서 펜스로 격리한다."""

    keyword: str
    situation: str | None = None
    memo: str | None = None
    tone_samples: list[str] = Field(default_factory=list)  # 사장 블로그 샘플(말투 few-shot)
    store_context: StoreContext | None = None
    photo_urls: list[str] = Field(default_factory=list)


class BlogSection(BaseModel):
    """200~300자 자기완결 단락. 소제목 = 네이버 자동완성 하위질문."""

    heading: str
    body: str


class BlogFaq(BaseModel):
    q: str
    a: str


class BlogDraft(BaseModel):
    title: str
    sections: list[BlogSection] = Field(default_factory=list)
    faq: list[BlogFaq] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
