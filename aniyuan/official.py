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


def apply(cands, officials):
    """借官方写法；仍然没有 play 的 json-api 候选标成无法转换（输出了也是配置不完整）。"""
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
            c["notes"] = [n for n in c.get("notes", []) if "没有播放接口" not in n] + [
                "json-api 数据源必须有 play（取视频地址的请求），Kazumi 规则里没有，官方订阅里也没有同一接口的源可借鉴，需要手写 play"]
            c["status"] = "unsupported"
            c["source"] = None
    return cands
