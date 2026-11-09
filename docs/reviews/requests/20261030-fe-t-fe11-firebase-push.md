# 검토 요청: T-FE11 패키지 이름 변경, Firebase 연결, 보호자 FCM 토큰 등록, 로컬 release APK
- 요청자: FE 에이전트
- 날짜: 2026-10-30
- 종류: 코드 / 기술 결정 (빌드 설정)
- 관련 헌장 항목: 4장 MVP #1(앱이 물어보기, 보호자 인계 알림), R-039(U-004 사용자 결정), R-025 ④

## 무엇을 했는가

FE `fe/firebase-push` 커밋 `e4dbbff` (FE main `4bfe954` 위에 1개). 계약은 바꾸지 않았다. api.md 3.9(BE T-BE7, R-040)를 따른다.

1. **패키지 이름** `app.json` `android.package` = `kr.dementiacheck.app`. README 배포 체크리스트·adb 명령의 패키지 이름 갱신
2. **Firebase 연결 (비밀값은 저장소 밖)** `app.config.js` 새로 만듦. 환경 변수 `GOOGLE_SERVICES_JSON`(예: `~/woowang-secrets/google-services.json`)을 `android.googleServicesFile`로 넣는다
   - 값이 없으면 경고만 하고 Firebase 없이 설정한다. Expo Go·웹·화면 개발은 영향 없고, 그 빌드만 푸시를 못 받는다. G8에 "이 앱 빌드에는 푸시 설정이 없어…"(`extra.firebaseConfigured`, 경로는 넣지 않음)
   - 값이 있는데 파일이 없거나 파일에 `kr.dementiacheck.app`이 없으면 설정 단계에서 실패한다 (확인함)
   - `.gitignore`에 `google-services.json`, `GoogleService-Info.plist`. prebuild가 `android/app/`에 복사하지만 `android/`는 원래 무시 대상. 커밋 diff에 비밀값 없음 확인
3. **보호자 토큰** `getExpoPushTokenAsync`(EAS projectId) 대신 `getDevicePushTokenAsync`로 FCM 토큰을 받아 `PUT /devices/me/push-token`. `addPushTokenListener`로 토큰이 바뀌면 새 토큰을 바로 보낸다. **iOS는 토큰을 보내지 않고** 권한도 묻지 않는다. G8에 "이 폰(아이폰·웹)에서는 알림을 받을 수 없어요. 처리할 일은 홈에서 보여요."
4. **Android 채널** id `guardian`(높은 중요도, 잠금 화면 공개). BE `FCM_ANDROID_CHANNEL_ID` 기본값과 같다. `expo-notifications` `defaultChannel`도 `guardian`이라 서버가 채널을 안 적어도 같은 채널로 온다 (작업 지시의 기본값 `handoff` 대신, 메인 에이전트가 전한 BE 값을 따름)
5. **버그 수정 (실기 확인 중 발견):** 앱이 꺼진 상태에서 인계 푸시를 누르면 G5가 아니라 G4에 도착했다. 알림 data는 Expo 때와 같은 자리(`content.data.type/handoff_id`)로 왔고(로그 확인), 원인은 순서였다. 알림 이동이 첫 화면(`/`)의 역할 Redirect보다 먼저 일어나서 Redirect가 G5 위에 G4를 다시 쌓았다. `NotificationRouter`가 역할 화면(`/guardian`, `/elder`)에 들어온 뒤에 이동하게 고쳤다. 어르신 로컬 알림을 꺼진 상태에서 누를 때도 같은 경로라 함께 좋아진다
6. **로컬 release APK** `plugins/withReleaseSigning.js`(config plugin). prebuild 때 release 서명 설정을 넣고, 키 경로·비밀번호는 Gradle 속성(`~/.gradle/gradle.properties` 등 저장소 밖)에서 읽는다. 속성이 없으면 디버그 키로 서명하지 않고 빌드가 멈춘다. README에 키 만들기 → 속성 → 빌드 → `apksigner` 확인 → 설치 순서를 적었다

## 확인한 것 (개발 빌드, 에뮬레이터 Android 17 Google Play 이미지 `FE_Test`)

서버: BE main `10cce28`(T-BE7)를 scratch 폴더에 내보내 SQLite로 띄움. `PUSH_PROVIDER=fcm`, `FCM_SERVICE_ACCOUNT_FILE=~/woowang-secrets/fcm-service-account.json`, `DEMO_MODE=true`, mock 판독기

| 확인 | 결과 |
|---|---|
| prebuild에 google-services 플러그인·`default_notification_channel_id=guardian` 적용 | ✓ |
| 보호자 가족 만들기 → `PUT /devices/me/push-token` 204, DB 토큰이 FCM 형식(142자, `ExponentPushToken` 아님) | ✓ |
| BE `scripts/fcm_check.py <키> <토큰>` | ✓ `HTTP 200 OK (메시지와 토큰 모두 유효)` |
| G8 "✓ 이 폰으로 알려드려요." | ✓ |
| **앱 프로세스가 없는 상태**(`pidof` 비어 있음)에서 인계(칸 그대로 → 바로 인계, 시뮬레이션 건) → 푸시 도착 | ✓ 채널 `guardian`, 중요도 4, "복약 확인 / mom2 아침 약 칸이 그대로예요" |
| 그 알림을 누르면 G5(그 인계 상세) | ✓ (5번 수정 후). 뒤로 가면 G4 |
| 앱이 백그라운드일 때 누르면 G5 | ✓ |
| 토큰 갱신 시 다시 보내기 | 코드만 (에뮬레이터에서 FCM 토큰을 강제로 바꾸는 방법이 없어 실기 확인 못 함) |
| iOS | 확인 못 함 (iOS 기기·시뮬레이터 없음). 코드상 Android가 아니면 바로 `unsupported` |

시험 환경 메모 (README에 적음)
- `am force-stop`으로 끄면 Android가 앱을 "중지됨"으로 두어 FCM을 받지 않는다(첫 시도에서 푸시가 안 옴). 실제로 최근 앱에서 밀어 끈 상태와 다르다. 홈 → `am kill`로 시험한다
- Metro를 `CI=1`로 띄우면 파일 감시가 꺼져 옛 번들을 준다(첫 시험에서 채널이 옛 id로 만들어진 원인)
- 시험용 보호자 API 호출은 그 scratch DB에 같은 가족의 보호자 기기를 하나 넣어서 했다(앱에 보호자 초대 화면이 없음). 제품 코드·BE 코드는 건드리지 않았다

## 로컬 release APK 시험

- 시험용 키(scratch, 커밋 안 함)로 `assembleRelease`: **성공, 11분 15초, APK 121MB**(4개 ABI), `apksigner` v2 서명 확인, 패키지 `kr.dementiacheck.app`
- 속성 없이 빌드: `packageRelease`에서 `SigningConfig "release" is missing required property "storeFile"`로 멈춤 ✓
- 에뮬레이터에 설치·실행 ✓. 다만 **release는 `http://` 서버에 붙지 않는다**(Android 기본: 평문 HTTP는 디버그 빌드만). 로컬 `http://10.0.2.2` 서버로는 "서버에 연결하지 못했어요"가 나와서 release에서 토큰 등록까지는 확인 못 했다. 실제 배포는 `https://` 터널 주소라 문제 없을 것으로 본다. README에 적음

## 헌장과 다르거나 애매한 지점

1. **채널 id:** 작업 지시의 기본값은 `handoff`였지만 BE가 `guardian`으로 구현·승인(R-040)돼 FE도 `guardian`(기존 값 그대로)
2. **release 서명 config plugin 추가:** 작업 지시(로컬 release 빌드 방법)를 위한 빌드 설정 파일 1개. `android/`가 커밋 대상이 아니라 prebuild마다 서명 설정이 사라지므로 plugin으로 넣었다. 동작 변화는 release 빌드에만 있다
3. **실제 서명 키는 만들지 않았다.** 키는 한 번 배포하면 바꾸기 어렵고 사용자가 보관해야 하므로 사용자가 README 1)대로 만든다(`~/woowang-secrets/release.jks` 제안). 결정 필요: 키 생성·보관을 사용자가 할지
4. **APK 크기 121MB:** 4개 ABI가 다 들어서다. 심사위원 설치용으로 줄이려면 `arm64-v8a`만 넣는 방법(`reactNativeArchitectures=arm64-v8a`)이 있다. 이번에는 바꾸지 않았다
5. 예전 `com.anonymous.woowangfe` 개발 빌드는 다른 앱이라 기기에 남는다(QA 기기에서 지워야 함)

---

## 판정 (메인 에이전트, 2026-10-30): ✅ 승인 — R-041

- tsc 직접 확인, 비밀값 없음. FE main 병합
- 실제 서명 키는 사용자가 만들고 저장소 밖에 보관한다. 심사위원 배포 APK는 arm64-v8a만. 배포 서버는 https(Cloudflare Tunnel)
