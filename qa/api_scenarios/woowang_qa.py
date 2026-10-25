"""QA 시나리오 테스트 도우미 (T-QA1). 제품 코드가 아니다.

- 서버는 _targets/BE (각 저장소 main 복사본)를 run.sh 가 띄운다
- 판독기는 MockReader(mock-v1). MockReader 는 사진 바이트의 sha256 으로 결과를 정하므로,
  원하는 칸 상태가 나오는 바이트를 찾아서 올린다 (find_photo). T-BE4 의 "모의 판독 시나리오 지정
  dev API"가 생기면 그것으로 바꾼다
- 시각이 필요한 시나리오는 시연 트리거(POST /dev/dose-events)로 복약 시각을 지금으로 당기고,
  인계 기한은 서버 환경 변수(NO_RESPONSE_HANDOFF_MIN 등)를 짧게 둔 "fast" 서버에서 실제로 기다린다.
  서버에는 HTTP 로 시각을 옮기는 수단이 없다 (app/clock.py 는 프로세스 안 테스트 전용)
- T-BE4(R-019) 이후: GET 은 상태를 바꾸지 않는다. 시각이 된 건 열기·무응답 인계는 1분 예약 작업이
  하므로 최대 1분 늦게 반영된다 (wait_for 로 기다린다). 다음 사진 1장의 판독 결과는
  POST /dev/mock-scenario 로 정할 수 있다 (set_scenario)
"""

from __future__ import annotations

import hashlib
import itertools
import os
import random
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

KST = ZoneInfo("Asia/Seoul")
BASE_URL = os.environ.get("QA_BASE_URL", "http://127.0.0.1:18200")
API = "/api/v1"
SERVER_LOG = os.environ.get("QA_SERVER_LOG")
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# 1×4 약통: 오늘 요일의 아침·점심·저녁·취침을 한 칸씩. 칸이 적어야 원하는 모의 결과를 빨리 찾는다
LAYOUT_1x4 = {
    "rows": 1,
    "cols": 4,
    "row_labels": [""],
    "col_labels": ["아침", "점심", "저녁", "취침"],
}
TODS = ["morning", "noon", "evening", "bedtime"]
CELLS = ["r0c0", "r0c1", "r0c2", "r0c3"]
TOD_CELL = dict(zip(TODS, CELLS, strict=True))


# ---------- MockReader 재현 (app/reader/mock.py, mock-v1) ----------


def mock_read(data: bytes, cell_ids: list[str], empty_ratio=0.45, unclear_ratio=0.1) -> dict:
    seed = hashlib.sha256(data).hexdigest()
    out = {}
    for cid in cell_ids:
        rng = random.Random(f"{seed}:{cid}")
        r = rng.random()
        if r < unclear_ratio:
            state = "unclear"
        elif r < unclear_ratio + empty_ratio:
            state = "empty"
        else:
            state = "full"
        out[cid] = (state, round(rng.uniform(0.55, 0.99), 2))
    return out


def find_photo(want: dict[str, str], cell_ids: list[str] = CELLS, tag: str = "") -> bytes:
    """want: {cell_id: "empty" | "empty_hi" | "empty_lo" | "full" | "unclear" | "any"}.

    empty_hi = 비어 있음 + 신뢰도 0.9 이상 (정상 판정 조건), empty_lo = 비어 있음 + 0.9 미만.
    tag 를 바꾸면 같은 조건의 다른 사진이 나온다 (재촬영 등).
    """
    for i in itertools.count():
        data = PNG_MAGIC + f"qa-mock:{tag}:{i}".encode()
        got = mock_read(data, cell_ids)
        ok = True
        for cid in cell_ids:
            w = want.get(cid, "any")
            state, conf = got[cid]
            if w == "any":
                continue
            if w == "empty_hi":
                ok = state == "empty" and conf >= 0.9
            elif w == "empty_lo":
                ok = state == "empty" and conf < 0.9
            else:
                ok = state == w
            if not ok:
                break
        if ok:
            return data
        if i > 2_000_000:
            raise RuntimeError(f"모의 사진을 찾지 못함: {want}")


def png(tag: str = "plain") -> bytes:
    return PNG_MAGIC + f"qa-plain:{tag}:{uuid.uuid4()}".encode()


# ---------- 서버 로그의 푸시 기록 (RecordingPushSender, logging INFO) ----------


def push_lines(device_ids: list[str]) -> list[str]:
    """서버 로그에서 이 기기들로 간 푸시(발송 생략 기록) 줄을 모은다. 로그가 없으면 None."""
    if not SERVER_LOG or not Path(SERVER_LOG).exists():
        return None
    lines = Path(SERVER_LOG).read_text(encoding="utf-8", errors="replace").splitlines()
    pat = re.compile(r"push\(skip\) to (\S+):")
    out = []
    for line in lines:
        m = pat.search(line)
        if m and m.group(1) in device_ids:
            out.append(line)
    return out


# ---------- 가족 만들기 ----------


def client() -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, timeout=90)


def fresh_ip() -> dict:
    # POST /families 는 IP당 시간당 10회. 시나리오마다 가족을 새로 만들기 때문에
    # 요청마다 다른 cf-connecting-ip 를 붙인다 (서버는 Cloudflare 뒤라 이 헤더를 믿는다)
    return {"cf-connecting-ip": f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"}


def now_kst() -> datetime:
    return datetime.now(KST)


@dataclass
class Family:
    c: httpx.Client
    family_id: str = ""
    g_token: str = ""
    e_token: str = ""
    g_device: str = ""
    e_device: str = ""
    pillbox: dict = field(default_factory=dict)
    refill: dict = field(default_factory=dict)
    slots: dict = field(default_factory=dict)  # time_of_day -> slot dict

    @property
    def g(self) -> dict:
        return {"Authorization": f"Bearer {self.g_token}"}

    @property
    def e(self) -> dict:
        return {"Authorization": f"Bearer {self.e_token}"}

    # --- 호출 도우미 ---
    def gget(self, path, **kw):
        return self.c.get(API + path, headers=self.g, **kw)

    def eget(self, path, **kw):
        return self.c.get(API + path, headers=self.e, **kw)

    def gpost(self, path, **kw):
        return self.c.post(API + path, headers=self.g, **kw)

    def epost(self, path, **kw):
        return self.c.post(API + path, headers=self.e, **kw)

    def gput(self, path, **kw):
        return self.c.put(API + path, headers=self.g, **kw)

    def trigger(self, tod: str) -> dict:
        r = self.gpost("/dev/dose-events", json={"slot_id": self.slots[tod]["id"]})
        assert r.status_code == 201, r.text
        return r.json()

    def upload(self, event_id: str, data: bytes, **form) -> httpx.Response:
        return self.epost(
            f"/dose-events/{event_id}/photo",
            files={"photo": ("p.png", data, "image/png")},
            data=form,
        )

    def event(self, event_id: str, as_guardian=True) -> dict:
        r = (self.gget if as_guardian else self.eget)("/dose-events/today")
        assert r.status_code == 200, r.text
        return next(i for i in r.json()["items"] if i["id"] == event_id)

    def handoffs(self, status="open") -> list[dict]:
        r = self.gget("/handoffs", params={"status": status})
        assert r.status_code == 200, r.text
        return r.json()["items"]

    def set_schedule(self, mapping: dict[str, str], dose_time: str = "23:59") -> dict:
        """mapping: time_of_day -> cell_id. 오늘 요일에만 일정을 둔다."""
        wd = now_kst().weekday()
        slots = [
            {"weekday": wd, "time_of_day": tod, "dose_time": dose_time, "cell_id": cid}
            for tod, cid in mapping.items()
        ]
        r = self.gput("/schedule", json={"slots": slots})
        assert r.status_code == 200, r.text
        self.slots = {s["time_of_day"]: s for s in r.json()["slots"]}
        return r.json()

    def set_scenario(self, scenario: str | None) -> httpx.Response:
        r = self.gpost("/dev/mock-scenario", json={"scenario": scenario})
        assert r.status_code == 200, r.text
        return r

    def guardian_pushes(self) -> list[str] | None:
        return push_lines([self.g_device])


def make_family(
    c: httpx.Client,
    *,
    elder="할머니QA",
    guardian="지훈QA",
    demo=True,
    consent=True,
    pillbox=True,
    schedule=True,
    unchanged_mode: str | None = None,
) -> Family:
    f = Family(c)
    r = c.post(
        API + "/families",
        json={"elder_display_name": elder, "guardian_display_name": guardian, "is_demo": demo},
        headers=fresh_ip(),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    f.family_id, f.g_token, f.g_device = body["family_id"], body["token"], body["device"]["id"]

    r = f.gpost("/pairing-codes", json={"kind": "elder"})
    assert r.status_code == 201, r.text
    r = c.post(API + "/pair", json={"code": r.json()["code"], "platform": "android"})
    assert r.status_code == 201, r.text
    f.e_token, f.e_device = r.json()["token"], r.json()["device"]["id"]

    if consent:
        me = f.eget("/me").json()
        r = f.epost(
            "/consent",
            json={
                "agreed": True,
                "consent_text_version": me["server"]["consent_text_version"],
                "ai_external_transfer_shown": me["server"]["ai_external_transfer"],
            },
        )
        assert r.status_code == 200, r.text
    if pillbox:
        r = f.gpost("/pillboxes/detect", files={"photo": ("pb.png", png("reg"), "image/png")})
        assert r.status_code == 200, r.text
        r = f.gpost("/pillboxes", json={"photo_id": r.json()["photo"]["id"], "layout": LAYOUT_1x4})
        assert r.status_code == 201, r.text
        f.pillbox, f.refill = r.json()["pillbox"], r.json()["refill"]
    if schedule and pillbox:
        f.set_schedule(TOD_CELL)
    if unchanged_mode:
        r = f.gput("/settings", json={"unchanged_mode": unchanged_mode})
        assert r.status_code == 200, r.text
    return f


def wait_for(fn, timeout: float = 130, every: float = 3):
    """fn() 이 참이 될 때까지 기다린다. 1분 예약 작업 반영용."""
    import time

    end = time.monotonic() + timeout
    while True:
        v = fn()
        if v or time.monotonic() > end:
            return v
        time.sleep(every)


def seconds_until_midnight() -> float:
    n = now_kst()
    tomorrow = (n + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return (tomorrow - n).total_seconds()
