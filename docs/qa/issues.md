# QA 이슈 (T-QA1)

- 원본은 이 파일이다. 같은 내용을 Notion 이슈 DB에 한 행씩 올린다 (보고자: QA 에이전트)
- 대상: BE main `dec9623` (T-BE4 병합 후), FE main `342a0bb`
- 재현 테스트가 있는 이슈는 `qa/api_scenarios`의 `test_q00N_*` 이다. 고쳐지면 그 테스트가 통과한다
- 알려진 문제였던 2건(동시 GET 때 `no_response` 인계 중복, CORS 없음)은 T-BE4 이후 다시 확인했고 재발하지 않았다 (`test_m10`, `test_m11`, `test_m12`)

| ID | 제목 | 심각도 | 담당 추정 | 원칙 |
|---|---|---|---|---|
| Q-001 | 일정을 저장하면 오늘 이미 지난 복약 시각 건이 바로 무응답 인계되고 보호자 푸시가 감 | 높음 | BE | 5-2 |
| Q-002 | 공백뿐인 호칭·보호자 이름이 받아들여져 빈 문자열로 저장됨 | 낮음 | BE | 5-3 |
| Q-003 | 어르신 화면 일부 글씨가 28pt보다 작음 (판정 배지 16pt, 모의·시뮬레이션 표시 18~20pt, E2 버튼 글씨 24pt) | 낮음 | FE | 5-3 |
| Q-004 | 늦은 사진이 정상이면 어르신에게 "기록해 뒀어요"라고 하지만 E8에는 "아직 기록이 없어요"로 나옴 | 보통 | BE (계약서 판단 필요) | 5-3, 5-5 |
| Q-005 | 애매와 칸 그대로가 이어지면 재촬영을 두 번 요청함 ("재촬영 최대 1회"와 다름) | 낮음 | BE | 5-3 |
| Q-006 | G5 "칸 그대로" 설명이 안내 후 재촬영 기한 초과 건에서 안내 사실을 빠뜨림 | 낮음 | FE | 5-1 |

---

## Q-001 일정을 저장하면 오늘 이미 지난 복약 시각 건이 바로 무응답 인계되고 보호자 푸시가 감

- 심각도: **높음**
- 담당 추정: BE
- 위반 원칙: 5장 2 (보호자 피로 최소화. 정상 상황 알림 금지), 3장 핵심 흐름 (무응답은 "물어봤는데 답이 없을 때")
- 재현:
  1. 가족·어르신 연결·동의·약통 등록까지 한다 (`qa/api_scenarios` `make_family(schedule=False)`)
  2. 지금보다 45분 이른 시각으로 오늘 요일 일정을 저장한다: `PUT /schedule {"slots":[{"weekday":<오늘>,"time_of_day":"morning","dose_time":"<지금-45분>","cell_id":"r0c0"}]}`
  3. 1분 예약 작업이 한 번 돌 때까지(최대 60초) 기다린 뒤 `GET /handoffs`
  - 자동: `qa/api_scenarios/run.sh default -k q001`
- 기대: 일정을 만들기 전에 지나간 오늘 시각은 어르신에게 물어본 적이 없으므로 무응답 인계가 생기지 않는다. api.md 3.14도 "오늘 **남은** `scheduled` 상태 복약 건은 새 일정으로 다시 만든다"고 한다
- 실제: 오늘 건이 지난 시각으로 만들어지고, 다음 예약 작업에서 `asked` → 기한(+30분) 초과로 바로 `handed_off(no_response)`, 보호자 푸시 1건 ("○○ 아침 약 시간에 응답이 없어요")
  ```
  일정 저장 직후 지난 시각(22:19) 건이 바로 인계됨: [('22:19', 'handed_off')], 푸시 1건
  ```
- 영향: 보호자가 처음 약통·일정을 등록하는 날(예: 저녁 8시에 아침 8시·점심 일정 저장), 일정을 고칠 때마다, 그리고 시연 가족 시드(`python -m app.seed_demo create`, 기본 08:00·19:00)를 19:30 이후에 만들면 첫 화면부터 거짓 인계가 1~2건 생긴다. 시연 트리거도 그 칸에는 `409 event_already_started`가 되어 시연이 막힌다
- 근거:
  - `_targets/BE/app/routers/pillboxes.py:280` `put_schedule` → `sync_events(db, auth.family.id, now)`
  - `_targets/BE/app/services/dose.py:46-74` `sync_events`가 오늘 요일 칸을 시각과 관계없이 모두 `scheduled`로 만든다 (`scheduled_at = at_kst(today, slot.dose_time)`, 지난 시각 확인 없음)
  - `_targets/BE/app/services/dose.py:177-194` `advance_event`가 `scheduled_at <= now` → `asked`, `now >= +30분` → `create_handoff(..., "no_response")`
  - 참고: 서버 재시작 등으로 예약 작업이 늦게 돈 경우에는 어르신 폰의 로컬 알림이 이미 물어봤으므로 인계가 맞을 수 있다. 문제는 **일정 저장 시점보다 이른 시각**의 건이다

## Q-002 공백뿐인 호칭·보호자 이름이 받아들여져 빈 문자열로 저장됨

- 심각도: 낮음
- 담당 추정: BE
- 위반 원칙: 5장 3 (어르신 화면 말투. 호칭이 빠진 문장 ", 저녁 약 드실 시간이에요", "님께 알려드렸어요"가 나올 수 있음)
- 재현: `POST /families {"elder_display_name":"   ","guardian_display_name":"지훈"}` (또는 `guardian_display_name`을 공백으로). 자동: `run.sh default -k q002`
- 기대: `422 validation_error` (api.md 3.2 "이름은 1~20자")
- 실제: `201`, 저장된 값은 `""` (응답 `device.display_name: ""`)
- 근거: `_targets/BE/app/routers/pairing.py:47,54` 길이 검증(`min_length=1`)은 strip 전에 하고 저장은 `.strip()` 뒤. 같은 패턴이 `pairing.py:200` (보호자 초대 `display_name`), `account.py:129` (`PUT /settings elder_display_name`)에도 있다
- 참고: FE는 입력을 trim해서 빈 값이면 버튼을 막으므로(`guardian/connect.tsx`) 앱으로는 잘 안 생긴다. API 직접 호출·다른 클라이언트 대비

## Q-003 어르신 화면 일부 글씨가 28pt보다 작음

- 심각도: 낮음
- 담당 추정: FE
- 위반 원칙: 5장 3 (큰 글씨), R-008 "본문 최소 28pt"
- 재현: FE mock 모드(`EXPO_PUBLIC_API_MODE=mock npx expo start --web --port 8299`) → 어르신 → 연결·동의 → 개발 도구로 저녁 약 시뮬레이션 → 사진 찍기 → E7, 그리고 [나 약 먹었나?] E8. 브라우저에서 계산된 `font-size`를 읽음
- 기대: 어르신이 읽어야 하는 글자는 28pt 이상
- 실제 (웹 계산값):
  | 화면 | 글자 | 크기 |
  |---|---|---|
  | E8 | "AI 판독 · 모의 결과", "○○ 판정" 배지 | 16px |
  | E4·E7 | "시뮬레이션 · 실제 복약 시각 알림 아님" | 20px |
  | E7 | "모의 결과" 배지 | 20px |
  | 모든 화면 | 상단 "모의 판독 (실제 AI 아님)" 띠 | 18px |
  | E2 연결 | [숫자로 연결] 버튼 글씨 (`size="guardian"`) | 24px (버튼 높이는 72로 기준 충족) |
- 근거: `_targets/FE/src/components/AiBadge.tsx:17` (`fontSize: 16`, `elder/history.tsx:40,42`에서 사용), `components/MockBanner.tsx:105,109,111`, `app/elder/connect.tsx:68`
- 참고: 모의·시뮬레이션 표시는 심사위원·시연 영상용이라 28pt 대상인지는 판단이 필요하다. E8 판정 배지("○○ 판정")는 어르신이 읽는 정보라 대상으로 본다. E2는 보통 보호자가 대신 조작한다(설계 문서)

## Q-004 늦은 사진이 정상이면 "기록해 뒀어요"라고 하지만 E8에는 "아직 기록이 없어요"

- 심각도: 보통
- 담당 추정: BE (api.md 3.18 계약 그대로 동작함. 계약서 판단 필요, 화면은 FE)
- 위반 원칙: 5장 3 (어르신 혼란), 1장 문제 정의(이중 복용 방지). 판단에 따라 5장 5
- 재현 (fast 프로필): 시연 트리거 → 인계 기한(+1분) + 예약 작업까지 기다려 `handed_off(no_response)` → 정상 사진 업로드. 자동: `run.sh fast -k s07` (현재 계약대로 통과함)
- 기대 (확인 요청): 어르신에게 "기록해 뒀어요"라고 말했으면 E8 "나 약 먹었나?"에서도 기록이 보여야 한다. 또는 기록하지 않을 거면 E7a 대신 다른 문구
- 실제: 업로드 응답 `result: "recorded"` → 앱 E7a "고마워요. 저녁 약 기록해 뒀어요." 그런데 건은 `handed_off`로 남아 `elder_status: "no_record"` → E8 "아직 기록이 없어요". 기억이 짧은 어르신이 E8을 보고 "안 먹었나 보다" 하고 다시 드실 위험이 있다 (앱이 막으려는 이중 복용)
- 근거: `docs/design/api.md:636` "늦은 사진이 정상이면 `recorded`를 돌려주지만 보호자 인계 건은 열린 채로 두고", `api.md:183` `no_record` 조건, `_targets/BE/app/services/dose.py:304-306`, FE `src/app/elder/reading/[id].tsx` (`recorded` → E7a)

## Q-005 애매와 칸 그대로가 이어지면 재촬영을 두 번 요청함

- 심각도: 낮음
- 담당 추정: BE
- 위반 원칙: 5장 3 (최소한의 조작)
- 재현: 시연 트리거 → `POST /dev/mock-scenario {"scenario":"unclear"}` + 사진 → `retake` → `{"scenario":"unchanged"}` + 사진 → `remind_retake` (세 번째 사진 요청). 순서를 바꿔도(`unchanged` → `unclear`) 같다. 자동: `run.sh default -k q005`
- 기대: backend.md 7.1 "재촬영 요청 최대 1회 / 그 뒤에도 애매하면 보호자 판정". 두 번째 사진 뒤에는 보호자에게 넘긴다 (설계 판단이 다르면 문서에 명시)
- 실제: 재촬영(E7b)과 안내 후 재촬영(E7d)을 따로 세서, 어르신이 사진을 3장까지 찍게 된다
- 근거: `_targets/BE/app/services/dose.py:320` (애매는 `retake_count`만 봄), `dose.py:330` (칸 그대로는 `reminded_at`만 봄), `docs/design/backend.md:188`

## Q-006 G5 "칸 그대로" 설명이 안내 후 기한 초과 건에서 안내 사실을 빠뜨림

- 심각도: 낮음
- 담당 추정: FE
- 위반 원칙: 5장 1 (보호자가 판단할 정보)
- 재현: 칸 그대로 1차 → `remind_retake` → 재촬영 없이 재촬영 기한(+15분, fast는 +1분) 초과 → `unchanged` 인계 → 보호자 G5
- 기대: "약 드실 시간이에요"라고 안내했다는 사실이 보인다 (어르신이 안내를 받고도 사진을 안 찍음)
- 실제: 판독이 1건뿐이라 "이번 칸에 약이 그대로 있어요."만 나온다. 안내 문구는 칸 그대로 판독이 2건 이상일 때만 나온다
- 근거: `_targets/FE/src/lib/handoff.ts:18,25` (`unchangedCount >= 2`). 서버 응답에는 안내 여부 필드가 없어서(`reminded_at` 비노출) FE만으로 정확히 고치기 어려울 수 있다 → 필요하면 BE에 필드 추가 요청
