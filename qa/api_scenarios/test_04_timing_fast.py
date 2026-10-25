"""시간이 필요한 시나리오. run.sh fast 프로필(NO_RESPONSE_HANDOFF_MIN=1, RETAKE_WAIT_MIN=1)에서만 돈다.

서버에 시각을 옮기는 HTTP 수단이 없어서 실제로 기다린다 (테스트 하나에 약 1분).
S06 무응답 → 인계, S07 늦은 사진, S04 +30분 규칙(C3), 재촬영·안내 기한 초과, 판독 한도.
T-BE4 이후 인계는 1분 예약 작업이 하므로 기한 + 최대 1분을 기다린다 (wait_for).
"""

import time

import pytest

from woowang_qa import find_photo, make_family, wait_for

pytestmark = pytest.mark.fast

NORMAL_EVENING = {"r0c0": "full", "r0c1": "full", "r0c2": "empty_hi", "r0c3": "full"}
UNCHANGED = {c: "full" for c in ("r0c0", "r0c1", "r0c2", "r0c3")}
UNCLEAR = {"r0c0": "full", "r0c1": "full", "r0c2": "unclear", "r0c3": "full"}


def wait_past(seconds_from: float, seconds: float):
    left = seconds_from + seconds - time.monotonic()
    if left > 0:
        time.sleep(left)


@pytest.fixture(scope="module")
def timing():
    from woowang_qa import client

    with client() as c:
        f = make_family(c, pillbox=False)
        t = f.gget("/me").json()["server"]["timing"]
    if t["no_response_handoff_min"] != 1 or t["retake_wait_min"] != 1:
        pytest.skip(f"fast 프로필 서버가 아님: {t}")
    return t


def test_s06_no_response_handoff_once(c, timing):
    f = make_family(c)
    t0 = time.monotonic()
    ev = f.trigger("evening")
    assert f.event(ev["id"])["state"] == "asked"
    wait_past(t0, 60)
    g = wait_for(lambda: (x := f.event(ev["id"]))["state"] == "handed_off" and x)
    assert g and g["handoff"]["reason"] == "no_response", f.event(ev["id"])["state"]
    f.event(ev["id"])  # 다시 조회해도 새 인계가 생기지 않는다 (순차 요청)
    hs = f.handoffs()
    assert [h["reason"] for h in hs] == ["no_response"]
    assert hs[0]["allowed_verdicts"] == ["taken", "not_taken", "acknowledged"]
    e = f.event(ev["id"], as_guardian=False)
    assert e["elder_status"] == "no_record" and e["handoff"] is None
    pushes = f.guardian_pushes()
    if pushes is not None:
        assert len(pushes) == 1 and "no_response" in pushes[0], pushes


def test_s07_late_photo_after_no_response(c, timing):
    f = make_family(c)
    t0 = time.monotonic()
    ev = f.trigger("evening")
    wait_past(t0, 60)
    assert wait_for(lambda: f.event(ev["id"])["state"] == "handed_off")
    r = f.upload(ev["id"], find_photo(NORMAL_EVENING, tag="late"))
    assert r.status_code == 200, r.text
    assert r.json()["result"] == "recorded"  # api.md 3.18: 늦은 사진 정상이면 recorded, 인계는 연 채로
    hs = f.handoffs()
    assert len(hs) == 1 and hs[0]["reason"] == "no_response" and hs[0]["late_photo"] is True
    g = f.event(ev["id"])
    assert g["state"] == "handed_off" and len(g["photos"]) == 1
    pushes = f.guardian_pushes()
    if pushes is not None:
        assert len(pushes) == 1, pushes  # 다시 알리지 않음
    # 늦은 사진이 칸 그대로여도 새 인계·푸시 없음
    r = f.upload(ev["id"], find_photo(UNCHANGED, tag="late2"))
    assert r.json()["result"] == "guardian_notified"
    assert len(f.handoffs("all")) == 1


def test_s04_reminded_timeout_hands_off_unchanged(c, timing):
    f = make_family(c)
    ev = f.trigger("evening")
    t0 = time.monotonic()
    assert f.upload(ev["id"], find_photo(UNCHANGED, tag="rm")).json()["result"] == "remind_retake"
    wait_past(t0, 60)
    g = wait_for(lambda: (x := f.event(ev["id"]))["state"] == "handed_off" and x)
    assert g and g["handoff"]["reason"] == "unchanged", f.event(ev["id"])["state"]
    assert len(f.handoffs()) == 1
    # Q-006 (R-021): 안내 후 재촬영 없이 인계된 건도 안내 시각이 보호자에게 보인다 (G5 문구 근거)
    assert g.get("reminded_at"), "reminded_at 없음 (api.md 2.5)"


def test_s03_retake_timeout_hands_off_unclear(c, timing):
    f = make_family(c)
    ev = f.trigger("evening")
    t0 = time.monotonic()
    assert f.upload(ev["id"], find_photo(UNCLEAR, tag="rt")).json()["result"] == "retake"
    wait_past(t0, 60)
    g = wait_for(lambda: (x := f.event(ev["id"]))["state"] == "handed_off" and x)
    assert g and g["handoff"]["reason"] == "unclear", f.event(ev["id"])["state"]
    assert len(f.handoffs()) == 1


def test_s04_no_remind_after_handoff_deadline_c3(c, timing):
    """R-007 C3: '약 드실 시간이에요' 안내는 복약 시각 +인계 기한 안에서만."""
    f = make_family(c)
    t0 = time.monotonic()
    ev = f.trigger("evening")
    wait_past(t0, 40)
    assert f.upload(ev["id"], find_photo(UNCLEAR, tag="c3a")).json()["result"] == "retake"
    wait_past(t0, 70)  # 인계 기한(1분) 지남, 재촬영 기한(업로드 +1분)은 남음
    assert f.event(ev["id"])["state"] == "retake_requested"
    r = f.upload(ev["id"], find_photo(UNCHANGED, tag="c3b"))
    assert r.json()["result"] == "guardian_notified", r.text  # remind_retake 가 아님
    hs = f.handoffs()
    assert [h["reason"] for h in hs] == ["unchanged"]


def test_s14_daily_reading_limit_hands_off(c, timing):
    """가족당 하루 판독 한도(fast 프로필 8회). 넘으면 판독 없이 unclear 인계 (backend 6장)."""
    f = make_family(c)  # 등록 판독 2회 (구조 + 기준선)
    seq = [("evening", UNCLEAR, "retake"), ("evening", UNCLEAR, "guardian_notified"),
           ("morning", UNCHANGED, "remind_retake"), ("morning", UNCHANGED, "guardian_notified"),
           ("noon", UNCLEAR, "retake"), ("noon", UNCLEAR, "guardian_notified")]
    events = {}
    for i, (tod, want, expect) in enumerate(seq):
        if tod not in events:
            events[tod] = f.trigger(tod)
        r = f.upload(events[tod]["id"], find_photo(want, tag=f"lim{i}"))
        assert r.json()["result"] == expect, (i, r.text)
    ev = f.trigger("bedtime")  # 판독 8회 사용 → 한도
    r = f.upload(ev["id"], find_photo({**NORMAL_EVENING, "r0c2": "any", "r0c3": "empty_hi"},
                                      tag="over"))
    assert r.json()["result"] == "guardian_notified", r.text
    assert r.json()["is_mock"] is False
    h = [x for x in f.handoffs() if x["dose_event"]["id"] == ev["id"]]
    assert h and h[0]["reason"] == "unclear"
    r = f.gpost("/refills", files={"photo": ("p.png", b"\x89PNG\r\n\x1a\nlim", "image/png")})
    assert r.status_code == 429 and r.json()["error"]["code"] == "daily_reading_limit"


def test_q008_no_response_handoff_latency(c, timing):
    """Q-008: 무응답 인계는 기한 + 최대 1분 안에 생겨야 한다 (api.md 1.6 "최대 1분 늦게").

    1회 관찰된 11분 지연은 결정적으로 재현할 수단이 없다. 이 테스트는 여러 건의 지연을 재서
    기준(75초)을 넘으면 실패한다. 지연은 notified_at - handoff_at 으로 잰다 (서버 시각끼리 비교).
    """
    from datetime import datetime

    fams = []
    for i in range(3):  # 20초 간격으로 열어 예약 작업 주기의 여러 위치에 걸치게 한다
        f = make_family(c)
        fams.append((f, f.trigger("evening")))
        if i < 2:
            time.sleep(20)
    lates = []
    for f, ev in fams:
        h = wait_for(lambda f=f: f.handoffs(), timeout=200, every=2)
        assert h, "인계가 생기지 않음"
        late = (datetime.fromisoformat(h[0]["notified_at"])
                - datetime.fromisoformat(ev["handoff_at"])).total_seconds()
        lates.append(late)
    print("no_response 지연(초):", lates)
    assert max(lates) <= 75, f"무응답 인계 지연이 75초를 넘음: {lates}"


def test_q004_late_normal_photo_is_recorded_for_elder(c, timing):
    """Q-004 (R-021, api.md 2.5·3.18): 늦은 정상 사진은 어르신 기준 recorded, taken_at=사진 촬영 시각.
    보호자 인계는 열린 채(late_photo), outcome 은 판정 전까지 null. not_taken 판정이면 no_record."""
    fams = [make_family(c) for _ in range(3)]
    t0 = time.monotonic()
    evs = [f.trigger("evening") for f in fams]
    wait_past(t0, 60)
    for f, ev in zip(fams, evs):
        assert wait_for(lambda f=f, ev=ev: f.event(ev["id"])["state"] == "handed_off")
    shot = "2026-10-25T12:00:00+09:00"
    for i, (f, ev) in enumerate(zip(fams, evs)):
        r = f.upload(ev["id"], find_photo(NORMAL_EVENING, tag=f"q004-{i}"), taken_at=shot)
        assert r.json()["result"] == "recorded", r.text
        e = f.event(ev["id"], as_guardian=False)
        assert e["elder_status"] == "recorded", f"E7a 는 '기록해 뒀어요'인데 E8 은 {e['elder_status']}"
        assert e["taken_at"] == shot
        g = f.event(ev["id"])
        assert g["state"] == "handed_off" and g["outcome"] is None
        assert g["handoff"]["reason"] == "no_response" and g["handoff"]["verdict"] is None
        h = f.handoffs()
        assert len(h) == 1 and h[0]["late_photo"] is True
    # 보호자 판정별 어르신 표시
    for f, ev, verdict, want in zip(fams, evs, ["not_taken", "acknowledged", "taken"],
                                    ["no_record", "recorded", "recorded"]):
        h = f.handoffs()[0]
        r = f.gpost(f"/handoffs/{h['id']}/verdict", json={"verdict": verdict})
        assert r.status_code == 200, r.text
        e = f.event(ev["id"], as_guardian=False)
        assert e["elder_status"] == want, (verdict, e["elder_status"])
        if verdict == "taken":
            assert e["taken_at"] == shot  # 판정 시각이 아니라 늦은 사진 시각 (api.md 2.5)
        if verdict == "not_taken":
            assert e["taken_at"] is None
