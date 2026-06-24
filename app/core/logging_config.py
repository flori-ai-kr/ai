"""``flori`` 네임스페이스 로깅 설정.

uvicorn 기본 설정은 앱 로거(INFO)를 보여주지 않으므로, ``flori.*`` 로거에 읽기 좋은
포맷의 StreamHandler를 1회 부착한다(멱등). 마케팅 생성 등 스텝 로그가 콘솔에 그대로 보인다.
"""

import logging
import sys


def configure_logging(level: int = logging.INFO) -> None:
    """``flori.*`` 로거에 핸들러를 1회 부착(멱등). uvicorn 루트 로깅과 독립적으로 동작한다."""
    logger = logging.getLogger("flori")
    if logger.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s | %(message)s", "%H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(level)
    # propagate는 유지(기본 True) — uvicorn은 root에 핸들러를 붙이지 않아 중복 출력이 없고,
    # 테스트의 caplog(root 전파 기반)가 flori.* 로그를 정상 캡처하려면 전파가 필요하다.
