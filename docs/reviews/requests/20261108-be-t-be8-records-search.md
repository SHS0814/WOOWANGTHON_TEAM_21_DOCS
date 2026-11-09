# 검토 요청: T-BE8 기록 검색과 요약 366일·전체
- 요청자: BE 에이전트
- 날짜: 2026-11-08
- 종류: 코드 (계약 변경 없음. api.md 3.19·3.25는 DOCS a470c7e의 메인 에이전트 계약을 그대로 구현)
- 관련 헌장 항목: 4장 MVP #6(하루·주간 요약), R-051

## 무엇을 했는가
1. `GET /dose-events?from=&to=` 선택 쿼리 (api.md 3.19)
   - `filter=exceptions|handoff|not_taken|taken`, `reason=<HandoffReason>`, `order=asc(기본)|desc` (`scheduled_at` 기준)
   - `exceptions` = 인계 행이 하나라도 있거나 `outcome=not_taken`. `handoff` = 인계 행이 하나라도 있음. `not_taken`·`taken` = `outcome` 값. `reason`은 그 사유의 인계 행이 있는 건, `filter`와 같이 오면 둘 다 만족
   - 기간: `filter`나 `reason`이 있으면 최대 366일(양 끝 포함), 없으면 31일 그대로. `order`만으로는 늘어나지 않는다
   - 잘못된 값(`filter=bogus`, `filter=`, `reason=bogus`, `order=newest`)은 `422 validation_error`, `details.fields[0].field`가 쿼리 이름
   - 쿼리가 없을 때 응답 형태·순서·31일 제한은 그대로
2. `GET /summaries` (api.md 3.25)
   - 하루 요약 최대 366일 (이전 31일). 주간 12주 그대로
   - `period=total`: `from`·`to` 무시, 항목 하나. `period_start` = 이 가족의 첫 복약 건 날짜(오늘 이전 건 중, 없으면 오늘), `period_end` = 오늘, `final: false`. 나머지 필드 계산 방식은 하루·주간과 같다 (`refill`은 지금 약통 상태)
3. 성능
   - 요약: 이전에는 날짜(또는 주)마다 쿼리 3번(366일이면 1,098번)이었다. 이제 기간 전체를 쿼리 3번(복약 건 열만, 인계 3열, 판독 4열)으로 읽고 날짜별로 나눠 더한다. 주간·전체도 같은 경로. 요약 푸시(`jobs.py`의 `summarize`)도 같은 함수를 쓴다
   - 기간 기록: 이전에는 건마다 쿼리 약 5번(칸·사진·판독·인계·판정자). 366일 검색이 되면서 `events_out`(종류별 일괄 조회, 500건씩 나눔)으로 바꿨다. 결과는 건별 `event_out`과 같다 (테스트로 비교). `/dose-events/today`·인계 목록 등 다른 곳은 그대로 `event_out`

## 확인한 것
- pytest **190 통과·2 건너뜀** (이전 177 + 새 `tests/test_records_search.py` 13개). ruff check·format 통과. 커밋 전 실제 종료 코드로 확인
- 새 테스트 (1년치 기록 730건을 `tests/history.py` 규칙으로 DB에 직접 넣음: AI 정상, 애매 인계→taken, 무응답 인계→not_taken, 인계 없는 not_taken, 열린 무응답 인계, 리필 확인 요청)
  - filter 4종 × reason × order asc/desc 조합 9가지: 기대 목록과 순서까지 일치. `exceptions = handoff ∪ not_taken` 확인
  - 기간 경계: 검색 없음 31일 OK·32일 422, `order`만 32일 422, filter/reason/둘 다 366일 OK·367일 422, from>to 422
  - 잘못된 쿼리 값 4종 422 `validation_error`
  - 쿼리 없을 때 응답 키·순서 그대로
  - `events_out` == 건별 `event_out` (보호자·어르신 형태 모두, 보관 기한으로 지운 사진 포함)
  - 하루 요약 366일: 항목 366개, **이전 구현(테스트 안에 그대로 옮겨 둠)과 366일 전부 같은 결과**. 주간 요약도 이전 구현과 같음. 367일 422
  - total: 데이터 있는 가족(합계 = 하루 요약 366개 합, 사유별 합 일치, 오늘 건 포함), 빈 가족(오늘~오늘, 숫자 모두 0, refill null), `from>to`를 줘도 무시, 미래 날짜 건·다른 가족 건 제외, 어르신 403, `period=month` 422
- 기존 테스트 수정 1곳: `test_summary_jobs.py`의 "하루 요약 296일 → 422" 확인을 "367일 → 422"로 (계약 변경에 따름)

## 1년치 응답 시간
측정: 이 PC(Apple M5 10코어 macOS), 앱은 같은 프로세스 TestClient(네트워크·터널 제외), DB는 **Docker Postgres 16**(운영과 같은 버전)과 SQLite 파일. 1년(2025-10-23~2026-10-22) 기록, 7회 중앙값. 서버(4코어 우분투)에서는 재지 않았다.

| 요청 | Postgres, 하루 2건 (730건) | Postgres, 하루 4건 (1,460건) |
|---|---|---|
| `/summaries?period=day` 366일 | **38 ms** | **50 ms** |
| `/summaries?period=total` | 25 ms | 37 ms |
| `/summaries?period=week` 12주 | 15 ms | 19 ms |
| (비교) 이전 방식 하루 요약 366일 | 664 ms | 659 ms |
| `/dose-events filter=exceptions` 366일 | 41 ms (263건, 296 KiB) | 77 ms (526건, 593 KiB) |
| `/dose-events reason=unclear` 366일 | 34 ms (73건) | 41 ms (146건) |
| `/dose-events filter=taken` 366일 (최악) | 107 ms (569건, 883 KiB) | 226 ms (1,138건, 1.7 MiB) |
| (비교) 이전 방식 건별 직렬화, taken 전체 | 1,205 ms | 2,411 ms |
| `/dose-events` 31일 (검색 없음) | 23 ms | 35 ms |

SQLite는 모두 이보다 빠르다(하루 요약 366일 28/38 ms). 서버 CPU가 이 PC보다 2~3배 느리다고 봐도 1초 목표 안이다.

## 관련 파일·브랜치·커밋
- BE `be/records-search` 81eb9f1 (main 61787c9에서 시작)
  - `app/routers/dose.py`, `app/routers/summaries.py`, `app/serializers.py`(`events_out`), `app/services/summary.py`
  - `tests/history.py`(1년치 시드), `tests/test_records_search.py`, `tests/test_summary_jobs.py`
- 측정 스크립트는 커밋하지 않음 (임시 파일)

## 계약이 모호해서 정한 점
1. **"인계가 있었던 건"은 인계 행이 하나라도 있으면** (사유·열림/닫힘·`binds_event` 무관). 그래서 `filter=handoff`·`exceptions`에 **리필 확인 요청(`refill_unconfirmed`, 대상 칸과 무관한 인계)만 있는 건도 들어간다.** 요약의 `handoffs_by_reason`이 이미 모든 인계를 세므로 맞췄다. 다만 DoseEvent의 `handoff` 필드는 원래대로 복약 건 결과를 정하는 인계(`binds_event`)만 보여 주므로, 이런 건은 목록에 `handoff: null`로 나온다. FE가 특이사항 표시를 `handoff`로만 하면 이유가 안 보일 수 있다. 리필 확인 요청을 `handoff`/`exceptions`에서 빼야 하면 한 줄 바꾸면 된다 (`reason=refill_unconfirmed`는 어느 쪽이든 나온다)
2. `period=total`의 `from`·`to` "무시": 값의 크기·순서는 보지 않지만 **날짜 형식이 아니면(`from=abc`) 422**다(FastAPI 형식 검사). 완전히 무시해야 하면 바꾼다
3. `period=total`의 첫 복약 건은 **오늘 이전(오늘 포함) 건 중** 가장 이른 날짜. 미래 날짜 건은 합계에도 넣지 않는다 (`period_end`가 오늘이므로)
4. 같은 `scheduled_at`인 건끼리의 순서는 정하지 않았다 (이전과 같음)
5. `order`는 검색 없이도(31일) 쓸 수 있다
6. 응답 크기: `filter=taken` 1년은 0.9~1.7 MiB(건마다 서명된 사진 URL·최신 판독 포함). 계약에 페이지 나누기가 없어 그대로 둔다. FE는 7일 페이지는 검색 없이 31일 안으로, 1년 검색은 `exceptions`·`reason` 위주로 쓰면 가볍다
7. Notion: API 엔드포인트 DB의 `/dose-events`·`/summaries` 행 요약·쿼리 설명을 갱신하고 상태를 "구현"으로 바꿨다. **업무 DB에 T-BE8 행이 없어** 갱신하지 못했다 (새 행은 만들지 않음). 메인 에이전트가 행을 만들면 상태·브랜치·커밋을 채운다
