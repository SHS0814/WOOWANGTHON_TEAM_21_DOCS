# 백엔드 설계

- 작성일: 2026-10-24
- 상태: 🟡 조건부 승인 (R-007, R-010). 조건 C1~C5, 사용자 결정 R-009, R-010 결정(애매한 지점 16개)을 반영함. 검토 요청: `docs/reviews/requests/20261024-api-contract.md`
- 전제 결정: 헌장 9장, `REVIEW_LOG.md` R-001 ~ R-009
- API 계약서: `docs/design/api.md`

> 인계 규칙, 요약 알림, 사진 보관 기간은 사용자가 확정했다 (R-006). 칸이 그대로일 때의 처리는 보호자 설정이다 (R-009). 남은 미결정 사항은 13장 참고.

## 1. 구성

```
[어르신 폰 (Expo)] ──┐
                     ├── HTTPS ── Cloudflare Tunnel ── [사용자 PC]
[보호자 폰 (Expo)] ──┘                                   ├─ FastAPI 서버 (+ APScheduler)
                                                         ├─ PostgreSQL
                                                         ├─ 사진 디렉터리 (/data/photos)
                                                         └─ (선택) Ollama + GTX 1660 Super
                     서버 → Claude API (판독, 키는 서버에만 있음)
                     서버 → Expo Push API (보호자 알림)
```

| 영역 | 선택 |
|---|---|
| 언어 | Python 3.12 |
| 웹 | FastAPI, Pydantic |
| DB | PostgreSQL 16, SQLAlchemy 2, Alembic |
| 예약 작업 | APScheduler (서버 프로세스 안에서 실행) |
| AI | `anthropic` SDK 또는 Ollama. 판독 인터페이스 뒤에서 교체 가능 (8장) |
| 푸시 | Expo Push API (httpx) |
| 배포 | Docker Compose (`restart: always`), 기존 Cloudflare Tunnel |
| 시간대 | 모든 일정은 `Asia/Seoul` 기준으로 계산하고, DB에는 UTC로 저장 |

## 2. 역할 분담

**서버가 진실의 원천이다.** 인계 규칙은 서버 한 곳에만 둔다 (헌장 원칙 1).

| 위치 | 하는 일 |
|---|---|
| 서버 | 짝짓기·인증, 기록 보관, AI 판독, 인계 판단, 보호자 푸시, 무응답 감시, 요약, 리필 계산, **재질문·인계 시간값 제공 (C5)** |
| 어르신 폰 | 복약 시간 로컬 알림과 재질문 (오프라인에서도 울림, 시각은 서버값 사용), 촬영·업로드, "나 약 먹었나?" 화면 |
| 보호자 폰 | 기록·사진 조회, 애매한 건 판정, 요약 보기, 약통 등록, 리필 등록(사진), 기기·보호자 관리, 설정 |

## 3. 인증과 짝짓기

ID와 비밀번호는 없다. **기기 토큰**이 유일한 인증 수단이다 (R-004).

- 기기 토큰: 256비트 난수. 폰의 `expo-secure-store`에 보관하고, 서버에는 해시만 저장한다
- 모든 API 요청은 `Authorization: Bearer <기기 토큰>` 형식이다. 서버는 토큰에서 기기, 가족, 역할을 찾고, **모든 쿼리를 그 가족으로 제한**한다

### 3.1 가족 만들기 (보호자)
보호자 앱에서 "가족 만들기"를 누르고 어르신 호칭(예: "어머니")과 자기 이름(예: "민수")을 입력한다. 서버가 가족과 보호자 기기를 만들고 토큰을 발급한다.

### 3.2 어르신 폰 연결 (대면)
1. 보호자 앱에서 "어르신 폰 연결"을 누른다. 서버가 1회용 짝짓기 코드를 발급하고, 보호자 폰이 QR을 띄운다
   - QR에 담는 값: 128비트 난수, 10분 후 만료
   - 예비 수단: 6자리 숫자. 10분 후 만료. 시도 횟수는 IP별로 제한한다 (13장 6번)
2. 어르신 폰에 앱을 설치하고, 보호자가 어르신 폰으로 그 QR을 스캔한다 (R-008 C1)
3. **동의 화면** (원칙 8): 짝짓기 후에 보여준다. 큰 글씨로 "○○님이 약 사진과 기록을 볼 수 있어요. 괜찮으세요?" [네] 버튼 한 개. 외부 AI를 쓰는 설정이면 "사진은 약 칸 확인을 위해 AI 서비스로 보내져요" 한 줄을 넣는다 (R-008 C4). 동의 시각과 보여준 문구 버전을 기록한다
4. 동의 전에는 어르신 기기가 복약 관련 API를 쓸 수 없다. 이 코드는 다시 사용할 수 없다

가족당 어르신 기기는 1대다. 새 기기를 연결하면 이전 기기는 자동으로 해제된다.

### 3.3 보호자 추가 (원격 허용, R-005)
1. 기존 보호자가 "보호자 초대"를 누른다. 서버가 초대 코드를 발급한다 (1회용, 24시간 후 만료). 공유 시트로 메신저에 보낸다
2. 새 보호자가 앱을 설치하고 코드를 입력하면 같은 가족에 합류한다
3. **기존 보호자 전원에게 "○○님이 보호자로 추가됐어요" 알림을 보낸다.** 의도하지 않은 합류를 바로 알아챌 수 있게 하기 위해서다
4. 모든 보호자의 권한은 같다. 어떤 보호자든 다른 보호자나 기기를 해제할 수 있다. 단, 마지막 보호자는 해제할 수 없다

### 3.4 해제
보호자 앱에서 기기를 해제하면 토큰이 즉시 무효화된다. 폰을 분실했을 때나 재설치했을 때 사용한다 (재설치 후에는 다시 연결).

## 4. 데이터 모델

| 테이블 | 주요 컬럼 | 비고 |
|---|---|---|
| `families` | id, elder_display_name, summary_push_enabled(기본 false), summary_push_time(기본 21:00), photo_retention_days(기본 90), **unchanged_mode(`remind_then_retake` 기본 / `handoff_immediately`)**, is_demo(기본 false, R-010 10번), created_at | 설정은 보호자가 앱에서 바꿈 (R-006, R-009) |
| `devices` | id, family_id, role(`elder`/`guardian`), display_name, platform, token_hash, push_token, consent_at, consent_text_version, revoked_at, last_seen_at | `last_seen_at`은 선택 기능 8(연락두절)에 쓸 수 있음 |
| `pairing_codes` | id, family_id, kind(`elder`/`guardian`), code_hash, short_code_hash, expires_at, used_at | |
| `pillboxes` | id, family_id, layout(JSON), registered_photo_id, confirmed_at, active | layout은 4.1 참고 |
| `schedule_slots` | id, family_id, weekday, time_of_day(`morning`/`noon`/`evening`/`bedtime`), dose_time, cell_id | 하나의 복약 시각이 약통의 한 칸에 대응 |
| `refills` | id, family_id, pillbox_id, filled_at, filled_by_device_id, **photo_id, baseline_reading_id, baseline_cells(JSON), ignored_cells(JSON), source(`registration`/`guardian_photo`/`refill_check`)** | **기준선 (C1).** 5장 참고 |
| `dose_events` | id, family_id, slot_id, scheduled_at, state, outcome, outcome_source(`ai`/`guardian`), retake_count, reminded_at, resolved_at, is_simulated | 6장 상태 흐름 |
| `photos` | id, family_id, dose_event_id(nullable), refill_id(nullable), path, taken_at, uploaded_at, uploaded_by_device_id | 디스크 경로만 저장 |
| `readings` | id, photo_id, kind(`layout`/`cells`), provider, model, is_mock, cells(JSON), classification, raw_response, latency_ms, error, created_at | AI 판독 결과 원본. `is_mock`은 UI 표시에 사용 |
| `handoffs` | id, dose_event_id, reason(`no_response`/`unclear`/`unchanged`/`double_suspected`/**`refill_unconfirmed`**), notified_at, verdict, verdict_by_device_id, verdict_at | verdict 값은 사유별로 다름 (7.2) |
| `summaries` | id, family_id, period(`day`/`week`), period_start, body(JSON), sent_at | |

### 4.1 약통 구조 (`pillboxes.layout`)
```json
{
  "rows": 4, "cols": 7,
  "row_labels": ["아침", "점심", "저녁", "취침"],
  "col_labels": ["월", "화", "수", "목", "금", "토", "일"],
  "cells": [{"id": "r0c0", "row": 0, "col": 0}]
}
```
요일만 있는 약통(1×7), 요일×시간대 약통(2×7, 3×7, 4×7), 세로 배열 약통도 같은 형식으로 표현한다 (원칙 4).

**등록 흐름:** 보호자가 대면으로 **약을 채운 약통** 사진 1장을 찍는다 (R-008 C3). AI가 칸 배열과 라벨을 추정하고, 보호자가 앱에서 확인하거나 고친다. 확정하면 같은 사진을 칸 판독해서 첫 기준선(`refills`, source=`registration`)을 만든다. 그다음 각 칸을 복약 시각에 연결하면 `schedule_slots`가 만들어진다.

## 5. 기대 상태와 기준선 (C1, C2)

서버는 **마지막 기준선(refill)** 이후의 일정을 보고, 지금 각 칸이 어떤 상태여야 하는지 계산한다.

### 5.1 기준선은 사진으로 잡는다 (C1)
- 리필은 **사진 1장과 함께** 등록한다. 서버가 그 사진을 칸 판독하고, 결과를 `refills.baseline_cells`에 기준선으로 저장한다
- 판독이 애매한 칸이 있으면 보호자가 앱에서 그 칸을 "차 있음/비어 있음"으로 고친다 (보호자는 약통 앞에 있다). 고친 값이 기준선이 된다
- "약통 채움" 버튼만 누르고 사진을 안 찍는 방식은 두지 않는다

### 5.2 계산 규칙
각 칸의 기대 상태:
1. 시작값은 기준선의 상태 (`full` 또는 `empty`)
2. 기준선 시각 이후, 지금 판독 대상 복약 건 **전**까지의 일정에 대응하는 칸
   - 그 복약 건이 `done(taken)`이면 → **비어 있어야 함**
   - 그 복약 건이 인계됐거나(`handed_off`) `not_taken`·`acknowledged`로 끝났으면 → **비교에서 제외** (C2, 5.3)
3. 지금 판독 대상 칸 → 비어 있어야 정상
4. 그 이후 칸 → 기준선 값 그대로 (보통 **차 있어야 함**)

판독 결과를 이 기대 상태와 비교해서 분류한다. 그래서 대상 칸 하나만 보는 게 아니라 **사진에 찍힌 모든 칸을 판독한다.** 이렇게 해야 이중 복용(미래 칸이 비어 있음)을 잡을 수 있다.

### 5.3 같은 원인으로 다시 인계하지 않는다 (C2)
놓친 칸은 다음 복약 때도 계속 "차 있음"으로 보인다. 이미 인계됐거나 `not_taken`으로 판정된 건의 칸은 이후 비교에서 빼서, 같은 칸 때문에 다시 인계되지 않게 한다.
- R-007 C2는 "기대 = 차 있음"이었으나 **비교 제외**로 확정했다 (R-010 1번). 놓친 칸을 나중에 비우는 건 그 끼니의 늦은 복용이지 이중 복용이 아니다
- 같은 리필 미기록 의심(5.4)도 확인 요청이 열려 있는 동안 다시 만들지 않는다

### 5.4 리필 기록 없이 칸이 다 차 있을 때 (C1)
보호자가 리필을 등록하지 않고 약통을 채웠으면, 지난 칸이 "비어 있어야 함"인데 다 차 있게 보인다.
- 조건: **대상 칸을 뺀 모든 칸이 `full`로 판독**되고, 그중 기대상 비어 있어야 할 칸이 1개 이상
- 처리: 이중 복용이나 불일치로 분류하지 않는다. 대상 칸만 평소대로 판단한다 (비었으면 정상, 차 있으면 칸 그대로)
- 보호자에게 "약통을 채우셨나요?" 확인을 **1회** 요청한다 (`handoffs.reason = refill_unconfirmed`, 푸시 1건)
  - "네, 채웠어요" → 그 사진의 판독 결과로 새 기준선을 만든다 (source=`refill_check`, filled_at = 사진 촬영 시각)
  - "아니요" → 확인 요청을 닫고, 그 판독에서 차 있던 지난 칸들을 비교 제외(`refills.ignored_cells`)로 바꾼다. 다음 리필 등록 전까지 같은 원인으로 다시 묻지 않는다 (R-010 3번)
- **대상 칸 외에 일부 칸만 기대와 다르면**(예: 지난 칸 하나만 차 있음) 재촬영하지 않는다. 대상 칸이 정상이면 정상 기록이다. 불일치는 판독의 `attention`과 하루 요약·G7의 "약통 상태가 기록과 달라요"에만 남긴다. 푸시도 없다 (R-010 2번). 단, 기대상 차 있어야 할 칸이 비어 있으면 이중 복용 의심이다

## 6. 복약 건 상태 흐름

```
scheduled ──(복약 시각)──▶ asked ──(사진 업로드)──▶ reading ──▶ 분류
    │                       │
    │                       ├─(+10분 무응답) 재질문 1   ← 어르신 폰 로컬 알림 (시각은 서버값, C5)
    │                       ├─(+20분 무응답) 재질문 2
    │                       └─(+30분 무응답) ▶ handed_off(no_response)   ← 서버 cron
    │
분류:
  ├─ 정상 (대상 칸 비어 있음 + 나머지 칸이 기대와 일치 + 신뢰도 충분)
  │     ▶ done(taken). 알림 없음, 요약에만 반영
  ├─ 애매 (대상 칸 신뢰도 부족·`unclear`, 다른 칸 `unclear`, 판독 실패)
  │     ▶ retake_requested ─(재촬영)─▶ reading
  │        재촬영 후에도 애매 ▶ handed_off(unclear) → 보호자 판정
  │        (이미 이 건에서 다시 찍어 달라고 했으면 재촬영 없이 바로 인계, R-021 Q-005)
  ├─ 칸 그대로 (대상 칸이 차 있음)  ← R-009 가족 설정 unchanged_mode 로 분기
  │     ├─ remind_then_retake (기본), 그리고 이 건에서 다시 찍어 달라고 한 적 없음, 그리고 복약 시각 +30분 이내 (C3, Q-005)
  │     │     ▶ reminded: 어르신 화면에 "약 드실 시간이에요" 1회 안내 + 재촬영 요청 (E7d)
  │     │        ─(재촬영)─▶ reading. 또 칸 그대로면 ▶ handed_off(unchanged)
  │     │        ─(+15분 재촬영 없음)─▶ handed_off(unchanged)
  │     └─ 그 밖 (handoff_immediately, 두 번째, 또는 +30분 지난 사진)
  │           ▶ handed_off(unchanged). 어르신 화면은 "○○님께 알려드렸어요" (E7c)
  ├─ 이중 복용 의심 (기대상 차 있어야 할 칸이 비어 있음)
        ▶ handed_off(double_suspected)
  └─ 이미 쓴 칸 (R-014): 대상 칸이 이번 주기(마지막 기준선 이후)에 이미 비어 있어야 하는 칸인데 비어 보임
        절대 정상(taken)으로 기록하지 않는다 (원칙 5). 재촬영 없음, 어르신 화면은 E7c
        ├─ 대상 칸 외 칸이 다 차 있음 (5.4 조건) ▶ handed_off(refill_unconfirmed), 이 건을 확인 요청에 묶음
        │     "네" → 그 사진이 새 기준선, 대상 칸이 비었으면 done(taken, 보호자)
        │     "아니요" → 같은 건에 refill_overdue 인계(푸시 없음)로 판정 대기
        └─ 그 밖 (약통이 채워지지 않음) ▶ handed_off(refill_overdue)

(분류와 별개로) 리필 미기록 의심 (5.4) ▶ 보호자 확인 요청 1회. 복약 건 상태에는 영향 없음

handed_off ──(보호자 판정 또는 확인)──▶ done(taken / not_taken / acknowledged)
```

- 모든 상태 전이는 서버가 결정하고 기록한다. 어르신 폰의 로컬 알림은 "물어보기"만 한다
- 서버 cron은 1분마다 `asked`, `retake_requested`, `reminded` 상태로 기한을 넘긴 건을 찾는다
- **상태 전이는 1분 예약 작업과 사진 업로드에서만 한다. GET 요청은 읽기만 한다** (R-018). 같은 복약 건·같은 사유의 열린 인계는 DB 부분 유니크 인덱스로 하나만 허용하고, 예약 작업은 `FOR UPDATE SKIP LOCKED`, 업로드·판정은 행 잠금을 쓴다. 푸시는 커밋이 성공한 뒤에만 보낸다
- 앱이 다시 열리면 서버 상태를 받아 로컬 알림을 다시 맞춘다. 이미 답한 건의 재질문은 취소한다
- **늦은 사진 (C3):** 복약 시각 +30분이 지난 뒤 올라온 사진에는 안내(E7d)도 재촬영 요청도 하지 않는다. 정상이 아니면 바로 인계하고 화면에는 "○○님께 알려드렸어요"만 띄운다. 이미 `handed_off(no_response)`인 건에 사진이 늦게 오면, 그 인계 건에 사진과 판독을 붙이고 다시 알리지는 않는다 (검토 요청 애매한 지점 4번). 그 늦은 사진이 정상이면 `taken_at`을 사진 촬영 시각으로 채워 **어르신 기준 기록된 건**으로 보여준다. 판정은 보호자가 한다 (R-021 Q-004)
- **일정 저장 (R-021 Q-001):** 일정을 저장하거나 바꿀 때, 저장 시각보다 이른 오늘 칸은 오늘 복약 건을 만들지 않는다 (물어본 적 없음 → 무응답 인계 금지, 원칙 2). 매일 00:05 생성과 서버 재시작 뒤 지연 처리는 그날 일정을 모두 만든다
- **자정을 넘긴 건 (R-021 Q-007):** 전날 끝나지 않은 건은 예정 시각 후 6시간 안이면 "오늘" 목록에 `carried_over`로 함께 보여준다
- **복약 시각 전 사진:** `scheduled` 건의 사진은 복약 시각 60분 전부터만 받는다 (R-010 13번)
- **판독 실패·한도 초과:** AI 호출이 실패하면 "애매"로 처리한다 (원칙 5). 가족당 하루 판독 한도(30회)를 넘으면 판독하지 않고 바로 `handed_off(unclear)`로 넘긴다

## 7. 인계 규칙 (R-006, R-009에서 사용자 확정)

### 7.1 기본값

| 항목 | 기본값 | 비고 |
|---|---|---|
| 재질문 | 2회, +10분 / +20분 | 확정. **서버 설정값 하나에서 앱이 내려받는다 (C5)** |
| 무응답 인계 | 복약 시각 +30분 | 확정. 같은 서버 설정값 (C5) |
| 재촬영 요청 | **한 복약 건에 최대 1회. 종류(애매 재촬영, 칸 그대로 안내)와 관계없이 센다** | 두 번째 사진도 정상이 아니면 보호자에게 넘긴다 (R-021 Q-005) |
| "정상" 판정 신뢰도 | 대상 칸 0.9 이상, 나머지 칸 모두 `unclear` 아님 | 임시값. **정확도 검증 결과로 다시 정한다.** 모델이 스스로 매긴 신뢰도는 보정이 안 되어 있을 수 있음 |
| 칸 그대로 | **보호자 설정 (R-009).** 기본 "1회 안내 후 재촬영": "약 드실 시간이에요" 1회 안내 후 재촬영, 그래도 그대로이거나 15분 안에 재촬영이 없으면 인계. 선택 "바로 인계" | 15분은 기본값. 안내는 **복약 시각 +30분 이내에만** (C3). 복약 시각 알림과 같은 내용이라 의료 조언에 해당하지 않음 |
| 이중 복용 의심 | 바로 인계 | |
| 이번 주기에 이미 쓴 칸이 대상 칸 | 정상 기록 금지. 리필 미기록 의심이면 확인 요청에 묶고, 아니면 `refill_overdue`로 바로 인계 | R-014 |
| 리필 미기록 의심 | 보호자 확인 요청 1회 (5.4) | C1 |
| 대상 칸 외 일부 불일치 | 재촬영·알림 없음. 요약·G7에만 표시 (5.4) | R-010 2번 |
| 리필 안내 기준 | 남은 칸 ≤ 하루 복용 횟수 × 2 | R-010 5번. 곱하는 일수는 서버 설정값 `REFILL_THRESHOLD_DAYS` |
| 이미 인계된 칸 | 이후 비교에서 제외, 다시 인계하지 않음 (5.3) | C2 |
| 판정 대기 중 보호자 재알림 | 없음 | 원칙 2 (피로 최소화) |

시간값(재질문 간격, 무응답 인계, 재촬영 대기)은 서버 환경 설정에 한 번만 두고, `GET /me`와 `GET /dose-events/today`로 앱에 내려준다. 앱에는 숫자를 하드코딩하지 않는다 (C5).

### 7.2 인계 사유와 보호자 응답

| 사유 | 언제 | 보호자 응답 (`verdict`) |
|---|---|---|
| `no_response` | +30분 무응답 | `taken` / `not_taken` / `acknowledged` |
| `unclear` | 재촬영 후에도 애매, 판독 한도 초과 | `taken` / `not_taken` (MVP 5) |
| `unchanged` | 칸 그대로 (6장) | `taken` / `not_taken` / `acknowledged` |
| `double_suspected` | 이중 복용 의심 | `taken` / `not_taken` / `acknowledged` |
| `refill_unconfirmed` | 리필 미기록 의심 (5.4) | `refilled` / `not_refilled` |
| `refill_overdue` | 이미 쓴 칸이 대상 칸인데 약통이 안 채워짐 (R-014) | `taken` / `not_taken` / `acknowledged` |

`acknowledged`는 "확인했어요"(드셨는지는 모름)다. `refill_unconfirmed`는 복약 건 상태를 바꾸지 않는다. 단, 이미 쓴 칸 때문에 생긴 확인 요청은 그 복약 건에 묶인다 (R-014).

**어르신 화면 문구 원칙:** 의료 조언을 하지 않는다 (원칙 6). "약 드실 시간이에요"는 정해진 복약 시각을 알리는 것까지만 한다. 인계 상황에서는 "○○님께 알려드렸어요"까지만 말하고, "한 번 더 드세요"나 "드시지 마세요" 같은 지시는 하지 않는다. 문구는 서버가 아니라 앱에 고정된 템플릿으로 둔다. 서버는 어떤 화면을 띄울지(`result`)만 알려준다.

## 8. AI 판독 인터페이스

```python
class Reader(Protocol):
    def detect_layout(self, image: bytes) -> LayoutProposal: ...          # 약통 등록 (1회)
    def read_cells(self, image: bytes, layout: Layout) -> CellReadings: ...  # 매 복약, 리필 기준선
```

- `CellReadings`: 칸마다 `{cell_id, state: "empty"|"full"|"unclear", confidence, bbox?}`. `bbox`(사진 안의 칸 위치)는 모델이 줄 수 있을 때만 채운다
- 구현체: `ClaudeReader` (structured output으로 JSON 스키마 강제), `OllamaReader`, `MockReader`
- 어떤 구현체를 쓸지는 환경 변수로 고른다. 등록과 매일 판정에 서로 다른 구현체를 쓸 수 있다 (예: 등록은 Claude, 매일은 로컬)
- **`MockReader` 결과는 `readings.is_mock = true`로 저장하고, 앱은 그 결과 옆에 "모의 결과" 배지를 반드시 표시한다** (헌장 6장). API는 판독 결과마다 `is_mock`을 내려준다
- 모델이 매긴 원본 신뢰도 숫자는 저장만 하고 보호자 API로 내보내지 않는다. 대신 "AI가 확실하지 않다고 본 칸"을 표시한다 (R-008 C5)
- 판독 원본 응답, 모델명, 지연 시간을 모두 저장한다. 발표의 "실제 결과·오류와 한계"와 정확도 분석에 쓴다
- 모델 선택은 정확도 검증(헌장 8장, ~11/1)으로 정한다. 후보: Claude Haiku 5.5, Sonnet 5.5, Gemma 3 4B, Qwen 2.5 VL 3B/7B. 검증 하네스는 서버 저장소의 `harness/`에 둔다

## 9. 예약 작업 (APScheduler)

| 작업 | 주기 | 내용 |
|---|---|---|
| `create_dose_events` | 매일 00:05 | 오늘 일정으로 `dose_events` 생성 |
| `open_due_events` | 1분 | 복약 시각이 된 건을 `asked`로 전환 |
| `escalate_overdue` | 1분 | 기한을 넘긴 무응답·재촬영·안내 건을 인계 |
| `daily_summary` | 매일 (가족 설정 시각) | 하루 요약 생성. **기본은 앱 안에서만 보여줌.** 보호자가 설정에서 켜면 그 시각에 푸시 1건. 정상인 날은 한 줄 |
| `weekly_summary` | 매주 일요일 | 주간 요약. 푸시 여부는 하루 요약 설정을 따름 |
| `refill_check` | 매일 | 남은 칸이 기준 이하이면 하루 요약에 리필 안내를 덧붙임 (별도 알림 없음). 기준값은 13장 |
| `cleanup` | 매일 | 만료된 짝짓기 코드 삭제, 가족별 `photo_retention_days`가 지난 사진 삭제 |

## 10. API

요청·응답 스키마, 오류 코드, 인증은 **`docs/design/api.md`** 가 기준이다. 아래는 목록만 둔다. ★ 표시는 이번 계약서에서 추가한 경로다 (검토 요청 `20261024-api-contract.md`).

| 메서드 | 경로 | 누가 |
|---|---|---|
| GET | `/health` | 누구나 (업타임 모니터) |
| POST | `/families` | 보호자 (새 가족) |
| POST | `/pairing-codes` | 보호자 (어르신 연결용 / 보호자 초대용) |
| POST | `/pair` | 새 기기 (코드 → 토큰) |
| POST | `/consent` | 어르신 |
| GET ★ | `/me` | 모두 (내 기기, 가족 호칭, 서버 시간값 C5, 모의 판독 여부) |
| GET/DELETE | `/devices`, `/devices/{id}` | 보호자 |
| PUT | `/devices/me/push-token` | 모두 |
| POST | `/pillboxes/detect` | 보호자 (사진 → 배열 제안) |
| POST | `/pillboxes` | 보호자 (확정 + 첫 기준선) |
| GET ★ | `/pillboxes/current` | 보호자 (약통 구조, 남은 칸, 리필 시점) |
| GET ★ / PUT | `/schedule` | GET 모두, PUT 보호자 |
| POST | `/refills` | 보호자 (사진과 함께, C1) |
| PUT ★ | `/refills/{id}/baseline` | 보호자 (기준선 칸 수정) |
| GET | `/dose-events/today` | 모두 ("나 약 먹었나?" 화면 포함) |
| POST | `/dose-events/{id}/photo` | 어르신 |
| GET | `/dose-events?from=&to=` | 보호자 |
| GET ★ | `/handoffs`, `/handoffs/{id}` | 보호자 (처리할 일, 인계 상세) |
| POST | `/handoffs/{id}/verdict` | 보호자 |
| GET | `/photos/{id}` | 같은 가족 (짧은 만료 시간의 서명 URL) |
| GET ★ | `/photo-files/{id}?exp=&sig=` | 서명 URL 자체 (토큰 없이 이미지 바이트) |
| GET | `/summaries` | 보호자 |
| GET/PUT | `/settings` | 보호자 (호칭, 요약 푸시, 사진 보관 기간, 칸 그대로 처리 방식) |

## 11. 개인정보와 보안 (원칙 8)

- 사진은 공개 경로에 두지 않는다. 같은 가족의 토큰으로만, 5분 만료 서명 URL로 제공한다
- 사진 보관 기간: 보호자가 설정. 기본 90일 (R-006)
- Claude API를 쓰면 사진이 Anthropic으로 전송된다. 이 사실을 동의 화면과 발표에 명시한다. 로컬 모델이면 사진이 PC 밖으로 나가지 않는다
- 판독 API 남용 방지: 가족당 하루 판독 30회 제한, Anthropic 콘솔에 월 사용 한도 설정
- 짝짓기 코드 추측 방지: 짧은 만료 시간, IP별 시도 횟수와 속도 제한
- 앱과 저장소에 비밀값을 두지 않는다. API 키는 서버의 `.env`에만 두고, Public GitHub에는 `.env.example`만 올린다
- 정확도 검증용 실사진은 저장소에 커밋하지 않는다 (`harness/data/`는 `.gitignore`). 저장소에는 합성 샘플만 둔다

## 12. 운영

- Docker Compose: `api`, `db`, (선택) `ollama`. 모두 `restart: always`
- PC 절전 모드를 끄고, 재부팅하면 Docker가 자동으로 시작되게 한다. 11/8 전에 재부팅 자동 복구를 한 번 시험한다 (R-007 권고)
- `/health` 엔드포인트를 두고 외부 업타임 모니터에 연결한다. 심사 기간(11/16~) 동안 서버가 꺼지면 바로 알 수 있게 하기 위해서다
- DB는 매일 `pg_dump`로 백업한다
- Alembic, 업타임 모니터, `pg_dump` 같은 운영 작업은 MVP 1~5가 동작한 뒤에 붙인다 (R-007 권고)
- **심사용 시연 가족 (C4):**
  - 실제 가족과 분리된 별도 가족을 만들고, **샘플 약통 사진만** 쓴다
  - 접근 정보(토큰 또는 짝짓기 방법)는 **Public README에 넣지 않고, 비공개인 제출 폼에만** 적는다. README에는 "심사용 접근 정보는 제출 폼 참고"라고만 쓴다
  - 심사 종료(11/21) 후 시연 가족의 토큰을 모두 폐기한다
- **시연 트리거 (R-010 10번):** `POST /dev/dose-events`는 서버 `DEMO_MODE=true`이고 가족 `is_demo=true`일 때만 동작한다 (그 밖에는 404). 복약 시각만 앞당기고 판독·분류·인계는 실제 흐름을 탄다. 그 건은 `is_simulated=true`로 저장하고 앱은 "시뮬레이션"을 표시한다

## 13. 미결정 사항

1. "정상" 판정 신뢰도 기준 (정확도 검증 후). **임시 0.9** (R-038, 정답 라벨 확인 뒤 확정)
2. ~~AI 모델~~ → 우선 OpenAI `gpt-6-luna`로 작동 (R-037, R-038). 비교 검증은 추가로
3. 심사위원용 접근 방식의 세부 (토큰을 직접 줄지, 짝짓기 코드를 줄지). 원칙은 12장 C4로 확정
4. ~~리필 안내 기준~~ → 하루 복용 횟수 × 2로 결정 (R-010 5번)
5. 사진 보관 기간 설정의 허용 범위
6. ~~6자리 예비 코드 시도 제한~~ → IP별 10분 5회 실패로 결정 (R-010 7번)
