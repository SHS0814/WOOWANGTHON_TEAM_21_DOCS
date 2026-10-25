# QA 이슈 (T-QA1, T-QA1b, T-QA2, T-QA3, T-QA4)

- 원본은 이 파일이다. 같은 내용을 Notion 이슈 DB에 한 행씩 올린다 (보고자: QA 에이전트)
- 대상: 처음 보고 BE main `dec9623`, FE main `342a0bb`. 회귀 확인(T-QA2) BE main `b13a127` (T-BE5, R-024), FE main `29124b2` (T-FE4, R-022)
- Q-001~Q-008의 처리 방향은 메인 에이전트 판정 R-021 (`docs/reviews/requests/20261025-qa-t-qa1-issues.md`)을 따른다. 수정 담당: BE T-BE5, FE T-FE4
- 재현 테스트가 있는 이슈는 `qa/api_scenarios`의 `test_q00N_*` 이다. 고쳐지면 그 테스트가 통과한다
- 알려진 문제였던 2건(동시 GET 때 `no_response` 인계 중복, CORS 없음)은 T-BE4 이후 다시 확인했고 재발하지 않았다 (`test_m10`, `test_m11`, `test_m12`)

| ID | 제목 | 심각도 | 담당 추정 | 원칙 | 상태 (2026-10-25) |
|---|---|---|---|---|---|
| Q-001 | 일정을 저장하면 오늘 이미 지난 복약 시각 건이 바로 무응답 인계되고 보호자 푸시가 감 | 높음 | BE | 5-2 | ✅ 확인됨 (`test_q001` 통과) |
| Q-002 | 공백뿐인 호칭·보호자 이름이 받아들여져 빈 문자열로 저장됨 | 낮음 | BE | 5-3 | ✅ 확인됨 (`test_q002` 통과) |
| Q-003 | 어르신 화면 일부 글씨가 28pt보다 작음 (판정 배지 16pt, 모의·시뮬레이션 표시 18~20pt, E2 버튼 글씨 24pt) | 낮음 | FE | 5-3 | ✅ 확인됨 (화면: E8 "AI 확인" 28px·"모의 결과" 18px, E2 버튼 32px) |
| Q-004 | 늦은 사진이 정상이면 어르신에게 "기록해 뒀어요"라고 하지만 E8에는 "아직 기록이 없어요"로 나옴 | 보통 | BE (계약서 판단 필요) | 5-3, 5-5 | ✅ 확인됨 (`test_q004` 통과, 화면 E8 ✓) |
| Q-005 | 애매와 칸 그대로가 이어지면 재촬영을 두 번 요청함 ("재촬영 최대 1회"와 다름) | 낮음 | BE | 5-3 | ✅ 확인됨 (`test_q005` 통과) |
| Q-006 | G5 "칸 그대로" 설명이 안내 후 재촬영 기한 초과 건에서 안내 사실을 빠뜨림 | 낮음 | FE | 5-1 | ✅ 확인됨 (`test_q006` 통과, 화면 G5 안내 문구) |
| Q-007 | 전날 끝나지 않은 복약 건이 자정이 지나면 어르신 "오늘" 목록에서 사라져 사진을 찍을 수 없음 | 보통 | BE (필드) → FE (화면) | 5-3 | ✅ 확인됨 (clock `test_q007_*` 3개 통과, 화면 E4·E8 "어젯밤 자기 전") |
| Q-008 | 무응답 인계가 기한보다 약 11분 늦게 생긴 일이 1회 있음 (원인 조사) | 낮음 | BE | 5-5 | ✅ 확인됨 (실행 환경 문제로 닫음: 맥 유휴 잠자기, R-024. BE 지연·잠자기 로그, deploy.md 절전 끄기. `test_q008` 지연 47·27·7초) |
| Q-009 | 오늘 건이 무응답 인계되면 어르신 앱에서 늦은 사진을 올릴 길이 없음 (전날 건은 됨) | 보통 | FE (설계 판단 필요) | 5-3, 5-5 | ✅ 확인됨 (R-026 결정·T-FE7 `e23f262`. 개발 빌드 실서버: E8 "드셨으면 약통 사진을 찍어 주세요" + [사진 찍기] → E7a, E8 ✓. E3 안내 문장. 복용 권유 없음) |
| Q-010 | 자정 무렵 시각을 "오전 12시"로 읽어 줌 (정오는 "오후 12시") | 낮음 | FE | 5-3 | ✅ 확인됨 (T-FE7. `spokenTime` 00:00 "밤 12시", 12:00 "낮 12시", 12:30 "낮 12시 30분") |
| Q-011 | Android 개발 빌드에서 어르신 사진 업로드가 서버에 닿지 않음 ("사진을 보내지 못했어요") | 높음 | FE (T-FE9, P0) | 핵심 흐름 차단 | ✅ 확인됨 (FE `7f53291`, R-031. 개발 빌드에서 어르신 4가지·재촬영·E8 늦은 사진, 보호자 등록·리필 업로드 모두 서버 도달) |
| Q-012 | 일정을 바꿔도 어르신 폰 알림은 앱을 다시 시작할 때까지 옛 시각에 울림 | 보통 | FE | 5-2, 5-3 | ✅ 확인됨 (T-FE10 `ae524e7`, R-034. 앱을 켠 채 내일 아침 08:00→09:00 변경과 내일 취침 칸 삭제가 저장 뒤 약 20초 안에 알림에 반영) |
| Q-013 | 기기 시간대가 서울이 아니면 어르신 화면의 날짜·시각이 기기 시각으로 나옴 ("저녁 오전 3시") | 낮음 | FE | 5-3 | ✅ 확인됨 (T-FE10. 기기 LA 시각 토 23:26에도 E3 "10월 25일 일요일 / 저녁 오후 7시", E8 기록 시각 "오후 3시 29분"(서울)) |

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

## Q-007 전날 끝나지 않은 복약 건이 자정이 지나면 어르신 "오늘" 목록에서 사라짐

- 심각도: 보통
- 담당 추정: BE (`GET /dose-events/today`에 전날 미완료 건 포함, `carried_over` 필드) → FE (E3·E8·E4에서 날짜 구분 표시). R-021 판단
- 위반 원칙: 5장 3 (어르신이 약을 먹고도 사진을 찍을 수 없음), 1장 (E8에서 기록이 안 보여 이중 복용 위험)
- 재현:
  - 자동 (서버 시각 제어): `qa/api_scenarios/run.sh clock` (약 1분). `clock_server.py`가 서버 시각을 오늘 23:59:00에서 시작하게 옮겨 띄운다 (제품 코드 변경 없음, `app.clock.clock.now`만 오프셋). 테스트 `test_q007_open_event_carried_over_after_midnight`
  - 수동 (2026-10-24 실제 자정): 토 23:40·23:58 일정 → 00:07에 두 건 모두 `asked`인데 어르신 `GET /dose-events/today`(일요일)에 없음
- 기대 (R-021): 전날 건 중 끝나지 않은 건(`asked`, `retake_requested`, `reminded`, 사진 없는 `handed_off(no_response)`)은 예정 시각 후 6시간 안이면 오늘 목록에 `carried_over: true`로 포함되고, `next_event`도 그 건을 가리킨다
- 실제: 서버 날짜가 바뀌면 오늘 목록이 `items=[]` (전날 23:59 `asked` 건 없음). FE E4는 목록에 건이 없으면 홈으로 돌아가서(`_targets/FE/src/app/elder/ask/[id].tsx` `router.dismissTo('/elder')`) 23:58 약을 00:05에 찍을 수 없다. E8에도 보이지 않는다. 서버는 그 건의 사진을 자정 뒤에도 받는다 (`test_q007_upload_after_midnight_to_previous_day_event` 통과)
- 근거: `_targets/BE/app/routers/dose.py:48-49` (`today = kst_date(now)`, `_events_for(db, family, today, today)`), `docs/design/api.md` 3.17

## Q-008 무응답 인계가 기한보다 약 11분 늦게 생긴 일이 1회 있음

- 심각도: 낮음
- 담당 추정: BE (원인 조사: 1분 작업의 실제 실행 간격·지연 로그). R-021 판단
- 위반 원칙: 5장 5 (예외를 제때 넘기지 못함). api.md 1.6 "최대 1분 늦게"
- 관찰 (2026-10-24, 기본 프로필 서버 하나, 맥에서 실행):
  - 가족 A: `handoff_at` 23:46:26 → 실제 인계 `notified_at` 23:57:45 (약 11분 19초 늦음)
  - 같은 서버의 가족 B: `handoff_at` 00:10:00 → 00:10:07 (정상)
  - 서버 로그에 오류·경고 없음. 서버는 1분 작업이 언제 돌았는지 기록하지 않아서 그 사이 작업이 멈췄는지 알 수 없다
- 재현: 결정적으로 재현하지 못했다. `run.sh fast -k q008`이 세 건의 지연(`notified_at - handoff_at`)을 재서 75초를 넘으면 실패한다. 2026-10-25 낮 실행: 47초·27초·7초로 통과 (재현 안 됨)
- 기대: 기한 + 최대 1분 안에 인계
- 근거 추정: `_targets/BE/app/jobs.py:105-111` 루프는 `run_once` 뒤 `asyncio.sleep(60)`이라 간격 = 60초 + 실행 시간. 맥 절전·App Nap으로 프로세스가 멈췄을 가능성이 있다. 실행 환경 문제면 `docs/deploy.md`의 절전 끄기 안내로 충분하다 (R-021)

## Q-009 오늘 건이 무응답 인계되면 어르신 앱에서 늦은 사진을 올릴 길이 없음

- 심각도: 보통
- 담당 추정: FE (어르신 홈·E4 진입 조건). 계약은 이미 늦은 사진을 받으므로 BE 변경은 없을 수 있음. 설계 판단 필요 (R-022 "열린 건" 정의)
- 위반 원칙: 5장 3 (최소한의 조작으로 기록), 5장 5 (보호자에게 넘긴 뒤에도 사진이 오면 판단 근거가 됨). R-021 Q-004에서 만든 "늦은 정상 사진 = 어르신 기준 기록" 흐름이 앱에서는 거의 쓰이지 않는다
- 재현 (http 모드, 1분 인계 서버): 오늘 칸 시연 트리거 → 어르신 홈이 E4 "저녁 약 드실 시간이에요" (R-022 정상) → 무응답 인계(+1분, 예약 작업) 뒤 어르신 홈 새로 열기 → E3 "다음 약은 아침 …"만 나옴. 저녁 건은 E3에 언급도 없음. `/elder/ask/<그 건 id>`로 직접 가도 홈으로 돌아감
- 기대: 서버가 받는 늦은 사진(api.md 3.18 "늦은 사진용으로 `handed_off(no_response)`", 사진 없는 경우)을 어르신이 올릴 수 있다. 전날 건은 이미 그렇게 한다 (`canTakePhoto`의 carried_over 조건)
- 실제: 오늘 건은 `asked`·`retake_requested`·`reminded`만 E4 대상이라, +30분이 지나 인계되면 어르신이 약을 먹고 사진을 찍으려 해도 앱에서 할 수 없다. E8에는 "아직 기록이 없어요"
- 근거: `_targets/FE/src/lib/openDose.ts` (`canTakePhoto`: 오늘 건 `handed_off` 제외, 전날 건만 허용), `src/app/elder/ask/[id].tsx:20` (`!canTakePhoto(ev)` → 홈), `src/app/elder/index.tsx` (`firstOpenDose`). 서버는 받음: fast `test_s07`, `test_q004` 통과
- 참고: 어르신 폰의 마지막 재질문(+20분) 뒤 인계(+30분)까지 10분이 지나면 바로 이 상태가 된다. 의도한 설계라면(인계 뒤에는 보호자가 처리) api.md 3.18의 늦은 사진 경로가 어떤 화면에서 쓰이는지 문서에 적어 둘 필요가 있다

## Q-010 자정 무렵 시각을 "오전 12시"로 읽어 줌

- 심각도: 낮음
- 담당 추정: FE
- 위반 원칙: 5장 3 (어르신이 이해하기 쉬운 말). Q-007로 자정을 넘긴 취침 약이 어르신 화면에 나오면서 생기는 경우가 늘었다
- 재현: 00:0x에 기록된 건(자정 뒤 찍은 전날 취침 약)의 E8 → "✓ 어젯밤 자기 전 · 오전 12시". 정오 기록은 "오후 12시"
- 기대: 한국어 일상 표현 "밤 12시"·"낮 12시" (또는 "자정"·"정오")처럼 헷갈리지 않는 말
- 실제: `spokenTime`이 0시를 "오전 12시", 12시를 "오후 12시"로 만든다. 치매 어르신에게 "오전 12시"는 낮으로 들릴 수 있다
- 근거: `_targets/FE/src/lib/time.ts:18-24`. E3·E4·E8·G4·G5 모두 같은 함수를 쓴다

## Q-011 Android 개발 빌드에서 어르신 사진 업로드가 서버에 닿지 않음

- 심각도: **높음** (핵심 흐름 차단: 어르신 폰 → AI → 보호자 폰. 메인 에이전트 지정)
- 담당: FE (T-FE9, P0. 원인 조사와 수정)
- 위반: 헌장 7장 "어르신 폰 → AI → 보호자 폰 흐름이 실제로 끝까지 작동". 원칙 위반은 아님
- 발견: T-QA3, 2026-10-25 13:49~13:52 KST. 웹(http 모드)에서는 같은 서버로 업로드가 된다(T-QA1·T-QA2, API 테스트는 httpx). **네이티브 앱에서 실서버로 사진을 올린 것은 이번이 처음**이다
- 재현 환경
  - Mac (Apple Silicon), Android SDK `~/Library/Android/sdk`, JDK 21 (Microsoft OpenJDK 21.0.11)
  - 에뮬레이터 AVD `Medium_Phone`: `sdk_gphone16k_arm64`, **Android 17 (API 37)**, 시간대 Asia/Seoul. 창 없이 실행: `emulator -avd Medium_Phone -no-window -no-audio -no-boot-anim -no-snapshot-save`
  - FE main `425ca96` (T-FE8). 빌드: `_targets/FE`에서 `npm install` 뒤
    `EXPO_PUBLIC_API_MODE=http EXPO_PUBLIC_API_BASE_URL=http://10.0.2.2:18200/api/v1 EXPO_PUBLIC_CREATE_DEMO_FAMILY=true CI=1 npx expo run:android --port 8298` (BUILD SUCCESSFUL 2m18s, debug APK, Metro 8298)
  - BE main `b13a127`, `_targets/BE`에서:
    `DATABASE_URL=sqlite:///…/dev.db PHOTO_DIR=…/photos-dev DEMO_MODE=true DAILY_READING_LIMIT=1000 REASK_OFFSETS_MIN=[1,2] NO_RESPONSE_HANDOFF_MIN=4 RETAKE_WAIT_MIN=7 uv run --no-sync uvicorn app.main:create_app --factory --host 127.0.0.1 --port 18200 --log-config <uvicorn.access INFO 설정>`
- 재현 단계
  1. 데모 가족·4×7 약통·일정을 API로 만들고 어르신 6자리 코드 발급 (`qa/api_scenarios` 도우미와 같은 방식)
  2. 앱: 어르신 폰으로 쓰기 → 6자리 입력 → 동의 → 알림 권한 허용 → 홈. 여기까지 서버에 `POST /pair`, `POST /consent`, `GET /me`·`/dose-events/today`·`/schedule`이 정상 도달
  3. 보호자 토큰으로 `POST /dev/dose-events` (저녁 칸) → 앱 홈이 E4 → [사진 찍기] → 카메라 권한 "앱 사용 중 허용" → 에뮬레이터 가상 카메라 미리보기 정상 → [찍기]
  4. E6 "확인하고 있어요" 잠깐 뒤 **"사진을 보내지 못했어요. 한 번만 더 찍어주실래요?"** (`elder/result/[id]` kind=`error`). 두 번 시도 모두 같음 (13:49:58, 13:51:24)
- 관찰한 것
  - 서버 access 로그에 `POST /api/v1/dose-events/{id}/photo` 줄이 **없다**. 같은 시간대 앱의 `GET /api/v1/dose-events/today` (30초 주기), `GET /schedule`, `GET /me`는 200으로 찍힌다. 서버 오류 로그도 없다 (413·415 같은 거절도 아님. 요청 자체가 안 옴)
  - DB `photos`에 그 건의 사진 없음, 복약 건은 `asked` 그대로
  - 카메라는 사진을 저장했다: `adb shell run-as com.anonymous.woowangfe ls -l cache/Camera/` → `9badc2cb-….jpg` 18468 B (13:49), `b401520f-….jpg` 18346 B (13:51). expo-camera 58.0.12는 `Uri.fromFile(...)`로 `file://` URI를 돌려준다 (`CameraViewModule.kt:292`)
  - logcat(앱 PID): CameraX 정상 열림·닫힘, `ImageReader … abandonLocked: ConsumerBase is abandoned!` (카메라 종료 때 흔한 메시지), 네트워크 오류 로그 없음. Metro 로그에도 JS 오류 없음 (`elder/reading/[id].tsx`가 오류를 잡아 kind=`error`로만 보낸다 → 원인 메시지가 남지 않음)
  - 같은 앱의 JSON POST(`/pair`, `/consent`)는 도달하므로 네트워크·cleartext·주소 문제는 아니고, **multipart 요청(또는 그 전 단계: 사진 URI 전달, `photoForm`)** 에서 실패하는 것으로 보인다
  - Hermes 디버거(Metro `/inspector/debug`)로 JS 오류를 직접 보려 했으나 연결이 바로 닫혀 확인하지 못했다
- 확인해 볼 것 (QA 추정, 판단은 FE)
  1. `reading/[id].tsx` catch의 실제 오류 (`no_photo`인지 `network_error`인지와 메시지)
  2. `PillboxCamera`의 `ready`(onCameraReady)가 false라 `pic`이 undefined인 경로 (`uri` 없음 → `photoForm`이 `no_photo`) — 단 사진 파일은 저장됐다
  3. RN 0.88 Android `FormData` + `{uri, name, type}` 파일 파트 + `fetch(..., {signal})` 조합
  4. 실기기에서도 같은지 (에뮬레이터 한정 여부)
- 영향: 이 빌드로는 어르신이 사진을 올릴 수 없어 정상 기록·재촬영·이중 의심 판정이 모두 안 되고, 결국 무응답 인계로 끝난다. QA 알림 항목 중 사진 업로드가 필요한 N14(사진 뒤 남은 재질문 취소), N25(재촬영 알림, 실서버)와 Q-009 E8 늦은 사진의 실서버 확인이 막힘 → 모의 서버 모드 개발 빌드로 대신 확인
- 스크린샷(로컬, 커밋 안 함): `_targets/run/shots/android/b09-camera.png`, `b10-e7b-retake.png`(실제 화면은 "사진을 보내지 못했어요")
- **원인과 수정 (R-031, FE `7f53291`):** Expo SDK 58의 전역 `fetch`(expo/fetch)가 RN식 `{uri}` FormData 파일 파트를 지원하지 않음 → expo-file-system `File`로 보냄. 개발 빌드 재빌드 없이 JS만 바뀜
- **확인 (T-QA3, 2026-10-25 14:27~14:41):** 같은 에뮬레이터·서버에서 Metro만 다시 불러와 확인. 어르신 정상(E7a)·애매(E7b)→재촬영 정상·칸 그대로(E7d)→다시 그대로(E7c)·이중 의심(E7c), E8 늦은 사진(오늘 무응답 인계 건 → E7a, 인계 `late_photo=true`, E8 ✓), 보호자 약통 등록(`POST /pillboxes/detect` 200, `POST /pillboxes` 201), 리필(`POST /refills` 201). 서버 access 로그에 모두 기록됨 → **확인됨**

## Q-012 일정을 바꿔도 어르신 폰 알림은 앱을 다시 시작할 때까지 옛 시각에 울림

- 심각도: 보통
- 담당 추정: FE
- 위반 원칙: 5장 2 (바뀐 시각에 물어보지 못해 무응답 인계가 생김), 5장 3 (어르신은 앱을 다시 시작하지 않는다). 계획 N17
- 재현 (개발 빌드, 에뮬레이터 API 37, FE `7f53291`, BE `b13a127`): 어르신 앱이 홈(E3)에 떠 있는 상태에서 보호자가 `PUT /schedule`로 내일 아침 08:00 → 09:00 변경 (14:32:36)
  - 70초 뒤 (오늘 목록 30초 주기 갱신 두 번 지남): `dumpsys alarm` 내일 알림이 여전히 08:00·08:01·08:02
  - 앱 강제 종료 후 다시 열기: 09:00·09:01·09:02로 바뀜
- 기대 (계획 N17): 다음 주기 갱신(30초) 안에 바뀐 일정으로 다시 예약, 지운 칸 알림은 취소
- 실제: 일정(`GET /schedule`)은 화면이 처음 붙을 때 한 번만 읽고 주기 갱신하지 않는다. 오늘 건은 서버 `ask_times`라 맞지만, 내일부터 7일치(R-028 N18)는 옛 일정 그대로 울린다. 어르신 폰은 보통 앱을 계속 켜 두므로 며칠씩 이어질 수 있다
- 근거: `_targets/FE/src/notify/ElderNotificationSync.tsx` (`schedule`은 `useApiData(..., [ok])`로 한 번, `today`만 `pollMs: POLL_MS`), `src/notify/elderSchedule.ts` (planAhead는 받은 schedule로만 계산)

## Q-013 기기 시간대가 서울이 아니면 어르신 화면의 날짜·시각이 기기 시각으로 나옴

- 심각도: 낮음 (어르신 폰 시간대가 서울이 아닌 경우는 드묾. 여행, 잘못된 설정)
- 담당 추정: FE
- 위반 원칙: 5장 3 (어르신이 이해하는 말). 계획 N22의 화면 쪽
- 재현: 개발 빌드에서 `adb shell service call alarm 3 s16 America/Los_Angeles` 후 앱 다시 열기 → E3 "10월 24일 토요일 / 다음 약은 저녁 **오전 3시**" (서울 19:00 = LA 03:00)
- 기대: 알림 예약(R-028 N22로 서울 기준 고정, 확인됨)과 같게 화면의 날짜·요일·시각도 서울 기준. 또는 기기 시간대가 다를 때 안내
- 실제: 알림은 서울 19:00에 맞게 울리지만, E3·E4·E8·G4·G5의 날짜·시각은 기기 시간대(`Date.getHours()` 등)로 표시된다. "저녁 약"이 "오전 3시"로 보인다. `doseName`도 기기 날짜로 오늘·어제를 비교해 "어젯밤" 표기가 어긋날 수 있다
- 근거: `_targets/FE/src/lib/time.ts` (`spokenTime`, `longDate`, `weekdayLong`이 기기 시간대 기준), `src/lib/doseLabel.ts` (`dateKey(today)` 기기 날짜). 서울 기준 함수 `src/lib/seoulTime.ts`가 이미 있음
