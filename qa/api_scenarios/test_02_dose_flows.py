"""복약 흐름 시나리오 (backend.md 5·6·7장, api.md 3.17~3.22, R-009, R-010, R-014).

약통은 1×4 (r0c0 아침, r0c1 점심, r0c2 저녁, r0c3 취침), 기준선은 모두 full.
"""

import pytest

from woowang_qa import find_photo, make_family

NORMAL_EVENING = {"r0c0": "full", "r0c1": "full", "r0c2": "empty_hi", "r0c3": "full"}


def no_confidence_numbers(obj) -> bool:
    """보호자 응답에 원본 신뢰도 숫자가 없어야 한다 (R-008 C5)."""
    if isinstance(obj, dict):
        if "confidence" in obj:
            return False
        return all(no_confidence_numbers(v) for v in obj.values())
    if isinstance(obj, list):
        return all(no_confidence_numbers(v) for v in obj)
    return True


def assert_elder_view_clean(f, event_id):
    """어르신 응답에는 판독·인계 정보가 없다 (api.md 2.5, 원칙 6)."""
    ev = f.event(event_id, as_guardian=False)
    assert ev["latest_reading"] is None
    assert ev["handoff"] is None
    assert ev["elder_status"] in ("upcoming", "waiting", "recorded", "no_record")
    return ev


# ---------- S02 정상 ----------


def test_s02_normal_records_quietly(c):
    f = make_family(c)
    ev = f.trigger("evening")
    r = f.upload(ev["id"], find_photo(NORMAL_EVENING))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["result"] == "recorded"
    assert body["is_mock"] is True
    assert body["dose_event"]["latest_reading"] is None  # 어르신 형태

    g = f.event(ev["id"])
    assert g["state"] == "done" and g["outcome"] == "taken" and g["outcome_source"] == "ai"
    assert g["taken_at"] is not None and g["decided_by"] is None
    assert g["is_mock"] is True and g["is_simulated"] is True
    assert g["latest_reading"]["classification"] == "normal"
    assert g["latest_reading"]["is_mock"] is True
    assert no_confidence_numbers(g)

    e = assert_elder_view_clean(f, ev["id"])
    assert e["elder_status"] == "recorded" and len(e["photos"]) == 1

    # 원칙 2: 정상이면 인계·보호자 푸시 없음
    assert f.handoffs("all") == []
    pushes = f.guardian_pushes()
    if pushes is not None:
        assert pushes == [], pushes


def test_s02_client_upload_id_idempotent(c):
    f = make_family(c)
    ev = f.trigger("evening")
    data = find_photo(NORMAL_EVENING)
    r1 = f.upload(ev["id"], data, client_upload_id="qa-retry-1")
    r2 = f.upload(ev["id"], data, client_upload_id="qa-retry-1")
    assert r1.status_code == r2.status_code == 200
    assert r1.json()["result"] == r2.json()["result"] == "recorded"
    assert len(f.event(ev["id"])["photos"]) == 1


# ---------- S03 애매 → 재촬영 → 보호자 판정 ----------


def test_s03_unclear_retake_then_guardian_verdict(c):
    f = make_family(c)
    ev = f.trigger("evening")
    unclear = {"r0c0": "full", "r0c1": "full", "r0c2": "unclear", "r0c3": "full"}
    r = f.upload(ev["id"], find_photo(unclear, tag="a"))
    assert r.json()["result"] == "retake", r.text
    g = f.event(ev["id"])
    assert g["state"] == "retake_requested" and g["retake_deadline_at"]
    assert f.handoffs() == []

    r = f.upload(ev["id"], find_photo(unclear, tag="b"))
    assert r.json()["result"] == "guardian_notified", r.text
    hs = f.handoffs()
    assert len(hs) == 1 and hs[0]["reason"] == "unclear"
    assert hs[0]["allowed_verdicts"] == ["taken", "not_taken"]

    d = f.gget(f"/handoffs/{hs[0]['id']}").json()
    assert len(d["readings"]) == 2
    assert d["layout"]["cols"] == 4
    assert no_confidence_numbers(d)
    tgt = next(x for x in d["readings"][-1]["cells"] if x["cell_id"] == "r0c2")
    assert tgt["attention"] == "unclear" and tgt["expected"] == "empty"
    assert d["readings"][-1]["is_mock"] is True

    r = f.gpost(f"/handoffs/{hs[0]['id']}/verdict", json={"verdict": "acknowledged"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "verdict_not_allowed"
    r = f.gpost(f"/handoffs/{hs[0]['id']}/verdict", json={"verdict": "taken"})
    assert r.status_code == 200, r.text
    g = f.event(ev["id"])
    assert g["state"] == "done" and g["outcome"] == "taken" and g["outcome_source"] == "guardian"
    assert g["decided_by"]["display_name"] == "지훈QA"
    r = f.gpost(f"/handoffs/{hs[0]['id']}/verdict", json={"verdict": "not_taken"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "handoff_already_resolved"
    assert r.json()["error"]["details"]["verdict"] == "taken"

    pushes = f.guardian_pushes()
    if pushes is not None:
        assert len(pushes) == 1 and "'reason': 'unclear'" in pushes[0], pushes


def test_s03_low_confidence_is_unclear_not_taken(c):
    """원칙 5: 대상 칸이 비었어도 신뢰도가 낮으면 정상으로 기록하지 않는다."""
    f = make_family(c)
    ev = f.trigger("evening")
    lo = {"r0c0": "full", "r0c1": "full", "r0c2": "empty_lo", "r0c3": "full"}
    r = f.upload(ev["id"], find_photo(lo))
    assert r.json()["result"] == "retake"
    g = f.event(ev["id"])
    tgt = next(x for x in g["latest_reading"]["cells"] if x["cell_id"] == "r0c2")
    assert tgt["attention"] == "low_confidence"
    # 재촬영이 정상이면 기록
    r = f.upload(ev["id"], find_photo(NORMAL_EVENING, tag="retake"))
    assert r.json()["result"] == "recorded"
    assert f.handoffs("all") == []


# ---------- S04 칸 그대로 (R-009 두 모드) ----------


UNCHANGED = {"r0c0": "full", "r0c1": "full", "r0c2": "full", "r0c3": "full"}


def test_s04_unchanged_remind_then_retake_mode(c):
    f = make_family(c)
    assert f.gget("/settings").json()["unchanged_mode"] == "remind_then_retake"
    ev = f.trigger("evening")
    r = f.upload(ev["id"], find_photo(UNCHANGED, tag="1"))
    assert r.json()["result"] == "remind_retake", r.text
    g = f.event(ev["id"])
    assert g["state"] == "reminded" and g["retake_deadline_at"]
    assert f.handoffs() == []
    # 두 번째도 그대로 → 인계
    r = f.upload(ev["id"], find_photo(UNCHANGED, tag="2"))
    assert r.json()["result"] == "guardian_notified"
    hs = f.handoffs()
    assert [h["reason"] for h in hs] == ["unchanged"]
    assert hs[0]["allowed_verdicts"] == ["taken", "not_taken", "acknowledged"]
    tgt = next(x for x in hs[0]["dose_event"]["latest_reading"]["cells"] if x["cell_id"] == "r0c2")
    assert tgt["attention"] == "unexpected_full"


def test_s04_unchanged_remind_then_normal(c):
    f = make_family(c)
    ev = f.trigger("evening")
    assert f.upload(ev["id"], find_photo(UNCHANGED, tag="x")).json()["result"] == "remind_retake"
    r = f.upload(ev["id"], find_photo(NORMAL_EVENING, tag="after-remind"))
    assert r.json()["result"] == "recorded"
    assert f.handoffs("all") == []


def test_s04_unchanged_handoff_immediately_mode(c):
    f = make_family(c, unchanged_mode="handoff_immediately")
    ev = f.trigger("evening")
    r = f.upload(ev["id"], find_photo(UNCHANGED, tag="imm"))
    assert r.json()["result"] == "guardian_notified", r.text
    assert [h["reason"] for h in f.handoffs()] == ["unchanged"]
    assert f.event(ev["id"])["state"] == "handed_off"


# ---------- S05 이중 복용 의심 ----------


def test_s05_double_suspected(c):
    f = make_family(c)
    ev = f.trigger("evening")
    dbl = {"r0c0": "full", "r0c1": "full", "r0c2": "empty_hi", "r0c3": "empty"}
    r = f.upload(ev["id"], find_photo(dbl))
    assert r.json()["result"] == "guardian_notified", r.text
    hs = f.handoffs()
    assert [h["reason"] for h in hs] == ["double_suspected"]
    cells = {x["cell_id"]: x for x in hs[0]["dose_event"]["latest_reading"]["cells"]}
    assert cells["r0c3"]["attention"] == "unexpected_empty"
    assert hs[0]["dose_event"]["latest_reading"]["classification"] == "double_suspected"
    e = assert_elder_view_clean(f, ev["id"])
    assert e["elder_status"] == "no_record"


def test_s05_handed_off_cell_not_handed_off_again(c):
    """R-007 C2: 이미 인계된 칸(아침)은 다음 복약 때 비교에서 제외한다."""
    f = make_family(c, unchanged_mode="handoff_immediately")
    am = f.trigger("morning")
    r = f.upload(am["id"], find_photo({**UNCHANGED}, tag="am"))
    assert r.json()["result"] == "guardian_notified"
    # 저녁: 아침 칸은 여전히 차 있음 (놓친 약). 저녁 칸만 비었으면 정상
    pm = f.trigger("evening")
    r = f.upload(pm["id"], find_photo(NORMAL_EVENING, tag="pm"))
    assert r.json()["result"] == "recorded", r.text
    cells = {x["cell_id"]: x for x in f.event(pm["id"])["latest_reading"]["cells"]}
    assert cells["r0c0"]["expected"] == "ignored"
    assert cells["r0c0"]["attention"] not in ("unexpected_full", "unexpected_empty")
    assert len(f.handoffs("all")) == 1


# ---------- S08 이미 쓴 칸 (R-014, R-015) ----------


def _take(f, tod, tag):
    ev = f.trigger(tod)
    want = {cid: "full" for cid in ("r0c0", "r0c1", "r0c2", "r0c3")}
    # 이미 드신 칸은 비어 있어야 한다
    for e in f.gget("/dose-events/today").json()["items"]:
        if e["outcome"] == "taken":
            want[e["slot"]["cell_id"]] = "empty"
    want[f.slots[tod]["cell_id"]] = "empty_hi"
    r = f.upload(ev["id"], find_photo(want, tag=tag))
    assert r.json()["result"] == "recorded", (tod, r.text)
    return ev


def test_s08_refill_overdue(c):
    f = make_family(c)
    _take(f, "morning", "am")
    # 같은 칸(r0c0)을 다시 쓰는 일정으로 바꾼다 (이번 주기에 이미 쓴 칸이 대상 칸)
    f.set_schedule({"noon": "r0c0", "evening": "r0c2", "bedtime": "r0c3"})
    ev = f.trigger("noon")
    # 대상 칸 비어 보임 + 다른 칸이 다 차 있지는 않음 (r0c1 unclear) → refill_overdue
    r = f.upload(ev["id"], find_photo({"r0c0": "empty", "r0c1": "unclear", "r0c2": "full",
                                       "r0c3": "full"}, tag="ov"))
    assert r.json()["result"] == "guardian_notified", r.text
    hs = f.handoffs()
    assert [h["reason"] for h in hs] == ["refill_overdue"]
    assert hs[0]["allowed_verdicts"] == ["taken", "not_taken", "acknowledged"]
    g = f.event(ev["id"])
    assert g["state"] == "handed_off" and g["outcome"] is None  # 절대 정상으로 기록하지 않음


def test_s08_refill_unconfirmed_bound_yes(c):
    f = make_family(c)
    _take(f, "morning", "am")
    _take(f, "evening", "pm")
    f.set_schedule({"noon": "r0c0", "bedtime": "r0c3"})
    ev = f.trigger("noon")
    # 대상 칸(r0c0) 비어 보임, 나머지 다 full (r0c2 는 기대 empty) → refill_unconfirmed 에 묶임
    r = f.upload(ev["id"], find_photo({"r0c0": "empty", "r0c1": "full", "r0c2": "full",
                                       "r0c3": "full"}, tag="ru"))
    assert r.json()["result"] == "guardian_notified", r.text
    hs = f.handoffs()
    assert [h["reason"] for h in hs] == ["refill_unconfirmed"]
    assert hs[0]["allowed_verdicts"] == ["refilled", "not_refilled"]
    r = f.gpost(f"/handoffs/{hs[0]['id']}/verdict", json={"verdict": "refilled"})
    assert r.status_code == 200, r.text
    g = f.event(ev["id"])
    assert g["state"] == "done" and g["outcome"] == "taken" and g["outcome_source"] == "guardian"
    cur = f.gget("/pillboxes/current").json()
    assert cur["last_refill"]["source"] == "refill_check"
    pushes = f.guardian_pushes()
    if pushes is not None:
        assert len(pushes) == 1, pushes


def test_s08_refill_unconfirmed_bound_no(c):
    f = make_family(c)
    _take(f, "morning", "am")
    _take(f, "evening", "pm")
    f.set_schedule({"noon": "r0c0", "bedtime": "r0c3"})
    ev = f.trigger("noon")
    r = f.upload(ev["id"], find_photo({"r0c0": "empty", "r0c1": "full", "r0c2": "full",
                                       "r0c3": "full"}, tag="ru"))
    assert r.json()["result"] == "guardian_notified"
    h = f.handoffs()[0]
    r = f.gpost(f"/handoffs/{h['id']}/verdict", json={"verdict": "not_refilled"})
    assert r.status_code == 200, r.text
    hs = f.handoffs()
    # 같은 건에 refill_overdue (푸시 없음)로 판정 대기
    assert [x["reason"] for x in hs] == ["refill_overdue"]
    assert hs[0]["dose_event"]["id"] == ev["id"]
    assert f.event(ev["id"])["state"] == "handed_off"
    pushes = f.guardian_pushes()
    if pushes is not None:
        assert len(pushes) == 1, pushes  # refill_unconfirmed 1건만


# ---------- S09 리필 확인 네/아니요 (묶이지 않은 확인 요청, backend 5.4) ----------


REFILL_SUSPECT_PM = {"r0c0": "full", "r0c1": "full", "r0c2": "empty_hi", "r0c3": "full"}


def test_s09_refill_check_yes(c):
    f = make_family(c)
    _take(f, "morning", "am")
    pm = f.trigger("evening")
    # 아침 칸은 비어 있어야 하는데 다 차 보임 → 정상 기록 + 리필 확인 1회
    r = f.upload(pm["id"], find_photo(REFILL_SUSPECT_PM, tag="rs"))
    assert r.json()["result"] == "recorded", r.text
    hs = f.handoffs()
    assert [h["reason"] for h in hs] == ["refill_unconfirmed"]
    assert f.event(pm["id"])["state"] == "done"
    r = f.gpost(f"/handoffs/{hs[0]['id']}/verdict", json={"verdict": "refilled"})
    assert r.status_code == 200
    assert f.event(pm["id"])["outcome_source"] == "ai"  # 묶이지 않은 확인 요청은 건을 안 바꿈
    cur = f.gget("/pillboxes/current").json()
    assert cur["last_refill"]["source"] == "refill_check"


def test_s09_refill_check_no_then_not_asked_again(c):
    f = make_family(c)
    _take(f, "morning", "am")
    pm = f.trigger("evening")
    r = f.upload(pm["id"], find_photo(REFILL_SUSPECT_PM, tag="rs2"))
    assert r.json()["result"] == "recorded"
    h = f.handoffs()[0]
    r = f.gpost(f"/handoffs/{h['id']}/verdict", json={"verdict": "not_refilled"})
    assert r.status_code == 200
    assert f.handoffs() == []
    # 다음 복약: 아침 칸은 비교 제외(ignored), 다시 묻지 않는다
    bt = f.trigger("bedtime")
    r = f.upload(bt["id"], find_photo({"r0c0": "full", "r0c1": "full", "r0c2": "empty",
                                       "r0c3": "empty_hi"}, tag="bt"))
    assert r.json()["result"] == "recorded", r.text
    cells = {x["cell_id"]: x for x in f.event(bt["id"])["latest_reading"]["cells"]}
    assert cells["r0c0"]["expected"] == "ignored"
    assert f.handoffs() == []


def test_s09_refill_check_not_duplicated_while_open(c):
    f = make_family(c)
    _take(f, "morning", "am")
    pm = f.trigger("evening")
    assert f.upload(pm["id"], find_photo(REFILL_SUSPECT_PM, tag="d1")).json()["result"] == "recorded"
    bt = f.trigger("bedtime")
    r = f.upload(bt["id"], find_photo({"r0c0": "full", "r0c1": "full", "r0c2": "full",
                                       "r0c3": "empty_hi"}, tag="d2"))
    assert r.json()["result"] == "recorded", r.text
    assert [h["reason"] for h in f.handoffs()] == ["refill_unconfirmed"]


# ---------- S10 지난 칸 불일치 (pillbox_mismatch, R-010 2번) ----------


def test_s10_pillbox_mismatch_no_retake_no_push(c):
    f = make_family(c, unchanged_mode="handoff_immediately")
    am = f.trigger("morning")
    assert f.upload(am["id"], find_photo(UNCHANGED, tag="am")).json()["result"] == "guardian_notified"
    _take(f, "noon", "noon")  # r0c1 taken (아침 칸 r0c0 은 ignored)
    pm = f.trigger("evening")
    # r0c0 비어 있음(ignored라 괜찮음), r0c1 차 있음(기대 empty → 불일치), 대상 r0c2 정상
    r = f.upload(pm["id"], find_photo({"r0c0": "empty", "r0c1": "full", "r0c2": "empty_hi",
                                       "r0c3": "full"}, tag="mm"))
    assert r.json()["result"] == "recorded", r.text
    cur = f.gget("/pillboxes/current").json()
    assert cur["pillbox_mismatch"]["detected"] is True
    assert cur["pillbox_mismatch"]["cell_ids"] == ["r0c1"]
    s = f.gget("/summaries", params={"period": "day"}).json()["items"][-1]
    assert s["pillbox_mismatch"] is True
    assert len(f.handoffs("all")) == 1  # 아침 인계 1건뿐
    pushes = f.guardian_pushes()
    if pushes is not None:
        assert len(pushes) == 1, pushes


# ---------- S12 요약 all_normal ----------


def test_s12_summary_all_normal(c):
    f = make_family(c)
    f.set_schedule({"evening": "r0c2"})
    ev = f.trigger("evening")
    assert f.upload(ev["id"], find_photo(NORMAL_EVENING, tag="sum")).json()["result"] == "recorded"
    s = f.gget("/summaries", params={"period": "day"}).json()["items"][-1]
    assert s["counts"]["scheduled"] == 1 and s["counts"]["taken_ai"] == 1
    assert s["all_normal"] is True
    assert s["includes_mock"] is True and s["includes_simulated"] is True
    assert s["final"] is False
    w = f.gget("/summaries", params={"period": "week"}).json()["items"][-1]
    assert w["all_normal"] is True
    assert list(s["handoffs_by_reason"]) == ["no_response", "unclear", "unchanged",
                                             "double_suspected", "refill_unconfirmed",
                                             "refill_overdue"]


def test_s12_summary_not_all_normal_with_handoff(c):
    f = make_family(c, unchanged_mode="handoff_immediately")
    f.set_schedule({"evening": "r0c2"})
    ev = f.trigger("evening")
    f.upload(ev["id"], find_photo(UNCHANGED, tag="s2"))
    s = f.gget("/summaries", params={"period": "day"}).json()["items"][-1]
    assert s["all_normal"] is False
    assert s["counts"]["open_handoffs"] == 1 and s["handoffs_by_reason"]["unchanged"] == 1


# ---------- S13 시연 트리거 ----------


def test_s13_demo_trigger(c):
    f = make_family(c)
    me = f.gget("/me").json()
    assert me["family"]["is_demo"] is True and me["server"]["demo_mode"] is True
    ev = f.trigger("evening")
    assert ev["is_simulated"] is True and ev["state"] == "asked"
    assert ev["handoff_at"] > ev["scheduled_at"]
    e = f.event(ev["id"], as_guardian=False)
    assert e["is_simulated"] is True
    # 같은 칸 두 번 → 409
    r = f.gpost("/dev/dose-events", json={"slot_id": f.slots["evening"]["id"]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "event_already_started"
    # 어르신도 부를 수 있다 (권한 any)
    r = f.epost("/dev/dose-events", json={"slot_id": f.slots["noon"]["id"]})
    assert r.status_code == 201 and r.json()["latest_reading"] is None
    # 없는 slot
    r = f.gpost("/dev/dose-events", json={"slot_id": "nope"})
    assert r.status_code == 404


def test_s13_demo_trigger_not_for_real_family(c):
    f = make_family(c, demo=False)
    r = f.gpost("/dev/dose-events", json={"slot_id": f.slots["evening"]["id"]})
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    me = f.gget("/me").json()
    assert me["family"]["is_demo"] is False


def test_s13_trigger_other_weekday_422(c):
    from woowang_qa import now_kst

    f = make_family(c)
    other = (now_kst().weekday() + 1) % 7
    r = f.gput("/schedule", json={"slots": [
        {"weekday": other, "time_of_day": "evening", "dose_time": "19:00", "cell_id": "r0c2"}]})
    slot = r.json()["slots"][0]
    r = f.gpost("/dev/dose-events", json={"slot_id": slot["id"]})
    assert r.status_code == 422


@pytest.mark.parametrize("tod", ["morning"])
def test_s02_photo_record_visible_in_elder_e8(c, tod):
    """E8 '나 약 먹었나?': 시각과 사진이 보인다 (MVP 3)."""
    f = make_family(c)
    _take(f, tod, "e8")
    items = f.eget("/dose-events/today").json()["items"]
    rec = [i for i in items if i["elder_status"] == "recorded"]
    assert len(rec) == 1 and rec[0]["taken_at"] and rec[0]["photos"][0]["url"]
    r = c.get(rec[0]["photos"][0]["url"].replace("http://127.0.0.1:18200", ""))
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/")
