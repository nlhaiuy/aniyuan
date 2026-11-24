"""借鉴官方订阅（creamycake-anime/animeko-subs）里的 json-api 写法。

Animeko 的 json-api 数据源必须有 play（取视频地址的请求），缺了就是"配置不完整"。
Kazumi 的接口规则里没有播放接口（只有一个让 WebView 嗅探的网页地址），所以光靠转换补不出 play。
官方订阅里有人工验证过的 json-api 源，同一个接口的源可以直接借鉴它的写法：

  * 匹配条件（通用，不认站点名）：章节接口的地址、方法一致，且剧集 id 的取值路径一致。
    这样才能保证"我们数出来的剧集 id"和"官方 play 请求里用的 id"是同一个东西。
  * 借用：play 整段；同一个接口的请求体（官方的是验证过的，比如 id 要不要带引号）；
    我们缺的剧集序号 / 类型字段（selectSort / selectType / typeMapping / nameTemplate）。
  * 找不到匹配的官方源、也没有 play 时，这个源不输出（输出了也是"配置不完整"，用不了）。
"""
import copy
import glob
import json
import os

from .check.domains import host_of, sld


def load(repo):
    """读 animeko-subs 里 subs/api/ 下所有 json-api 源。"""
    out = []
    for path in sorted(glob.glob(os.path.join(repo, "subs", "api", "**", "*.json"), recursive=True)):
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        sc = (d.get("arguments") or {}).get("searchConfig") or {}
        if d.get("factoryId") == "json-api" and sc.get("play") and sc.get("subject") and sc.get("search"):
            out.append(d)
    return out


def _abs(url, base):
    if url.startswith(("http://", "https://")):
        return url
    return base.rstrip("/") + "/" + url.lstrip("/")


def _same_api(a, b):
    """两个源的章节接口是不是同一个：地址（相对地址按 baseUrl 补全）、方法、剧集 id 取值路径都一致。"""
    ra, rb = a["subject"]["request"], b["subject"]["request"]
    if _abs(ra.get("url", ""), a.get("baseUrl", "")).split("?")[0] != _abs(rb.get("url", ""), b.get("baseUrl", "")).split("?")[0]:
        return False
    if str(ra.get("method", "GET")).upper() != str(rb.get("method", "GET")).upper():
        return False
    return (a["subject"].get("episodes") or {}).get("selectId") == (b["subject"].get("episodes") or {}).get("selectId")


def borrow(source, officials):
    """给缺 play 的 json-api 源借官方的写法；返回说明列表（空 = 没借到）。"""
    sc = (source.get("arguments") or {}).get("searchConfig") or {}
    if source.get("factoryId") != "json-api" or sc.get("play") or not sc.get("subject"):
        return []
    for o in officials:
        osc = o["arguments"]["searchConfig"]
        if not _same_api(sc, osc):
            continue
        notes = ["播放接口（play）借鉴自官方订阅里同一接口的源「%s」" % o["arguments"].get("name", o.get("id", "?"))]
        sc["play"] = copy.deepcopy(osc["play"])
        # 同一个接口的请求体：官方的是人工验证过的（比如 id 要不要带引号）
        for part in ("search", "subject"):
            ours, theirs = sc[part]["request"], osc[part]["request"]
            if _abs(ours.get("url", ""), sc.get("baseUrl", "")).split("?")[0] == _abs(theirs.get("url", ""), osc.get("baseUrl", "")).split("?")[0] \
                    and ours.get("body") != theirs.get("body"):
                ours["body"] = theirs.get("body", "")
                if part == "search" and osc["search"].get("pageSize"):
                    sc["search"]["pageSize"] = osc["search"]["pageSize"]   # 请求体里的 {pageSize} 跟着官方的数
                notes.append("%s请求体改用官方写法" % ("搜索" if part == "search" else "详情"))
        eps, oeps = sc["subject"]["episodes"], osc["subject"]["episodes"]
        if eps.get("selectEpisodes") == oeps.get("selectEpisodes") and not eps.get("selectSort"):
            for k in ("selectSort", "selectType", "typeMapping", "nameTemplate"):
                if oeps.get(k):
                    eps[k] = oeps[k]
            notes.append("剧集序号 / 类型字段借鉴官方")
        return notes
    return []


def apply(cands, officials, final=True):
    """借官方写法。借不到 play 的 json-api 候选标 needs_play（之后可以由 playlearn 从播放页学）；
    final=True（不会再学了）时直接收尾：仍然没有 play 的标成无法转换。"""
    for c in cands:
        src = c.get("source")
        if not src or src.get("factoryId") != "json-api":
            continue
        sc = src["arguments"]["searchConfig"]
        if sc.get("play"):
            continue
        notes = borrow(src, officials)
        if notes:
            c["notes"] = [n for n in c.get("notes", []) if "没有播放接口" not in n and "序号" not in n] + notes
            c["status"] = "partial"
        else:
            c["needs_play"] = True
    if final:
        finalize(cands)
    return cands


def finalize(cands):
    """收尾：到这里还没有 play 的 json-api 候选不输出（输出了 Animeko 也是「配置不完整」）。"""
    for c in cands:
        if not c.get("needs_play") or c.get("source") is None:
            continue
        sc = c["source"]["arguments"]["searchConfig"]
        if sc.get("play"):
            c["needs_play"] = False
            continue
        need_login = any("要求登录" in n for n in c.get("notes", []))
        c["notes"] = [n for n in c.get("notes", []) if "没有播放接口" not in n] + [
            ("json-api 数据源必须有 play（取视频地址的请求）：这个站的播放接口要求登录，匿名取不到视频地址，没法转换"
             if need_login else
             "json-api 数据源必须有 play（取视频地址的请求）：Kazumi 规则里没有，官方订阅里没有同一接口的源，"
             "也没能从播放页学出来，需要手写 play")]
        c["status"] = "unsupported"
        c["source"] = None
        c["needs_play"] = False
        c.pop("smoke", None)


# ---------------------------------------------------------------------------
# 与官方订阅互补
#
# 你同时订阅官方源和自己的源时，同一个站在 Animeko 里会出现两次。官方的是人工验证 + 人工分档的，
# 所以：官方同站源检测通过 → 自有的这条是重复的，降到最低档（或按配置剔除）；
# 官方同站源检测没通过、自有的通过 → 自有的留着补位，保持原档位；没有结论 / 没联网 → 只降档，绝不剔除。
# 站点怎么认：和 check/domains.py 一样，看主域名的“名字部分”（lmm22.com 和 lmm22.net 是同一个站），
# 名字不同但其实是一个站的写进 config.official_aliases（{自有名字: 官方名字}）。
# ---------------------------------------------------------------------------
GENERIC_SLDS = {"", "github", "githubusercontent", "googleusercontent", "gstatic", "cloudflare", "jsdelivr", "unpkg", "gravatar"}
MODES = ("demote", "exclude", "off")


def _urls(source):
    a = source.get("arguments") or {}
    sc = a.get("searchConfig") or {}
    req = (sc.get("search") or {}).get("request") or {}
    # 不看 iconUrl：图标常放在百度云 / GitHub 之类的 CDN 上，按它认站会把不相干的站认成一个（真实数据里出现过）
    return [sc.get("searchUrl"), sc.get("rawBaseUrl"), sc.get("baseUrl"), req.get("url")]


def site_names(source, extra=()):
    """一个源涉及的主域名名字集合（去掉 github 之类的通用域名）。extra：检测时改写域名前的原站点等。"""
    hosts = [host_of(u) for u in _urls(source) if isinstance(u, str) and u.startswith(("http://", "https://"))]
    hosts += [h for h in extra if h]
    return {sld(h) for h in hosts} - GENERIC_SLDS


def load_sites(repo):
    """读 animeko-subs 里 subs/web/ 和 subs/api/ 下全部 web-selector / json-api 源（不要求有 play），
    返回 [{name, tier, source, names, path}]；读不出来的文件跳过。"""
    out = []
    for sub in ("web", "api"):
        for path in sorted(glob.glob(os.path.join(repo, "subs", sub, "**", "*.json"), recursive=True)):
            try:
                with open(path, encoding="utf-8") as f:
                    d = json.load(f)
            except (OSError, ValueError):
                continue
            if not isinstance(d, dict) or d.get("factoryId") not in ("web-selector", "json-api"):
                continue
            a = d.get("arguments") or {}
            tier = a.get("tier")
            out.append({"name": a.get("name") or d.get("id") or os.path.basename(path)[:-5],
                        "tier": tier if isinstance(tier, int) else None,
                        "source": d, "names": site_names(d), "path": os.path.relpath(path, repo)})
    return out


def find_matches(source, sites, aliases=None, extra=()):
    """官方订阅里和这个源是同一个站的条目（可能有多个，比如 girigiri 有两条），档位高的（数字小的）在前。"""
    aliases = aliases or {}
    mine = {aliases.get(n, n) for n in site_names(source, extra)}
    hit = [s for s in sites if mine & s["names"]]
    return sorted(hit, key=lambda s: (99 if s["tier"] is None else s["tier"], s["name"]))


def _verdict(own_status, official_status):
    """返回 (动作, 说明)。动作：redundant（官方已覆盖）/ rescue（官方没通过、自有补位）/ unsure（没结论，只降档）。"""
    if official_status == "ok":
        return "redundant", "官方同站源检测通过"
    if official_status == "fail":
        if own_status == "ok":
            return "rescue", "官方同站源检测没通过（选择器失效），自有源通过，留着补位"
        return "unsure", "官方同站源检测没通过，自有源也没通过"
    if official_status is None:
        return "unsure", "没联网检测官方同站源"
    return "unsure", "官方同站源检测没有结论（%s）" % official_status


def reconcile(chosen, sites, config, check=None):
    """把最终入选的自有源和官方订阅对一遍。
    chosen：入选候选列表（c["source"] 是订阅里的源）；check(official_source) -> {"status": ...}（可选，联网检测官方源用，
    同一个官方源只测一次）；返回报告用的行：[{id, name, official, official_tier, official_status, action, note}]。
    会改动候选：降档的改 source.arguments.tier，剔除的打 c["dropped"] = True。
    config：official_dedupe（demote 默认 / exclude / off）、official_demote_tier（默认 4）、official_aliases。"""
    mode = config.get("official_dedupe", "demote")
    if mode not in MODES:
        raise ValueError("official_dedupe 只能是 %s，现在是 %r" % ("/".join(MODES), mode))
    if mode == "off" or not sites:
        return []
    aliases = config.get("official_aliases") or {}
    lowest = int(config.get("official_demote_tier", 4))
    checked = {}
    rows = []
    for c in chosen:
        src = c["source"]
        a = src["arguments"]
        hits = find_matches(src, sites, aliases, [c.get("orig_site")] if c.get("orig_site") else [])
        if not hits:
            continue
        best = hits[0]
        if check is not None:
            # 同站有多条官方源时，只要有一条通过就算官方覆盖了
            sts = []
            for h in hits:
                if h["path"] not in checked:
                    try:
                        checked[h["path"]] = (check(h["source"]) or {}).get("status")
                    except Exception as e:   # 官方源检测出任何问题都只当没结论，不影响订阅
                        checked[h["path"]] = "error:%s" % type(e).__name__
                sts.append(checked[h["path"]])
            ost = "ok" if "ok" in sts else ("fail" if "fail" in sts else sts[0])
        else:
            ost = None
        own = (c.get("smoke") or {}).get("status")
        action, why = _verdict(own, ost)
        row = {"id": src["id"], "name": a.get("name", src["id"]), "official": "、".join(h["name"] for h in hits),
               "official_tier": best["tier"], "official_status": ost or "-", "action": "keep", "note": why}
        if action == "rescue":
            pass   # 保持原档位
        elif mode == "exclude" and action == "redundant":
            c["dropped"] = True
            row["action"] = "drop"
            c["notes"].append("官方订阅里已有同一个站的源「%s」，已从订阅里剔除（%s）" % (row["official"], why))
        else:
            old = a.get("tier")
            if old is None or old < lowest:
                a["tier"] = lowest
                row["action"] = "demote"
                c["notes"].append("官方订阅里已有同一个站的源「%s」，优先级降到 %d（%s）" % (row["official"], lowest, why))
            else:
                row["note"] += "；本来就在最低档"
        rows.append(row)
    return rows


def report_section(rows, total, mode):
    """报告里的「与官方订阅的重叠」一节（没有重叠也写一句，方便确认功能在工作）。"""
    names = {"drop": "已剔除", "demote": "已降档", "keep": "保持"}
    out = ["", "## 与官方订阅的重叠", "",
           "你同时订阅官方源时，同一个站会出现两次。这次入选的 %d 个源里 **%d 个**和官方订阅重复，**%d 个**是官方没有的（自有独有）。处理方式：`official_dedupe` = `%s`。"
           % (total, len(rows), total - len(rows), mode)]
    if rows:
        out += ["", "| 自有源 | 官方同站源（档位） | 官方检测 | 处理 | 说明 |", "|---|---|---|---|---|"]
        for r in rows:
            tier = "" if r["official_tier"] is None else "（T%d）" % r["official_tier"]
            out.append("| %s | %s%s | %s | %s | %s |" % (r["name"].replace("|", "/"), r["official"].replace("|", "/"), tier,
                                                   r["official_status"], names.get(r["action"], r["action"]), r["note"].replace("|", "/")))
    return out
