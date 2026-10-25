"""자정 경계 (run.sh clock 전용). 서버 시각은 오늘 23:58:00 에서 시작한다 (clock_server.py).

Q-007 (R-021): 전날 끝나지 않은 건은 예정 시각 후 6시간 안이면 `GET /dose-events/today`에
`carried_over: true` 로 포함되어야 한다. 그래야 23:59 취침 약을 자정 넘어 찍을 수 있다.
api.md 3.17 (a50c805): 전날 건 중 asked·retake_requested·reminded 이거나 사진 없는 handed_off(no_response)인
건을 예정 시각 후 6시간 안이면 items 앞쪽에, date 는 원래 날짜 그대로. 끝난 건은 넣지 않는다.
6시간 경계는 실제로 6시간을 기다려야 해서 다루지 않는다.
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
    """자정 전에 가족 셋을 준비하고 서버 날짜가 바뀔 때까지 기다린다.

    0: 취침 약 asked 로 둠 (carried_over 대상), 1: 같은 상태, 자정 뒤 사진 업로드용,
    2: 자정 전에 정상 기록 끝냄 (carried_over 아님)
    """
    from woowang_qa import client

    with client() as c:
        fams = [make_family(c) for _ in range(3)]
        day1 = server_date(fams[0])
        evs = [f.trigger("bedtime") for f in fams]
        assert all(e["state"] == "asked" and e["date"] == day1 for e in evs)
        r = fams[2].upload(evs[2]["id"], find_photo(NORMAL_BEDTIME, tag="before-midnight"))
        assert r.json()["result"] == "recorded", r.text
        day2 = wait_server_date_change(fams[0], day1)
        time.sleep(5)  # 자정 직후 예약 작업 한 번
        yield fams, evs, day1, day2


def test_q007_open_event_carried_over_after_midnight(c, crossed):
    fams, evs, day1, day2 = crossed
    f, ev = fams[0], evs[0]
    f.c = c
    g = f.gget("/dose-events", params={"from": day1, "to": day2}).json()["items"]
    prev = next(i for i in g if i["id"] == ev["id"])
    assert prev["state"] == "asked", prev["state"]  # 아직 끝나지 않은 전날 건
    for who in ("elder", "guardian"):
        body = (f.eget if who == "elder" else f.gget)("/dose-events/today").json()
        assert body["date"] == day2
        ids = {i["id"]: i for i in body["items"]}
        assert ev["id"] in ids, (
            f"[{who}] 자정 뒤 '오늘'({day2}) 목록에 전날({day1}) asked 건이 없음 → "
            f"E4 에서 홈으로 돌아가 사진을 찍을 수 없음. items={[(i['date'], i['state']) for i in body['items']]}"
        )
        item = ids[ev["id"]]
        assert item["carried_over"] is True and item["date"] == day1
        assert body["items"][0]["id"] == ev["id"]  # 앞쪽
        assert all(i["carried_over"] is False for i in body["items"] if i["date"] == day2)
        # next_event 는 "다음 약"이라 전날 건을 가리키지 않는다 (BE dose.py, FE elder/index.tsx 가 같은 해석)
        assert body["next_event"] is None or body["next_event"]["id"] != ev["id"]


def test_q007_finished_event_not_carried_over(c, crossed):
    fams, evs, _, _ = crossed
    f, ev = fams[2], evs[2]
    f.c = c
    items = f.eget("/dose-events/today").json()["items"]
    assert ev["id"] not in [i["id"] for i in items], "자정 전에 끝난 건이 오늘 목록에 다시 나옴"


def test_q007_upload_after_midnight_to_previous_day_event(c, crossed):
    """서버는 자정 뒤에도 전날 asked 건의 사진을 받아 기록한다.

    R-024: 자정 뒤 찍어 기록된 전날 건도 6시간 안에는 오늘 목록에 남는다 (올리자마자 빠지면
    E8 이 "기록 없음"을 보여 이중 복용을 부를 수 있음). api.md 3.17 문구에는 아직 없다.
    """
    fams, evs, day1, _ = crossed
    f, ev = fams[1], evs[1]
    f.c = c
    r = f.upload(ev["id"], find_photo(NORMAL_BEDTIME, tag="midnight"))
    assert r.status_code == 200, r.text
    assert r.json()["result"] == "recorded"
    assert r.json()["dose_event"]["date"] == day1
    items = {i["id"]: i for i in f.eget("/dose-events/today").json()["items"]}
    assert ev["id"] in items, "자정 뒤 기록한 전날 건이 바로 오늘 목록에서 빠짐 (R-024)"
    assert items[ev["id"]]["carried_over"] is True
    assert items[ev["id"]]["elder_status"] == "recorded"
