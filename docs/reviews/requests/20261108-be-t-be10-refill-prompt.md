# 검토 요청: T-BE10 마지막 칸 정상 기록 뒤 어르신 약통 채우기 안내
- 요청자: BE 에이전트
- 날짜: 2026-11-08
- 종류: 코드 (계약 변경 없음. api.md 3.18·3.26 메인 에이전트 계약 그대로)
- 관련 헌장 항목: 4장 MVP #3(나 약 먹었나)·#7(리필 알림), R-071

## 무엇을 했는가
1. **설정 `elder_refill_prompt`** (bool, 기본 false): `GET /settings` 응답에 추가, `PUT /settings`로 바꿈(보낸 필드만). bool이 아닌 값은 422 `validation_error`
   - DB: `families.elder_refill_prompt` 열. 기존 관례(`db._add_missing_columns`, 서버 시작 때 빠진 nullable 열을 `ALTER TABLE ADD COLUMN`)를 따라 **nullable**로 두었다. 기존 가족 행은 NULL이고 서버는 false로 읽는다. 새 가족은 false로 저장
2. **사진 응답 `refill_prompt`** (`POST /dose-events/{id}/photo`)
   - true 조건: `result == "recorded"` + 설정 true + 기록 뒤 남은 칸 0. 남은 칸은 `GET /pillboxes/current`의 `remaining_cells`와 같은 함수(`refill_status`)로 이 기록을 반영한 뒤 계산한다. 그 밖에는 항상 false (약통·기준선이 없을 때 포함)
   - 처음 응답 값을 사진 행(`photos.upload_refill_prompt`, nullable)에 저장해, **같은 `client_upload_id` 재전송에는 처음과 같은 값**을 준다(그사이 설정을 바꿔도). 이 열이 생기기 전에 올린 사진의 재전송은 false
3. **데모 시드**: `seed_demo create --pillbox day`는 일정 저장 뒤 `elder_refill_prompt=true`로 둔다. 일주일 약통 시드는 기본 false 그대로
4. 다른 응답·동작 변경 없음 (DoseEvent, `result` 판정, 인계 흐름 그대로)

## 확인한 것
- pytest **204 통과·2 건너뜀** (이전 196 + 새 8개). ruff check·format 통과. 커밋 전 실제 종료 코드로 확인
- `tests/test_refill_prompt.py`
  - 설정: 기본 false, PUT true/false, 다른 필드만 바꾸면 유지, `"maybe"` 422, 어르신 403
  - 하루 약통(설정 true): 아침 false, 점심 false, **저녁 true** → 같은 `client_upload_id` 재전송 true(설정을 꺼도) → 리필 뒤 다음 날 아침 false
  - 하루 약통 설정 false(기본): 저녁도 false
  - 일주일 약통: 마지막 남은 칸 정상 기록 → 설정 true면 true, false면 false. 마지막 칸이 아니면 false
  - `retake`, `guardian_notified`, `remind_retake`는 false
  - 기존 DB(열 없음)에 `ensure_schema` → 열이 붙고 기존 행은 NULL
- 기존 테스트 수정: `test_settings_get_put`의 GET 본문에 `elder_refill_prompt: false` 추가, 시드 테스트 2개에 설정 값 확인 추가

## 관련 파일·브랜치·커밋
- BE `be/refill-prompt` 876e44b (main 7964e70에서 시작)
  - `app/models.py`, `app/routers/account.py`, `app/routers/dose.py`, `app/seed_demo.py`
  - `tests/test_refill_prompt.py`(새), `tests/test_pairing.py`, `tests/test_seed_demo.py`

## 계약이 모호해서 정한 점
1. "이 기록으로 남은 칸이 0이 되었으면"은 **기록 뒤 `remaining_cells == 0`** 으로 계산했다(지시와 같음). 예: 하루 약통에서 점심이 인계(비교 제외)로 끝나고 저녁이 정상 기록이면 저녁 뒤 0칸이라 true
2. **늦은 정상 사진**(무응답 인계 뒤 온 정상 사진, `result=recorded`지만 인계는 열린 채): 그 칸은 기대 상태에서 비교 제외라 남은 칸 계산에 따라 true가 될 수 있다. 어르신에게는 "기록해 뒀어요"를 보여 주는 경우라 안내 한 줄도 같이 보여 주는 게 자연스럽다고 보고 따로 막지 않았다
3. 설정 PUT에 `null`을 보내면 다른 필드처럼 "바꾸지 않음"으로 처리한다
4. 보호자 앱이 하루 약통을 등록할 때 true로 저장하는 것은 FE(T-FE25) 몫이다. 서버는 약통 모양을 보고 자동으로 켜지 않는다
5. Notion: API 엔드포인트 DB의 `GET·PUT /settings`, `POST /dose-events/{id}/photo` 행을 갱신했다(상태 "구현"). 업무 DB에 T-BE10 행이 없어 갱신하지 못했다
