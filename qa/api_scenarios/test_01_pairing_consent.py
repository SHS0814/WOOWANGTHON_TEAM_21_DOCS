"""S01 짝짓기와 동의, S11 기기 해제 → token_revoked (api.md 3.2~3.9, backend.md 3장)."""

from woowang_qa import API, fresh_ip, make_family, png


def test_s01_pairing_and_consent_flow(c):
    f = make_family(c, consent=False, pillbox=False)
    me = f.eget("/me")
    assert me.status_code == 200
    body = me.json()
    assert body["consent_required"] is True
    assert body["device"]["role"] == "elder"
    # 호칭은 보호자가 입력한 값이 그대로 내려온다 (하드코딩 없음)
    assert body["family"]["elder_display_name"] == "할머니QA"
    assert body["family"]["guardians"][0]["display_name"] == "지훈QA"
    assert body["server"]["reader_is_mock"] is True
    for k in ("reask_offsets_min", "no_response_handoff_min", "retake_wait_min"):
        assert k in body["server"]["timing"]

    # 동의 전: 복약 API 는 403 consent_required, 허용 3개는 통과
    r = f.eget("/dose-events/today")
    assert r.status_code == 403 and r.json()["error"]["code"] == "consent_required"
    r = f.eget("/schedule")
    assert r.status_code == 403 and r.json()["error"]["code"] == "consent_required"
    r = c.put(API + "/devices/me/push-token", headers=f.e, json={"push_token": None})
    assert r.status_code == 204

    # agreed=false 는 422
    r = f.epost("/consent", json={"agreed": False, "consent_text_version": "v1",
                                  "ai_external_transfer_shown": False})
    assert r.status_code == 422

    r = f.epost("/consent", json={"agreed": True, "consent_text_version": "v1",
                                  "ai_external_transfer_shown": False})
    assert r.status_code == 200 and r.json()["consent_at"]
    assert f.eget("/me").json()["consent_required"] is False
    assert f.eget("/dose-events/today").status_code == 200

    # 보호자는 동의 API 를 못 쓴다
    r = f.gpost("/consent", json={"agreed": True, "consent_text_version": "v1",
                                  "ai_external_transfer_shown": False})
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden_role"


def test_s01_pair_code_errors(c):
    f = make_family(c, consent=False, pillbox=False)
    r = c.post(API + "/pair", json={"code": "nope-not-a-code"}, headers=fresh_ip())
    assert r.status_code == 400 and r.json()["error"]["code"] == "code_invalid"

    code = f.gpost("/pairing-codes", json={"kind": "elder"}).json()
    assert len(code["short_code"]) == 6
    # 새 elder 코드를 발급하면 이전 것은 무효
    code2 = f.gpost("/pairing-codes", json={"kind": "elder"}).json()
    r = c.post(API + "/pair", json={"code": code["code"]}, headers=fresh_ip())
    assert r.status_code == 410 and r.json()["error"]["code"] == "code_used"

    # 6자리 예비 코드로 연결 → 이전 어르신 기기는 자동 해제
    r = c.post(API + "/pair", json={"short_code": code2["short_code"]}, headers=fresh_ip())
    assert r.status_code == 201, r.text
    r = f.eget("/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "token_revoked"

    # 사용된 코드 재사용
    r = c.post(API + "/pair", json={"code": code2["code"]}, headers=fresh_ip())
    assert r.status_code == 410 and r.json()["error"]["code"] == "code_used"

    # code 와 short_code 동시
    r = c.post(API + "/pair", json={"code": "a", "short_code": "123456"}, headers=fresh_ip())
    assert r.status_code == 422


def test_s01_guardian_invite(c):
    f = make_family(c, pillbox=False)
    inv = f.gpost("/pairing-codes", json={"kind": "guardian"}).json()
    assert inv["short_code"] is None
    # 이름 없이 합류 → 422
    r = c.post(API + "/pair", json={"code": inv["code"]}, headers=fresh_ip())
    assert r.status_code == 422
    r = c.post(API + "/pair", json={"code": inv["code"], "display_name": "민지QA"},
               headers=fresh_ip())
    assert r.status_code == 201, r.text
    assert r.json()["consent_required"] is False
    assert [g["display_name"] for g in r.json()["family"]["guardians"]] == ["지훈QA", "민지QA"]
    # 기존 보호자에게 "추가됐어요" 푸시 (서버 로그가 있을 때만 확인)
    pushes = f.guardian_pushes()
    if pushes is not None:
        assert any("보호자로 추가됐어요" in p for p in pushes), pushes


def test_s11_revoke_device_token_revoked(c):
    f = make_family(c, pillbox=False)
    devices = f.gget("/devices").json()["items"]
    assert {d["role"] for d in devices} == {"guardian", "elder"}
    r = c.delete(API + f"/devices/{f.e_device}", headers=f.g)
    assert r.status_code == 204
    r = f.eget("/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "token_revoked"
    assert f.e_device not in [d["id"] for d in f.gget("/devices").json()["items"]]
    # 다시 해제 → 404
    r = c.delete(API + f"/devices/{f.e_device}", headers=f.g)
    assert r.status_code == 404
    # 마지막 보호자는 해제 불가
    r = c.delete(API + f"/devices/{f.g_device}", headers=f.g)
    assert r.status_code == 409 and r.json()["error"]["code"] == "last_guardian"


def test_s11_other_family_isolation(c):
    a = make_family(c)
    b = make_family(c)
    ev = a.trigger("evening")
    # b 가 a 의 건·사진·기기에 접근 → 404 (존재 여부를 알려주지 않음)
    r = b.upload(ev["id"], png())
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    r = c.delete(API + f"/devices/{a.e_device}", headers=b.g)
    assert r.status_code == 404
    r = b.gget(f"/handoffs/{'0' * 36}")
    assert r.status_code == 404

