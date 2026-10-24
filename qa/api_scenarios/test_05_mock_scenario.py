"""POST /dev/mock-scenario (api.md 3.28, R-019) 로 결정적으로 돌리는 시나리오.

test_02 는 사진 바이트를 골라 MockReader 결과를 맞추고, 여기서는 서버가 정해 주는 결과를 쓴다.
재촬영, 칸 그대로 두 모드, 이중 복용, 그리고 T-BE4 수정 2건(인계 중복, CORS)의 회귀 확인.
"""

import concurrent.futures as cf

import httpx

from woowang_qa import API, BASE_URL, make_family, png


def up(f, ev, scenario):
    f.set_scenario(scenario)
    r = f.upload(ev["id"], png(scenario or "none"))
    assert r.status_code == 200, r.text
    return r.json()


def test_m01_scenario_endpoint_guard(c):
    f = make_family(c)
    r = f.gpost("/dev/mock-scenario", json={"scenario": "unclear"})
    assert r.json() == {"scenario": "unclear", "applies_to": "next_dose_photo", "is_mock": True}
    r = f.gpost("/dev/mock-scenario", json={"scenario": "bogus"})
    assert r.status_code == 422
    real = make_family(c, demo=False)
    r = real.gpost("/dev/mock-scenario", json={"scenario": "unclear"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_m02_normal(c):
    f = make_family(c)
    ev = f.trigger("evening")
    body = up(f, ev, "normal")
    assert body["result"] == "recorded" and body["is_mock"] is True
    g = f.event(ev["id"])
    assert g["latest_reading"]["provider"] == "mock" and g["latest_reading"]["is_mock"] is True
    assert f.handoffs("all") == []
    pushes = f.guardian_pushes()
    if pushes is not None:
        assert pushes == []


def test_m03_unclear_retake_then_normal(c):
    f = make_family(c)
    ev = f.trigger("evening")
    assert up(f, ev, "unclear")["result"] == "retake"
    assert up(f, ev, "normal")["result"] == "recorded"
    assert f.handoffs("all") == []


def test_m04_unclear_twice_guardian_verdict(c):
    f = make_family(c)
    ev = f.trigger("evening")
    assert up(f, ev, "unclear")["result"] == "retake"
    assert up(f, ev, "unclear")["result"] == "guardian_notified"
    h = f.handoffs()
    assert [x["reason"] for x in h] == ["unclear"]
    r = f.gpost(f"/handoffs/{h[0]['id']}/verdict", json={"verdict": "not_taken"})
    assert r.status_code == 200
    g = f.event(ev["id"])
    assert g["outcome"] == "not_taken" and g["outcome_source"] == "guardian"
    e = f.event(ev["id"], as_guardian=False)
    assert e["elder_status"] == "no_record"  # 어르신 화면에 "안 드셨어요"를 보여주지 않음


def test_m05_unchanged_remind_mode(c):
    f = make_family(c)
    ev = f.trigger("evening")
    assert up(f, ev, "unchanged")["result"] == "remind_retake"
    assert f.event(ev["id"])["state"] == "reminded"
    assert up(f, ev, "unchanged")["result"] == "guardian_notified"
    assert [x["reason"] for x in f.handoffs()] == ["unchanged"]


def test_m06_unchanged_immediate_mode(c):
    f = make_family(c, unchanged_mode="handoff_immediately")
    ev = f.trigger("evening")
    assert up(f, ev, "unchanged")["result"] == "guardian_notified"
    assert [x["reason"] for x in f.handoffs()] == ["unchanged"]


def test_m07_double_suspected(c):
    f = make_family(c)
    ev = f.trigger("evening")
    assert up(f, ev, "double_suspected")["result"] == "guardian_notified"
    h = f.handoffs()
    assert [x["reason"] for x in h] == ["double_suspected"]
    att = [x["attention"] for x in h[0]["dose_event"]["latest_reading"]["cells"]]
    assert "unexpected_empty" in att


def test_m08_scenario_applies_to_one_photo_only(c):
    f = make_family(c)
    ev = f.trigger("evening")
    f.set_scenario("unclear")
    assert f.upload(ev["id"], png()).json()["result"] == "retake"
    # 두 번째 사진은 시나리오 없이 원래 MockReader (사진 해시 결과)
    r = f.upload(ev["id"], png())
    assert r.status_code == 200
    g = f.event(ev["id"])
    assert len(g["photos"]) == 2


def test_m09_already_used_with_normal_scenario(c):
    """3.28: 이미 쓴 칸에 normal 을 주면 recorded 가 아니다 (R-014)."""
    f = make_family(c)
    am = f.trigger("morning")
    assert up(f, am, "normal")["result"] == "recorded"
    f.set_schedule({"noon": "r0c0", "evening": "r0c2"})
    ev = f.trigger("noon")
    body = up(f, ev, "normal")
    assert body["result"] == "guardian_notified", body
    reasons = [x["reason"] for x in f.handoffs()]
    assert reasons in (["refill_overdue"], ["refill_unconfirmed"]), reasons
    assert f.event(ev["id"])["outcome"] is None


# ---------- T-BE4 회귀 확인 ----------


def test_m10_concurrent_uploads_single_result(c):
    """같은 건에 사진 두 장이 동시에 오면 판독은 하나, 인계도 최대 하나."""
    f = make_family(c, unchanged_mode="handoff_immediately")
    ev = f.trigger("evening")
    f.set_scenario("unchanged")

    def send(i):
        with httpx.Client(base_url=BASE_URL, timeout=90) as cl:
            return cl.post(API + f"/dose-events/{ev['id']}/photo", headers=f.e,
                           files={"photo": ("p.png", png(f"cc{i}"), "image/png")})

    with cf.ThreadPoolExecutor(4) as ex:
        rs = list(ex.map(send, range(4)))
    codes = sorted(r.status_code for r in rs)
    assert codes.count(200) >= 1, [(r.status_code, r.text[:80]) for r in rs]
    assert all(r.status_code in (200, 409) for r in rs), [(r.status_code, r.text[:120]) for r in rs]
    bound = [h for h in f.handoffs("all") if h["dose_event"]["id"] == ev["id"]]
    assert len(bound) <= 1, bound


def test_m11_concurrent_reads_no_duplicate_handoff(c):
    """동시 GET 이 인계를 만들지 않는다 (R-018 수정: GET 은 읽기만)."""
    f = make_family(c)
    ev = f.trigger("evening")
    up(f, ev, "unclear")
    up(f, ev, "unclear")

    def get(i):
        with httpx.Client(base_url=BASE_URL, timeout=30) as cl:
            return cl.get(API + "/dose-events/today", headers=f.g if i % 2 else f.e).status_code

    with cf.ThreadPoolExecutor(8) as ex:
        assert set(ex.map(get, range(16))) == {200}
    assert len(f.handoffs("all")) == 1


def test_m12_cors_preflight(c):
    ok_origin = "http://localhost:8299"
    r = c.options(API + "/me", headers={"Origin": ok_origin,
                                         "Access-Control-Request-Method": "GET",
                                         "Access-Control-Request-Headers": "authorization"})
    assert r.status_code == 200, r.text
    assert r.headers.get("access-control-allow-origin") == ok_origin
    r = c.get("/health", headers={"Origin": ok_origin})
    assert r.headers.get("access-control-allow-origin") == ok_origin
    r = c.options(API + "/me", headers={"Origin": "https://evil.example",
                                         "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") is None


# ---------- 이슈 재현 (실패하면 이슈가 아직 있음) ----------


def test_q005_at_most_one_retake_request(c):
    """backend.md 7.1 '재촬영 요청 최대 1회'. 애매→칸 그대로 순서면 어르신이 사진을 3장 찍게 된다."""
    for first, second in (("unclear", "unchanged"), ("unchanged", "unclear")):
        f = make_family(c)
        ev = f.trigger("evening")
        r1 = up(f, ev, first)["result"]
        r2 = up(f, ev, second)["result"]
        assert r1 in ("retake", "remind_retake")
        assert r2 == "guardian_notified", (
            f"{first}→{second}: 두 번째 사진 뒤에도 또 찍어 달라고 함 ({r1}→{r2})"
        )
