"""LLM 게이트웨이 데모 — 위에서 아래로 읽으면 된다.

  uv run demo.py                         # tour: 4장면을 순서대로 (기본 mock 모드)
  uv run demo.py swap | fallback | compare | summary
  uv run demo.py ask "질문" --model smart
  uv run demo.py swap --mode real        # 로컬 Ollama·내 키로 진짜 호출
"""
import argparse
import os
import sys
import time

CONFIG_DIR = "configs"
LOG = os.path.join("runs", "calls.jsonl")
REPORT = os.path.join("runs", "report.md")
QUESTION = "LLM 게이트웨이가 무엇인지 한 문장으로 설명해 줘."


def banner(mode):
    if mode == "mock":
        print("=" * 72)
        print("※ 연습용 목(mock) 모드 — 응답 문장·토큰 수(10/20 고정)·지연은 가짜입니다.")
        print("  진짜인 것: Router 의 재시도·폴백·백오프, 가격표 비용 계산, 설정 교체 효과.")
        print("=" * 72)
    else:
        print("=" * 72)
        print("real 모드 — Ollama·키가 있는 공급자는 진짜로 부릅니다. 느릴 수 있습니다.")
        print("  키가 없는 공급자와 꺼진 Ollama 는 MOCK 배지를 단 채 mock 으로 진행합니다.")
        print("=" * 72)


def messages_for(gw, text=QUESTION):
    return [{"role": "user", "content": text}]


def scene_swap(args, report, calls, config):
    """장면 1: 같은 ask() 로 별칭만 바꿔 4 공급자를 부른다."""
    print("\n[1/4] swap — 같은 코드, 별칭(모델 문자열)만 다르다")
    gw = config.build_gateway(os.path.join(CONFIG_DIR, "gateway.yaml"), args.mode)
    for n in gw.notices:
        print("  안내:", n)
    recs = []
    for alias in ["openai", "anthropic", "gemini", "local"]:
        msgs = messages_for(gw)
        rec = calls.ask(gw, alias, msgs, "swap", args.log)
        recs.append(rec)
    print(report.swap_table(recs))
    for r in recs:
        if r["alias"] == "local" and r["status"] == "ok" and not r["mock"]:
            if r["_content"]:
                print("  local 응답:", r["_content"][:80])
            else:
                print("  local 응답: (빈 응답: 생각 단계가 토큰을 다 씀)")
                print("  생각 앞부분:", (r["_reasoning"] or "")[:80].replace("\n", " "))
    print("  *", report.PRICE_NOTE)
    if args.mode == "mock":
        print("  * mock 의 토큰은 고정값이라 비용 열은 '같은 토큰량일 때의 단가 비교'로만 읽으세요.")
    return recs


def scene_fallback(args, report, calls, config):
    """장면 2: 오류를 주입하고 재시도 -> 폴백 순서를 타임라인으로 본다."""
    print("\n[2/4] fallback — 같은 그룹에서 재시도, 그다음 다른 그룹(backup)으로 폴백")
    names = [args.scenario] if getattr(args, "scenario", None) else ["server_error", "rate_limit", "timeout"]
    for name in names:
        gw = config.build_gateway(os.path.join(CONFIG_DIR, "gateway.yaml"), args.mode, scenario=name)
        for n in gw.notices:
            print("  안내:", n)
        prim = gw.deployments("primary")[0]["litellm_params"]
        print("\n  시나리오 %s: primary=%s (재시도 %d회, timeout %ss)" % (
            name, prim["model"], gw.router.num_retries, prim.get("timeout", gw.router.timeout)))
        rec = calls.ask(gw, "primary", messages_for(gw), "fallback", args.log)
        print(report.timeline(rec))
        if not rec["_attempts"]:
            print("  (real 모드 primary 는 시도 단위 기록이 없어 최종 결과만 보입니다. 시도 단위는 mock 모드가 정확)")


def scene_compare(args, report, calls, config):
    """장면 3: 코드는 그대로, yaml 만 바꿔 같은 요청 10개를 처리한다."""
    print("\n[3/4] compare — 같은 요청 10개, 설정 파일만 다르다 (primary 는 실패·실패·성공 반복)")
    rows = []
    for fname in ["no-fallback.yaml", "with-fallback.yaml"]:
        gw = config.build_gateway(os.path.join(CONFIG_DIR, fname), args.mode)
        recs = [calls.ask(gw, "primary", messages_for(gw), "compare", args.log) for _ in range(10)]
        lat = [r["latency_ms"] for r in recs]
        rows.append([fname, "%d/10" % sum(r["status"] == "ok" for r in recs),
                     sum(r["fallback_used"] for r in recs), "%.0f" % (sum(lat) / len(lat)),
                     "%.0f" % report.percentile50(lat), "%.2e" % sum((r["cost_usd"] or 0) for r in recs)])
    print(report.table(["설정", "성공", "폴백 횟수", "평균 지연(ms)", "p50 지연(ms)", "총 추정 비용(USD)"], rows))
    print("  * 값이 다른 곳: num_retries, fallbacks 두 곳 (나머지는 주석 차이, diff configs/no-fallback.yaml configs/with-fallback.yaml)")


def scene_summary(args, report, calls, config):
    """장면 4: calls.jsonl 에 쌓인 기록을 별칭별로 집계한다."""
    print("\n[4/4] summary — %s 에 쌓인 호출 기록 집계" % args.log)
    recs = calls.read_calls(args.log)
    if not recs:
        print("  기록이 없습니다. 먼저 `uv run demo.py` 를 실행하세요.")
        return
    print(report.summary_table(recs))
    report.write_markdown(recs, REPORT)
    print("  마크다운 표를 %s 에 저장했습니다." % REPORT)


def scene_ask(args, report, calls, config):
    gw = config.build_gateway(os.path.join(CONFIG_DIR, "gateway.yaml"), args.mode)
    for n in gw.notices:
        print("안내:", n)
    # 없는 별칭이면 트레이스백 대신 고칠 방법을 알려 주고 종료 코드 2 로 끝낸다
    known = sorted({d["model_name"] for d in gw.router.model_list})
    if args.model not in known:
        print(f"별칭 {args.model} 이 configs/gateway.yaml model_list 에 없습니다. 사용 가능: {', '.join(known)}", file=sys.stderr)
        sys.exit(2)
    rec = calls.ask(gw, args.model, [{"role": "user", "content": args.question}], "ask", args.log)
    print(report.swap_table([rec]))
    print("응답:", rec["_content"])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mode", choices=["mock", "real"], default=os.environ.get("DEMO_MODE", "mock"))
    p.add_argument("--log", default=LOG, help="호출 기록 파일")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("tour")
    sub.add_parser("swap")
    f = sub.add_parser("fallback")
    f.add_argument("--scenario", choices=["server_error", "rate_limit", "timeout"])
    sub.add_parser("compare")
    sub.add_parser("summary")
    a = sub.add_parser("ask")
    a.add_argument("question")
    a.add_argument("--model", default="smart")
    # --mode 를 하위 명령 뒤에도 쓸 수 있게 한다 (예: swap --mode real)
    for sp in sub.choices.values():
        sp.add_argument("--mode", choices=["mock", "real"], default=argparse.SUPPRESS)
    args = p.parse_args()
    cmd = args.cmd or "tour"

    from dotenv import load_dotenv
    load_dotenv()                                       # .env 의 선택 키를 읽는다 (없어도 된다)
    print("LiteLLM 불러오는 중… (처음엔 10초쯤 걸립니다)", flush=True)
    from gateway import calls, config, report           # litellm 을 여기서 import 한다

    banner(args.mode)
    t0 = time.perf_counter()
    if cmd == "tour":
        if os.path.exists(args.log):
            os.remove(args.log)                         # tour 는 새 기록으로 시작한다
        scene_swap(args, report, calls, config)
        scene_fallback(args, report, calls, config)
        scene_compare(args, report, calls, config)
        scene_summary(args, report, calls, config)
        print("\n끝. 총 %.1f초" % (time.perf_counter() - t0))
    else:
        {"swap": scene_swap, "fallback": scene_fallback, "compare": scene_compare,
         "summary": scene_summary, "ask": scene_ask}[cmd](args, report, calls, config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
