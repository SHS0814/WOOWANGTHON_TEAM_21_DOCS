# QA 시나리오 계획 (T-QA1)

- 작성: QA 에이전트, 2026-10-24
- 대상: BE `WOOWANGTHON_TEAM_00_BE` main, FE `WOOWANGTHON_TEAM_00_FE` main (각각 `_targets/`에 복사해서 실행)
- 기준 문서: 헌장 3·5·6장, `design/backend.md`, `design/api.md`, UI 설계 `reviews/requests/20261024-ui-ux-screen-design.md` (R-008), `REVIEW_LOG.md` R-006~R-019
- 자동 테스트: `qa/api_scenarios/` (실행법은 `docs/qa/results.md`)
- 결과: `docs/qa/results.md`, 이슈: `docs/qa/issues.md`

## 1. 테스트 환경과 수단

| 항목 | 값 |
|---|---|
| BE | `_targets/BE`, 포트 18200, SQLite, `DEMO_MODE=true`, 판독기 `mock`, 푸시는 기록만(`EXPO_PUSH_ENABLED=false`) |
| FE 웹 | `_targets/FE`, `npx expo start --web --port 8299`, mock 모드 (http 모드는 T-BE4 CORS 이후) |
| 약통 | 테스트용 1×4 (`r0c0` 아침, `r0c1` 점심, `r0c2` 저녁, `r0c3` 취침). 오늘 요일에만 일정, 복약 시각 23:59 |
| 시각 당기기 | 시연 트리거 `POST /dev/dose-events` (복약 시각 = 지금, `is_simulated=true`) |
| 판독 결과 지정 | ① `POST /dev/mock-scenario` (T-BE4, api.md 3.28) ② MockReader가 사진 해시로 결과를 정하는 점을 이용해, 원하는 칸 상태가 나오는 사진 바이트를 찾아 올림 (`find_photo`, 칸별 상태까지 지정 가능) |
| 기한 경과 | 서버에 시각을 옮기는 HTTP 수단이 없다 (`app/clock.py`는 프로세스 안 테스트 전용). **fast 프로필** 서버(`NO_RESPONSE_HANDOFF_MIN=1`, `RETAKE_WAIT_MIN=1`)에서 실제로 기다린다. T-BE4 이후 인계는 1분 예약 작업이 하므로 기한 + 최대 1분 |
| 서버 시각 옮기기 | **clock 프로필** (T-QA1b): `qa/api_scenarios/clock_server.py`가 `app.clock.clock.now`를 오프셋으로 바꿔 서버 시각을 오늘 23:59:00에서 시작한다 (제품 코드 변경 없음). 자정 경계용 |
| 보호자 푸시 확인 | 서버 로그(`RecordingPushSender`의 `push(skip) to <기기>`)를 보호자 기기 id로 센다 |

## 2. 시나리오

표의 "자동"은 `qa/api_scenarios`의 테스트 이름이다. P = 기본 프로필, F = fast 프로필, C = clock 프로필.

| ID | 시나리오 | 확인할 것 (기대 결과) | 근거 | 자동 |
|---|---|---|---|---|
| S01 | 짝짓기와 동의 | 가족 만들기 → elder 코드 → QR/6자리 연결 → 동의 전 `403 consent_required`(허용 3개 제외) → 동의 → 사용 가능. 새 elder 코드는 이전 코드 무효, 새 어르신 연결은 이전 어르신 기기 해제. 보호자 초대는 이름 필수, 기존 보호자에게 "추가됐어요" 푸시. 호칭은 입력값 그대로 | backend 3장, api 3.2~3.6, R-004, R-005, R-008 C1 | P `test_s01_*` |
| S02 | 정상 | `recorded`, 건 `done/taken/ai`, `is_mock`, 인계 0건, **보호자 푸시 0건**, 어르신 응답에 판독·인계 없음, E8 `recorded`+사진, 같은 `client_upload_id` 재전송은 판독 1회 | 3장, 원칙 2, api 3.18 | P `test_s02_*`, `test_m02_normal` |
| S03 | 애매 → 재촬영 → 보호자 판정 | 1차 `retake`(`retake_requested`, 기한 있음) → 2차도 애매면 `unclear` 인계(푸시 1) → `allowed_verdicts` = 드심/안 드심, 다른 값 422 → 판정 시 `done/guardian`, `decided_by` 이름 → 두 번째 판정 409. 대상 칸 비었어도 신뢰도 낮으면 정상 금지(`low_confidence`). 재촬영 기한 초과 시 `unclear` 인계 | 원칙 1·5, MVP 5, backend 6장 | P `test_s03_*`, `test_m03`, `test_m04`; F `test_s03_retake_timeout_*` |
| S04 | 칸 그대로 (R-009 두 모드, +30분 규칙) | 기본 `remind_then_retake`: 1차 `remind_retake`(E7d) → 2차 그대로면 `unchanged` 인계, 안내 뒤 정상이면 기록, 안내 뒤 기한 초과면 인계. `handoff_immediately`: 바로 인계. **+30분(인계 기한)이 지난 사진에는 안내 없음** (C3) | R-006, R-009, R-007 C3 | P `test_s04_*`, `test_m05`, `test_m06`; F `test_s04_*` |
| S05 | 이중 복용 의심 | 기대상 차 있어야 할 칸이 비어 보이면 `double_suspected` 인계, 그 칸 `attention=unexpected_empty`, 어르신 E7c·E8 `no_record`. 이미 인계된 칸은 이후 비교 제외(같은 칸으로 재인계 없음) | 3장, R-007 C2 | P `test_s05_*`, `test_m07` |
| S06 | 무응답 → 인계 | 기한(+30분, fast는 +1분) 지나면 `no_response` 인계 1건, 푸시 1건, 다시 조회해도 중복 없음. 어르신 화면에 사유 없음 | 3장, R-006, R-007 C2, R-019 | F `test_s06_*`, P `test_m11` |
| S07 | 늦은 사진 | `no_response` 인계 뒤 사진: 정상이면 `recorded`, 인계는 열린 채 `late_photo=true`, 새 인계·푸시 없음. 칸 그대로여도 새 인계 없음 | backend 6장 C3, api 3.18 | F `test_s07_*` |
| S08 | 이미 쓴 칸 (R-014·R-015) | 대상 칸이 이번 주기에 이미 비어야 하는 칸인데 비어 보이면 절대 정상 기록 안 함. 다른 칸이 다 차 있지 않으면 `refill_overdue`, 다 차 있으면 `refill_unconfirmed`(건에 묶임) → 네: 새 기준선 + `done/taken/guardian` / 아니요: 같은 건에 `refill_overdue`(푸시 없음) | R-014, R-015, api 3.22 | P `test_s08_*`, `test_m09` |
| S09 | 리필 확인 네/아니요 (건과 무관) | 대상 칸 정상 + 지난 칸이 다 차 보임 → `recorded` + `refill_unconfirmed` 1회. 네 → 기준선 `refill_check`, 건은 그대로. 아니요 → 차 있던 지난 칸 `ignored`, 다시 묻지 않음. 열려 있는 동안 중복 요청 없음 | backend 5.4, R-010 3번, C1·C2 | P `test_s09_*` |
| S10 | 지난 칸 불일치 (`pillbox_mismatch`) | 대상 칸 정상 + 지난 칸 하나만 기대와 다름 → `recorded`, 재촬영·푸시 없음, `GET /pillboxes/current`와 하루 요약에 `pillbox_mismatch` | R-010 2번 | P `test_s10_*` |
| S11 | 기기 해제 → `token_revoked` | 해제 즉시 `401 token_revoked`, 목록에서 빠짐, 재해제 404, 마지막 보호자 `409 last_guardian`. 다른 가족 자원은 404 | backend 3.4, api 3.8, 원칙 8 | P `test_s11_*` |
| S12 | 요약 `all_normal` | 모든 건이 AI 정상이고 열린 인계가 없으면 true(하루·주간), 인계가 있으면 false. `includes_mock`, `includes_simulated` 표시 | MVP 6, 원칙 2, api 3.25 | P `test_s12_*` |
| S13 | 시연 트리거 (`is_simulated`) | 데모 가족만(그 밖 404), `asked`·`is_simulated=true`, 기한 재계산, 같은 칸 두 번 409, 다른 요일 422. 어르신·보호자 응답 모두 표시 | R-010 10번, 6장 | P `test_s13_*` |
| S14 | 오류 코드 | 오류 형식 `{"error":{code,message,details}}`. 401(없음·형식·없는 토큰), 403 `forbidden_role`, 404, 409(`pillbox_required`, `event_not_open`, `refill_not_latest`, `handoff_already_resolved`, `event_already_started`), 410(`code_used`), 413, 415, 422(`validation_error`, `verdict_not_allowed`), 429(`rate_limited`+`Retry-After`, `daily_reading_limit`), 사진 서명 403, 복약 60분 전 사진 창 | api 1.5, 5장, R-010 13번 | P `test_s14_*`, F `test_s14_daily_*` |
| S15 | T-BE4 회귀 | 동시 업로드·동시 GET에서 인계 중복 없음, CORS 허용 출처만 통과, mock-scenario는 데모·mock에서만, 사진 1장에만 적용 | R-018, R-019 | P `test_m*` |
| S16 | 자정 경계 | 전날 끝나지 않은 건(`asked` 등)은 예정 시각 후 6시간 안이면 오늘 목록에 `carried_over: true`, `next_event`가 그 건. 자정 뒤 사진 업로드 가능 | R-021 (Q-007) | C `test_q007_*` |
| S17 | 무응답 인계 지연 | 기한 + 최대 1분(테스트 기준 75초) 안에 인계 | api.md 1.6, R-021 (Q-008) | F `test_q008` |
| U01 | 어르신 화면 점검 (FE mock) | E1~E8 문구·글씨·버튼 (아래 점검표) | 원칙 3·6·7, R-008 | 수동 (브라우저) |
| U02 | 보호자 화면 점검 (FE mock) | G4 처리할 일·상태 한 줄, G5 사유·사진·격자 강조·한계 문구·판정 버튼·모의 배지 | 원칙 1·2·7, R-008 C5 | 수동 |
| U03 | FE http 모드 연동 | 실제 BE(18200)에 붙여서 G4 무응답 표시, G5 판정, G6, G7, G8 해제 → 어르신 `token_revoked` 첫 화면 이동 | R-018, R-020 | 수동 |

## 3. 원칙 점검표

| # | 점검 | 방법 | 근거 |
|---|---|---|---|
| C1 | 어르신 화면에 의료 지시 문구 없음 ("더 드세요", "드시지 마세요", 용량, "안 드셨어요", "미복용") | FE 소스 문구 검색 + E1~E8 화면 확인. 서버는 어르신 응답에 사유·판독을 주지 않는지 API로 확인 | 원칙 6, backend 7.2 |
| C2 | 모의·시뮬레이션 표시 누락 없음 | 모든 판독 응답 `is_mock`, 요약 `includes_mock`/`includes_simulated`, 화면의 "모의 판독" 띠·"모의 결과"·"AI 판독 · 모의 결과"·"시뮬레이션" | 헌장 6장 |
| C3 | 정상인데 보호자 푸시 없음 | 정상·지난 칸 불일치·늦은 정상 사진에서 서버 푸시 기록 0건(또는 늘지 않음) | 원칙 2 |
| C4 | 신뢰도 숫자 비노출 | 보호자 응답 JSON 전체에 `confidence` 키 없음, G5 화면에 숫자 없음 | R-008 C5 |
| C5 | 어르신 글씨 28pt·버튼 72pt 이상 | 웹 화면에서 계산된 `font-size`와 버튼 높이를 읽음 | 원칙 3, R-008 |
| C6 | 호칭 하드코딩 없음 | FE 소스에서 "어머니/민수" 등 검색(모의 데이터 제외), 화면 호칭이 서버 값인지 | R-008 |
| C7 | 한계 문구 | E8 "사진으로 약 칸이 빈 것만 확인해요", G5 "칸이 빈 것만 확인했어요. 드셨는지는 직접 확인해 주세요" | 원칙 7 |
| C8 | 결정은 사람 | 보호자 판정이 결과에 반영되고 "○○ 판정"으로 구분 | 원칙 1 |

## 4. 하지 않은 것 (범위·수단 한계)

- 실제 AI 판독기(Claude, Ollama): 정확도 검증(R-011) 전이라 mock만
- 실제 Expo 푸시 발송, 어르신 폰 로컬 알림·전체 화면 알림: 웹·서버만으로는 확인 불가
- 하루·주간 요약 푸시 시각(`summary_push_time`), 사진 보관 기간 정리(`cleanup`): 아직 안 함. clock 프로필로 가능해졌다 (다음 작업 후보)
- 외부 AI 전송 동의(`consent_incomplete`): mock 판독기에서는 `ai_external_transfer=false`라 재현 불가
- 시나리오는 "오늘 요일" 일정을 쓰므로 자정 전후 10분에는 돌리지 않는다

## 5. 로컬 알림·푸시 (T-FE5, R-025)

- 대상: FE main `fe297aa` (`src/notify/`), T-FE6 `1f1ae84` (R-027), T-FE8 (R-028, 병합 예정). 어르신 로컬 복약 알림, 보호자 인계 푸시 등록, 알림을 누르면 E4·G5
- 결정 사항: 정확한 알람 권한 안내 화면은 T-FE6 (R-025 ①), 원격 푸시 자격 증명은 U-004 사용자 결정 대기 (②), full-screen intent는 ⏸ 보류 (③)
- 표기: 🔧 = **개발 빌드 필요** (`npx expo run:android` 또는 EAS). Expo Go(Android 58.0.5)는 `expo-notifications`를 불러오지 못해 알림이 아예 없고, 웹도 알림이 없다 (`src/notify/module.ts`). 🍎 = iOS 실기기 필요 (이 맥에는 iOS 시뮬레이터가 없다). ☁ = U-004 (EAS 프로젝트·FCM/APNs 자격 증명) 이후
- QA 환경: 이 맥에 Android SDK, `adb`, 에뮬레이터 AVD `Medium_Phone`이 있다. BE는 `_targets/BE` 18200번 (에뮬레이터에서는 `http://10.0.2.2:18200/api/v1`). 시각이 필요하면 시연 트리거(지금으로 당기기), fast 프로필(인계 1분), clock 실행기를 쓴다
- 알림 시각 확인: `adb shell dumpsys alarm | grep -A3 <패키지>`로 예약된 알람과 시각을 본다. 실제로 울린 시각은 `adb logcat`과 화면 녹화로 잰다

### 5.1 웹·Expo Go·서버로 확인 (개발 빌드 없이)

| ID | 시나리오 | 기대 | 근거 | 환경 |
|---|---|---|---|---|
| N01 | 알림 모듈이 없는 환경 | 웹과 Expo Go에서 앱이 멈추지 않고 모든 화면이 동작. G8에 "이 환경(웹)에서는 알림을 받을 수 없어요. 처리할 일은 홈에서 보여요." | `module.ts`, `guardian/settings.tsx` PUSH_TEXT | 웹, Expo Go |
| N02 | 알림 시각의 출처가 서버 값 | 오늘 알림 시각 = `ask_times` (서버 `REASK_OFFSETS_MIN`), 내일부터 = `GET /schedule` + `GET /me` `timing`. 서버 timing을 바꾸면 그대로 따라간다 (R-007 C5) | backend 7.1, `elderSchedule.ts` | 서버 API (기존 S-시나리오가 `ask_times` 확인), 🔧로 실제 예약 시각 대조 |
| N03 | 알림 문구 (원칙 6) | 제목 "○○ 약 드실 시간이에요", 재질문 "다시 여쭤봐요", 본문 "{호칭}, {○○} 약 드시고 약통 사진 한 장 찍어주실래요?". 추가 복용·용량 지시 없음. 호칭은 서버 값. 시연 트리거 건은 "[시뮬레이션]" 앞머리 | 원칙 6, 헌장 6장, R-008 | 소스 확인 + 🔧 화면 |

### 5.2 어르신 로컬 알림 (🔧 개발 빌드, Android 에뮬레이터)

| ID | 시나리오 | 기대 | 근거 |
|---|---|---|---|
| N10 | 첫 실행 권한 | 연결·동의 뒤 알림 권한 요청 1회. 허용하면 예약 시작 | `channels.ts` ensurePermission |
| N11 | 정시 울림 (정확한 알람 권한 있음) | 복약 시각에 울림 (오차 ±1분). 채널 `dose-ask`, 알람 볼륨, 잠금 화면에 내용 표시 | R-025, UI 설계 4장 |
| N12 | 정확한 알람 권한 없음 (Android 14+ 기본) | 늦게 울릴 수 있음(FE 측정 최대 +7분 29초). T-FE6 안내 화면이 연결·동의 직후 권한이 없을 때만 나오고 [설정 열기] 하나, 문구는 "보호자께: …" (보호자가 대신 조작). 설정에서 켜고 돌아오면 안내가 사라지고 정시 울림 | R-025 ①, R-027 |
| N13 | 재질문 | +10분·+20분에 "다시 여쭤봐요" (서버 timing 값) | R-006 |
| N14 | 사진을 올리면 남은 재질문 취소 | E4에서 사진 → 다음 동기화에서 그 건의 남은 알림이 `dumpsys alarm`에서 사라지고 울리지 않음 | backend 6장 |
| N15 | 알림을 누르면 | 오늘 건 → E4 (`event_id`). 미리 예약한 날(내일 이후) → 어르신 홈 → 열린 건이 있으면 E4 (R-022). 이미 끝난 건의 알림을 누르면 E4에서 홈으로 | `NotificationRouter.tsx` |
| N16 | 시연 트리거 | 지금으로 당긴 건의 재질문이 새 `ask_times`로 다시 예약. 첫 알림(지금)은 이미 지나 건너뜀. "[시뮬레이션]" 표시 | R-010 10번 |
| N17 | 일정 변경 | 보호자가 일정을 바꾸면 어르신 앱이 다음에 열리거나 주기 갱신(30초) 때 예약이 바뀜. 지운 칸의 알림은 취소 | `elderSchedule.ts` (같은 식별자 덮어쓰기) |
| N18 | 앱을 닫아 둔 경우 | 앱을 스와이프로 닫아도 이미 예약된 알림은 울림. **R-028:** 미리 예약 기간이 iOS 대기 한도(64개) 안에서 약 7일로 늘어남 → 앱을 열지 않아도 7일치가 `dumpsys alarm`에 있다. 장기 미접속 감지는 선택 기능 #8 (MVP 뒤) | R-028, T-FE8 |
| N19 | 재부팅 | 폰을 재부팅해도 예약된 알림이 남아 울림 | expo-notifications 재부팅 복구 |
| N20 | 절전(Doze)·무음·방해 금지 | Doze 중에도 정시 (`delivery: 'alarmClock'`). 무음·진동 모드에서도 알람 볼륨으로 울림. 방해 금지 모드에서의 동작을 기록 | `channels.ts` audioAttributes |
| N21 | 자정 경계 | 자정 뒤 미리 예약분(`slot@날짜`)이 오늘 건 기준(`event_id`)으로 바뀌는지. 자정~00:05(오늘 건 생성 전)에 앱을 열어도 알림이 지워지지 않는지. 전날 건(`carried_over`)은 알림 대상이 아님 | R-021 Q-007, api.md 3.17 |
| N22 | 기기 시간대가 서울이 아님 | **R-028:** 예약 시각을 Asia/Seoul 기준으로 계산. 에뮬레이터 시간대를 UTC·America/New_York 등으로 바꿔도 오늘·내일부터 알림이 모두 서울 시각의 복약 시각에 울림 | api.md 1.3, R-028 |
| N23 | 연결 해제·토큰 무효·역할 변경 | 어르신 기기 해제 → 다음 요청에서 첫 화면으로 가면서 예약 알림 모두 취소 | `role.tsx` clearElderNotifications |
| N24 | 알림 권한 거부 | **R-028:** 알림 권한이 없으면 T-FE6 안내 화면(연결·동의 직후)이 알림 권한도 함께 안내하고 [설정 열기] 하나. 권한이 있으면 안내 화면이 나오지 않음. 앱은 계속 동작 | R-027, R-028 |
| N25 | 재촬영·안내 대기 중 알림 | **R-028:** 재촬영(E7b)·안내(E7d)를 요청한 뒤 5분 안에 사진이 없으면 로컬 알림 1회 "사진 한 장만 더 부탁드려요". 복용 권유 문구 없음(원칙 6). 5분 안에 사진을 올리면 그 알림은 취소. 재촬영 기한(+15분) 인계는 그대로 | R-028, 원칙 6 |
| N26 | 🍎 iOS | 시간 민감 알림 (집중 모드에서도 표시), 예약 60개 제한 안에 들어감, 누르면 E4 | R-025, `IOS_PENDING_LIMIT` |

### 5.3 보호자 인계 푸시 (🔧 + ☁ U-004 이후)

| ID | 시나리오 | 기대 | 근거 |
|---|---|---|---|
| N30 | 푸시 토큰 등록 | 보호자 앱이 열리면 `PUT /devices/me/push-token`, G8 "✓ 이 폰으로 알려드려요". 자격 증명이 없으면 "푸시 설정이 없어 알림을 받을 수 없어요" | api.md 3.9 |
| N31 | 인계 푸시 | 서버 `EXPO_PUSH_ENABLED=true`에서 인계 1건당 보호자 기기마다 1건. 누르면 G5 (`handoff_id`) | api.md 4.3 |
| N32 | 정상은 푸시 없음 | 정상 기록·지난 칸 불일치·늦은 정상 사진에서 푸시 0건 (서버 쪽은 기존 S02·S10·S07로 확인됨) | 원칙 2 |
| N33 | 보호자 추가·요약 푸시 | 누르면 G8·G6. 요약 푸시는 `summary_push_enabled`일 때만 (clock 실행기로 `summary_push_time` 맞춰 확인) | backend 3.3, 9장 |

### 5.4 판정 기준

- 🔧 항목은 FE가 개발 빌드(APK)를 만들면 에뮬레이터에서 돌린다. 결과는 `docs/qa/results.md`에 기기·OS·빌드 커밋과 함께 적는다
- 실제 복약 시각과 울린 시각의 차이는 1분 이내를 통과로 본다 (정확한 알람 권한이 있을 때). 권한이 없을 때의 지연은 기록만 한다
