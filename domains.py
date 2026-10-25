"""跟随上游域名：手动/基线/手写这类“静态”的源，域名换了不会自己更新。

做法：同一个站的“活”上游（Kazumi / AniBaka / 纯纯看番的规则，社区会随域名变化更新）
如果多数已经换到另一个主域名（比如 girigirilove.com -> girigirilove.xyz），
就把静态源里的旧主域名整体换掉（保留 ani. / m3u8. / bg. 这些子域名前缀），
**重新联网检测通过才采用**，没通过就保持原样并在报告里提示。

站点怎么认：看主域名里的“名字部分”（girigirilove），与后缀（.com/.xyz）无关。
"""
import json
import re
from collections import Counter
from urllib.parse import urlparse

SECOND_LEVEL = {"com", "net", "org", "co", "gov", "edu", "ac"}


def host_of(url):
    return (urlparse(url).netloc or "").lower().split(":")[0]


def registrable(host):
    """主域名：example.com / example.co.jp（没引入公共后缀库，用常见规则估计）。"""
    parts = [p for p in host.split(".") if p]
    if len(parts) <= 2:
        return ".".join(parts)
    if len(parts[-1]) == 2 and parts[-2] in SECOND_LEVEL:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def sld(host):
    """主域名的名字部分：girigirilove.com -> girigirilove。"""
    reg = registrable(host)
    return reg.split(".")[0] if reg else ""


def source_hosts(source):
    a = source["arguments"]
    sc = a.get("searchConfig", {})
    urls = [sc.get("searchUrl", ""), sc.get("rawBaseUrl", ""), a.get("iconUrl", ""),
            (sc.get("matchVideo") or {}).get("addHeadersToVideo", {}).get("referer", "")]
    return [h for h in (host_of(u) for u in urls) if h]


def rewrite_domain(source, old_reg, new_reg):
    """把 …old_reg 整体换成 …new_reg，保留子域名前缀。"""
    pat = re.compile(r"(?<=[/.])" + re.escape(old_reg) + r"(?![A-Za-z0-9-]|\.[A-Za-z])")
    return json.loads(pat.sub(new_reg, json.dumps(source, ensure_ascii=False)))


def is_static(c):
    return c["origin"] in ("manual", "baseline") or c.get("status") == "override"


def current_domains(cands):
    """{名字: 主域名}：各活上游规则（每条规则每个主域名算一票）投票；票数相同取最近改动过的那条规则用的。"""
    votes = {}
    for c in cands:
        for reg in {registrable(h) for h in c.get("live_hosts") or [] if h}:
            votes.setdefault(sld(reg), Counter())[reg] += 1
    out = {}
    for name, cnt in votes.items():
        top = max(cnt.values())
        tied = [r for r, n in cnt.items() if n == top]
        if len(tied) == 1:
            out[name] = tied[0]
        else:
            newest = max(((c.get("date") or 0, reg) for c in cands
                          for reg in {registrable(h) for h in c.get("live_hosts") or [] if h} if reg in tied))
            out[name] = newest[1]
    return out


def follow_upstream(cands, check):
    """check(source) -> 冒烟结果 dict。返回做过的改动说明列表。"""
    cur = current_domains(cands)
    changes = []
    for c in cands:
        if c["source"] is None or not is_static(c):
            continue
        for host in sorted(set(source_hosts(c["source"]))):
            reg, name = registrable(host), sld(host)
            new = cur.get(name)
            if not new or new == reg:
                continue
            trial = rewrite_domain(c["source"], reg, new)
            r = check(trial)
            if r.get("status") == "ok":
                c["source"] = trial
                c["notes"].append("上游已换主域名 %s → %s，已跟随（重新检测通过）" % (reg, new))
                c["smoke"] = r
                changes.append((c["key"], reg, new, True))
            else:
                c["notes"].append("上游已换主域名 %s → %s，但换过去检测没通过（%s），保持原样" % (
                    reg, new, r.get("reason", r.get("status"))))
                changes.append((c["key"], reg, new, False))
            break
    return changes
