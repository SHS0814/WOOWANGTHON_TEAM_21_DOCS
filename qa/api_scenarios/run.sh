#!/usr/bin/env bash
# QA API 시나리오 실행 (T-QA1). _targets/BE (BE main 복사본)를 18200번에 띄우고 pytest 를 돌린다.
#   qa/api_scenarios/run.sh            # 기본 프로필(인계 30분) + fast 프로필(인계 1분) 둘 다
#   qa/api_scenarios/run.sh default    # 기본 프로필만 (~10초)
#   qa/api_scenarios/run.sh fast       # 시간 시나리오만 (~9분, 실제로 기다림)
#   qa/api_scenarios/run.sh clock      # 자정 경계 (서버 시각을 23:58:00 에서 시작, ~2분). clock_server.py 사용
# 원본 저장소 폴더에서는 아무것도 실행하지 않는다. 남의 프로세스(8000번 등)는 건드리지 않는다.
set -euo pipefail
cd "$(dirname "$0")/../.."
ROOT="$PWD"
BE="$ROOT/_targets/BE"
RUN="$ROOT/_targets/run"
PORT="${QA_PORT:-18200}"
[ -d "$BE" ] || { echo "_targets/BE 가 없다. git clone .../WOOWANGTHON_TEAM_00_BE _targets/BE"; exit 2; }
(cd "$BE" && uv sync -q)

if lsof -tiTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "포트 $PORT 이 이미 쓰이고 있다. 내가 띄운 서버면 먼저 끈다: kill \$(cat $RUN/server.pid)"; exit 2
fi

UVICORN="uv run --no-sync uvicorn app.main:create_app --factory --host 127.0.0.1"
SERVER_CMD="$UVICORN"
start_server() {  # $1 = 프로필 이름, 나머지 = 환경 변수
  local profile="$1"; shift
  mkdir -p "$RUN"
  rm -rf "$RUN/$profile.db" "$RUN/photos-$profile"
  : > "$RUN/server-$profile.log"
  (cd "$BE" && env DATABASE_URL="sqlite:///$RUN/$profile.db" PHOTO_DIR="$RUN/photos-$profile" \
      DEMO_MODE=true CORS_ORIGINS="http://localhost:8299,http://127.0.0.1:8299" READER_LAYOUT=mock READER_CELLS=mock EXPO_PUSH_ENABLED=false "$@" \
      nohup $SERVER_CMD --port "$PORT" \
      --log-config "$ROOT/qa/api_scenarios/logging.json" >> "$RUN/server-$profile.log" 2>&1 &
   echo $! > "$RUN/server.pid")
  for _ in $(seq 1 40); do curl -sf "http://127.0.0.1:$PORT/health" >/dev/null && return 0; sleep 0.5; done
  echo "서버가 안 뜬다: $RUN/server-$profile.log"; exit 1
}
stop_server() {
  local pid; pid="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN || true)"
  [ -n "$pid" ] && kill $pid; sleep 1
}
trap stop_server EXIT

run_pytest() {  # $1 = 프로필, $2 = -m 표현식
  QA_BASE_URL="http://127.0.0.1:$PORT" QA_SERVER_LOG="$RUN/server-$1.log" \
    uv run --no-project -q --with httpx --with pytest pytest qa/api_scenarios -m "$2" -rA "${@:3}"
}

status=0
what="${1:-all}"; shift || true
if [ "$what" = all ] || [ "$what" = default ]; then
  start_server default DAILY_READING_LIMIT=1000
  run_pytest default "not fast and not clock" "$@" || status=1
  stop_server
fi
if [ "$what" = all ] || [ "$what" = fast ]; then
  start_server fast NO_RESPONSE_HANDOFF_MIN=1 RETAKE_WAIT_MIN=1 'REASK_OFFSETS_MIN=[0,1]' DAILY_READING_LIMIT=8
  run_pytest fast "fast" "$@" || status=1
  stop_server
fi
if [ "$what" = all ] || [ "$what" = clock ]; then
  SERVER_CMD="uv run --no-sync python $ROOT/qa/api_scenarios/clock_server.py"
  start_server clock DAILY_READING_LIMIT=1000 QA_CLOCK_START="$(TZ=Asia/Seoul date +%Y-%m-%d)T23:58:00+09:00"
  QA_CLOCK=1 run_pytest clock "clock" "$@" || status=1
  stop_server
  SERVER_CMD="$UVICORN"
fi
exit $status
