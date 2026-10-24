# 백엔드 설계 (초안)

- 작성일: 2026-10-24
- 상태: 검토 요청 중 (`docs/reviews/requests/20261024-backend-design.md`)
- 전제 결정: 헌장 9장, `REVIEW_LOG.md` R-001 ~ R-006

> 인계 규칙, 요약 알림, 사진 보관 기간은 사용자가 확정했다 (R-006). 남은 미결정 사항은 13장 참고.

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
| AI | `anthropic` SDK 또는 Ollama. 판독 인터페이스 뒤에서 교체 가능 (7장) |
| 푸시 | Expo Push API (httpx) |
| 배포 | Docker Compose (`restart: always`), 기존 Cloudflare Tunnel |
| 시간대 | 모든 일정은 `Asia/Seoul` 기준으로 계산하고, DB에는 UTC로 저장 |

## 2. 역할 분담

**서버가 진실의 원천이다.** 인계 규칙은 서버 한 곳에만 둔다 (헌장 원칙 1).

| 위치 | 하는 일 |
|---|---|
| 서버 | 짝짓기·인증, 기록 보관, AI 판독, 인계 판단, 보호자 푸시, 무응답 감시, 요약, 리필 계산 |
| 어르신 폰 | 복약 시간 로컬 알림과 재질문 (오프라인에서도 울림), 촬영·업로드, "나 약 먹었나?" 화면 |
| 보호자 폰 | 기록·사진 조회, 애매한 건 판정, 요약 보기, 약통 등록, 리필 완료 표시, 기기·보호자 관리 |

## 3. 인증과 짝짓기

ID와 비밀번호는 없다. **기기 토큰**이 유일한 인증 수단이다 (R-004).

- 기기 토큰: 256비트 난수. 폰의 `expo-secure-store`에 보관하고, 서버에는 해시만 저장한다
- 모든 API 요청은 `Authorization: Bearer <기기 토큰>` 형식이다. 서버는 토큰에서 기기, 가족, 역할을 찾고, **모든 쿼리를 그 가족으로 제한**한다

### 3.1 가족 만들기 (보호자)
보호자 앱에서 "가족 만들기"를 누르고 어르신 호칭(예: "어머니")을 입력한다. 서버가 가족과 보호자 기기를 만들고 토큰을 발급한다.

### 3.2 어르신 폰 연결 (대면)
1. 보호자 앱에서 "어르신 폰 연결"을 누른다. 서버가 1회용 짝짓기 코드를 발급한다
   - QR에 담는 값: 128비트 난수, 10분 후 만료
   - 예비 수단: 6자리 숫자. 10분 후 만료, 5회 틀리면 폐기
2. 어르신 폰에 앱을 설치하고, 보호자가 대신 QR을 스캔한다
3. **동의 화면** (원칙 8): 큰 글씨로 "○○님이 약 사진과 기록을 볼 수 있어요. 괜찮으세요?" [네] 버튼 한 개를 보여준다. 동의 시각을 기록한다
4. 서버가 어르신 기기 토큰을 발급한다. 이 코드는 다시 사용할 수 없다

가족당 어르신 기기는 1대다. 새 기기를 연결하면 이전 기기는 자동으로 해제된다.

### 3.3 보호자 추가 (원격 허용, R-005)
1. 기존 보호자가 "보호자 초대"를 누른다. 서버가 초대 코드를 발급한다 (1회용, 24시간 후 만료). 공유 시트로 메신저에 보낸다
2. 새 보호자가 앱을 설치하고 코드를 입력하면 같은 가족에 합류한다
3. **기존 보호자 전원에게 "○○님이 보호자로 추가됐어요" 알림을 보낸다.** 의도하지 않은 합류를 바로 알아챌 수 있게 하기 위해서다
4. 모든 보호자의 권한은 같다. 어떤 보호자든 다른 보호자나 기기를 해제할 수 있다

### 3.4 해제
보호자 앱에서 기기를 해제하면 토큰이 즉시 무효화된다. 폰을 분실했을 때나 재설치했을 때 사용한다 (재설치 후에는 다시 연결).

## 4. 데이터 모델

| 테이블 | 주요 컬럼 | 비고 |
|---|---|---|
| `families` | id, elder_display_name, summary_push_enabled(기본 false), summary_push_time(기본 21:00), photo_retention_days(기본 90), created_at | 설정은 보호자가 앱에서 바꿈 (R-006) |
| `devices` | id, family_id, role(`elder`/`guardian`), display_name, token_hash, push_token, consent_at, revoked_at, last_seen_at | `last_seen_at`은 선택 기능 8(연락두절)에 쓸 수 있음 |
| `pairing_codes` | id, family_id, kind(`elder`/`guardian`), code_hash, short_code_hash, expires_at, used_at, failed_attempts | |
| `pillboxes` | id, family_id, layout(JSON), registered_photo_id, confirmed_at, active | layout은 5.1 참고 |
| `schedule_slots` | id, family_id, weekday, time_of_day(`morning`/`noon`/`evening`/`bedtime`), dose_time, cell_id | 하나의 복약 시각이 약통의 한 칸에 대응 |
| `refills` | id, family_id, pillbox_id, filled_at, filled_by_device_id | 보호자가 "약통 채움"을 누르면 생성. 이후 기대 상태의 기준이 됨 |
| `dose_events` | id, family_id, slot_id, scheduled_at, state, outcome, resolved_at | 6장 상태 흐름 |
| `photos` | id, family_id, dose_event_id(nullable), path, taken_at, uploaded_by_device_id | 디스크 경로만 저장 |
| `readings` | id, photo_id, provider, model, is_mock, cells(JSON), raw_response, latency_ms, created_at | AI 판독 결과 원본. `is_mock`은 UI 표시에 사용 |
| `handoffs` | id, dose_event_id, reason(`no_response`/`unclear`/`unchanged`/`double_suspected`), notified_at, verdict(`taken`/`not_taken`/null), verdict_by_device_id, verdict_at | |
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

**등록 흐름:** 보호자가 대면으로 약통을 채운 상태로 사진 1장을 찍는다. AI가 칸 배열과 라벨을 추정하고, 보호자가 앱에서 확인하거나 고친다. 그다음 각 칸을 복약 시각에 연결하면 `schedule_slots`가 만들어진다.

## 5. 기대 상태

서버는 마지막 리필 이후의 일정을 보고, 지금 각 칸이 어떤 상태여야 하는지 계산한다.

- 리필 이후 지금 복약 건까지의 칸 → **비어 있어야 함**
- 그 이후 칸 → **차 있어야 함**

판독 결과를 이 기대 상태와 비교해서 분류한다. 그래서 대상 칸 하나만 보는 게 아니라 **사진에 찍힌 모든 칸을 판독한다.** 이렇게 해야 이중 복용(미래 칸이 비어 있음)을 잡을 수 있다.

## 6. 복약 건 상태 흐름

```
scheduled ──(복약 시각)──▶ asked ──(사진 업로드)──▶ reading ──▶ 분류
    │                       │
    │                       ├─(+10분 무응답) 재질문 1   ← 어르신 폰 로컬 알림
    │                       ├─(+20분 무응답) 재질문 2
    │                       └─(+30분 무응답) ▶ handed_off(no_response)   ← 서버 cron
    │
분류:
  ├─ 정상 (대상 칸 비어 있음 + 나머지 칸이 기대와 일치 + 신뢰도 충분)
  │     ▶ done(taken). 알림 없음, 요약에만 반영
  ├─ 애매 (신뢰도 부족 또는 `unclear` 칸 있음)
  │     ▶ retake_requested ─(재촬영)─▶ reading
  │        재촬영 후에도 애매 ▶ handed_off(unclear) → 보호자 판정
  ├─ 칸 그대로 (대상 칸이 차 있음)
  │     ▶ reminded: 어르신 화면에 "약 드실 시간이에요" 1회 안내 + 재촬영 요청
  │        ─(재촬영)─▶ reading. 또 칸 그대로면 ▶ handed_off(unchanged)
  │        ─(+15분 재촬영 없음)─▶ handed_off(unchanged)
  └─ 이중 복용 의심 (기대상 차 있어야 할 칸이 비어 있음)
        ▶ handed_off(double_suspected)

handed_off ──(보호자 판정 또는 확인)──▶ done(taken / not_taken / acknowledged)
```

- 모든 상태 전이는 서버가 결정하고 기록한다. 어르신 폰의 로컬 알림은 "물어보기"만 한다
- 서버 cron은 1분마다 `asked`, `retake_requested`, `reminded` 상태로 기한을 넘긴 건을 찾는다
- 앱이 다시 열리면 서버 상태를 받아 로컬 알림을 다시 맞춘다. 이미 답한 건의 재질문은 취소한다

## 7. 인계 규칙 (R-006에서 사용자 확정)

| 항목 | 기본값 | 비고 |
|---|---|---|
| 재질문 | 2회, +10분 / +20분 | 확정 |
| 무응답 인계 | 복약 시각 +30분 | 확정 |
| 재촬영 요청 | 최대 1회 | 그 뒤에도 애매하면 보호자 판정 |
| "정상" 판정 신뢰도 | 대상 칸 0.9 이상, 나머지 칸 모두 `unclear` 아님 | 임시값. **정확도 검증 결과로 다시 정한다.** 모델이 스스로 매긴 신뢰도는 보정이 안 되어 있을 수 있음 |
| 칸 그대로 | "약 드실 시간이에요" 1회 안내 후 재촬영. 그래도 그대로이거나 15분 안에 재촬영이 없으면 인계 | 확정 (15분은 기본값). 복약 시각 알림과 같은 내용이라 의료 조언에 해당하지 않음 |
| 이중 복용 의심 | 바로 인계 | |
| 판정 대기 중 보호자 재알림 | 없음 | 원칙 2 (피로 최소화) |

**어르신 화면 문구 원칙:** 의료 조언을 하지 않는다 (원칙 6). "약 드실 시간이에요"는 정해진 복약 시각을 알리는 것까지만 한다. 인계 상황에서는 "○○님께 알려드렸어요"까지만 말하고, "한 번 더 드세요"나 "드시지 마세요" 같은 지시는 하지 않는다. 문구는 서버가 아니라 앱에 고정된 템플릿으로 둔다.

## 8. AI 판독 인터페이스

```python
class Reader(Protocol):
    def detect_layout(self, image: bytes) -> LayoutProposal: ...          # 약통 등록 (1회)
    def read_cells(self, image: bytes, layout: Layout) -> CellReadings: ...  # 매 복약
```

- `CellReadings`: 칸마다 `{cell_id, state: "empty"|"full"|"unclear", confidence}`
- 구현체: `ClaudeReader` (structured output으로 JSON 스키마 강제), `OllamaReader`, `MockReader`
- 어떤 구현체를 쓸지는 환경 변수로 고른다. 등록과 매일 판정에 서로 다른 구현체를 쓸 수 있다 (예: 등록은 Claude, 매일은 로컬)
- **`MockReader` 결과는 `readings.is_mock = true`로 저장하고, 앱은 그 결과 옆에 "모의 결과" 배지를 반드시 표시한다** (헌장 6장)
- 판독 원본 응답, 모델명, 지연 시간을 모두 저장한다. 발표의 "실제 결과·오류와 한계"와 정확도 분석에 쓴다
- 모델 선택은 정확도 검증(헌장 8장, ~11/1)으로 정한다. 후보: Claude Haiku 5.5, Sonnet 5.5, Gemma 3 4B, Qwen 2.5 VL 3B/7B

## 9. 예약 작업 (APScheduler)

| 작업 | 주기 | 내용 |
|---|---|---|
| `create_dose_events` | 매일 00:05 | 오늘 일정으로 `dose_events` 생성 |
| `open_due_events` | 1분 | 복약 시각이 된 건을 `asked`로 전환 |
| `escalate_overdue` | 1분 | 기한을 넘긴 무응답·재촬영 건을 인계 |
| `daily_summary` | 매일 (가족 설정 시각) | 하루 요약 생성. **기본은 앱 안에서만 보여줌.** 보호자가 설정에서 켜면 그 시각에 푸시 1건. 정상인 날은 한 줄 |
| `weekly_summary` | 매주 일요일 | 주간 요약. 푸시 여부는 하루 요약 설정을 따름 |
| `refill_check` | 매일 | 남은 칸이 기준 이하이면 하루 요약에 리필 안내를 덧붙임 (별도 알림 없음) |
| `cleanup` | 매일 | 만료된 짝짓기 코드 삭제, 가족별 `photo_retention_days`가 지난 사진 삭제 |

## 10. API 초안

| 메서드 | 경로 | 누가 |
|---|---|---|
| POST | `/families` | 보호자 (새 가족) |
| POST | `/pairing-codes` | 보호자 (어르신 연결용 / 보호자 초대용) |
| POST | `/pair` | 새 기기 (코드 → 토큰) |
| POST | `/consent` | 어르신 |
| GET/DELETE | `/devices`, `/devices/{id}` | 보호자 |
| PUT | `/devices/me/push-token` | 모두 |
| POST | `/pillboxes/detect` | 보호자 (사진 → 배열 제안) |
| POST | `/pillboxes` | 보호자 (확정) |
| PUT | `/schedule` | 보호자 |
| POST | `/refills` | 보호자 |
| GET | `/dose-events/today` | 모두 ("나 약 먹었나?" 화면 포함) |
| POST | `/dose-events/{id}/photo` | 어르신 |
| GET | `/dose-events?from=&to=` | 보호자 |
| POST | `/handoffs/{id}/verdict` | 보호자 |
| GET | `/photos/{id}` | 같은 가족 (짧은 만료 시간의 서명 URL) |
| GET | `/summaries` | 보호자 |
| GET/PUT | `/settings` | 보호자 (요약 푸시, 사진 보관 기간) |

## 11. 개인정보와 보안 (원칙 8)

- 사진은 공개 경로에 두지 않는다. 같은 가족의 토큰으로만, 5분 만료 서명 URL로 제공한다
- 사진 보관 기간: 보호자가 설정. 기본 90일 (R-006)
- Claude API를 쓰면 사진이 Anthropic으로 전송된다. 이 사실을 동의 화면과 발표에 명시한다. 로컬 모델이면 사진이 PC 밖으로 나가지 않는다
- 판독 API 남용 방지: 가족당 하루 판독 30회 제한, Anthropic 콘솔에 월 사용 한도 설정
- 짝짓기 코드 추측 방지: 짧은 만료 시간, 시도 횟수 제한, IP별 속도 제한
- 앱과 저장소에 비밀값을 두지 않는다. API 키는 서버의 `.env`에만 두고, Public GitHub에는 `.env.example`만 올린다

## 12. 운영

- Docker Compose: `api`, `db`, (선택) `ollama`. 모두 `restart: always`
- PC 절전 모드를 끄고, 재부팅하면 Docker가 자동으로 시작되게 한다
- `/health` 엔드포인트를 두고 외부 업타임 모니터에 연결한다. 심사 기간(11/16~) 동안 서버가 꺼지면 바로 알 수 있게 하기 위해서다
- DB는 매일 `pg_dump`로 백업한다
- 심사용 시연 가족: 미리 연결해 둔 어르신 기기와 보호자 기기의 토큰을 README의 테스트 안내에 넣는다. 정확한 제공 방식은 배포 단계에서 정한다

## 13. 미결정 사항

1. "정상" 판정 신뢰도 기준 (정확도 검증 후)
2. AI 모델 (정확도 검증 후)
3. 심사위원용 테스트 계정 제공 방식
