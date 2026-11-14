"""和上一次发布的订阅比，这次变了什么：新增 / 移除 / 档位变化 / 换域名。写进报告，也生成提交说明里的一句话。"""
from urllib.parse import urlparse

LIMIT = 40   # 每类最多列几条，免得报告被一次大变动淹没


def _sc(s):
    return (s.get("arguments") or {}).get("searchConfig") or {}


def host_of(s):
    sc = _sc(s)
    url = sc.get("searchUrl") or sc.get("baseUrl") or (((sc.get("search") or {}).get("request") or {}).get("url")) or ""
    return urlparse(url).hostname or ""


def _name(s):
    return (s.get("arguments") or {}).get("name") or s.get("id", "?")


def diff(old, new):
    o, n = {s["id"]: s for s in old}, {s["id"]: s for s in new}
    out = {"added": [], "removed": [], "tier": [], "host": [], "kind": []}
    for i, s in n.items():
        if i not in o:
            out["added"].append((i, _name(s), host_of(s)))
            continue
        p = o[i]
        ta, tb = (p.get("arguments") or {}).get("tier"), (s.get("arguments") or {}).get("tier")
        if ta != tb:
            out["tier"].append((i, _name(s), ta, tb))
        ha, hb = host_of(p), host_of(s)
        if ha and hb and ha != hb:
            out["host"].append((i, _name(s), ha, hb))
        if p.get("factoryId") != s.get("factoryId"):
            out["kind"].append((i, _name(s), p.get("factoryId"), s.get("factoryId")))
    for i, s in o.items():
        if i not in n:
            out["removed"].append((i, _name(s), host_of(s)))
    return out


def is_empty(d):
    return not any(d.values())


def summary(d, total):
    if is_empty(d):
        return "订阅没有变化，共 %d 个源" % total
    parts = [("新增", "added"), ("移除", "removed"), ("档位变化", "tier"), ("换域名", "host"), ("换类型", "kind")]
    return "、".join("%s %d" % (label, len(d[k])) for label, k in parts if d[k]) + "；共 %d 个源" % total


def section(d):
    """报告里的「本次变化」。"""
    if is_empty(d):
        return ["", "## 本次变化", "", "和上次发布的订阅相比没有变化。"]
    rep = ["", "## 本次变化", ""]

    def block(title, rows, fmt):
        if not rows:
            return
        rep.append("**%s（%d）**" % (title, len(rows)))
        rep.append("")
        rep.extend("- " + fmt(r) for r in rows[:LIMIT])
        if len(rows) > LIMIT:
            rep.append("- …… 还有 %d 条" % (len(rows) - LIMIT))
        rep.append("")

    block("新增", d["added"], lambda r: "%s（%s，%s）" % (r[1], r[0], r[2] or "-"))
    block("移除", d["removed"], lambda r: "%s（%s，%s）" % (r[1], r[0], r[2] or "-"))
    block("档位变化", d["tier"], lambda r: "%s：%s → %s" % (r[1], r[2], r[3]))
    block("换域名", d["host"], lambda r: "%s：%s → %s" % (r[1], r[2], r[3]))
    block("换类型", d["kind"], lambda r: "%s：%s → %s" % (r[1], r[2], r[3]))
    while rep and rep[-1] == "":
        rep.pop()
    return rep
