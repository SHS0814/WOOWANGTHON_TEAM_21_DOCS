# API 시나리오 테스트 (T-QA1)

QA 에이전트의 테스트 코드다. 제품 코드가 아니다. `_targets/BE`(BE main 복사본) 서버에 HTTP로만 요청한다.

```bash
qa/api_scenarios/run.sh            # default + fast
qa/api_scenarios/run.sh default -k s08
```

| 파일 | 내용 |
|---|---|
| `woowang_qa.py` | 가족 만들기, 시연 트리거, MockReader 결과가 나오는 사진 찾기(`find_photo`), `set_scenario`(api.md 3.28), 서버 로그로 푸시 세기 |
| `test_01_pairing_consent.py` | S01 짝짓기·동의, S11 해제·가족 격리 |
| `test_02_dose_flows.py` | S02~S05, S08~S10, S12, S13 (사진 바이트로 칸 상태를 칸별로 지정) |
| `test_03_errors.py` | S14 오류 코드, 이슈 재현 `test_q001`, `test_q002` |
| `test_04_timing_fast.py` | fast 프로필 전용: S06 무응답, S07 늦은 사진, 기한 초과, C3, 판독 한도 |
| `test_05_mock_scenario.py` | `POST /dev/mock-scenario`로 결정적 시나리오, T-BE4 회귀(동시성·CORS), `test_q005` |
| `logging.json` | 서버 로그에 앱 INFO(푸시 기록)를 남기는 uvicorn 설정 |

- `test_q00N_*`는 이슈 재현 테스트다. 이슈가 고쳐지면 통과한다
- 가족 만들기는 IP당 시간당 10회 제한이 있어서, 테스트는 요청마다 다른 `cf-connecting-ip` 헤더를 붙인다 (Cloudflare 뒤를 가정한 서버 동작)
- 결과 기록: `docs/qa/results.md`
