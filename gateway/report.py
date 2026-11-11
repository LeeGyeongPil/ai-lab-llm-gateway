"""표·타임라인·집계. 외부 패키지 없이 고정폭 텍스트로 그린다."""
import statistics
import unicodedata

from .i18n import t


def price_note():
    return t("price_note")


def width(s):
    """터미널 표시 폭 (한글 등은 2칸)."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in str(s))


def pad(s, w):
    return str(s) + " " * (w - width(s))


def table(headers, rows):
    rows = [[str(c) for c in r] for r in rows]
    widths = [max(width(h), *(width(r[i]) for r in rows)) if rows else width(h)
              for i, h in enumerate(headers)]
    line = lambda cells: "| " + " | ".join(pad(c, w) for c, w in zip(cells, widths)) + " |"
    sep = "|-" + "-|-".join("-" * w for w in widths) + "-|"
    return "\n".join([line(headers), sep] + [line(r) for r in rows])


def cost_text(rec):
    """None/0 을 구분해서 보여 준다: chaos=계산 안 됨, ollama=로컬(무료)."""
    if rec["status"] != "ok":
        return "-"
    if rec["provider"] == "chaos":
        return t("cost.not_computed")
    if rec["provider"] in ("ollama_chat", "ollama"):
        return t("cost.local_free")
    if rec["cost_usd"] is None:
        return t("cost.not_computed")
    return "%.2e" % rec["cost_usd"]


def swap_table(recs):
    rows = []
    for r in recs:
        tok = "-" if r["prompt_tokens"] is None else "%d / %d" % (r["prompt_tokens"], r["completion_tokens"])
        rows.append([r["alias"], r["provider"], r["model"], tok, r["prompt_tokens_counted"] or "-",
                     cost_text(r), "%.0f" % r["latency_ms"], "MOCK" if r["mock"] else t("cell.real"), r["status"]])
    return table([t(k) for k in ("col.alias", "col.provider", "col.model", "col.tokens", "col.counted",
                                 "col.cost", "col.latency", "col.mock", "col.status")], rows)


def timeline(rec):
    """시도 단위 타임라인. attempts 는 chaos 가 본 시도, 마지막 줄은 최종 결과."""
    lines = []
    for i, a in enumerate(rec["_attempts"], 1):
        res = a["error_type"] if a["outcome"] == "error" else t("tl.success")
        lines.append(t("tl.attempt", t=a["t"], i=i, behavior=a["behavior"], result=res))
    total = rec["latency_ms"] / 1000
    if rec["status"] == "ok":
        how = t("tl.answered_fallback") if rec["fallback_used"] else t("tl.answered")
        lines.append("  +%5.2fs  %s: %s%s" % (total, how, rec["model"], " (MOCK)" if rec["mock"] else ""))
    else:
        lines.append("  +%5.2fs  %s: %s" % (total, t("tl.final_failure"), rec["error_type"]))
    return "\n".join(lines)


def percentile50(values):
    return statistics.median(values) if values else None


def summarize(recs):
    """별칭(alias)별 호출 수·성공률·총 비용·p50 지연."""
    groups = {}
    for r in recs:
        groups.setdefault(r["alias"], []).append(r)
    out = []
    for alias, rs in groups.items():
        ok = [r for r in rs if r["status"] == "ok"]
        out.append({
            "alias": alias, "calls": len(rs), "success_rate": len(ok) / len(rs),
            "fallbacks": sum(1 for r in rs if r["fallback_used"]),
            "total_cost_usd": sum((r["cost_usd"] or 0) for r in rs),
            "p50_latency_ms": percentile50([r["latency_ms"] for r in rs]),
            "mock_calls": sum(1 for r in rs if r["mock"]),
        })
    return out


def summary_table(recs):
    rows = [[s["alias"], s["calls"], "%.0f%%" % (s["success_rate"] * 100), s["fallbacks"],
             "%.2e" % s["total_cost_usd"], "%.0f" % s["p50_latency_ms"], s["mock_calls"]]
            for s in summarize(recs)]
    return table([t(k) for k in ("col.alias", "col.calls", "col.success_rate", "col.fallbacks",
                                 "col.total_cost", "col.p50_latency", "col.mock_calls")], rows)


def write_markdown(recs, path):
    """runs/report.md — summary 표를 마크다운으로 저장."""
    import os
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# " + t("report.title") + "\n\n" + summary_table(recs) + "\n\n" + price_note() + "\n")
