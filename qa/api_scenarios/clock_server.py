"""QA 전용 서버 실행기: 서버 시각을 QA_CLOCK_START 에서 시작하게 옮겨서 띄운다 (T-QA1b).

제품 코드는 고치지 않는다. 서버는 현재 시각을 `app.clock.clock.now()` 한 곳에서만 읽으므로
(`app/clock.py`), 그 메서드를 "실제 시각 + 고정 오프셋"으로 바꿔서 자정 경계 같은 시나리오를
실제 시간 몇 분 안에 재현한다. 시각은 실제 속도로 흐른다. `/health` 의 time 만 실제 시각이다.

    QA_CLOCK_START=2026-10-25T23:59:00+09:00 uv run --no-sync python <이 파일> --port 18200
    (작업 디렉터리는 _targets/BE)
"""

import argparse
import os
from datetime import UTC, datetime

import uvicorn

from app.clock import clock

start = datetime.fromisoformat(os.environ["QA_CLOCK_START"])
offset = start - datetime.now(UTC)
clock.now = lambda: datetime.now(UTC) + offset  # 인스턴스 메서드만 바꾼다

from app.main import create_app  # noqa: E402  (시계를 바꾼 뒤에 앱을 만든다)

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=18200)
ap.add_argument("--log-config")
args = ap.parse_args()
uvicorn.run(create_app(), host="127.0.0.1", port=args.port, log_config=args.log_config)
