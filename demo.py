"""LLM 게이트웨이 데모 — 위에서 아래로 읽으면 된다.

  uv run demo.py                         # tour: 4장면을 순서대로 (기본 mock 모드)
  uv run demo.py swap | fallback | compare | summary
  uv run demo.py ask "질문" --model smart
  uv run demo.py swap --mode real        # 로컬 Ollama·내 키로 진짜 호출
  uv run demo.py swap --lang en          # 출력 언어 (en|ko, 문구는 gateway/i18n.py 에 모여 있다)
"""
import argparse
import os
import sys
import time

from gateway import i18n
from gateway.i18n import t

CONFIG_DIR = "configs"
LOG = os.path.join("runs", "calls.jsonl")
REPORT = os.path.join("runs", "report.md")
QUESTION = "LLM 게이트웨이가 무엇인지 한 문장으로 설명해 줘."


def banner(mode):
    kind = "mock" if mode == "mock" else "real"
    print("=" * 72)
    print(t("banner.%s.1" % kind))
    print(t("banner.%s.2" % kind))
    print("=" * 72)


def print_notices(gw, indent):
    """gateway 가 모은 안내 (code, params) 를 현재 언어로 찍는다."""
    for code, params in gw.notices:
        print(indent + t("label.notice"), i18n.render_notice(code, params))


def messages_for(gw, text=QUESTION):
    return [{"role": "user", "content": text}]


def scene_swap(args, report, calls, config):
    """장면 1: 같은 ask() 로 별칭만 바꿔 4 공급자를 부른다."""
    print(t("scene.swap.title"))
    gw = config.build_gateway(os.path.join(CONFIG_DIR, "gateway.yaml"), args.mode)
    print_notices(gw, "  ")
    recs = []
    for alias in ["openai", "anthropic", "gemini", "local"]:
        msgs = messages_for(gw)
        rec = calls.ask(gw, alias, msgs, "swap", args.log)
        recs.append(rec)
    print(report.swap_table(recs))
    for r in recs:
        if r["alias"] == "local" and r["status"] == "ok" and not r["mock"]:
            if r["_content"]:
                print("  " + t("label.local_reply"), r["_content"][:80])
            else:
                print("  " + t("label.local_reply"), t("local.empty"))
                print("  " + t("label.thinking"), (r["_reasoning"] or "")[:80].replace("\n", " "))
    print("  *", report.price_note())
    if args.mode == "mock":
        print(t("swap.mock_note"))
    return recs


def scene_fallback(args, report, calls, config):
    """장면 2: 오류를 주입하고 재시도 -> 폴백 순서를 타임라인으로 본다."""
    print(t("scene.fallback.title"))
    names = [args.scenario] if getattr(args, "scenario", None) else ["server_error", "rate_limit", "timeout"]
    for name in names:
        gw = config.build_gateway(os.path.join(CONFIG_DIR, "gateway.yaml"), args.mode, scenario=name)
        print_notices(gw, "  ")
        prim = gw.deployments("primary")[0]["litellm_params"]
        print(t("fallback.scenario_line", name=name, model=prim["model"], retries=gw.router.num_retries,
                timeout=prim.get("timeout", gw.router.timeout)))
        rec = calls.ask(gw, "primary", messages_for(gw), "fallback", args.log)
        print(report.timeline(rec))
        if not rec["_attempts"]:
            print(t("fallback.no_attempts"))


def scene_compare(args, report, calls, config):
    """장면 3: 코드는 그대로, yaml 만 바꿔 같은 요청 10개를 처리한다."""
    print(t("scene.compare.title"))
    rows = []
    for fname in ["no-fallback.yaml", "with-fallback.yaml"]:
        gw = config.build_gateway(os.path.join(CONFIG_DIR, fname), args.mode)
        recs = [calls.ask(gw, "primary", messages_for(gw), "compare", args.log) for _ in range(10)]
        lat = [r["latency_ms"] for r in recs]
        rows.append([fname, "%d/10" % sum(r["status"] == "ok" for r in recs),
                     sum(r["fallback_used"] for r in recs), "%.0f" % (sum(lat) / len(lat)),
                     "%.0f" % report.percentile50(lat), "%.2e" % sum((r["cost_usd"] or 0) for r in recs)])
    print(report.table([t(k) for k in ("col.config", "col.success", "col.fallbacks_count", "col.avg_latency",
                                      "col.p50_latency", "col.total_cost")], rows))
    print(t("compare.footnote"))


def scene_summary(args, report, calls, config):
    """장면 4: calls.jsonl 에 쌓인 기록을 별칭별로 집계한다."""
    print(t("scene.summary.title", log=args.log))
    recs = calls.read_calls(args.log)
    if not recs:
        print(t("summary.empty"))
        return
    print(report.summary_table(recs))
    report.write_markdown(recs, REPORT)
    print(t("summary.saved", path=REPORT))


def scene_ask(args, report, calls, config):
    gw = config.build_gateway(os.path.join(CONFIG_DIR, "gateway.yaml"), args.mode)
    print_notices(gw, "")
    # 없는 별칭이면 calls.ask 가 GatewayError 를 던지고, main 이 로캘 문구로 바꿔 종료 코드 2 로 끝낸다
    rec = calls.ask(gw, args.model, [{"role": "user", "content": args.question}], "ask", args.log)
    print(report.swap_table([rec]))
    print(t("label.answer"), rec["_content"])


def build_parser():
    """도움말도 번역 대상이라 parse 전에 정해 둔 언어로 파서를 만든다."""
    p = argparse.ArgumentParser(description=t("help.description"), formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mode", choices=["mock", "real"], default=os.environ.get("DEMO_MODE", "mock"), help=t("help.mode"))
    p.add_argument("--log", default=LOG, help=t("help.log"))
    p.add_argument("--lang", choices=list(i18n.LANGS), default=None, help=t("help.lang"))
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("tour")
    sub.add_parser("swap")
    f = sub.add_parser("fallback")
    f.add_argument("--scenario", choices=["server_error", "rate_limit", "timeout"], help=t("help.scenario"))
    sub.add_parser("compare")
    sub.add_parser("summary")
    a = sub.add_parser("ask")
    a.add_argument("question", help=t("help.question"))
    a.add_argument("--model", default="smart", help=t("help.model"))
    # --mode, --lang 을 하위 명령 뒤에도 쓸 수 있게 한다 (예: swap --mode real)
    for sp in sub.choices.values():
        sp.add_argument("--mode", choices=["mock", "real"], default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        sp.add_argument("--lang", choices=list(i18n.LANGS), default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    return p


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    i18n.set_lang(i18n.resolve_lang(i18n.lang_from_argv(argv)))   # --lang > AI_LAB_LLM_GATEWAY_LANG > LC_ALL/LC_MESSAGES/LANG
    args = build_parser().parse_args(argv)
    cmd = args.cmd or "tour"

    from dotenv import load_dotenv
    load_dotenv()                                       # .env 의 선택 키를 읽는다 (없어도 된다)
    print(t("loading"), flush=True)
    from gateway import calls, config, report           # litellm 을 여기서 import 한다

    banner(args.mode)
    t0 = time.perf_counter()
    try:
        if cmd == "tour":
            if os.path.exists(args.log):
                os.remove(args.log)                     # tour 는 새 기록으로 시작한다
            scene_swap(args, report, calls, config)
            scene_fallback(args, report, calls, config)
            scene_compare(args, report, calls, config)
            scene_summary(args, report, calls, config)
            print(t("done", secs=time.perf_counter() - t0))
        else:
            {"swap": scene_swap, "fallback": scene_fallback, "compare": scene_compare,
             "summary": scene_summary, "ask": scene_ask}[cmd](args, report, calls, config)
    except i18n.GatewayError as e:                      # 없는 별칭 등: 트레이스백 대신 고칠 방법을 알려 준다
        print(i18n.render_error(e.code, e.params), file=sys.stderr)
        return 2
    except OSError as e:                                # --log·report.md 를 쓰거나 읽을 수 없을 때
        print(i18n.render_error("io_error", {"path": e.filename or args.log, "reason": e.strerror or e}),
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
