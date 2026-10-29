# 검토 요청: T-BE7 보호자 푸시 FCM HTTP v1 직접 발송
- 요청자: BE 에이전트
- 날짜: 2026-10-30
- 종류: 코드 (+ 계약서 api.md 3.9 설명)
- 관련 헌장 항목: 4장 MVP #4(단계적 인계)·#6(요약), 5장 원칙 2·8, R-039

## 무엇을 하려는가
보호자 푸시(인계 알림, 요약 푸시)를 Expo 푸시 서비스 대신 서버가 FCM HTTP v1로 직접 보낸다 (R-039 사용자 결정).

- `app/push.py` `FcmPushSender`
  - 서비스 계정 키(`FCM_SERVICE_ACCOUNT_FILE`)로 RS256 JWT를 서명해 OAuth 액세스 토큰을 받고, 만료 1분 전까지 캐시. 발송에서 401이 오면 한 번만 새로 받아 다시 보낸다
  - 메시지: `notification{title, body}` + `data`(FCM 규칙대로 값은 모두 문자열) + `android{priority: HIGH, notification{channel_id: "guardian", sound: default, notification_priority: PRIORITY_HIGH, visibility: PUBLIC}}`. 채널 id는 FE `src/notify/channels.ts`의 `GUARDIAN_CHANNEL`과 같고 `FCM_ANDROID_CHANNEL_ID`로 바꿀 수 있다
  - 푸시 내용(제목·본문·data)은 기존 호출부 그대로 (인계 `type=handoff`, 요약 `type=summary`, 보호자 합류 `type=guardian_joined`)
  - 토큰 무효면 그 기기 `push_token`을 지운다: `UNREGISTERED`, `SENDER_ID_MISMATCH`, 그리고 `INVALID_ARGUMENT` 중 `fieldViolations.field == "message.token"`인 경우만(메시지 내용 오류로 토큰을 지우지 않도록). 지울 때 `push_token == 보낸 토큰` 조건이라 그사이 새로 등록한 토큰은 남는다
  - 실패(네트워크, 5xx, 토큰 발급 실패, 삭제 실패)는 로그만 남기고 요청 흐름을 막지 않는다 (기존과 같이 커밋 뒤 after_commit에서 발송)
  - 로그에 키·액세스 토큰 내용을 남기지 않는다 (설정 오류도 예외 종류만)
- 설정 `PUSH_PROVIDER=fcm|expo|recording`. **비우면 지금 동작 그대로** (`EXPO_PUSH_ENABLED`가 true면 expo, 아니면 recording). FCM 파일이 없거나 JSON·키가 잘못되면 시작 로그에 ERROR를 남기고 recording으로 뜬다(서버는 정상 시작). 알 수 없는 값도 ERROR + recording
- 새 의존성: `cryptography` 하나 (JWT RS256 서명). google-auth는 rsa·pyasn1·cachetools 등이 더 붙어서 쓰지 않았다. 함께 설치되는 것은 cffi·pycparser
- `docker-compose.yml`: `.env`의 `SECRETS_DIR`(저장소 밖 절대 경로, 예 `~/woowang-secrets`)을 컨테이너 `/run/secrets/woowang`에 읽기 전용으로 붙인다. 비우면 빈 `./data/secrets`(이미 .gitignore)
- `scripts/fcm_check.py`: validate_only로 인증만 확인 (실제로 보내지 않음, 키 내용 출력 없음)
- `docs/deploy.md`, `.env.example`: `PUSH_PROVIDER`, `SECRETS_DIR`, `FCM_SERVICE_ACCOUNT_FILE`, `FCM_ANDROID_CHANNEL_ID`
- 계약 `docs/design/api.md` 3.9: `push_token` 예시와 설명을 "Android 기기 FCM 등록 토큰"으로. 필드 이름·응답은 그대로

## 확인한 것
- pytest 164 통과·2 건너뜀 (새 `tests/test_fcm_push.py` 22개: 페이로드·JWT 서명 검증, 토큰 캐시·만료 전 재발급, 401 재발급, 무효 토큰 3종 삭제, 그 밖의 오류 4종은 토큰 유지·예외 없음, 토큰 발급·네트워크·삭제 실패 무시, 무응답 인계 → UNREGISTERED → DB `push_token` 삭제, 새 토큰 유지, 설정 선택·잘못된 파일 4종 ERROR, 파일 없어도 서버 시작). ruff check·format 통과. 커밋 전 `set -o pipefail`
- **실제 FCM dry-run** (`~/woowang-secrets/fcm-service-account.json`, validate_only, 가짜 기기 토큰): `oauth: ok`, `HTTP 400 INVALID_ARGUMENT bad_token=True` → 인증과 메시지 형식은 통과, 토큰 형식만 거절됨(예상대로). 401/403 없음
- 비밀값: 키 파일 내용 출력·복사·커밋 없음. 테스트 키는 테스트마다 새로 만든 RSA 키

## 범위와 예상 소요 시간
끝남. 실제 기기 수신 확인은 FE T-FE11이 기기 FCM 토큰을 등록한 뒤 함께 한다 (`scripts/fcm_check.py <키> <기기 토큰>`으로 200 확인 → `PUSH_PROVIDER=fcm`으로 인계 발생).

## 관련 파일·브랜치·커밋
- BE `be/fcm-push` 5851bde (`app/push.py`, `app/config.py`, `app/main.py`, `tests/test_fcm_push.py`, `scripts/fcm_check.py`, `docker-compose.yml`, `docs/deploy.md`, `.env.example`, `pyproject.toml`, `uv.lock`)
- DOCS `be/t-be7-fcm-contract` (api.md 3.9, 이 요청 파일)

## 헌장과 다르거나 애매한 지점
1. **backend.md는 고치지 않았다.** 1장 그림("서버 → Expo Push API")과 기술 표("푸시 | Expo Push API (httpx)")가 아직 Expo다. 지시 범위가 api.md 3.9뿐이라 두었다. 메인 에이전트가 고치거나, 승인하면 내가 같은 브랜치에 고친다
2. **FE에 전할 점 (T-FE11):** ① 토큰은 `getExpoPushTokenAsync`가 아니라 기기 토큰(`getDevicePushTokenAsync`, Android에서 FCM 토큰)을 등록해야 한다 ② `data` 값은 모두 문자열로 온다 ③ 채널 id `guardian`이 앱과 같아야 한다 ④ 알림을 눌렀을 때 `data`(type, handoff_id 등)가 Expo 경유 때와 같은 자리로 오는지 확인 필요 (Expo 서비스는 data를 따로 감싸서 보냈다)
3. Expo 발송(`ExpoPushSender`)은 `PUSH_PROVIDER=expo`로 남겨 두었다. R-039로 쓰지 않으니 지워도 된다. 지우라면 지운다
4. 기본값은 지시대로 지금과 같은 `recording`이다. 실제 운영 `.env`에는 `PUSH_PROVIDER=fcm`과 `SECRETS_DIR`을 사용자가 넣어야 한다 (deploy.md에 적음)
5. 발송은 기존처럼 요청 스레드에서 커밋 직후 동기로 한다. FCM v1은 메시지마다 요청 1건이라 보호자 수만큼 요청한다(제한 시간 5초씩). 보호자가 한두 명이라 그대로 두었다

---

## 판정 (메인 에이전트, 2026-10-30): ✅ 승인 — R-040

- pytest 164·ruff 직접 확인, 비밀값 없음. BE main 병합, api.md 3.9 DOCS main 병합
- backend.md의 Expo 표기는 메인 에이전트가 고쳤다. ExpoPushSender는 남긴다. 기본값 recording 유지
- 실제 기기 수신은 T-FE11과 함께 확인한다
