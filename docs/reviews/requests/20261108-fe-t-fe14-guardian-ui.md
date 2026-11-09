# 검토 요청: T-FE14 보호자·처음 설정 화면 디자인 전면 정리
- 요청자: FE 에이전트
- 날짜: 2026-11-08
- 종류: 설계 / 코드
- 관련 헌장 항목: 5장 원칙 1·2·3·6·7, 6장 (모의 표시), R-008, R-047
- 브랜치·커밋: FE `fe/guardian-redesign` 02db755 (main c956a0c에서 시작, main 병합 안 함)

## 무엇을 했나

R-047 사용자 결정대로 처음 설정 화면과 보호자 화면을 의료 앱 모습으로 다시 만들었다. 기능, API 호출, 계약은 바꾸지 않았다.

### 바뀐 화면
| 화면 | 파일 | 바뀐 점 |
|---|---|---|
| 시작 | `src/app/index.tsx` | 역할을 읽는 짧은 순간에 빈 화면 대신 앱 표시(흰 바탕이라 어르신 화면으로 넘어갈 때 깜빡이지 않음) |
| 역할 선택 | `src/app/role.tsx` | "약 챙김" 로고, 한 줄 설명, 역할 카드 2개(아이콘, 제목, 한 줄 설명). 어르신 쪽 버튼을 누르면 `/elder`로 가고 그 뒤 화면은 그대로 |
| G1 연결 | `guardian/connect.tsx` | 3단계 표시(가족 만들기 → QR로 연결 → 어르신 동의), 입력칸 카드, QR 카드(6자리 숫자 크게, 만료 시각 칩), 초대 코드 합류 행. 합류 화면도 같은 모습 |
| G4 홈 | `guardian/(tabs)/index.tsx` | 날짜 + "어머니 오늘" 제목 → 오늘 요약 카드(큰 숫자 n/m번, 진행 막대, 상태 칩, 모의·시뮬레이션 표시, 오늘 복약 건별 상태) → 확인할 일 카드 목록 → 다음 할 일(다음 복약, 약통 남은 칸). 약통·일정이 없으면 맨 위에 "시작하기" 카드 |
| G5 인계 상세 | `guardian/handoff/[id].tsx` | 사유 카드(아이콘, 사유, 시간대·알림 시각 칩, 설명, 전화하기) → "사진과 AI 판독" 카드(촬영 시각, AI 판독·모의 결과 배지, 사진, 칸 격자) → 한계 안내 → **하단 고정 "보호자 판정"** 버튼(같은 무게로 나란히, 아이콘 + 글자). 판정이 있으면 판정 결과 칩 |
| G6 기록 | `guardian/(tabs)/records.tsx` | 오늘 / 이번 주(큰 숫자 카드) / 최근 7일 목록 행 |
| G8 설정 | `guardian/(tabs)/settings.tsx` | 묶음 목록(호칭, 약통과 시각, 칸 그대로일 때 라디오, 알림, 사진 보관 라디오, 연결된 폰). "약통 채우기" 이동 행을 하나 더 둠(홈 버튼을 탭으로 바꾸면서 이동 경로 유지용) |
| G2 약통 등록 | `guardian/pillbox.tsx` | 구조 카드, 줄 수 고치기 카드, 하단 고정 "이대로 등록". 촬영 화면은 기존 `PillboxCamera` 그대로 |
| G3 복약 시각 | `guardian/schedule.tsx` | 시간대별 카드(큰 시각, −10분/+10분 버튼), 하단 고정 저장 |
| G7 리필 | `guardian/refill.tsx` | 남은 칸 큰 숫자 카드, 남은 기간, 경고 상자, 마지막 채운 날 행, 하단 고정 촬영 버튼 |
| 기준선 확인 | `components/guardian/BaselineReview.tsx` | 칸마다 카드, "차 있어요 / 비어 있어요" 고르기(고른 쪽은 ✓ 아이콘 + 테두리), 하단 고정 "확인 끝" |

### 내비게이션
- 보호자 홈·기록·설정을 하단 탭으로 묶었다 (`src/app/guardian/(tabs)/`, expo-router 내장 `Tabs`). 그룹 폴더라 **주소는 `/guardian`, `/guardian/records`, `/guardian/settings` 그대로**다.
- 연결, 인계 상세, 약통 등록, 복약 시각, 약통 채우기는 그 위에 쌓이는 화면(머리줄 + 뒤로)이다.
- `NotificationRouter`의 딥링크 경로(`/guardian/handoff/[id]`, `/guardian/records`, `/guardian/settings`)는 모두 그대로 맞는다. 파일은 수정하지 않았다.
- 홈 아래쪽 "기록 보기 / 약통 채우기 / 설정" 버튼 3개는 탭(기록·설정)과 홈의 약통 행(→ 약통 채우기)으로 바뀌었다.

### 디자인 토큰 (`src/theme.ts` 끝에 `guardian` 블록 추가, 기존 값 무변경)
- 색: 바탕 `#F2F4F7`, 카드 `#FFFFFF`, 테두리 `#E1E6ED`, 글자 `#14202E`, 보조 글자 `#4B5767`, 주 색(의료 파랑) `#1B5FBF`
- 상태 색(글자/바탕): 정상 `#11704F/#E5F4EC`, 주의 `#8F5200/#FFF3DC`, 위험 `#B3261E/#FDECEA`, 중립 `#4B5767/#EEF1F5`. 모의 표시는 어르신과 같은 `colors.mockBg`(보라) 바탕 흰 글자
- 대비(WCAG): 글자/바탕 14.9, 보조 글자/바탕 6.7, 흰 글자/주 색 6.1, 상태 글자/상태 바탕 5.3~5.7, 흰 글자/모의 보라 9.9. 모두 AA(4.5) 이상
- 글자 단계: 화면 제목 30, 카드 제목 24, 섹션 19, 본문 17, 보조·칩·탭 이름 16, 큰 숫자 34. **보호자 화면 글자는 16 이상** (예외: 약통 격자 칸 안의 "이번" 표시 12. 기존과 같은 크기이고 같은 뜻을 굵은 테두리와 16 크기 범례가 함께 알려 준다)
- 모서리: 카드 16, 버튼·입력 12. 버튼 높이 54(줄 안 작은 버튼 48), 목록 행 64, 탭 56 이상 → 터치 영역 44 이상

### 새 구성 요소 (`src/components/guardian/`)
`Icon`(react-native-svg 선 아이콘 31종), `ui.tsx`(GText, GScreen, Card, SectionTitle, ListGroup, ListRow, RadioRow, StatusChip, Notice, GButton, GField, GJudgeBadge, MockTag, Stat, ErrorText, IconBubble), `Brand`, 그리고 보호자만 쓰던 `PillboxGrid`·`BaselineReview`·`PhotoWithBoxes`를 이 폴더로 옮겼다. 보호자만 쓰던 `components/Field.tsx`는 `GField`로 대체해 지웠다. 복약 건 상태 칩 판단은 `src/lib/doseStatus.ts`(기존 기록 화면 판단 순서 그대로).

## 지킨 것 확인
1. **어르신 화면 무변경**
   - `git diff main --stat -- src/app/elder` → 비어 있음
   - 어르신이 쓰는 공용 파일 `Text, BigButton, Screen, AskView, PillboxCamera, AiBadge, MockBanner, RemotePhoto`, `src/app/_layout.tsx`, `src/app/dev.tsx` → `git diff main --stat` 비어 있음
   - `src/theme.ts` → 삭제·수정 줄 0, 추가만 있음
   - 웹 모의 모드로 어르신 연결·질문·결과 화면을 찍어 기존 모습 그대로임을 눈으로 봤다(`x-elder-*.png`)
2. 새 기능, 새 API 호출, api.md 변경 없음. 홈의 "다음 복약"과 오늘 복약 건 목록은 기존에 이미 부르던 `api.today()` 응답(`next_event`, `items`)을 쓴다
3. 모의·시뮬레이션 표시: 상단 띠(MockBanner)와 `SimulationTag`는 그대로 쓴다. "모의 결과", "모의 결과 포함", "시뮬레이션 포함", "지난 날 기록은 모의 데이터예요", "남은 칸은 모의 계산이에요", 개발용 모의 코드 버튼은 이전 글자색 표시에서 **보라 바탕 흰 글자 칩**으로 바뀌어 더 눈에 띈다. 기록·홈의 복약 건 "· 시뮬레이션" 글자도 보라 칩으로 바꿨다
4. 상태는 아이콘 모양 + 글자: 정상 ✓원, 안 드심 ✕원, 주의 △!, 위험 ○!, 예정 시계, 진행 중 화살표. 격자의 ○●?! 기호와 점선·굵은 테두리도 그대로
5. 문구: 의료 조언 없음. 새로 넣은 짧은 설명은 역할 카드 설명 2개, 시작하기 카드 설명 2개, 연결 화면 설명 1줄, 합류 화면 설명 1줄, 3단계 이름이다(모두 앱 동작 설명). 판정 버튼·칩은 `VERDICT_LABEL`의 ✓/✕ 기호를 아이콘으로 바꿔 "드심 / 안 드심 / 확인했어요"로 보인다(화면 낭독 이름은 기존 `VERDICT_LABEL` 그대로)
6. 판정 버튼 3개는 같은 모양(흰 바탕 테두리)으로 나란히 둔다. 어느 쪽으로도 유도하지 않으려고 주 색을 쓰지 않았다
7. **새 의존성 없음.** `@expo/vector-icons`는 이 프로젝트 node_modules에 없고 `expo-font`(네이티브 모듈)가 필요해 개발 빌드 재설치가 생긴다. 그래서 이미 들어 있는 `react-native-svg`로 아이콘을 직접 그렸다. 하단 탭은 expo-router 안에 들어 있는 `Tabs`를 쓴다
8. 비밀값·.env·google-services.json 커밋 없음

## 검사 결과
- `npx tsc --noEmit` 통과 (`--noUnusedLocals`로도 바뀐 파일에 미사용 없음)
- 테스트: 저장소에 테스트 스크립트·테스트 파일이 없다(`package.json`에 test 없음). 돌릴 기존 테스트가 없었다
- `npx expo export --platform android` 번들 성공
- `EXPO_PUBLIC_API_MODE=mock npx expo export --platform web` 번들을 로컬에서 띄워 Playwright(작업 폴더 밖 임시 설치)로 390×844 화면에서 흐름을 실제로 눌러 봤다: 역할 선택 → 가족 만들기 → QR → 홈(약통 등록 시작 카드) / 초대 코드 합류 → 홈 → 기록 → 설정 → 약통 채우기 → 복약 시각 → 개발 도구로 무응답·애매 인계 2건 만들기(어르신 쪽 촬영 포함) → 홈 → G5 두 건 → "드심" 판정 → 홈으로 돌아가 반영 확인 → 약통 다시 등록(모의 사진) → 구조 확인 → 등록

## 스크린샷
`docs/reviews/requests/20261108-fe-t-fe14-guardian-ui/` (커밋 안 함). 웹 모의 모드, 390×844 @2x. 긴 화면은 창을 늘려 한 장에 담았다(`-viewport`가 붙은 것은 실제 첫 화면 크기).
- `01-role`, `02-connect-create`, `03-connect-join`, `14-connect-qr`, `15-home-setup-pillbox`
- `04-home-normal`, `05-home-handoffs`, `05b-home-handoffs-viewport`
- `10-handoff-1`(애매, 사진·격자 2장), `10-handoff-2`(무응답), `10c-after-verdict`
- `06-records`, `06b-records-after`, `07-settings`, `08-refill`, `09-schedule`, `11-pillbox-camera`, `12-pillbox-confirm`, `13-pillbox-after`
- `x-elder-1~6`: 어르신 화면이 그대로인지 확인용

## 확인 못 한 것
- **실제 폰(Android 개발 빌드) 확인 안 함.** 에뮬레이터는 쓰지 않았다(R-044). 폰에서 확인해 주세요: 하단 탭 높이·안전 영역, 머리줄 뒤로 버튼, 그림자(elevation), 키보드가 하단 고정 버튼을 가리는지(연결·설정 입력칸), 알림을 눌렀을 때 G5로 이동(경로는 그대로지만 탭 묶음 안으로 옮긴 뒤 기기에서는 안 눌러 봤다)
- 웹 모의 모드에는 사진이 없어 "사진 없음 (모의 촬영)" 상자로만 보였다. 실제 사진 위 강조 상자(PhotoWithBoxes)는 위치·크기 계산을 바꾸지 않았고 모서리·색만 다듬었다
- 아이폰은 확인 안 함
- 화면 낭독기(TalkBack)로 직접 들어 보지 않았다. 접근성 이름은 코드에서 확인했다

## 헌장과 다르거나 애매한 지점
- 홈에서 "기록 보기 / 약통 채우기 / 설정" 버튼이 하단 탭과 약통 행으로 바뀌었다. 기능은 같고 이동 경로만 바뀌었다
- 정상인 날에도 홈 요약 카드에 오늘 복약 건별 상태(예정·정상)가 보인다. 알림은 늘지 않으므로 원칙 2(알림 최소화)와 충돌하지 않는다고 봤지만, 이전보다 화면 정보가 많아졌다
- 역할 선택 화면은 어르신이 볼 수도 있는데 보호자 모습(본문 17~21)으로 바꿨다. 이전은 어르신 크기(28~40)였다. R-047이 처음 설정 화면을 보호자 쪽 디자인으로 정한 것으로 이해했다. 크게 유지해야 하면 알려 주세요
