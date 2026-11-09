# 검토 요청: T-BE9 하루 약통 (아침·점심·저녁 3칸)
- 요청자: BE 에이전트
- 날짜: 2026-11-08
- 종류: 코드 (+ 계약 문구 갱신 요청 1건: api.md 3.12 `threshold_cells`)
- 관련 헌장 항목: 4장 MVP #2(AI 판독)·#7(리필 알림), R-054, R-014, R-010 5번

## 무엇을 했는가
1. **`PUT /schedule` 검증 (api.md 3.14 그대로)**: 같은 `cell_id`+`weekday`, 같은 `weekday`+`time_of_day` 중복만 422 `validation_error`(각각 `slots.N.cell_id`, `slots.N`). 같은 칸을 여러 요일에 쓰는 일정(1×3 약통의 아침 칸 = 월~일 아침)은 허용한다. 이전에는 같은 칸이 두 번 나오면 무조건 422였다
2. **기대 상태 수정 (`app/services/expected.py` `expected_states`)**: 이번 주기에 이미 쓴 칸(기대 `empty`)은 뒤에 같은 칸 건이 인계·안 드심·확인함으로 끝나도 **채울 때까지 `empty`로 남는다**. 이전에는 `ignored`로 덮였다
   - 왜: 하루 약통을 채우지 않고 쓰면 같은 칸에 건이 날마다 생긴다. 둘째 날 아침은 `refill_overdue` 인계(→ `ignored`)가 되고, **셋째 날 아침에는 대상 칸 기대가 `ignored`라서 빈 약통 사진이 정상(`taken`)으로 기록됐다.** 테스트로 재현했고 이 수정 없이는 실패한다
   - 일주일 약통은 한 주기에 칸마다 건이 하나라 그대로다. 일주일 약통을 7일 넘게 안 채우는 경우에도 같은 문제가 있었으므로 그 경우도 함께 고쳐진다
3. **리필 기준 (`threshold_cells`) — 정한 규칙**
   - `threshold_cells = 하루 복용 횟수 × min(REFILL_THRESHOLD_DAYS, 약통 가는 일수 − 1)`
   - `약통 가는 일수 = 일정에 쓰인 서로 다른 칸 수 ÷ 하루 복용 횟수` (내림)
   - 일주일 약통 14칸·하루 2번: 7일 → min(2, 6) = 2 → **4칸, 이전과 같음**. 평일만 10칸: 5일 → 4칸(같음)
   - 하루 약통 3칸·하루 3번: 1일 → min(2, 0) = 0 → **0칸**. `needs_refill`은 남은 칸이 0일 때만, 즉 **저녁 복약(또는 저녁 건 인계) 뒤 "오늘 채워야 함"**. 아침·점심 뒤에는 false라 매일 아침부터 경고하지 않는다
   - 이틀 약통 6칸·하루 3번: 2일 → 1 → 3칸 (하루치 남으면 안내)
   - 이전 공식(`하루 횟수 × 2`)이면 하루 약통은 기준 6칸 > 최대 3칸이라 **항상 `needs_refill: true`** 였다
   - 리필 기준선이 없을 때 `needs_refill`은 "일정이 있으면 true"로 썼다 (이전 `threshold > 0`과 일주일 약통에서 같은 결과. 하루 약통은 기준이 0이라 따로 둠)
4. **나머지 값 점검** (하루 약통, 테스트로 확인)
   - `remaining_cells`: 리필 직후 3 → 아침 뒤 2 → 점심 뒤 1 → 저녁 뒤 0 → 리필 3
   - `covered_until`: 아침 전·뒤 "오늘 저녁", 저녁 뒤 `null`, 저녁 뒤 리필하면 "내일 저녁" (같은 칸이 다시 나오면 멈추는 기존 계산이 그대로 맞다)
   - 하루·주간 요약의 `refill`은 `GET /pillboxes/current`와 같은 값 (지금 상태)
   - **리필 알림 = 요약 푸시 문구**(별도 리필 푸시는 없다): 남은 칸 0이면 "약통이 0칸 남았어요" 대신 **"약통을 채워 주세요"**. 남은 칸이 1 이상이면 이전 문구 그대로. 하루 약통은 요약 푸시를 켠 경우에만 하루 한 번(설정 시각)
5. **데모 시드**: `python -m app.seed_demo create --pillbox day` → 1×3 약통(열 이름 아침·점심·저녁), 21칸 일정(아침 08:00 `r0c0`, 점심 12:00 `r0c1`, 저녁 19:00 `r0c2`, 시각은 `--morning`·`--noon`·`--evening`). 기본은 지금처럼 2×7 일주일 약통. `docs/deploy.md` 7장에 적음
6. 일주일 약통 동작과 기존 테스트는 그대로 (기존 테스트 수정 1곳: "다른 요일에 같은 칸 → 422"였던 확인을 계약대로 "같은 요일에 같은 칸 → 422"로)

## 확인한 것
- pytest **196 통과·2 건너뜀** (이전 190 + 새 6개). ruff check·format 통과. 커밋 전 실제 종료 코드로 확인
- `tests/test_daily_pillbox.py`
  - 검증: 같은 칸·같은 요일 422, 같은 요일·시간대 422, 같은 칸 요일마다 200
  - **하루 흐름**: 기준선 → 아침·점심·저녁 정상 기록(인계·푸시 없음, 요약 3번 모두 정상) → 저녁 뒤 `needs_refill: true`·0칸·`covered_until: null`, 요약 푸시 문구 → 20:00 `POST /refills` → 3칸·내일 저녁 → 다음 날 아침 정상 기록, 주간 요약 값
  - **안 채우고 다음 날**: 토요일 아침 빈 약통 → `guardian_notified`, `refill_overdue` 인계, 기록 없음 → (판정 후) 일요일 아침도 `refill_overdue` (위 2번 수정 확인, 수정을 되돌리면 이 테스트가 실패함을 확인) → 채우면 점심 정상
  - **채웠지만 등록 안 함**: 아침 칸만 비고 나머지 차 있음 → `refill_unconfirmed`에 묶임 → "refilled" → 새 기준선, 아침 보호자 판정 taken, 남은 2칸, 점심 정상 (기존 `already_used` 경로)
  - 이틀 약통 기준 3칸
- `tests/test_seed_demo.py`: 하루 약통 시드 (1×3, 21칸, 기준 0, needs_refill false)

## 관련 파일·브랜치·커밋
- BE `be/daily-pillbox` 1cf282a (main a26ee41에서 시작)
  - `app/routers/pillboxes.py`, `app/services/expected.py`, `app/jobs.py`, `app/seed_demo.py`, `docs/deploy.md`
  - `tests/test_daily_pillbox.py`(새), `tests/test_pillbox.py`, `tests/test_seed_demo.py`

## 계약이 모호하거나 다른 점
1. **계약 문구 갱신 필요**: api.md 3.12 "`threshold_cells` = 하루 복용 횟수 × 2"와 backend.md "리필 안내 기준 | 남은 칸 ≤ 하루 복용 횟수 × 2"는 위 3번 규칙과 다르다(일주일 약통 값은 같음). DOCS는 고치지 않았다. 메인 에이전트가 문구를 고치거나 다른 규칙을 정해 주면 따른다. 필드 이름·형태는 그대로
2. **안 채운 하루 약통은 복약마다 `refill_overdue` 인계와 푸시**가 간다 (하루 최대 3번). 계약(3.14 "채우지 않고 다음 날 같은 칸을 쓰면 `refill_overdue`")대로 두었다. 같은 리필 주기에 두 번째부터 푸시를 빼는 것도 한 줄이지만 계약에 없어 하지 않았다. 필요하면 정해 달라
3. 하루 약통에서 기준선 없이(리필 0번) 일정만 있으면 `needs_refill: true`, `remaining_cells: 0` (일주일 약통과 같은 동작)
4. 칸 일부만 공유하는 섞인 약통도 같은 공식(칸 수 ÷ 하루 최대 횟수, 내림)으로 계산한다
5. `MockReader`(무작위 모의 판독)는 하루 약통에서도 무작위라 시연에는 `POST /dev/mock-scenario`(정상 시나리오는 기대 상태를 따름)를 쓰는 것이 안전하다. 바꾼 것은 없다
6. Notion: API 엔드포인트 DB의 `PUT /schedule`·`GET /pillboxes/current` 요약을 갱신했다. 업무 DB에 T-BE9 행이 없어 갱신하지 못했다
