"""报告里给人看的部分：总览、需要关注、订阅里每个源的现状；调试明细折叠起来。

entries 是写进订阅的 [(候选 c, 最终的 source)]，所有数字都以它为准（被移出 / 剔除的源不算在内）。
"""
from .check.health import abroad_ok, confirmed_fail


def cell(text):
    return str(text).replace("|", "/").replace("\n", " ")


def play_state(c):
    """这个源现在能不能播，如实区分“这次实测到的”和“按以前的成绩算的”。返回 (类别, 说明)。"""
    sm, h = c.get("smoke") or {}, c.get("health") or {}
    st = sm.get("status")
    if st is None:
        return "untested", "没做联网检测"
    if st == "ok":
        if sm.get("play_raw") == "none":
            return "assumed", "这次没抓到视频，以前能播（宽限中）"
        if sm.get("play") == "ok":
            return "verified", "✅ 实测能播"
        why = {"none": "没抓到视频地址", "blocked": "播放页有验证码 / 被拦", "mismatch": "认不出视频地址"}.get(sm.get("play"), "播放没测成")
        return "unsure", "❓ 能搜到、能出剧集，%s" % why
    if abroad_ok(c):
        return "assumed", "国内出口没通过，海外直连通过"
    if confirmed_fail(c):
        return "failed", "❌ 检测失败"
    if h.get("grace"):
        return "assumed", "这次检测失败，以前通过过（宽限中）"
    why = {"blocked": "被拦", "unreachable": "打不开"}.get(st, "没结论（%s）" % st)
    if h.get("carry") and h.get("play") == "ok":
        return "assumed", "这次%s，%s 天前实测能播" % (why, h.get("carry_age"))
    return "unknown", "❔ 这次%s，没有近期的通过记录" % why


def line_state(c, source):
    sc = (source.get("arguments") or {}).get("searchConfig") or {}
    if source.get("factoryId") != "web-selector":
        return "-"
    if sc.get("channelFormatId") != "index-grouped":
        return "合并"
    total, tested = len(c.get("lines") or []), c.get("line_play") or {}
    if tested:
        good = sum(1 for v in tested.values() if v == "ok")
        return "%d/%d 能播%s" % (good, len(tested), "（共 %d 条）" % total if total > len(tested) else "")
    if total == 1:
        return "1 条"
    return "%d 条（未试播）" % total if total else "分线路"


def _name(source):
    return (source.get("arguments") or {}).get("name") or source.get("id", "?")


def overview(entries, pruned, official_rows, ua_audit, smoked):
    if not smoked:
        return []
    kinds = [play_state(c)[0] for c, _ in entries]
    grouped = [line_state(c, s) for c, s in entries if s.get("factoryId") == "web-selector"]
    ids = {s["id"] for _, s in entries}
    rows = [("订阅里的源", len(entries)),
            ("这次实测能播", kinds.count("verified")),
            ("按以前的成绩 / 海外结果算能用", kinds.count("assumed")),
            ("能打开但播放没确认", kinds.count("unsure")),
            ("这次看不到、也没有近期记录", kinds.count("unknown")),
            ("检测失败", kinds.count("failed")),
            ("网页源里分了线路的", "%d / %d" % (sum(1 for g in grouped if g != "合并"), len(grouped))),
            ("和官方订阅重复", sum(1 for r in official_rows if r["id"] in ids)),
            ("长期失效、已移出", len(pruned))]
    out = ["", "## 总览", "", "| 项目 | 数量 |", "|---|---|"] + ["| %s | %s |" % r for r in rows]
    if ua_audit:
        bad = [n for n, ok, _ in ua_audit if not ok]
        out += ["", ("⚠️ UA 体检未通过：%s（见文末明细）" % "、".join(bad)) if bad else "UA 体检全部通过。"]
    return out


ATTENTION = [("failed", "检测失败，还留在订阅里"), ("unsure", "能打开但播放没确认"), ("unknown", "这次看不到、也没有近期的通过记录")]


def attention(entries, smoked):
    if not smoked:
        return []
    out = []
    for kind, title in ATTENTION:
        names = [_name(s) for c, s in entries if play_state(c)[0] == kind]
        if names:
            out.append("- **%s（%d）**：%s" % (title, len(names), "、".join(names)))
    grace = ["%s（连续失败 %d 次）" % (_name(s), c["health"].get("fails", 0))
             for c, s in entries if (c.get("health") or {}).get("grace")]
    if grace:
        out.append("- **失败宽限中，再失败会降档（%d）**：%s" % (len(grace), "、".join(grace)))
    return ["", "## 需要关注", ""] + (out or ["没有需要处理的源。"])


def source_table(entries, official_rows, smoked):
    overlap = {r["id"]: r["official"] for r in official_rows}
    out = ["", "## 订阅里的源", "", "按档位排序（数字越小，Animeko 越优先）。", "",
           "| 源 | 档位 | 现状 | 线路 | 官方同站源 |", "|---|---|---|---|---|"]
    for c, s in sorted(entries, key=lambda e: ((e[1]["arguments"].get("tier") is None, e[1]["arguments"].get("tier") or 0), _name(e[1]).lower())):
        tier = s["arguments"].get("tier")
        out.append("| %s | %s | %s | %s | %s |" % (
            cell(_name(s)), "-" if tier is None else tier, cell(play_state(c)[1]) if smoked else "-",
            line_state(c, s), cell(overlap.get(s["id"], ""))))
    return out


def fold(section):
    """把一节（["", "## 标题", "", 正文…]）的正文折叠起来。标题留在外面，目录里还能看到。"""
    if len(section) < 3:
        return section
    body = section[2:]
    while body and body[0] == "":
        body = body[1:]
    return section[:2] + ["", "<details><summary>展开查看</summary>", ""] + body + ["", "</details>"]
