import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from woowang_qa import client, make_family, seconds_until_midnight  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "fast: 인계 기한을 짧게 둔 서버(run.sh fast)에서만 돌린다")
    config.addinivalue_line("markers", "clock: 서버 시각을 옮긴 서버(run.sh clock)에서만 돌린다")


@pytest.fixture(scope="session", autouse=True)
def _not_near_midnight():
    # 시나리오는 "오늘 요일" 일정을 쓴다. 자정을 넘기면 시연 트리거가 422 가 된다
    # (clock 프로필은 서버 시각을 따로 쓰므로 실제 시각을 보지 않는다)
    if not os.environ.get("QA_CLOCK") and seconds_until_midnight() < 10 * 60:
        pytest.exit("자정 10분 전부터는 돌리지 않는다 (오늘 요일 일정이 바뀜)", returncode=2)


@pytest.fixture
def c():
    with client() as cl:
        yield cl


@pytest.fixture
def fam(c):
    return make_family(c)
