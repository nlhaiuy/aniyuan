"""AniBaka 规则（anx-rule/2）-> Animeko 数据源（订阅格式）的转换。

只转“能确定地转”的部分：
  搜索：fetch(GET)+searchList（HTML）、maccmsSuggest / fetch+jsonSeries（JSON 接口）
  章节：episodes（listSelectors / tabSelectors）
  播放：统一交给 Animeko 的 WebView 嗅探（scanDomMediaUrls）
转不了的（POST/JSON 站、磁力站、anime1、jsonEpisodes/maccmsApiEpisodes 等）返回 unsupported，
由 build.py 回退到 baseline/anibaka.json 里同 id 的现成配置。
"""
import re
from urllib.parse import urljoin, urlparse

from convert import MATCH_VIDEO_URL, Result, _origin

# 播放步骤里出现这些 op，说明 AniBaka 是靠站内解密/接口取直链，Animeko 只能靠 WebView 嗅探
PLAY_HARD_OPS = {"crypto", "playerDecrypt", "maccmsVerify", "aesDecrypt"}


def source_id(key):
    return "anibaka-" + key.replace("_", "-")


def _pipeline(rule):
    p = rule.get("pipeline")
    return p if isinstance(p, dict) else rule


def _walk_ops(ops):
    """深度优先遍历 ops（含 first 的各分支）。"""
    for o in ops or []:
        if not isinstance(o, dict):
            continue
        yield o
        for br in o.get("branches") or []:
            yield from _walk_ops(br)


def _branches(ops):
    """把 ops 展开成候选分支列表：顶层是 first 就取它的各个分支，否则整个 ops 是唯一分支。"""
    ops = ops or []
    if len(ops) == 1 and ops[0].get("op") == "first":
        out = []
        for br in ops[0].get("branches") or []:
            out += _branches(br)
        return out
    return [ops]


def split_selectors(s):
    """按顶层逗号切 CSS 选择器（括号、引号、方括号里的逗号不切）。"""
    parts, depth, quote, cur = [], 0, "", []
    for ch in s:
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
            continue
        cur.append(ch)
    parts.append("".join(cur).strip())
    return [p for p in parts if p]


def _last_compound_is_a(sel):
    last = re.split(r"[\s>+~]+", sel.strip())[-1]
    return bool(re.match(r"^a($|[.#\[:])", last))


def _to_link_selector(sel, pattern):
    """把“条目容器选择器”变成“指向 <a> 的选择器”。"""
    href = "[href*='%s']" % pattern.replace("'", "\\'") if pattern else ""
    if _last_compound_is_a(sel):
        return sel + href
    return "%s a%s" % (sel, href)


def _join_urls(origin_base, url):
    return urljoin(origin_base, url)


def _json_path(list_path):
    lp = (list_path or "").strip().strip(".")
    return "$" + ("." + lp if lp else "") + "[*]"


def _is_get(op):
    return str(op.get("method", "GET")).upper() == "GET" and not op.get("body")


def _search_html(branch, base):
    """fetch(GET)+searchList -> (searchUrl, searchConfigPart, notes)。"""
    fetch = next((o for o in branch if o.get("op") == "fetch"), None)
    sl = next((o for o in branch if o.get("op") == "searchList"), None)
    other = [o.get("op") for o in branch if o.get("op") not in ("fetch", "searchList")]
    if not fetch or not sl or other or not _is_get(fetch) or not fetch.get("url"):
        return None
    sels = sl.get("selectors") or []
    if not sels:
        return None
    pattern = sl.get("detailPattern") or ""
    pieces = []
    for s in sels:
        pieces += [_to_link_selector(p, pattern) for p in split_selectors(s)]
    notes = []
    if not pattern and not any("href" in x for x in pieces):
        notes.append("searchList 没有 detailPattern，条目里的所有链接都会被当作结果（已启用 preferShorterName）")
    url = _join_urls(base, fetch["url"])
    return url, {
        "subjectFormatId": "a",
        "selectorSubjectFormatA": {"selectLists": ", ".join(pieces), "preferShorterName": True},
    }, notes


def _json_search(url, list_path, id_key, name_key, link_template, link_key):
    if link_template:
        link_field, tpl = id_key, link_template.replace("{id}", "{value}")
    else:
        link_field, tpl = link_key, ""
    if not link_field or not name_key:
        return None
    cfg = {
        "selectLinks": "%s['%s']" % (_json_path(list_path), link_field),
        "selectNames": "%s['%s']" % (_json_path(list_path), name_key),
        "preferShorterName": True,
    }
    if tpl:
        cfg["linkTemplate"] = tpl
    return url, {"subjectFormatId": "json-path-indexed", "selectorSubjectFormatJsonPathIndexed": cfg}


def _search_json(branch, base, origin):
    ops = [o for o in branch if o.get("op") != "maccmsVerify"]
    notes = []
    if len(ops) != len(branch):
        notes.append("搜索用到 maccmsVerify（站点验证码），Animeko 无法处理，遇到验证时会失败")
    if len(ops) == 1 and ops[0].get("op") == "maccmsSuggest":
        o = ops[0]
        tpl = o.get("detailUrlTemplate")
        if not tpl:
            return None
        url = origin + "/index.php/ajax/suggest?mid=1&wd={keyword}&limit=30"
        r = _json_search(url, "list", "id", "name", tpl, o.get("urlKey"))
        if r:
            notes.append("GUESS:搜索用 MacCMS 的 suggest 接口（%s，路径是按 MacCMS 默认值推的，AniBaka 里没写）" % url)
        return (r + (notes,)) if r else None
    if len(ops) == 2 and ops[0].get("op") == "fetch" and ops[1].get("op") == "jsonSeries":
        f, j = ops
        if not _is_get(f) or not f.get("url"):
            return None
        r = _json_search(_join_urls(base, f["url"]), j.get("listPath"), j.get("idKey"), j.get("nameKey"),
                         j.get("detailUrlTemplate"), j.get("urlKey"))
        return (r + (notes,)) if r else None
    return None


def convert_search(rule_ops, base, origin):
    """在所有候选分支里找第一个可转的；HTML 优先（和现有手写源的做法一致）。"""
    branches = _branches(rule_ops)
    for br in branches:
        r = _search_html(br, base)
        if r:
            return r
    for br in branches:
        r = _search_json(br, base, origin)
        if r:
            return r
    return None


def convert_episodes(detail_ops):
    eps = [o for o in _walk_ops(detail_ops) if o.get("op") == "episodes"]
    lists, tabs = [], []
    for o in eps:
        for s in o.get("listSelectors") or []:
            if s not in lists:
                lists.append(s)
        for s in o.get("tabSelectors") or []:
            if s not in tabs:
                tabs.append(s)
    if not lists:
        return None
    if tabs:
        return {
            "channelFormatId": "index-grouped",
            "selectorChannelFormatFlattened": {
                "selectChannelNames": ", ".join(tabs),
                "selectEpisodeLists": ", ".join(lists),
                "selectEpisodesFromList": "a",
            },
        }
    return {
        "channelFormatId": "no-channel",
        "selectorChannelFormatNoChannel": {
            "selectEpisodes": ", ".join("%s a" % s for s in lists),
            "selectEpisodeLinks": "",
        },
    }


def convert_anx(rule, entry=None, config=None):
    """rule: anx-rule/2 的 JSON；entry: index.json 里对应的条目。返回 Result。"""
    config = config or {}
    entry = entry or {}
    key = entry.get("key") or rule.get("id", "")
    res = Result(rule.get("name") or entry.get("title") or key, str(entry.get("rev", "")))
    res.guess = False   # True：搜索地址是推测出来的（没有现成的 HTML 搜索可用）
    p = _pipeline(rule)
    base = rule.get("baseUrl") or entry.get("site") or ""
    origin = _origin(base)
    if not origin:
        return res.fail("缺少 baseUrl")

    s = convert_search(p.get("search"), base, origin)
    if not s:
        return res.fail("搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等）")
    search_url, sc_part, notes = s
    if "{keyword}" not in search_url:
        return res.fail("搜索地址里没有 {keyword}")
    res.guess = any(n.startswith("GUESS:") for n in notes)
    res.notes += [n.replace("GUESS:", "") for n in notes]

    ch = convert_episodes(p.get("detail"))
    if not ch:
        kinds = sorted({o.get("op") for o in _walk_ops(p.get("detail")) if o.get("op")} - {"follow", "first"})
        return res.fail("章节步骤无法转换（需要 episodes 操作，实际是：%s）" % (", ".join(kinds) or "无"))

    play_ops = {o.get("op") for o in _walk_ops(p.get("play"))}
    hard = sorted(play_ops & PLAY_HARD_OPS)
    if hard:
        res.notes.append("AniBaka 播放步骤用了 %s 取直链；Animeko 只能靠 WebView 嗅探，可能拿不到视频" % "/".join(hard))
    if "sniff" not in play_ops and not hard:
        res.notes.append("AniBaka 播放步骤不是嗅探（%s），已改成 WebView 嗅探，请在 Animeko 里试播确认" %
                         ("/".join(sorted(play_ops - {"follow", "first"})) or "直取"))

    headers = p.get("headers") or rule.get("headers") or {}
    referer = headers.get("Referer") or headers.get("referer") or origin + "/"
    ua = headers.get("User-Agent") or ""
    sc = {
        "searchUrl": search_url,
        "searchUseOnlyFirstWord": True,
        "searchRemoveSpecial": True,
        "searchUseSubjectNamesCount": 1,
        "rawBaseUrl": origin,
        "requestInterval": 3000,
    }
    sc.update(sc_part)
    sc.update(ch)
    if ua:
        sc["userAgent"] = ua
    add_headers = {"referer": referer}
    sc.update({
        "defaultResolution": "1080P",
        "defaultSubtitleLanguage": "CHS",
        "onlySupportsPlayers": [],
        "filterByEpisodeSort": True,
        "filterBySubjectName": True,
        "selectMedia": {"distinguishSubjectName": True, "distinguishChannelName": ch["channelFormatId"] != "no-channel"},
        "matchVideo": {
            "enableNestedUrl": False,
            "matchNestedUrl": "$^",
            "matchVideoUrl": MATCH_VIDEO_URL,
            "cookies": "quality=1080",
            "addHeadersToVideo": add_headers,
            "scanDomMediaUrls": True,
        },
    })

    tier = (config.get("tiers") or {}).get(key, config.get("default_tier", 4))
    desc = (rule.get("description") or entry.get("intro") or "").strip()   # “来源”说明由 build.py 统一生成
    res.source = {
        "id": source_id(key),
        "factoryId": "web-selector",
        "version": 2,
        "arguments": {
            "name": res.name,
            "description": desc,
            "iconUrl": rule.get("iconUrl") or entry.get("badge") or origin + "/favicon.ico",
            "searchConfig": sc,
            "tier": tier,
            "channelTiers": {},
        },
    }
    res.status = "partial" if res.notes else "ok"
    return res


def site_host(source):
    """用于“同一个站”判断：web-selector 取搜索地址的主机名，json-api 取图标地址的主机名
    （接口域名往往和网站域名不同）；去掉 www./m. 前缀。"""
    a = source["arguments"]
    if source.get("factoryId") == "json-api":
        url = a.get("iconUrl") or a.get("searchConfig", {}).get("baseUrl", "")
    else:
        url = a["searchConfig"].get("searchUrl") or a.get("iconUrl", "")
    host = (urlparse(url).netloc or "").lower().split(":")[0]
    return re.sub(r"^(www|m)\.", "", host)
