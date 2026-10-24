# QA 실행 결과 (T-QA1)

- 실행: QA 에이전트, 2026-10-24 22:50 ~ 2026-10-25 00:30 (KST)
- 대상: BE main `dec9623` (T-BE4 병합, R-019), FE main `11dbecc` (T-FE3 병합, R-020). 처음 실행은 BE `89c1ad2`, FE `342a0bb`
- 계획: `docs/qa/test-plan.md`, 이슈: `docs/qa/issues.md`

## 1. 실행 방법

```bash
# 이 워크스페이스(DOCS 저장소) 루트에서. _targets/ 는 .gitignore
git clone /Users/decehnk/project/woowang/WOOWANGTHON_TEAM_00_BE _targets/BE
git clone /Users/decehnk/project/woowang/WOOWANGTHON_TEAM_00_FE _targets/FE

qa/api_scenarios/run.sh            # 기본 프로필(약 1분) + fast 프로필(약 9분)
qa/api_scenarios/run.sh default    # 기본만
qa/api_scenarios/run.sh fast       # 시간 시나리오만 (인계 기한 1분 서버에서 실제로 기다림)
qa/api_scenarios/run.sh default -k q00   # 이슈 재현 테스트만
```

- `run.sh`는 `_targets/BE`를 18200번에 SQLite·`DEMO_MODE=true`·mock 판독기로 띄우고 끝나면 끈다. 18200번이 이미 쓰이고 있으면 멈춘다 (남의 프로세스는 건드리지 않음)
- 필요한 것: `uv`. 테스트 의존성(httpx, pytest)은 `uv run --with`로 받는다
- 자정 전후 10분에는 돌리지 않는다 (시나리오가 "오늘 요일" 일정을 씀)

FE 화면 점검:
```bash
cd _targets/FE && npm install
EXPO_PUBLIC_API_MODE=mock npx expo start --web --port 8299                       # mock
EXPO_PUBLIC_API_MODE=http EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:18200/api/v1 \
  EXPO_PUBLIC_CREATE_DEMO_FAMILY=true npx expo start --web --port 8299            # http (BE는 CORS_ORIGINS 에 8299 추가)
```

## 2. 자동 테스트 결과 (최종, BE `dec9623`)

| 프로필 | 통과 | 실패 | 건너뜀 | 시간 |
|---|---|---|---|---|
| default | 48 | 4 (모두 이슈 재현 테스트) | 1 | 약 60초 |
| fast | 6 | 0 | 0 | 약 9분 |

실패 4건은 `test_q001` (Q-001), `test_q002` ×2 (Q-002), `test_q005` (Q-005)이다. 건너뛴 1건은 `test_s14_early_photo_window`로, 23시 이후에는 오늘 안에 +90분 일정을 둘 수 없어서 건너뛴다 (낮에 돌리면 실행됨).

## 3. 시나리오별 결과

| ID | 시나리오 | 결과 | 테스트 | 비고 |
|---|---|---|---|---|
| S01 | 짝짓기와 동의 | ✅ 통과 | `test_s01_*` (3) | 동의 전 403, 코드 재사용 410, 6자리 연결, 이전 어르신 기기 해제, 보호자 초대 푸시 |
| S02 | 정상 | ✅ 통과 | `test_s02_*` (3), `test_m02` | 보호자 푸시 0건, 어르신 응답에 판독·인계 없음, 재전송 멱등 |
| S03 | 애매 → 재촬영 → 보호자 판정 | ✅ 통과 | `test_s03_*` (2), `test_m03`, `test_m04`, F `test_s03_retake_timeout` | 신뢰도 낮으면 정상 금지 확인 |
| S04 | 칸 그대로 (두 모드, +30분) | ✅ 통과 / ⚠ Q-005 | `test_s04_*` (3), `test_m05`, `test_m06`, F `test_s04_*` (2) | +인계 기한 지난 사진에 안내 없음(C3) 확인. 애매와 섞이면 재촬영 2회 (Q-005) |
| S05 | 이중 복용 의심 | ✅ 통과 | `test_s05_*` (2), `test_m07` | 인계된 칸 비교 제외(C2) 확인 |
| S06 | 무응답 → 인계 | ✅ 통과 | F `test_s06`, `test_m11` | 1분 예약 작업으로 반영, 중복 없음. 보호자 화면 표시는 4장 |
| S07 | 늦은 사진 | ✅ 통과 (계약대로) / ⚠ Q-004 | F `test_s07` | 새 인계·푸시 없음, `late_photo`. 어르신 문구와 E8 불일치 (Q-004) |
| S08 | 이미 쓴 칸 | ✅ 통과 | `test_s08_*` (3), `test_m09` | refill_overdue, refill_unconfirmed 네/아니요 |
| S09 | 리필 확인 네/아니요 | ✅ 통과 | `test_s09_*` (3) | 아니요 후 다시 묻지 않음, 열린 동안 중복 없음 |
| S10 | 지난 칸 불일치 | ✅ 통과 | `test_s10` | 재촬영·푸시 없음, 현재 약통·요약에 표시 |
| S11 | 기기 해제 → token_revoked | ✅ 통과 | `test_s11_*` (2) | 다른 가족 자원 404 |
| S12 | 요약 all_normal | ✅ 통과 | `test_s12_*` (2) | `includes_mock`, `includes_simulated` |
| S13 | 시연 트리거 | ✅ 통과 | `test_s13_*` (3) | 실제 가족 404, 같은 칸 409, 다른 요일 422 |
| S14 | 오류 코드 | ✅ 통과 (1건 건너뜀) / ⚠ Q-002 | `test_s14_*` (9), F `test_s14_daily_*` | 공백 이름 허용 (Q-002) |
| S15 | T-BE4 회귀 | ✅ 통과 | `test_m01`, `test_m08`, `test_m10`~`m12` | 동시 업로드·동시 GET 인계 중복 없음, CORS 허용 출처만 |
| — | 일정 저장 시 지난 시각 | ❌ 실패 | `test_q001` | Q-001 |

## 4. 화면 점검 (FE 웹)

| 항목 | 모드 | 결과 | 비고 |
|---|---|---|---|
| E1 동의, E2 연결, E3 홈, E4 질문, E5 촬영, E6 판독 중, E7a/b/c/d, E8 | mock | ✅ | 4가지 모의 시나리오로 E7 전부 확인. 문구에 의료 지시 없음 |
| G4 홈, G5 인계 상세 (이중 의심) | mock | ✅ | 신뢰도 숫자 없음, 한계 문구, 판정 버튼, "AI 판독 · 모의 결과" |
| E3, E4, E8 (실제 서버) | http | ✅ | CORS 통과. 브라우저 패널에 카메라가 없어 E5 셔터가 동작하지 않음 → 사진은 API로 올려서 E8 확인 (환경 한계, 이슈 아님) |
| G4 홈 (실제 서버) | http | 결과는 5장 | 1분 예약 작업이 만든 `no_response`가 보호자 화면에 뜨는지 |

## 5. 원칙 점검표 결과

| # | 점검 | 결과 | 근거 |
|---|---|---|---|
| C1 | 어르신 화면 의료 지시 문구 없음 | ✅ | FE 소스 검색("드세요/더 드/드시지/복용/용량/미복용/안 드셨")에서 어르신 화면 문구 없음. 어르신 API 응답에 사유·판독 없음 (`assert_elder_view_clean`) |
| C2 | 모의·시뮬레이션 표시 누락 없음 | ✅ | 모든 판독 `is_mock=true`, 요약 `includes_mock`·`includes_simulated`, 화면 띠·배지·"시뮬레이션" 표시 확인 |
| C3 | 정상인데 보호자 푸시 없음 | ✅ / ❌ Q-001 | 정상·불일치·늦은 정상 사진에서 푸시 0건 증가. 단 일정 저장 직후 거짓 무응답 푸시 (Q-001) |
| C4 | 신뢰도 숫자 비노출 | ✅ | 보호자 응답 JSON에 `confidence` 키 없음, G5에 숫자 없음 |
| C5 | 어르신 글씨 28pt·버튼 72pt | ⚠ Q-003 | 본문·버튼은 기준 충족(본문 28~56px, 버튼 96px). 판정 배지·모의 표시가 16~20px |
| C6 | 호칭 하드코딩 없음 | ✅ | FE 소스의 "어머니/민수"는 입력 예시(placeholder)와 모의 데이터뿐. 화면 호칭은 서버 값(할머니QA, 지훈QA 등) |
| C7 | 한계 문구 | ✅ | E8 "사진으로 약 칸이 빈 것만 확인해요", G5 "칸이 빈 것만 확인했어요. 드셨는지는 직접 확인해 주세요" |
| C8 | 결정은 사람 | ✅ | 판정 반영(`outcome_source=guardian`, `decided_by`), E8 "○○ 판정" 배지 |

## 6. 이슈 요약

치명 0, 높음 1, 보통 1, 낮음 4 (자세한 내용은 `docs/qa/issues.md`, Notion 이슈 DB에도 등록)
