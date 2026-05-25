# SPEC-AI-003 — B OCR→예약 (비전 + human-in-loop 쓰기)

> status: DONE · deps: SPEC-AI-001(DONE), SPEC-AI-002(DONE) · Phase 1 · 65 tests 통과 · ruff clean

## 목표

카톡 등 대화 스크린샷 이미지를 비전 LLM(Claude Haiku 4.5, 멀티모달)으로 읽어 **예약 후보**(고객·날짜·시간·품목·금액)를 추출하고, **확인 카드(human-in-loop)** 로 사용자에게 제시한 뒤, 확인 시에만 백엔드에 예약을 생성한다. 첫 쓰기 경로 — LLM이 단독으로 예약을 만들지 못한다.

## 범위 (In)

- **비전 추출** (`app/agents/vision.py`): `extract_reservation_draft(model, image_url)` — 멀티모달 메시지(이미지 + 추출 프롬프트) → 구조화 JSON → `ReservationDraft`(Pydantic). 코드펜스/잡텍스트에 견고한 JSON 파싱, 실패 시 `VisionExtractionError`.
- **모델** (`app/session/models.py` 확장 또는 `app/confirm/models.py`): `ReservationDraft`, `ConfirmationCard{proposal_id, action, summary, fields[], expires_at}`. `PendingWrite`(기존) 재사용.
- **쓰기 제안 저장** (`app/confirm/store.py`): `PendingWriteStore` — Redis `flori:pending:{proposal_id}`에 user_id 바인딩 + TTL. 소유자 검증, 만료/미존재 처리.
- **쓰기 실행** (`app/confirm/executor.py`): `execute(client, ctx, pending)` — `create_reservation` 액션 → 백엔드 `POST /reservations`(JWT 패스스루). 에이전트 루프 밖에서만 실행(human-in-loop).
- **엔드포인트**:
  - `POST /ocr/reservation` {image_url} → 비전 추출 → `PendingWrite` 저장 → `ConfirmationCard` 반환.
  - `POST /confirm` {proposal_id} → 소유자 검증 → 실행 → 생성 결과. 미존재/만료 404, 타 유저 403, 1회성(실행 후 삭제).
- **확인 카드 계약**: `ConfirmationCard` JSON = 앱(`flori-ai/mobile`)과 공유하는 계약. DESIGN §14 초안 확정.

## 범위 밖 (Out)

- 음성(→ C), 선제 제안(→ D). 예약 외 쓰기(매출 등)는 동일 패턴으로 후속.
- 실제 Bedrock Vision 호출(테스트는 fake model + respx). 이미지 업로드/스토리지(이미지 URL은 클라이언트가 제공/접근 가능 전제).
- 상대 날짜("내일") 자연어 → 절대일 변환의 고급 처리: 비전 프롬프트가 절대일(YYYY-MM-DD) 산출을 지시하되, 모호하면 draft에 그대로 두고 확인 카드에서 사용자가 수정(필드 편집은 앱 책임).

## 인수 기준

1. `uv run ruff check . && uv run ruff format --check . && uv run pytest` 통과.
2. 비전 추출: fake model이 예약 JSON(코드펜스 포함/미포함)을 반환하면 `ReservationDraft`로 파싱된다. 비-JSON이면 `VisionExtractionError`.
3. `POST /ocr/reservation`: 인증 필요(미인증 401). 유효 시 200 + `ConfirmationCard{proposal_id, action:"create_reservation", summary, fields[], expires_at}`. `PendingWrite`가 user_id 바인딩으로 저장된다.
4. `POST /confirm`: 저장된 proposal을 소유자만 실행 → 백엔드 `POST /reservations`에 JWT 패스스루로 후보 payload 전송(respx) → 생성 결과 반환. 실행 후 pending 삭제(재실행 시 404).
5. 타 유저의 proposal_id로 confirm → 403. 미존재/만료 proposal_id → 404.
6. **쓰기는 confirm 경유만**: 에이전트 ReAct 루프(dispatch)는 여전히 쓰기 도구를 차단한다(AI-002 가드 유지).
7. 비전 입력(이미지에서 나온 텍스트 포함)이 시스템 지시로 격리된다(프롬프트 인젝션 방어).

## 설계 메모

- 쓰기 게이팅 = 보안 핵심: LLM 출력(draft)은 **제안일 뿐**, 실제 백엔드 쓰기는 사용자가 `POST /confirm`을 호출해야만 일어난다. proposal은 user_id 바인딩 + TTL + 1회성으로 위변조/재사용 방지.
- 예약 payload는 백엔드 `POST /reservations` DTO와 1:1: `date`*, `time?`, `customerName`*, `customerPhone?`, `title`*, `amount`, `reminderAt?`. `userId`는 JWT로 백엔드가 주입.
- 비전·confirm 모두 같은 인증 의존성(`get_request_context`) + 사용량 캡 적용.
- ConfirmationCard.fields는 표시·편집용(label/value) — 앱이 렌더하고, 수정 후 confirm 시 수정된 payload를 보낼 수 있게 계약에 여지를 둔다(후속).
