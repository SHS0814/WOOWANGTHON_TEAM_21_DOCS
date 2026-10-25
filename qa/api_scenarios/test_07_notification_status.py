"""S18 알림 준비 상태 보고 (api.md 2.7·3.17·3.29, R-032·R-033).

ready = notifications_allowed && exact_alarm_allowed !== false.
보호자 경고(elder_notification_warning)는 해제 안 된 어르신 기기 중 보고했고 ready=false가 있을 때만.
보고가 없으면 경고하지 않는다 (원칙 2). 오래된 보고로는 경고하지 않는다 (R-033).
"""

import time

import pytest

from woowang_qa import API, fresh_ip, make_family


def warning(f):
    r = f.gget("/dose-events/today")
    assert r.status_code == 200, r.text
    return r.json()["elder_notification_warning"]


def report(f, who, notif, exact):
    hdr = f.e if who == "elder" else f.g
    return f.c.put(API + "/devices/me/notification-status", headers=hdr,
                   json={"notifications_allowed": notif, "exact_alarm_allowed": exact})


def elder_device(f):
    return next(d for d in f.gget("/devices").json()["items"] if d["role"] == "elder")


def test_s18_no_report_no_warning(c):
    f = make_family(c)
    assert warning(f) is False
    assert f.eget("/dose-events/today").json()["elder_notification_warning"] is None  # 어르신은 null
    assert f.eget("/me").json()["device"]["notification_status"] is None
    assert elder_device(f)["notification_status"] is None


@pytest.mark.parametrize("notif,exact,ready", [
    (True, True, True),
    (True, None, True),     # iOS·Android 11 이하
    (True, False, False),   # 정확한 알람 권한 없음 (Android 14+ 기본)
    (False, True, False),
    (False, None, False),
])
def test_s18_ready_and_warning(c, notif, exact, ready):
    f = make_family(c)
    r = report(f, "elder", notif, exact)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["notifications_allowed"] is notif and body["exact_alarm_allowed"] is exact
    assert body["ready"] is ready and body["reported_at"]
    assert warning(f) is (not ready)
    st = elder_device(f)["notification_status"]
    assert st["ready"] is ready and st["reported_at"] == body["reported_at"]
    assert f.eget("/me").json()["device"]["notification_status"]["ready"] is ready


def test_s18_warning_clears_when_fixed(c):
    f = make_family(c)
    report(f, "elder", True, False)
    assert warning(f) is True
    report(f, "elder", True, True)
    assert warning(f) is False


def test_s18_reported_at_updates_on_same_value(c):
    f = make_family(c)
    a = report(f, "elder", True, True).json()["reported_at"]
    time.sleep(1.1)
    b = report(f, "elder", True, True).json()["reported_at"]
    assert b > a


def test_s18_guardian_report_not_counted(c):
    f = make_family(c)
    r = report(f, "guardian", False, False)
    assert r.status_code == 200
    assert warning(f) is False
    me = next(d for d in f.gget("/devices").json()["items"] if d["is_me"])
    assert me["notification_status"]["ready"] is False  # 저장은 되지만 경고에는 안 씀


def test_s18_revoked_elder_excluded(c):
    f = make_family(c)
    report(f, "elder", True, False)
    assert warning(f) is True
    old_elder = f.e_device
    assert c.delete(API + f"/devices/{old_elder}", headers=f.g).status_code == 204
    assert warning(f) is False
    # 새 어르신 기기를 연결 (보고 전) → 경고 없음
    code = f.gpost("/pairing-codes", json={"kind": "elder"}).json()["code"]
    r = c.post(API + "/pair", json={"code": code}, headers=fresh_ip())
    assert r.status_code == 201 and r.json()["device"]["notification_status"] is None
    assert warning(f) is False


def test_s18_pre_consent_report_allowed(c):
    f = make_family(c, consent=False, pillbox=False)
    r = report(f, "elder", True, False)
    assert r.status_code == 200, r.text
    assert warning(f) is True  # 동의 전 기기도 해제 안 된 어르신 기기


@pytest.mark.parametrize("body", [
    {"notifications_allowed": True},                       # exact 키 없음
    {"exact_alarm_allowed": True},                         # notifications 키 없음
    {"notifications_allowed": "maybe", "exact_alarm_allowed": True},
    {"notifications_allowed": True, "exact_alarm_allowed": [1]},
    {"notifications_allowed": None, "exact_alarm_allowed": True},
])
def test_s18_validation(c, body):
    f = make_family(c, pillbox=False)
    r = c.put(API + "/devices/me/notification-status", headers=f.e, json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error", (body, r.text)


def test_s18_auth(c):
    r = c.put(API + "/devices/me/notification-status",
              json={"notifications_allowed": True, "exact_alarm_allowed": True})
    assert r.status_code == 401
