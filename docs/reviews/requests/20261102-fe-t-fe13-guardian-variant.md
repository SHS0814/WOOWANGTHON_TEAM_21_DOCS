# 검토 요청: T-FE13 한 폰에 함께 설치하는 보호자용 빌드 변형
- 요청자: FE 에이전트
- 날짜: 2026-11-02
- 종류: 코드
- 관련 헌장 항목: 4장 MVP 지원(시험·시연 환경). 새 기능 없음. R-044, R-039, R-041

## 무엇을 했는가

FE `fe/guardian-variant` 커밋 `c956a0c` (FE main `90af226` 위에 1개). 바꾼 파일은 `app.config.js`, `README.md` 둘이다.

| | 기본 (`APP_VARIANT` 없음) | `APP_VARIANT=guardian` |
|---|---|---|
| Android 패키지 | `kr.dementiacheck.app` | `kr.dementiacheck.app.guardian` |
| 앱 이름 | 약 챙김 | 약 챙김 보호자 |
| 딥링크 scheme | `woowang` | `woowang-guardian` |

- 그 밖의 `APP_VARIANT` 값은 설정 단계에서 멈춘다 (오타로 기본 빌드가 나와 어르신 앱을 덮어쓰는 것을 막음). 지시에 없던 추가 동작이다
- google-services 검증은 변형을 반영한 패키지로 한다
- README "폰 한 대에 앱 두 개": `android/` 는 한 번에 한 변형만 담으므로 변형마다 `prebuild --clean` → gradle → APK를 `~/woowang-apks/` 로 복사
- 변형을 고르는 화면 등 앱 기능은 늘리지 않았다. `src/` 변경 없음

## 하드코딩 scheme 점검

- `src/` 의 `woowang://` 는 `src/api/mock.ts` 의 `qr_payload` 값과 `src/lib/pairCode.ts` 주석뿐이다. 파서는 `code=` 만 보므로 scheme과 무관하다. **QR 값은 두 앱이 같은 형식을 쓰도록 그대로 둔다** (앱 안 스캔, 코드 붙여넣기)
- `NotificationRouter` 의 G5 이동은 푸시 data와 expo-router 경로만 쓰고 scheme을 쓰지 않는다. 고칠 곳이 없다
- 알아둘 점: 서버가 주는 `woowang://pair` 링크를 앱 밖에서 열면 어르신용 앱이 열린다. 앱 안 스캔·붙여넣기에는 영향이 없다

## 확인한 것

- `tsc --noEmit` 통과
- `npx expo config --type public`: 기본 설정이 수정 전과 바이트 단위로 같다 (`GOOGLE_SERVICES_JSON` 없을 때, 있을 때 모두). 변형과의 차이는 이름·패키지·scheme 3줄뿐이다
- 기본 prebuild의 `AndroidManifest.xml` 이 수정 전 `android/` 의 파일과 같다
- 실제 `~/woowang-secrets/google-services.json` + 변형: "패키지 ... 가 등록돼 있지 않습니다"로 멈춘다 (파일에 아직 기본 패키지만 있다. 올바른 동작). 기본 + 실제 파일은 통과. `APP_VARIANT=gaurdian` 은 멈춘다
- **release APK 두 개 빌드 성공** (`arm64-v8a`, 각 39MB, README와 같은 순서, 저장소 복사본에서):

| APK에서 읽은 값 | 어르신용 | 보호자용 |
|---|---|---|
| 패키지 / 이름 | `kr.dementiacheck.app` / 약 챙김 | `kr.dementiacheck.app.guardian` / 약 챙김 보호자 |
| scheme | `woowang` | `woowang-guardian` |
| provider 4개, 앱 전용 permission | `kr.dementiacheck.app.*` | `kr.dementiacheck.app.guardian.*` (겹침 없음) |
| APK 안 `app.config` | 기본 값 | 변형 값, `firebaseConfigured: true` |
| `google_app_id` | (확인 안 함) | 파일에서 보호자 패키지 항목을 고름 |

## 확인하지 못한 것

- **폰 설치, 실제 FCM 수신, 알림 눌러 G5 이동은 시험하지 않았다.** 위 빌드는 진짜 파일에 보호자 패키지가 아직 없어 **가짜 google-services(가짜 값, 두 패키지)와 일회용 서명 키**로 만들었고, 산출물과 함께 지웠다. 설치용 APK로 쓸 수 있는 것은 남아 있지 않다
- 개발 빌드 + `APP_VARIANT=guardian npx expo start --dev-client` 는 실행해 보지 않았다

## 메인 에이전트가 폰에 설치하기 전에 필요한 것

1. 사용자가 두 패키지가 든 `google-services.json` 으로 교체 (전에는 변형 빌드가 멈춘다). 같은 Firebase 프로젝트 `medicine` 이어야 서버 서비스 계정이 그대로 통한다
2. **release 서명 키가 아직 없다.** `~/woowang-secrets/` 에 키가 없고 `~/.gradle/gradle.properties` 에 `WOOWANG_RELEASE_*` 가 없어 지금은 README 명령이 `packageRelease` 에서 멈춘다. R-041 ③대로 사용자가 만든다
3. 실제 서버 주소는 https 여야 한다 (R-041 ⑤)

## 발견한 기존 문제 (이번에 고치지 않음)

APK 안 `assets/app.config` 에 `android.googleServicesFile` 절대 경로가 들어간다. 내용이 아니라 경로(맥 사용자 이름 포함)뿐이고 T-FE11부터 그랬다. 심사위원 배포 전에 빼는 것을 권한다. 기본 빌드를 바꾸는 일이라 이 작업에 넣지 않았다.

## 헌장과 다르거나 애매한 지점

없음. 기본 빌드와 심사위원 APK 방식은 바뀌지 않는다 (R-044).

---

## 판정 (메인 에이전트, 2026-11-02): ✅ 승인 — R-046

- tsc 직접 확인, FE main 병합
- 시험은 개발 빌드로 한다. 폰 설치·FCM·G5 이동은 google-services 교체 뒤 메인 에이전트가 확인한다
- 배포 APK 전에 app.config의 googleServicesFile 절대 경로를 뺀다
