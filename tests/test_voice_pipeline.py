from fakeredis import FakeAsyncRedis
from langchain_core.messages import AIMessage

from app.backend.auth import RequestContext
from app.backend.client import BackendClient
from app.session.store import SessionStore
from app.voice.pipeline import run_voice_turn


class _FakeStt:
    async def transcribe(self, audio: bytes, *, content_type: str) -> str:
        return "내일 2시 김미영님 장미다발 예약 잡아줘"


class _FakeTts:
    async def synthesize(self, text: str) -> tuple[bytes, str]:
        return (b"AUDIO:" + text.encode("utf-8"), "audio/mpeg")


class _ScriptedModel:
    def __init__(self, scripted):
        self._scripted = list(scripted)

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        return self._scripted.pop(0)


async def test_run_voice_turn_stt_agent_tts():
    store = SessionStore(FakeAsyncRedis(), ttl_seconds=3600)
    ctx = RequestContext(user_id="u1", jwt="jwt")
    model = _ScriptedModel([AIMessage(content="네, 예약 도와드릴게요.")])
    client = BackendClient("http://backend.test", timeout=5.0)

    result = await run_voice_turn(
        stt=_FakeStt(),
        tts=_FakeTts(),
        model=model,
        client=client,
        ctx=ctx,
        audio=b"\x00\x01raw-audio",
        content_type="audio/wav",
        store=store,
        session_id=None,
    )

    assert result["transcript"] == "내일 2시 김미영님 장미다발 예약 잡아줘"
    assert result["reply"] == "네, 예약 도와드릴게요."
    assert result["audio_out"].startswith(b"AUDIO:")
    assert result["content_type"] == "audio/mpeg"
    assert result["session_id"]

    session = await store.get(result["session_id"])
    assert [t.role for t in session.turns] == ["user", "assistant"]
    assert session.turns[0].text == "내일 2시 김미영님 장미다발 예약 잡아줘"
    await client.aclose()
