# API 계약서

- 작성일: 2026-10-24
- 상태: 검토 요청 중 (`docs/reviews/requests/20261024-api-contract.md`)
- 근거: `docs/design/backend.md` (R-007 조건 C1~C5, R-009 반영), UI 설계 `reviews/requests/20261024-ui-ux-screen-design.md` (R-008 조건 반영)
- 대상: FE(Expo 앱)와 BE(FastAPI). **FE는 이 문서만 보고 모의 데이터를 만들 수 있어야 한다.** 예시 JSON은 그대로 모의 데이터로 써도 된다

> 이 문서와 `backend.md`가 다르면 이 문서의 스키마가, 동작 규칙은 `backend.md`가 우선한다.

## 0. 목차

1. 공통 규칙 (주소, 인증, 시간, 오류)
2. 공통 객체
3. 엔드포인트
4. 화면별 데이터 출처 (UI 설계 대조표)
5. 오류 코드 전체 목록

---

## 1. 공통 규칙

### 1.1 주소
- 기본 주소: `https://<터널 도메인>/api/v1` (예: `https://woowang.example.com/api/v1`). 이 문서의 경로는 모두 `/api/v1` 뒤에 붙는다. `/health`만 예외로 루트(`/health`)에 둔다
- 본문은 `application/json; charset=utf-8`. 사진 업로드만 `multipart/form-data`

### 1.2 인증
- 모든 요청에 `Authorization: Bearer <기기 토큰>` 헤더를 붙인다
- 토큰 없이 부를 수 있는 것: `GET /health`, `POST /families`, `POST /pair`, `GET /photo-files/{id}` (서명으로 보호)
- 토큰은 43자 base64url 문자열 (256비트). 앱은 `expo-secure-store`에 보관한다. 서버는 해시만 저장한다
- 서버는 토큰으로 기기·가족·역할을 찾고, **모든 조회를 그 가족으로 제한**한다. 다른 가족의 id를 넣으면 `404 not_found`로 응답한다 (존재 여부를 알려주지 않음)
- 역할 표기: 각 엔드포인트의 **권한** 줄에 `elder`(어르신 기기), `guardian`(보호자 기기), `any`(둘 다)
- **어르신 동의 전 제한:** 어르신 기기는 동의(`POST /consent`) 전에는 `GET /me`, `POST /consent`, `PUT /devices/me/push-token`만 쓸 수 있다. 나머지는 `403 consent_required`

### 1.3 시간과 날짜
- 시각(`*_at`)은 ISO 8601, 서울 시간 오프셋 포함: `"2026-10-24T08:12:30+09:00"`. 서버 내부 저장은 UTC
- 날짜(`date`)는 서울 기준 `"YYYY-MM-DD"`
- 하루 중 시각(`dose_time`, `summary_push_time`)은 `"HH:MM"` 24시간제
- 요일 `weekday`: `0`=월 … `6`=일
- 시간대 `time_of_day`: `"morning"`(아침) / `"noon"`(점심) / `"evening"`(저녁) / `"bedtime"`(취침)

### 1.4 id
- 모든 id는 문자열(UUID). 칸 id(`cell_id`)만 `"r{행}c{열}"` 형식 (예: `"r0c3"`)

### 1.5 오류 형식
```json
{
  "error": {
    "code": "consent_required",
    "message": "어르신 동의가 필요합니다.",
    "details": {}
  }
}
```
- `code`는 영문 고정값이고 앱 분기에 쓴다. `message`는 개발용 한국어 설명이며 **어르신 화면에 그대로 띄우지 않는다** (문구는 앱 템플릿)
- 입력 검증 실패는 `422 validation_error`, `details.fields`에 `[{"field": "dose_time", "problem": "형식은 HH:MM"}]`
- 전체 목록은 5장

### 1.6 기타
- 목록 응답은 `{"items": [...]}` 형태. 페이지 나누기는 없다 (가족 단위라 양이 적음). 기간 조회는 최대 31일
- 빈 값은 키를 빼지 않고 `null`로 보낸다
- 클라이언트는 모르는 필드를 무시해야 한다 (필드 추가는 호환 변경으로 본다)
- 속도 제한: 토큰 없는 엔드포인트는 IP별 제한. 넘으면 `429 rate_limited`, `Retry-After` 헤더

---

## 2. 공통 객체

FE 타입 정의에 그대로 옮길 수 있게 TypeScript 표기로 적는다.

### 2.1 열거형
```ts
type Role = "elder" | "guardian";
type TimeOfDay = "morning" | "noon" | "evening" | "bedtime";
type CellState = "empty" | "full" | "unclear";              // AI가 본 칸 상태
type ExpectedState = "empty" | "full" | "ignored";            // 서버가 계산한 기대 상태. ignored = 비교 제외 (backend 5.3)
type DoseState = "scheduled" | "asked" | "reading" | "retake_requested" | "reminded" | "handed_off" | "done";
type DoseOutcome = "taken" | "not_taken" | "acknowledged";
type HandoffReason = "no_response" | "unclear" | "unchanged" | "double_suspected" | "refill_unconfirmed";
type Verdict = "taken" | "not_taken" | "acknowledged" | "refilled" | "not_refilled";
type Classification = "normal" | "unclear" | "unchanged" | "double_suspected" | "error";
type UnchangedMode = "remind_then_retake" | "handoff_immediately";  // R-009
```

### 2.2 Layout (약통 구조)
```ts
interface Layout {
  rows: number;                 // 1~7
  cols: number;                 // 1~7
  row_labels: string[];         // 길이 = rows. 예: ["아침", "저녁"]. 없으면 ""
  col_labels: string[];         // 길이 = cols. 예: ["월","화","수","목","금","토","일"]
  cells: { id: string; row: number; col: number }[];  // 보통 rows×cols개
}
```
세로 배열 약통(요일이 행)은 rows=7, cols=n으로 표현한다.

### 2.3 Photo
```ts
interface Photo {
  id: string;
  taken_at: string;             // 앱이 보낸 촬영 시각 (없으면 업로드 시각)
  url: string;                  // 서명 URL. 토큰 없이 <Image source>에 바로 쓴다
  url_expires_at: string;       // 5분 뒤. 지나면 GET /photos/{id}로 새로 받는다
}
```

### 2.4 Reading (판독 결과, 보호자용)
원본 신뢰도 숫자는 내보내지 않는다 (R-008 C5). 대신 칸마다 `attention`을 준다.
```ts
interface CellResult {
  cell_id: string;
  ai_state: CellState;          // AI가 본 상태
  expected: ExpectedState | null;   // 기대 상태. 등록·리필 판독이면 null
  attention: null               // 강조 없음
    | "unclear"                 // AI가 판단 못 함
    | "low_confidence"          // AI가 확실하지 않다고 봄
    | "unexpected_empty"        // 차 있어야 하는데 비어 보임 (이중 복용 의심의 근거)
    | "unexpected_full";        // 비어 있어야 하는데 차 보임 (칸 그대로의 근거 등)
  bbox: [number, number, number, number] | null;  // 사진 안 칸 위치 [x, y, w, h], 0~1 비율. 모델이 못 주면 null → 앱은 격자 그림으로 대신 표시
}

interface Reading {
  id: string;
  photo: Photo;
  is_mock: boolean;             // true면 "모의 결과" 배지 필수 (헌장 6장)
  provider: "mock" | "claude" | "ollama";
  model: string;                // 예: "mock-v1", "claude-haiku-5-5"
  created_at: string;
  target_cell_id: string | null;    // 이번 복약 칸. 등록·리필 판독이면 null
  classification: Classification | null;  // 등록·리필 판독이면 null
  cells: CellResult[];
}
```

### 2.5 DoseEvent (복약 건)
역할에 따라 일부 필드가 `null`이다.
```ts
interface DoseEvent {
  id: string;
  date: string;                 // "2026-10-24"
  slot: {
    id: string;
    weekday: number;
    time_of_day: TimeOfDay;
    dose_time: string;          // "08:00"
    cell_id: string;
  };
  scheduled_at: string;
  state: DoseState;
  outcome: DoseOutcome | null;
  outcome_source: "ai" | "guardian" | null;   // "AI 판독" / "민수 판정" 구분 표시
  decided_by: { device_id: string; display_name: string } | null;  // outcome_source=guardian일 때
  taken_at: string | null;      // outcome=taken일 때. AI면 사진 촬영 시각, 보호자 판정이면 판정 시각
  resolved_at: string | null;
  elder_status: "upcoming" | "waiting" | "recorded" | "no_record";  // E8용 단순화 값 (아래 표)
  ask_times: string[];          // 로컬 알림 시각: [복약 시각, 재질문1, 재질문2]. 서버값 (C5)
  handoff_at: string;           // 무응답 인계 기한 (복약 시각 + 30분)
  retake_deadline_at: string | null;  // reminded·retake_requested일 때만
  photos: Photo[];              // 이 건의 사진, 오래된 순
  is_mock: boolean;             // 이 건의 판독 중 하나라도 모의면 true
  latest_reading: Reading | null;   // 보호자만. 어르신 응답에서는 항상 null
  handoff: HandoffBrief | null;     // 보호자만. 어르신 응답에서는 항상 null
}

interface HandoffBrief {
  id: string;
  reason: HandoffReason;
  notified_at: string;
  verdict: Verdict | null;
  verdict_at: string | null;
}
```

`elder_status` 규칙 ("나 약 먹었나?" E8):

| 값 | 조건 | E8 표시 예 |
|---|---|---|
| `upcoming` | `state = scheduled` | "저녁 7시 예정" |
| `waiting` | `asked`, `reading`, `retake_requested`, `reminded` | "아직 기록이 없어요" |
| `recorded` | `outcome = taken` (AI든 보호자든) | "아침 ✓ 8시 12분" + 사진 |
| `no_record` | 그 밖 (`handed_off`, `not_taken`, `acknowledged`) | "아직 기록이 없어요" |

어르신 화면에는 "안 드셨어요"나 인계 사유를 보여주지 않는다 (원칙 6, 검토 요청 애매한 지점 12번).

### 2.6 Handoff (인계 상세, 보호자용)
```ts
interface Handoff {
  id: string;
  reason: HandoffReason;
  notified_at: string;
  verdict: Verdict | null;
  verdict_by: { device_id: string; display_name: string } | null;
  verdict_at: string | null;
  allowed_verdicts: Verdict[];  // 사유별 버튼 (backend 7.2). 예: unclear → ["taken","not_taken"]
  late_photo: boolean;          // 인계 뒤에 사진이 늦게 올라왔는지 (backend 6장 늦은 사진)
  dose_event: DoseEvent;        // latest_reading, photos 포함
  readings: Reading[];          // 이 건의 모든 판독 (첫 촬영, 재촬영), 오래된 순
  layout: Layout;               // 격자 그림·강조 표시용
}
```

### 2.7 Device
```ts
interface Device {
  id: string;
  role: Role;
  display_name: string;         // 어르신 기기는 가족의 elder_display_name
  platform: "android" | "ios" | null;
  paired_at: string;
  consent_at: string | null;    // 어르신만. 보호자는 null
  last_seen_at: string | null;
  is_me: boolean;
}
```

---

## 3. 엔드포인트

### 3.1 `GET /health`
- 권한: 없음
- 용도: 업타임 모니터, 앱 시작 시 서버 확인
```json
200
{
  "status": "ok",
  "version": "0.1.0",
  "time": "2026-10-24T21:00:00+09:00",
  "reader": { "layout": "mock", "cells": "mock", "is_mock": true }
}
```

### 3.2 `POST /families` — 가족 만들기 (G1)
- 권한: 없음 (IP별 속도 제한)
```json
요청
{
  "elder_display_name": "어머니",
  "guardian_display_name": "민수",
  "platform": "android"
}
```
```json
201
{
  "family_id": "f1c0…",
  "token": "q3J0X2…(43자)",
  "device": { "id": "d-g1", "role": "guardian", "display_name": "민수", "platform": "android",
              "paired_at": "2026-10-24T20:00:00+09:00", "consent_at": null, "last_seen_at": null, "is_me": true }
}
```
- 검증: 이름은 1~20자. 오류 `422 validation_error`, `429 rate_limited`

### 3.3 `POST /pairing-codes` — 연결 코드 발급 (G1 QR, 보호자 초대)
- 권한: `guardian`
```json
요청
{ "kind": "elder" }          // "elder" = 어르신 폰 연결용(QR), "guardian" = 보호자 초대용
```
```json
201 (kind=elder)
{
  "kind": "elder",
  "code": "Zq8m…(22자 base64url, 128비트)",
  "short_code": "482915",
  "expires_at": "2026-10-24T20:10:00+09:00",
  "qr_payload": "woowang://pair?code=Zq8m…"
}
```
```json
201 (kind=guardian)
{
  "kind": "guardian",
  "code": "Hk2p…(22자)",
  "short_code": null,
  "expires_at": "2026-10-25T20:00:00+09:00",
  "qr_payload": "woowang://pair?code=Hk2p…"
}
```
- 새 `elder` 코드를 발급하면 같은 가족의 사용 안 된 이전 `elder` 코드는 무효가 된다
- 앱은 `qr_payload`를 QR로 띄우거나, 초대 코드는 공유 시트로 보낸다. 링크 형식(`woowang://`)은 FE가 정해도 된다. 서버는 `code`만 본다

### 3.4 `POST /pair` — 코드로 기기 연결
- 권한: 없음 (IP별 제한: 실패 5회/10분)
```json
요청 (어르신 폰, QR 스캔)
{ "code": "Zq8m…", "platform": "android" }

요청 (어르신 폰, 6자리 입력)
{ "short_code": "482915", "platform": "android" }

요청 (새 보호자, 초대 코드)
{ "code": "Hk2p…", "display_name": "민지", "platform": "ios" }
```
- `code`와 `short_code` 중 하나만. 보호자 초대일 때는 `display_name` 필수, 어르신일 때는 무시
```json
201
{
  "token": "x9Yd…(43자)",
  "device": { "id": "d-e1", "role": "elder", "display_name": "어머니", "platform": "android",
              "paired_at": "2026-10-24T20:03:00+09:00", "consent_at": null, "last_seen_at": null, "is_me": true },
  "family": { "id": "f1c0…", "elder_display_name": "어머니",
              "guardians": [{ "device_id": "d-g1", "display_name": "민수" }] },
  "consent_required": true
}
```
- 어르신 연결이면 이전 어르신 기기는 자동 해제된다
- 보호자 합류면 기존 보호자 전원에게 푸시 "민지님이 보호자로 추가됐어요" (backend 3.3)
- 오류: `400 code_invalid`(없는 코드), `410 code_expired`, `410 code_used`, `422 validation_error`, `429 rate_limited`

### 3.5 `POST /consent` — 어르신 동의 (E1)
- 권한: `elder` (동의 전에도 가능)
```json
요청
{
  "agreed": true,
  "consent_text_version": "v1",
  "ai_external_transfer_shown": true
}
```
- `consent_text_version`: 앱이 보여준 동의 문구 버전. `ai_external_transfer_shown`: "사진은 AI 서비스로 보내져요" 줄을 보여줬는지 (R-008 C4). `GET /me`의 `server.ai_external_transfer`가 true인데 이 값이 false면 `422 consent_incomplete`
```json
200
{ "consent_at": "2026-10-24T20:04:00+09:00" }
```
- `agreed: false`는 받지 않는다 (`422`). 동의하지 않으면 앱이 아무 요청도 안 보내면 된다

### 3.6 `GET /me` — 내 정보와 서버 설정 (앱 시작 시 1회) ★추가
- 권한: `any` (어르신 동의 전에도 가능)
```json
200
{
  "device": { "id": "d-e1", "role": "elder", "display_name": "어머니", "platform": "android",
              "paired_at": "2026-10-24T20:03:00+09:00", "consent_at": "2026-10-24T20:04:00+09:00",
              "last_seen_at": "2026-10-24T21:00:00+09:00", "is_me": true },
  "consent_required": false,
  "family": {
    "id": "f1c0…",
    "elder_display_name": "어머니",
    "guardians": [
      { "device_id": "d-g1", "display_name": "민수" },
      { "device_id": "d-g2", "display_name": "민지" }
    ],
    "has_pillbox": true,
    "has_schedule": true
  },
  "server": {
    "timezone": "Asia/Seoul",
    "timing": {
      "reask_offsets_min": [10, 20],
      "no_response_handoff_min": 30,
      "retake_wait_min": 15
    },
    "reader_is_mock": true,
    "ai_external_transfer": false,
    "consent_text_version": "v1"
  }
}
```
- `timing`: 재질문·인계·재촬영 대기 시간. 앱은 이 값으로 로컬 알림을 예약하고 숫자를 하드코딩하지 않는다 (C5)
- `reader_is_mock`: true면 앱 상단에 **"모의 판독 (실제 AI 아님)"** 띠를 항상 띄운다 (UI 설계 5장)
- `ai_external_transfer`: 서버가 외부 AI(Claude API)로 사진을 보내는 설정이면 true. E1 동의 화면에 그 줄을 넣는다 (R-008 C4)
- 어르신 화면의 "민수"는 `family.guardians[0].display_name`을 쓴다. 보호자가 여럿이면 표시 방식은 FE가 정한다 (예: "민수님")
- 해제된 토큰이면 `401 token_revoked` → 앱은 저장된 토큰을 지우고 첫 화면으로 간다

### 3.7 `GET /devices` — 기기 목록 (G8)
- 권한: `guardian`
```json
200
{ "items": [
  { "id": "d-g1", "role": "guardian", "display_name": "민수", "platform": "android",
    "paired_at": "2026-10-24T20:00:00+09:00", "consent_at": null, "last_seen_at": "2026-10-24T21:00:00+09:00", "is_me": true },
  { "id": "d-e1", "role": "elder", "display_name": "어머니", "platform": "android",
    "paired_at": "2026-10-24T20:03:00+09:00", "consent_at": "2026-10-24T20:04:00+09:00", "last_seen_at": "2026-10-24T20:59:00+09:00", "is_me": false }
] }
```
해제된 기기는 목록에 없다.

### 3.8 `DELETE /devices/{id}` — 기기 해제 (G8 연결 해제)
- 권한: `guardian`
- `204` (본문 없음). 해당 토큰은 즉시 `401 token_revoked`
- 오류: `404 not_found`, `409 last_guardian` (마지막 남은 보호자는 해제 불가)

### 3.9 `PUT /devices/me/push-token`
- 권한: `any` (어르신 동의 전에도 가능)
```json
요청
{ "push_token": "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]" }
```
- `204`. `push_token: null`이면 푸시 해제

### 3.10 `POST /pillboxes/detect` — 약통 구조 제안 (G2)
- 권한: `guardian`
- `multipart/form-data`
  - `photo`: 이미지 파일 (JPEG/PNG/HEIC, 최대 10MB). **약을 채운 약통** 사진 (R-008 C3)
  - `taken_at`: (선택) 촬영 시각 ISO 8601
- 판독이 끝날 때까지 기다렸다가 응답한다 (최대 60초)
```json
200
{
  "photo": { "id": "p-reg1", "taken_at": "2026-10-24T20:10:00+09:00",
             "url": "https://…/api/v1/photo-files/p-reg1?exp=1761304500&sig=…", "url_expires_at": "2026-10-24T20:15:00+09:00" },
  "proposal": {
    "layout": {
      "rows": 2, "cols": 7,
      "row_labels": ["아침", "저녁"],
      "col_labels": ["월", "화", "수", "목", "금", "토", "일"],
      "cells": [ { "id": "r0c0", "row": 0, "col": 0 }, "… 14개 …" ]
    },
    "suggested_time_of_day": ["morning", "evening"],
    "uncertain": false
  },
  "is_mock": true,
  "provider": "mock",
  "model": "mock-v1"
}
```
- `suggested_time_of_day`: 행 라벨에서 추정한 시간대 (행 순서대로). 모르면 `null` 원소. G2·G3에서 기본값으로 쓴다
- `uncertain`: AI가 구조를 확신하지 못함 → 앱은 "구조를 직접 확인해 주세요"를 강조한다
- 오류: `413 photo_too_large`, `415 unsupported_media`, `429 daily_reading_limit`, `502 reading_failed` (앱은 다시 찍기 또는 수동 입력 안내)

### 3.11 `POST /pillboxes` — 약통 확정 (G2)
- 권한: `guardian`
- 보호자가 확인하거나 고친 구조를 확정한다. 서버는 같은 사진을 칸 판독해서 **첫 기준선**을 만든다 (backend 4.1, 5.1)
```json
요청
{
  "photo_id": "p-reg1",
  "layout": { "rows": 2, "cols": 7, "row_labels": ["아침","저녁"], "col_labels": ["월","화","수","목","금","토","일"],
              "cells": [ { "id": "r0c0", "row": 0, "col": 0 }, "…" ] }
}
```
```json
201
{
  "pillbox": { "id": "pb1", "layout": { "…": "…" }, "registered_photo_id": "p-reg1",
               "confirmed_at": "2026-10-24T20:12:00+09:00", "active": true },
  "refill": "Refill 객체 (3.15와 같음, source = \"registration\")"
}
```
- 새 약통을 확정하면 이전 약통은 `active=false`. 기존 일정(`schedule`)은 지워지므로 앱은 바로 G3로 간다
- 기준선에 `attention`이 있는 칸이 있으면 앱은 그 칸을 고치게 한다 (`PUT /refills/{id}/baseline`)
- 오류: `404 not_found`(photo_id), `422 validation_error`(cells와 rows·cols 불일치), `502 reading_failed`

### 3.12 `GET /pillboxes/current` — 약통·남은 칸·리필 시점 (G7, G8) ★추가
- 권한: `guardian`
```json
200
{
  "pillbox": { "id": "pb1", "layout": { "…": "…" }, "registered_photo_id": "p-reg1",
               "confirmed_at": "2026-10-24T20:12:00+09:00", "active": true },
  "last_refill": "Refill 객체 또는 null",
  "refill_status": {
    "remaining_cells": 5,
    "covered_until": { "date": "2026-10-30", "weekday": 3, "time_of_day": "evening", "dose_time": "19:00" },
    "needs_refill": false,
    "threshold_cells": 4
  }
}
```
- `remaining_cells`: 기대 상태 기준으로 앞으로 드실 약이 남은 칸 수
- `covered_until`: 남은 약으로 갈 수 있는 마지막 복약 → G7 "목요일 저녁까지 남았어요". 남은 칸이 없으면 `null`
- `needs_refill`: `remaining_cells <= threshold_cells`. 기준값 기본은 미정 (backend 13장 4번). 모의 데이터는 4로 쓴다
- 약통이 없으면 `404 pillbox_required`

### 3.13 `GET /schedule` — 복약 일정 ★추가
- 권한: `any`
- 어르신 폰은 오프라인 대비로 며칠치 로컬 알림을 이 값 + `GET /me`의 `timing`으로 예약한다
```json
200
{
  "pillbox_id": "pb1",
  "slots": [
    { "id": "s-mon-am", "weekday": 0, "time_of_day": "morning", "dose_time": "08:00", "cell_id": "r0c0" },
    { "id": "s-mon-pm", "weekday": 0, "time_of_day": "evening", "dose_time": "19:00", "cell_id": "r1c0" }
  ],
  "updated_at": "2026-10-24T20:15:00+09:00"
}
```
- 일정이 없으면 `slots: []`

### 3.14 `PUT /schedule` — 복약 일정 저장 (G2 칸 매핑, G3 시각)
- 권한: `guardian`
- 전체 교체. 칸 하나에 일정 하나 (같은 `cell_id` 두 번 불가). 같은 `weekday`+`time_of_day`도 두 번 불가
```json
요청
{
  "slots": [
    { "weekday": 0, "time_of_day": "morning", "dose_time": "08:00", "cell_id": "r0c0" },
    { "weekday": 0, "time_of_day": "evening", "dose_time": "19:00", "cell_id": "r1c0" }
  ]
}
```
- `200`: `GET /schedule`과 같은 본문
- 오늘 남은 `scheduled` 상태 복약 건은 새 일정으로 다시 만든다. 이미 물어본 건(`asked` 이후)은 그대로 둔다
- 오류: `409 pillbox_required`, `422 validation_error` (없는 cell_id, 중복)

### 3.15 `POST /refills` — 약통 채움 + 사진 (G7)
- 권한: `guardian`
- `multipart/form-data`: `photo`(필수, 채운 약통), `taken_at`(선택)
- 사진 없이 리필만 기록하는 방법은 없다 (C1)
- 판독이 끝날 때까지 기다린다 (최대 60초)
- `201`: Refill 객체
- 이 리필이 열려 있는 `refill_unconfirmed` 확인 요청을 자동으로 닫지는 않는다 (보호자가 따로 응답)
- 오류: `409 pillbox_required`, `413`, `415`, `429 daily_reading_limit`, `502 reading_failed`

Refill 객체:
```json
{
  "id": "rf1",
  "pillbox_id": "pb1",
  "filled_at": "2026-10-24T20:20:00+09:00",
  "filled_by": { "device_id": "d-g1", "display_name": "민수" },
  "source": "guardian_photo",
  "baseline_reading": {
    "id": "rd-rf1", "photo": { "id": "p-rf1", "taken_at": "…", "url": "…", "url_expires_at": "…" },
    "is_mock": true, "provider": "mock", "model": "mock-v1", "created_at": "…",
    "target_cell_id": null, "classification": null,
    "cells": [
      { "cell_id": "r0c0", "ai_state": "full", "expected": null, "attention": null, "bbox": null },
      { "cell_id": "r0c1", "ai_state": "unclear", "expected": null, "attention": "unclear", "bbox": null }
    ]
  },
  "baseline_cells": [
    { "cell_id": "r0c0", "state": "full", "edited": false },
    { "cell_id": "r0c1", "state": "full", "edited": false }
  ],
  "needs_review": true
}
```
- `source`: `"registration"` (약통 등록) / `"guardian_photo"` (리필 화면) / `"refill_check"` (리필 미기록 확인에 "네")
- `baseline_cells`: 실제 기준선. AI가 `unclear`라고 본 칸은 일단 `full`로 두고 `needs_review: true`로 알린다 → 앱이 그 칸을 보호자에게 확인받는다
- 기준선 값은 `full` / `empty`만 있다

### 3.16 `PUT /refills/{id}/baseline` — 기준선 칸 고치기 ★추가
- 권한: `guardian`
```json
요청
{ "cells": [ { "cell_id": "r0c1", "state": "full" } ] }
```
- 보낸 칸만 바꾼다. `200`: Refill 객체 (`edited: true`, 모두 확인되면 `needs_review: false`)
- 가장 최근 리필만 고칠 수 있다. 그 외는 `409 refill_not_latest`

### 3.17 `GET /dose-events/today` — 오늘 복약 건 (E3, E4, E8, G4)
- 권한: `any`
- 역할별 차이: 어르신 응답은 `latest_reading`, `handoff`가 항상 `null`
```json
200 (어르신)
{
  "date": "2026-10-24",
  "items": [
    {
      "id": "ev-am", "date": "2026-10-24",
      "slot": { "id": "s-fri-am", "weekday": 4, "time_of_day": "morning", "dose_time": "08:00", "cell_id": "r0c4" },
      "scheduled_at": "2026-10-24T08:00:00+09:00",
      "state": "done", "outcome": "taken", "outcome_source": "ai", "decided_by": null,
      "taken_at": "2026-10-24T08:12:30+09:00", "resolved_at": "2026-10-24T08:12:41+09:00",
      "elder_status": "recorded",
      "ask_times": ["2026-10-24T08:00:00+09:00", "2026-10-24T08:10:00+09:00", "2026-10-24T08:20:00+09:00"],
      "handoff_at": "2026-10-24T08:30:00+09:00",
      "retake_deadline_at": null,
      "photos": [ { "id": "p-am", "taken_at": "2026-10-24T08:12:30+09:00",
                    "url": "https://…/api/v1/photo-files/p-am?exp=…&sig=…", "url_expires_at": "2026-10-24T21:05:00+09:00" } ],
      "is_mock": true,
      "latest_reading": null,
      "handoff": null
    },
    {
      "id": "ev-pm", "date": "2026-10-24",
      "slot": { "id": "s-fri-pm", "weekday": 4, "time_of_day": "evening", "dose_time": "19:00", "cell_id": "r1c4" },
      "scheduled_at": "2026-10-24T19:00:00+09:00",
      "state": "asked", "outcome": null, "outcome_source": null, "decided_by": null,
      "taken_at": null, "resolved_at": null,
      "elder_status": "waiting",
      "ask_times": ["2026-10-24T19:00:00+09:00", "2026-10-24T19:10:00+09:00", "2026-10-24T19:20:00+09:00"],
      "handoff_at": "2026-10-24T19:30:00+09:00",
      "retake_deadline_at": null,
      "photos": [], "is_mock": false, "latest_reading": null, "handoff": null
    }
  ],
  "open_handoff_count": null,
  "next_event": { "id": "ev-pm", "scheduled_at": "2026-10-24T19:00:00+09:00", "time_of_day": "evening" }
}
```
- `open_handoff_count`: 보호자만 (가족 전체의 열린 인계 수, G4 "처리할 일" 표시 여부). 어르신은 `null`
- `next_event`: 아직 `scheduled` 또는 `asked`인 가장 이른 건 (E3 "다음 약 시간"). 없으면 `null`
- 어르신 앱은 응답을 받을 때마다 `ask_times`로 로컬 알림을 다시 맞추고, `state`가 `asked`·`retake_requested`·`reminded`가 아닌 건의 알림은 취소한다 (backend 6장)
- 일정이 없으면 `items: []`

### 3.18 `POST /dose-events/{id}/photo` — 약통 사진 올리기 (E5 → E6 → E7)
- 권한: `elder`
- `multipart/form-data`
  - `photo`: 이미지 파일 (JPEG/PNG/HEIC, 최대 10MB)
  - `taken_at`: (선택) 촬영 시각
  - `client_upload_id`: (선택) 앱이 만든 UUID. 네트워크 오류로 다시 보낼 때 같은 값을 쓰면 서버는 판독을 다시 하지 않고 처음 결과를 돌려준다
- 받을 수 있는 상태: `asked`, `retake_requested`, `reminded`, 그리고 늦은 사진용으로 `handed_off(no_response)`. `scheduled`(복약 시각 전)도 받는다 (미리 드신 경우)
- **판독이 끝날 때까지 기다렸다가 응답한다** (최대 60초. E6 "확인하고 있어요"를 그동안 띄움)
```json
200
{
  "result": "recorded",
  "dose_event": { "…": "DoseEvent (어르신 형태)" },
  "is_mock": true
}
```
`result` → 어르신 화면:

| `result` | 화면 | 언제 (backend 6장) |
|---|---|---|
| `recorded` | E7a "고마워요. 저녁 약 기록해 뒀어요." | 정상 |
| `retake` | E7b "사진이 잘 안 보여요. 한 번만 더 찍어주실래요?" | 첫 번째 애매 (+30분 이내) |
| `remind_retake` | E7d "약 드실 시간이에요. 드시고 한 번만 더 찍어주실래요?" | 칸 그대로, 첫 번째, `unchanged_mode = remind_then_retake`, +30분 이내 (R-009, C3) |
| `guardian_notified` | E7c "민수님께 알려드렸어요." | 두 번째 애매·칸 그대로, `handoff_immediately`, 이중 복용 의심, +30분 지난 사진(C3), 판독 한도 초과 |

- 어떤 경우에도 서버는 의료적 지시를 내리지 않는다. 문구는 앱 템플릿이다
- `is_mock: true`면 E7 화면에도 "모의 결과" 배지를 띄운다
- 판독 실패(AI 오류)는 오류 응답이 아니라 애매로 처리해서 `retake` 또는 `guardian_notified`로 돌려준다
- 늦은 사진이 정상이면 `recorded`를 돌려주지만 보호자 인계 건은 열린 채로 두고 사진만 붙인다 (`late_photo: true`). 다시 알리지는 않는다
- 오류: `404 not_found`, `409 event_not_open` (`done`이거나 다른 사유로 인계된 건), `409 reading_in_progress` (같은 건을 판독 중), `413 photo_too_large`, `415 unsupported_media`

### 3.19 `GET /dose-events?from=&to=` — 기간 기록 (G6)
- 권한: `guardian`
- `from`, `to`: `YYYY-MM-DD` (둘 다 포함, 최대 31일)
```json
200
{ "from": "2026-10-18", "to": "2026-10-24", "items": [ "DoseEvent (보호자 형태)", "…" ] }
```
- 오류: `422 validation_error` (31일 초과, from > to)

### 3.20 `GET /handoffs` — 처리할 일 목록 (G4) ★추가
- 권한: `guardian`
- 쿼리: `status=open`(기본) / `closed` / `all`, `limit`(기본 50)
```json
200
{
  "items": [
    {
      "id": "h1", "reason": "unclear", "notified_at": "2026-10-24T19:16:00+09:00",
      "verdict": null, "verdict_by": null, "verdict_at": null,
      "allowed_verdicts": ["taken", "not_taken"],
      "late_photo": false,
      "dose_event": { "…": "DoseEvent (보호자 형태, latest_reading 포함)" }
    }
  ]
}
```
- 목록 항목에는 `readings`, `layout`이 없다 (상세에서 받음)
- 정렬: 열린 건 먼저, 그다음 `notified_at` 최신순

### 3.21 `GET /handoffs/{id}` — 인계 상세 (G5)
- 권한: `guardian`
- `200`: Handoff 객체 (2.6). 예:
```json
{
  "id": "h1", "reason": "unclear", "notified_at": "2026-10-24T19:16:00+09:00",
  "verdict": null, "verdict_by": null, "verdict_at": null,
  "allowed_verdicts": ["taken", "not_taken"],
  "late_photo": false,
  "dose_event": { "id": "ev-pm", "state": "handed_off", "…": "…" },
  "readings": [
    {
      "id": "rd1", "photo": { "id": "p1", "taken_at": "2026-10-24T19:05:00+09:00", "url": "…", "url_expires_at": "…" },
      "is_mock": true, "provider": "mock", "model": "mock-v1", "created_at": "2026-10-24T19:05:04+09:00",
      "target_cell_id": "r1c4", "classification": "unclear",
      "cells": [
        { "cell_id": "r1c4", "ai_state": "unclear", "expected": "empty", "attention": "unclear", "bbox": [0.58, 0.52, 0.12, 0.40] },
        { "cell_id": "r1c5", "ai_state": "full", "expected": "full", "attention": null, "bbox": [0.71, 0.52, 0.12, 0.40] },
        { "cell_id": "r0c3", "ai_state": "full", "expected": "ignored", "attention": null, "bbox": null }
      ]
    },
    { "id": "rd2", "…": "재촬영 판독" }
  ],
  "layout": { "rows": 2, "cols": 7, "…": "…" }
}
```
- G5 강조 표시: `attention`이 `null`이 아닌 칸을 사진 위(`bbox`가 있을 때) 또는 격자 그림 위(`bbox`가 `null`일 때)에 표시한다. 대상 칸(`target_cell_id`)은 다른 모양으로 표시한다
- 신뢰도 숫자는 응답에 없다 (R-008 C5)
- 사유별 문구, [전화하기], 한계 문구("칸이 빈 것만 확인했어요. 드셨는지는 직접 확인해 주세요")는 앱 템플릿이다. 전화번호는 서버가 갖지 않는다 (폰 연락처 사용)
- `reason = refill_unconfirmed`이면 `allowed_verdicts = ["refilled", "not_refilled"]`. 앱은 "약통을 채우셨나요?" [네, 채웠어요] [아니요]를 보여준다

### 3.22 `POST /handoffs/{id}/verdict` — 보호자 판정 (G5, MVP 5)
- 권한: `guardian`
```json
요청
{ "verdict": "taken" }
```
- `verdict`는 그 건의 `allowed_verdicts` 중 하나
- `200`: 갱신된 Handoff 객체
- 효과:
  - `taken` / `not_taken` / `acknowledged` → 복약 건 `done`, `outcome_source = "guardian"`, `decided_by` 기록 ("민수 판정" 표시)
  - `refilled` → 그 판독으로 새 기준선 생성 (source `refill_check`, backend 5.4). 응답의 `dose_event`는 바뀌지 않는다
  - `not_refilled` → 확인 요청만 닫는다
- 오류: `404 not_found`, `409 handoff_already_resolved` (다른 보호자가 먼저 판정함. `details`에 현재 `verdict`, `verdict_by`), `422 verdict_not_allowed`

### 3.23 `GET /photos/{id}` — 사진 서명 URL 새로 받기
- 권한: `any` (같은 가족)
```json
200
{ "id": "p1", "taken_at": "2026-10-24T19:05:00+09:00",
  "url": "https://…/api/v1/photo-files/p1?exp=1761300600&sig=…", "url_expires_at": "2026-10-24T19:10:00+09:00" }
```
- 다른 응답에 들어 있는 `Photo.url`도 같은 방식으로 만든 것이다. 만료되면 이걸로 다시 받는다
- 보관 기간이 지나 삭제된 사진은 `410 photo_expired`

### 3.24 `GET /photo-files/{id}?exp=&sig=` — 사진 바이트 ★추가
- 권한: 없음. `sig` = 서버 비밀값으로 만든 HMAC(`id`, `exp`)
- `200`: 이미지 바이트 (`Content-Type: image/jpeg` 등, `Cache-Control: private, max-age=300`)
- 오류: `403 signature_invalid`, `403 signature_expired`, `410 photo_expired`
- 앱은 이 URL을 만들지 않는다. 서버가 준 `url`만 쓴다

### 3.25 `GET /summaries` — 하루·주간 요약 (G4 한 줄, G6)
- 권한: `guardian`
- 쿼리: `period=day|week`(필수), `from`, `to` (`YYYY-MM-DD`, 기본은 최근 7일 / 최근 4주). 주간은 월~일
```json
200
{
  "items": [
    {
      "period": "day",
      "period_start": "2026-10-24",
      "period_end": "2026-10-24",
      "final": false,
      "counts": {
        "scheduled": 2,
        "taken_ai": 1,
        "taken_guardian": 0,
        "not_taken": 0,
        "acknowledged": 0,
        "open_handoffs": 1,
        "pending": 0
      },
      "handoffs_by_reason": { "no_response": 0, "unclear": 1, "unchanged": 0, "double_suspected": 0, "refill_unconfirmed": 0 },
      "all_normal": false,
      "refill": { "needs_refill": false, "remaining_cells": 5,
                  "covered_until": { "date": "2026-10-30", "weekday": 3, "time_of_day": "evening", "dose_time": "19:00" } },
      "includes_mock": true
    }
  ]
}
```
- `final: false`면 아직 끝나지 않은 기간 (오늘, 이번 주)이라 실시간 계산값이다
- `pending`: 아직 복약 시각 전이거나 진행 중인 건
- `all_normal`: 모든 건이 AI 정상 판독(`taken_ai`)이고 열린 인계가 없으면 true → G4 "오늘 2번 모두 정상", G6 "이번 주 14번 중 14번 정상"
- 문장은 앱이 만든다. 서버는 숫자만 준다
- `includes_mock`: 기간 안에 모의 판독이 하나라도 있으면 true → 요약 옆에 "모의 결과 포함" 표시

### 3.26 `GET /settings`, `PUT /settings` — 설정 (G8)
- 권한: `guardian`
```json
GET 200
{
  "elder_display_name": "어머니",
  "summary_push_enabled": false,
  "summary_push_time": "21:00",
  "photo_retention_days": 90,
  "unchanged_mode": "remind_then_retake"
}
```
- `PUT`: 바꿀 필드만 보낸다. 응답은 `GET`과 같은 본문
```json
PUT 요청
{ "unchanged_mode": "handoff_immediately" }
```
- `unchanged_mode` (R-009): `"remind_then_retake"`(기본, "앱에서 1회 안내 후 다시 찍기") / `"handoff_immediately"`("바로 나에게 알리기"). 앱의 선택지 문구는 FE가 정한다
- `photo_retention_days`: 정수. 허용 범위는 미정 (backend 13장 5번). 지금은 1~365만 검증한다
- 보호자 자신의 표시 이름은 이 API로 바꾸지 않는다 (검토 요청 애매한 지점 11번)
- 바뀐 설정은 바로 다음 판독·요약부터 적용된다
- 오류: `422 validation_error`

---

## 4. 화면별 데이터 출처 (UI 설계 대조)

UI 설계(R-008 조건 반영)의 모든 화면이 필요한 데이터를 얻을 수 있는지 대조했다.

### 4.1 어르신

| 화면 | 필요한 데이터 | 출처 |
|---|---|---|
| 짝짓기 (어르신 폰이 QR 스캔, R-008 C1) | 코드 → 토큰 | `POST /pair` |
| E1 동의 (짝짓기 후) | 보호자 이름, 외부 AI 전송 여부 (C4), 문구 버전 | `POST /pair` 응답 `family.guardians`, `GET /me` `server.ai_external_transfer`·`consent_text_version` → `POST /consent` |
| E3 대기 홈 | 오늘 날짜, 다음 약 시간 | `GET /dose-events/today` `date`, `next_event` |
| E4 복약 시간 질문 | 시간대("저녁"), 호칭, 로컬 알림 시각 (C5) | `GET /dose-events/today` `slot.time_of_day`, `ask_times`; `GET /schedule` + `GET /me` `timing` (오프라인 대비) |
| E5 촬영 → E6 판독 중 | 업로드 대상 건 id | 위 `items[].id` → `POST /dose-events/{id}/photo` |
| E7a / E7b / E7c / E7d | 어떤 화면인지, 모의 여부 | `POST …/photo` 응답 `result`, `is_mock` |
| E8 나 약 먹었나? | 시간대별 기록, 시각, 사진 | `GET /dose-events/today` `elder_status`, `taken_at`, `photos[].url` |
| 모의 판독 띠 | 서버가 모의 판독 중인지 | `GET /me` `server.reader_is_mock` |
| 연결 해제 감지 | 토큰 무효 | 모든 API의 `401 token_revoked` |

### 4.2 보호자

| 화면 | 필요한 데이터 | 출처 |
|---|---|---|
| G1 가족 만들기·호칭 | — | `POST /families` |
| G1 어르신 폰 QR 표시 | QR 값, 6자리 예비 코드, 만료 | `POST /pairing-codes {kind:"elder"}` |
| 보호자 초대 | 초대 코드 | `POST /pairing-codes {kind:"guardian"}` |
| G2 약통 등록 (채운 약통, R-008 C3) | 구조 제안, 시간대 추정, 모의 여부 | `POST /pillboxes/detect` → `POST /pillboxes` (첫 기준선 포함) → 필요하면 `PUT /refills/{id}/baseline` |
| G2 칸 ↔ 요일·시간대 매핑, G3 복약 시각 | 현재 일정 | `GET /schedule`, `PUT /schedule` |
| G4 홈 "처리할 일" | 열린 인계 목록 (리필 확인 요청 포함) | `GET /handoffs?status=open`, `GET /dose-events/today` `open_handoff_count` |
| G4 오늘 상태 한 줄 | 오늘 집계 | `GET /summaries?period=day&from=오늘&to=오늘` |
| G5 인계 상세 | 사유, 사진(재촬영 포함), AI가 본 칸, **애매한 칸 강조 (C5: 숫자 대신 `attention`)**, 대상 칸, 판정 버튼, 모의 여부 | `GET /handoffs/{id}` `reason`, `readings[].photo`, `readings[].cells[].attention`·`bbox`, `layout`, `allowed_verdicts`, `is_mock` |
| G5 판정 [드심]/[안 드심] | — | `POST /handoffs/{id}/verdict` |
| "AI 판독" / "민수 판정" 구분 | 결과 출처, 판정자 이름 | `DoseEvent.outcome_source`, `decided_by.display_name` |
| G6 기록 (하루·주간) | 집계, 건별 기록 | `GET /summaries`, `GET /dose-events?from=&to=` |
| G7 리필 (남은 칸, "목요일 저녁까지") | 남은 칸, 마지막으로 갈 수 있는 복약 | `GET /pillboxes/current` `refill_status` |
| G7 [약통 채웠어요 + 사진 찍기] (R-008 C3) | 기준선 판독, 확인이 필요한 칸 | `POST /refills` → 필요하면 `PUT /refills/{id}/baseline` |
| G8 설정: 호칭, 요약 푸시, 사진 보관, **칸 그대로 처리 방식 (R-009)** | | `GET/PUT /settings` |
| G8 설정: 시각 | | `GET/PUT /schedule` |
| G8 설정: 약통 재등록 | | `POST /pillboxes/detect` → `POST /pillboxes` |
| G8 설정: 연결 해제, 보호자 목록 | | `GET /devices`, `DELETE /devices/{id}` |
| 푸시 수신 | 푸시 토큰 등록 | `PUT /devices/me/push-token` |

### 4.3 푸시 내용 (서버 → 보호자)
푸시 본문의 `data`는 앱이 어느 화면을 열지 정하는 데 쓴다.
```json
{ "type": "handoff", "handoff_id": "h1", "reason": "unclear" }
{ "type": "guardian_joined", "device_id": "d-g2" }
{ "type": "summary", "period": "day", "period_start": "2026-10-24" }
```
- 푸시 제목·본문 문구는 서버 템플릿이다 (보호자용이라 앱 템플릿 원칙 대상 아님). 예: "어머니 저녁 약 사진을 확인해 주세요"
- 정상 복약에는 푸시가 없다 (원칙 2). 요약 푸시는 `summary_push_enabled = true`일 때만

---

## 5. 오류 코드 전체 목록

| HTTP | `code` | 뜻 | 앱 처리 |
|---|---|---|---|
| 400 | `code_invalid` | 없는 짝짓기 코드 | 다시 입력 |
| 401 | `unauthorized` | 토큰 없음·형식 오류·없는 토큰 | 첫 화면 |
| 401 | `token_revoked` | 해제된 기기 | 저장된 토큰 삭제, 첫 화면 |
| 403 | `forbidden_role` | 역할에 맞지 않는 API | (버그) |
| 403 | `consent_required` | 어르신 동의 전 | E1로 |
| 403 | `signature_invalid` / `signature_expired` | 사진 URL 서명 오류·만료 | `GET /photos/{id}`로 새 URL |
| 404 | `not_found` | 없거나 다른 가족 소유 | |
| 404 | `pillbox_required` | (`GET /pillboxes/current`) 약통 없음 | G2로 |
| 409 | `pillbox_required` | (일정·리필) 약통 먼저 등록 | G2로 |
| 409 | `last_guardian` | 마지막 보호자 해제 시도 | |
| 409 | `event_not_open` | 사진을 받을 수 없는 상태의 복약 건 | 어르신: E3로, `GET /dose-events/today` 다시 |
| 409 | `reading_in_progress` | 같은 건을 판독 중 | E6 유지 후 다시 조회 |
| 409 | `handoff_already_resolved` | 다른 보호자가 먼저 판정 | 상세 다시 조회 |
| 409 | `refill_not_latest` | 최근 리필이 아님 | |
| 410 | `code_expired` / `code_used` | 만료·사용된 짝짓기 코드 | 새 코드 발급 안내 |
| 410 | `photo_expired` | 보관 기간이 지나 삭제된 사진 | "보관 기간이 지난 사진" 표시 |
| 413 | `photo_too_large` | 10MB 초과 | 앱에서 줄여서 다시 |
| 415 | `unsupported_media` | 이미지가 아님 | |
| 422 | `validation_error` | 입력 검증 실패 (`details.fields`) | |
| 422 | `consent_incomplete` | 외부 AI 전송 안내 없이 동의 | |
| 422 | `verdict_not_allowed` | 사유에 맞지 않는 판정 값 | |
| 429 | `rate_limited` | IP·요청 속도 제한 (`Retry-After`) | |
| 429 | `daily_reading_limit` | 가족당 하루 판독 30회 초과 (보호자 등록·리필에서만. 어르신 사진은 인계로 처리) | |
| 502 | `reading_failed` | AI 판독 실패 (보호자 등록·리필에서만. 어르신 사진은 애매로 처리) | 다시 찍기 |
| 500 | `internal_error` | 서버 오류 | |
