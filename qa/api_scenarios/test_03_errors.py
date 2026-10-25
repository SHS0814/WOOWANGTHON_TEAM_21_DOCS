"""S14 오류 코드 (api.md 1.5, 5장)와 경계 조건. 이슈 재현 테스트는 이름에 이슈 번호를 붙인다."""

from datetime import timedelta

import pytest

from woowang_qa import API, find_photo, fresh_ip, make_family, now_kst, png, wait_for

NORMAL_EVENING = {"r0c0": "full", "r0c1": "full", "r0c2": "empty_hi", "r0c3": "full"}


def err(r, status, code):
    assert r.status_code == status, (r.status_code, r.text)
    body = r.json()
    assert set(body) == {"error"} and set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == code, body
    return body["error"]


def test_s14_auth_errors(c):
    f = make_family(c, pillbox=False)
    err(c.get(API + "/me"), 401, "unauthorized")
    err(c.get(API + "/me", headers={"Authorization": "Bearer nope"}), 401, "unauthorized")
    err(c.get(API + "/me", headers={"Authorization": "Basic abc"}), 401, "unauthorized")
    err(f.eget("/handoffs"), 403, "forbidden_role")
    err(f.eget("/settings"), 403, "forbidden_role")
    err(f.gpost("/dose-events/x/photo", files={"photo": ("p.png", png(), "image/png")}),
        403, "forbidden_role")
    err(c.get(API + "/no-such-path"), 404, "not_found")


def test_s14_validation_errors(c):
    f = make_family(c, pillbox=False)
    e = err(c.post(API + "/families", json={"elder_display_name": "", "guardian_display_name": "a"},
                   headers=fresh_ip()), 422, "validation_error")
    assert e["details"]["fields"][0]["field"] == "elder_display_name"
    err(c.post(API + "/families", json={"elder_display_name": "가" * 21,
                                       "guardian_display_name": "a"}, headers=fresh_ip()),
        422, "validation_error")
    err(f.gput("/settings", json={"photo_retention_days": 0}), 422, "validation_error")
    err(f.gput("/settings", json={"summary_push_time": "25:00"}), 422, "validation_error")
    err(f.gput("/settings", json={"unchanged_mode": "whatever"}), 422, "validation_error")
    # 약통 없이 일정·리필
    err(f.gput("/schedule", json={"slots": []}), 409, "pillbox_required")
    err(f.gpost("/refills", files={"photo": ("p.png", png(), "image/png")}), 409,
        "pillbox_required")
    err(f.gget("/pillboxes/current"), 404, "pillbox_required")
    err(f.gget("/dose-events", params={"from": "2026-10-01", "to": "2026-11-15"}),
        422, "validation_error")
    err(f.gget("/dose-events", params={"from": "2026-10-24", "to": "2026-10-01"}),
        422, "validation_error")
    err(f.gget("/summaries", params={"period": "month"}), 422, "validation_error")


def test_s14_schedule_validation(c):
    f = make_family(c)
    wd = now_kst().weekday()
    dup_cell = [{"weekday": wd, "time_of_day": t, "dose_time": "23:59", "cell_id": "r0c0"}
                for t in ("morning", "noon")]
    err(f.gput("/schedule", json={"slots": dup_cell}), 422, "validation_error")
    dup_time = [{"weekday": wd, "time_of_day": "noon", "dose_time": "23:59", "cell_id": cid}
                for cid in ("r0c0", "r0c1")]
    err(f.gput("/schedule", json={"slots": dup_time}), 422, "validation_error")
    err(f.gput("/schedule", json={"slots": [{"weekday": wd, "time_of_day": "noon",
                                             "dose_time": "23:59", "cell_id": "r9c9"}]}),
        422, "validation_error")
    err(f.gpost("/pillboxes", json={"photo_id": "nope", "layout": {"rows": 1, "cols": 4}}),
        404, "not_found")
    det = f.gpost("/pillboxes/detect", files={"photo": ("p.png", png(), "image/png")}).json()
    err(f.gpost("/pillboxes", json={"photo_id": det["photo"]["id"],
                                    "layout": {"rows": 8, "cols": 4}}), 422, "validation_error")
    err(f.gpost("/pillboxes", json={"photo_id": det["photo"]["id"],
                                    "layout": {"rows": 1, "cols": 4, "col_labels": ["a"]}}),
        422, "validation_error")


def test_s14_photo_upload_errors(c):
    f = make_family(c)
    ev = f.trigger("evening")
    err(f.upload(ev["id"], b"not an image at all"), 415, "unsupported_media")
    err(f.upload(ev["id"], b""), 415, "unsupported_media")
    err(f.upload(ev["id"], b"\x89PNG\r\n\x1a\n" + b"0" * (10 * 1024 * 1024)), 413,
        "photo_too_large")
    err(f.upload("no-such-event", png()), 404, "not_found")
    assert f.upload(ev["id"], find_photo(NORMAL_EVENING)).json()["result"] == "recorded"
    err(f.upload(ev["id"], png()), 409, "event_not_open")  # 이미 done
    err(f.gpost("/pillboxes/detect", files={"photo": ("p.txt", b"hello", "text/plain")}), 415,
        "unsupported_media")


def test_s14_early_photo_window(c):
    """R-010 13번: scheduled 건 사진은 복약 시각 60분 전부터만 받는다."""
    n = now_kst()
    near, far = n + timedelta(minutes=30), n + timedelta(minutes=90)
    if far.date() != n.date():
        pytest.skip("자정 근처라 오늘 안에 +90분 일정을 둘 수 없음")
    f = make_family(c, schedule=False)
    wd = n.weekday()
    f.gput("/schedule", json={"slots": [
        {"weekday": wd, "time_of_day": "evening", "dose_time": near.strftime("%H:%M"),
         "cell_id": "r0c2"},
        {"weekday": wd, "time_of_day": "bedtime", "dose_time": far.strftime("%H:%M"),
         "cell_id": "r0c3"},
    ]})
    items = {i["slot"]["time_of_day"]: i for i in f.eget("/dose-events/today").json()["items"]}
    assert items["evening"]["state"] == "scheduled"
    assert items["evening"]["elder_status"] == "upcoming"
    err(f.upload(items["bedtime"]["id"], png()), 409, "event_not_open")
    r = f.upload(items["evening"]["id"], find_photo(NORMAL_EVENING, tag="early"))
    assert r.status_code == 200 and r.json()["result"] == "recorded", r.text


def test_s14_photo_url_signature(c):
    f = make_family(c)
    ev = f.trigger("evening")
    f.upload(ev["id"], find_photo(NORMAL_EVENING, tag="sig"))
    p = f.event(ev["id"])["photos"][0]
    assert c.get(p["url"]).status_code == 200
    err(c.get(p["url"].replace("sig=", "sig=x")), 403, "signature_invalid")
    err(c.get(API + f"/photo-files/{p['id']}?exp=1&sig=abc"), 403, "signature_invalid")
    r = f.eget(f"/photos/{p['id']}")
    assert r.status_code == 200 and r.json()["url"]
    other = make_family(c, pillbox=False)
    err(other.gget(f"/photos/{p['id']}"), 404, "not_found")


def test_s14_baseline_edit_and_refill_not_latest(c):
    f = make_family(c)
    old = f.refill["id"]
    r = f.gput(f"/refills/{old}/baseline", json={"cells": [{"cell_id": "r0c1", "state": "full"}]})
    assert r.status_code == 200 and r.json()["baseline_cells"][1]["edited"] is True
    r = f.gpost("/refills", files={"photo": ("p.png", png("rf"), "image/png")})
    assert r.status_code == 201, r.text
    assert r.json()["source"] == "guardian_photo"
    assert r.json()["baseline_reading"]["is_mock"] is True
    err(f.gput(f"/refills/{old}/baseline", json={"cells": [{"cell_id": "r0c1",
                                                            "state": "full"}]}),
        409, "refill_not_latest")
    err(f.gput(f"/refills/{r.json()['id']}/baseline", json={"cells": [{"cell_id": "zz",
                                                                       "state": "full"}]}),
        422, "validation_error")


def test_s14_pair_rate_limited(c):
    ip = fresh_ip()
    for _ in range(5):
        err(c.post(API + "/pair", json={"code": "bad"}, headers=ip), 400, "code_invalid")
    r = c.post(API + "/pair", json={"code": "bad"}, headers=ip)
    err(r, 429, "rate_limited")
    assert int(r.headers["retry-after"]) > 0


def test_s14_refill_status_numbers(c):
    """G7: 남은 칸·리필 기준 (R-010 5번: 하루 복용 횟수 × 2)."""
    f = make_family(c)
    st = f.gget("/pillboxes/current").json()["refill_status"]
    assert st["remaining_cells"] == 4 and st["threshold_cells"] == 8
    assert st["needs_refill"] is True
    assert st["covered_until"]["time_of_day"] in ("morning", "noon", "evening", "bedtime")


# ---------- 이슈 재현 (실패하면 이슈가 아직 있음) ----------


def test_q001_new_schedule_does_not_hand_off_past_times_today(c):
    """일정을 저장한 시각보다 이른 오늘 복약 시각은 무응답 인계되면 안 된다 (원칙 2)."""
    n = now_kst()
    if n.hour < 1:
        pytest.skip("자정 직후에는 '오늘 이미 지난 시각'을 만들 수 없음")
    f = make_family(c, schedule=False)
    past = (n - timedelta(minutes=45)).strftime("%H:%M")
    f.gput("/schedule", json={"slots": [
        {"weekday": n.weekday(), "time_of_day": "morning", "dose_time": past, "cell_id": "r0c0"}]})
    # T-BE4 이후 인계는 1분 예약 작업이 한다 → 최대 70초 기다려 본다
    wait_for(lambda: f.handoffs(), timeout=70)
    items = f.gget("/dose-events/today").json()["items"]
    hs = f.handoffs()
    pushes = f.guardian_pushes() or []
    assert hs == [], (
        f"일정 저장 직후 지난 시각({past}) 건이 바로 인계됨: "
        f"{[(i['slot']['dose_time'], i['state']) for i in items]}, 푸시 {len(pushes)}건"
    )


@pytest.mark.parametrize("field", ["elder_display_name", "guardian_display_name"])
def test_q002_blank_names_rejected(c, field):
    """호칭·이름이 공백뿐이면 거절해야 한다 (strip 뒤 빈 문자열이 저장됨)."""
    body = {"elder_display_name": "할머니", "guardian_display_name": "지훈", field: "   "}
    r = c.post(API + "/families", json=body, headers=fresh_ip())
    assert r.status_code == 422, f"공백 이름이 받아들여짐: {r.status_code} {r.text[:200]}"
