"""浏览器对比：拿「联网检测没通过」的候选，在每个浏览器上各重测一遍，看哪个浏览器救回得最多。

为什么拿失败的候选来比：换浏览器要救的就是这些——被站点防火墙 / 验证码 / 环境检查拦住的、对 requests 返回不同页面的。
已经通过的候选换什么浏览器都一样，拿它们比没有区分度。

做法：每个浏览器各启动一次，开「浏览器优先」模式（smoke.FORCE_BROWSER：每个页面都由浏览器自己去取，不先用 requests），
对每个失败候选跑一遍和正式检测一样的 check_source（搜索 + 详情），记下结论。
成绩：tested = 测了几个，ok = 救回几个（检测通过）。结果交给 browser_pick 决定日常构建用哪个浏览器。

只比这些结论的候选（默认 blocked / fail）：unreachable（SSL 出错、超时、5xx）是站点自己的问题，换浏览器救不回来，还会白等超时。
"""
import time

from . import smoke as smoke_mod
from .smoke import check_source

DEFAULT_BROWSERS = ("chromium", "chrome", "firefox")
DEFAULT_STATUSES = ("blocked", "fail")


def pick_targets(cands, statuses=DEFAULT_STATUSES, limit=12):
    """要重测的候选：有源、主出口检测没通过、结论在 statuses 里。按站点名去重（同一个站的几个来源只测一个），最多 limit 个。"""
    out, seen = [], set()
    for c in cands:
        if c.get("source") is None:
            continue
        if (c.get("smoke") or {}).get("status") not in statuses:
            continue
        host = c.get("orig_site") or c.get("site") or c.get("key")
        if host in seen:
            continue
        seen.add(host)
        out.append(c)
        if len(out) >= limit:
            break
    return out


def compare(cands, config, proxy, session, browsers=None, make_checker=None, keyword=None):
    """返回 {"targets": [候选名...], "browsers": {浏览器: {"tested": n, "ok": n, "by": {候选名: 结论}, "error": 起不来的原因}}}。
    候选不够（没有失败的）时 targets 为空，不启动任何浏览器。make_checker(proxy, name) 默认是 PlayChecker，测试里换成假的。"""
    names = [b for b in (browsers or config.get("browser_compare_browsers") or DEFAULT_BROWSERS)]
    targets = pick_targets(cands, tuple(config.get("browser_compare_statuses") or DEFAULT_STATUSES), int(config.get("browser_compare_max", 12)))
    out = {"targets": ["%s:%s" % (c.get("origin"), c.get("key")) for c in targets], "browsers": {}}
    if not targets:
        return out
    if make_checker is None:
        from .playcheck import PlayChecker
        make_checker = PlayChecker
    keyword = keyword or config.get("smoke_keyword", "葬送的芙莉莲")
    prev_fetcher, prev_force = smoke_mod.FETCHER, smoke_mod.FORCE_BROWSER
    try:
        for name in names:
            row = {"tested": 0, "ok": 0, "by": {}}
            out["browsers"][name] = row
            try:
                pc = make_checker(proxy, name)
            except Exception as e:   # 没装 / 起不来：记下原因，不参与比较
                row["error"] = (str(e).strip().splitlines() or [type(e).__name__])[0][:100]
                continue
            try:
                smoke_mod.set_browser_fetcher(pc.fetch)
                smoke_mod.set_force_browser(True)
                for c, label in zip(targets, out["targets"]):
                    try:
                        r = check_source(c["source"], keyword, session=session)
                        status = r.get("status", "fail")
                    except Exception as e:   # 一个候选出错不影响别的
                        status = "error:%s" % type(e).__name__
                    row["by"][label] = status
                    row["tested"] += 1
                    row["ok"] += 1 if status == "ok" else 0
                    time.sleep(config.get("browser_compare_wait", 0.5))
            finally:
                smoke_mod.set_force_browser(False)
                smoke_mod.set_browser_fetcher(prev_fetcher)
                pc.close()
    finally:
        smoke_mod.set_browser_fetcher(prev_fetcher)
        smoke_mod.set_force_browser(prev_force)
    return out


def to_scores(result):
    """转成 browser_pick.decide 要的成绩格式：{浏览器: {"sites": 测了几个, "ok": 救回几个, "media": 救回几个}}；起不来的、没测的不出现。"""
    return {b: {"sites": r["tested"], "ok": r["ok"], "media": r["ok"]}
            for b, r in (result.get("browsers") or {}).items() if r.get("tested")}


def summary_lines(result):
    """报告里的一小节：每个浏览器救回几个，哪些候选只有某个浏览器救得回来。"""
    bs = result.get("browsers") or {}
    if not result.get("targets") or not bs:
        return []
    lines = ["## 浏览器对比（拿联网检测没通过的候选，每个浏览器各重测一遍）", "",
             "重测了 %d 个：%s" % (len(result["targets"]), "、".join(result["targets"])), "",
             "| 浏览器 | 救回（检测通过） | 测了 | 说明 |", "|---|---|---|---|"]
    for b, r in bs.items():
        lines.append("| %s | %s | %s | %s |" % (b, r["ok"] if r.get("tested") else "-", r.get("tested", 0), r.get("error", "")))
    only = []
    for label in result["targets"]:
        ok = [b for b, r in bs.items() if r.get("by", {}).get(label) == "ok"]
        if ok and len(ok) < len([b for b, r in bs.items() if r.get("tested")]):
            only.append("%s 只有 %s 通过" % (label, "、".join(ok)))
    if only:
        lines += ["", "只有部分浏览器救得回来：" + "；".join(only)]
    return lines + [""]
