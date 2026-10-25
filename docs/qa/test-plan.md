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
