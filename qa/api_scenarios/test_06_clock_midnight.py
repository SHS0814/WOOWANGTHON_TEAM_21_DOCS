"""자정 경계 (run.sh clock 전용). 서버 시각은 오늘 23:59:00 에서 시작한다 (clock_server.py).

Q-007 (R-021): 전날 끝나지 않은 건은 예정 시각 후 6시간 안이면 `GET /dose-events/today`에
`carried_over: true` 로 포함되어야 한다. 그래야 23:59 취침 약을 자정 넘어 찍을 수 있다.
"""

import time

import pytest

from woowang_qa import find_photo, make_family

pytestmark = pytest.mark.clock

NORMAL_BEDTIME = {"r0c0": "full", "r0c1": "full", "r0c2": "full", "r0c3": "empty_hi"}


def server_date(f) -> str:
    return f.eget("/dose-events/today").json()["date"]


def wait_server_date_change(f, before: str, timeout: float = 150) -> str:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        d = server_date(f)
        if d != before:
            return d
        time.sleep(3)
    pytest.fail(f"서버 날짜가 {before} 에서 바뀌지 않음 (clock 프로필 서버인지 확인)")


@pytest.fixture(scope="module")
def crossed():
    """자정 전에 가족 둘을 만들고 취침 약을 연 뒤, 서버 날짜가 바뀔 때까지 기다린다."""
    from woowang_qa import client

    with client() as c:
        fams = [make_family(c) for _ in range(2)]
        day1 = server_date(fams[0])
        evs = [f.trigger("bedtime") for f in fams]  # 23:59 무렵 복약 시각, asked
        assert all(e["state"] == "asked" and e["date"] == day1 for e in evs)
        day2 = wait_server_date_change(fams[0], day1)
        time.sleep(5)  # 자정 직후 예약 작업 한 번
        yield fams, evs, day1, day2


def test_q007_open_event_carried_over_after_midnight(c, crossed):
    fams, evs, day1, day2 = crossed
    f, ev = fams[0], evs[0]
    f.c = c
    elder = f.eget("/dose-events/today").json()
    ids = {i["id"]: i for i in elder["items"]}
    g = f.gget("/dose-events", params={"from": day1, "to": day2}).json()["items"]
    prev = next(i for i in g if i["id"] == ev["id"])
    assert prev["state"] == "asked", prev["state"]  # 아직 끝나지 않은 전날 건
    assert ev["id"] in ids, (
        f"자정 뒤 어르신 '오늘'({day2}) 목록에 전날({day1}) asked 건이 없음 → "
        f"E4 에서 홈으로 돌아가 사진을 찍을 수 없음. items={[(i['date'], i['state']) for i in elder['items']]}"
    )
    assert ids[ev["id"]].get("carried_over") is True
    assert elder["next_event"] and elder["next_event"]["id"] == ev["id"]


def test_q007_upload_after_midnight_to_previous_day_event(c, crossed):
    """현재 동작 확인: 서버는 자정 뒤에도 전날 asked 건의 사진을 받아 기록한다."""
    fams, evs, day1, _ = crossed
    f, ev = fams[1], evs[1]
    f.c = c
    r = f.upload(ev["id"], find_photo(NORMAL_BEDTIME, tag="midnight"))
    assert r.status_code == 200, r.text
    assert r.json()["result"] == "recorded"
    assert r.json()["dose_event"]["date"] == day1
