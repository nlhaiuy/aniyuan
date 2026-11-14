"""冒烟测试：真正请求站点，验证「搜得到 → 进得去详情页 → 剧集选择器有结果」。

只验证到剧集列表；能不能播放由 playcheck.py 用无头浏览器另行检测。
GitHub Actions 的服务器在海外，部分国内站点可能访问不了，
这种情况会标成 unreachable（不是配置错误），默认不会被剔除。
"""
import re
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from . import ua as ua_mod

BLOCK_WORDS = ["验证码", "安全验证", "检查环境", "请输入验证", "Just a moment", "cf-challenge", "人机验证"]


FETCHER = None   # 可选：requests 被 403/503 拦时，改用无头浏览器取页面（见 playcheck.BrowserFetcher）


def set_browser_fetcher(fn):
    global FETCHER
    FETCHER = fn


class _BrowserResp:
    def __init__(self, status, text, url, moved):
        self.status_code, self.text, self.url = status, text, url
        self.history = ["redirect"] if moved else []

    def json(self):
        import json
        return json.loads(self.text)


def _get(url, session, timeout, ua=None):
    """ua：源自己在 searchConfig.userAgent 里指定的 UA（Animeko 就是用它请求的），空则用统一 UA（见 ua.py）。"""
    r = session.get(url, headers=ua_mod.request_headers(ua), timeout=timeout, allow_redirects=True)
    if r.status_code in (403, 503) and FETCHER:
        try:
            got = FETCHER(url, ua=ua)
        except Exception:
            got = None
        if got and got[0] == 200 and not _blocked(got[1]):
            return _BrowserResp(got[0], got[1], got[2], _host(got[2]) != _host(url))
    return r


def _blocked(text):
    head = text[:6000]
    return any(w in head for w in BLOCK_WORDS)


def eval_simple_jsonpath(data, path):
    """只支持本工具生成的形式：$.a.b[*]['field'] 或 $[*]['field'] 或 $.a.b[*]。"""
    m = re.match(r"^\$((?:\.[\w]+)*)(\[\*\])?(?:\['(\w+)'\]|\.(\w+))?$", path)
    if not m:
        raise ValueError("不支持的 JSONPath: " + path)
    cur = data
    for key in [k for k in m.group(1).split(".") if k]:
        cur = cur.get(key) if isinstance(cur, dict) else None
        if cur is None:
            return []
    items = cur if m.group(2) and isinstance(cur, list) else [cur]
    field = m.group(3) or m.group(4)
    if field:
        items = [i.get(field) for i in items if isinstance(i, dict)]
    return [i for i in items if i is not None]


def _host(url):
    return re.sub(r"^(www|m)\.", "", (urlparse(url).netloc or "").lower())


def _search_subjects(sc, keyword, session, timeout, ctx=None, ua=None):
    """返回 (subjects[(name, url)], reason|None)；reason 非空表示没成功。"""
    ctx = ctx if ctx is not None else {}
    url = sc["searchUrl"].replace("{keyword}", quote(keyword))
    ctx["search_url"] = url
    try:
        r = _get(url, session, timeout, ua)
    except requests.RequestException as e:
        return [], ("unreachable", "请求失败：%s" % type(e).__name__)
    ctx["search_html"], ctx["search_final_url"] = r.text, r.url
    if r.history and _host(r.url) != _host(url):
        p = urlparse(r.url)
        ctx["final_origin"] = "%s://%s" % (p.scheme, p.netloc)
    if r.status_code != 200:
        return [], ("blocked" if r.status_code in (403, 429, 503) else "fail", "HTTP %d" % r.status_code)
    fmt = sc.get("subjectFormatId")
    if fmt == "json-path-indexed":
        try:
            data = r.json()
        except ValueError:
            return [], ("blocked" if _blocked(r.text) else "fail", "返回的不是 JSON")
        jp = sc["selectorSubjectFormatJsonPathIndexed"]
        try:
            ids = eval_simple_jsonpath(data, jp["selectLinks"])
            names = eval_simple_jsonpath(data, jp["selectNames"])
        except ValueError as e:
            return [], ("fail", str(e))
        tpl = jp.get("linkTemplate") or "{value}"
        base = sc.get("rawBaseUrl") or url   # 相对链接按 rawBaseUrl 补全（接口域名常常不是网站域名）
        return [(str(n), urljoin(base, tpl.replace("{value}", str(i)))) for n, i in zip(names, ids)], None
    if _blocked(r.text):
        return [], ("blocked", "搜索页出现验证码/环境检查")
    soup = BeautifulSoup(r.text, "lxml")
    if fmt == "a":
        els = soup.select(sc["selectorSubjectFormatA"]["selectLists"])
        subs = [(e.get_text(" ", strip=True), urljoin(url, e.get("href", ""))) for e in els]
    elif fmt == "indexed":
        ix = sc["selectorSubjectFormatIndexed"]
        names, links = soup.select(ix["selectNames"]), soup.select(ix["selectLinks"])
        subs = [(n.get_text(" ", strip=True), urljoin(url, l.get("href", ""))) for n, l in zip(names, links)]
    else:
        return [], ("skipped", "暂不检测的搜索格式 %s" % fmt)
    return subs, None


def _text_or_title(e):
    return e.get_text(" ", strip=True) or (e.get("title") or "").strip()


def extract_episodes(sc, html, base_url):
    """按源的章节配置从详情页取剧集 [(名称, 链接)]。支持 no-channel 和 index-grouped。"""
    soup = BeautifulSoup(html, "lxml")
    out, seen = [], set()

    def add(el, link_sel):
        link = (el.select_one(link_sel) if link_sel else el)
        href = (link.get("href") or "").strip() if link is not None else ""
        if not href or href.startswith(("javascript", "#")):
            return
        url = urljoin(base_url, href)
        if url not in seen:
            seen.add(url)
            out.append((_text_or_title(el), url))

    if sc.get("channelFormatId") == "index-grouped":
        fl = sc.get("selectorChannelFormatFlattened") or {}
        if not fl.get("selectEpisodeLists"):
            return out
        for lst in soup.select(fl["selectEpisodeLists"]):
            for el in lst.select(fl.get("selectEpisodesFromList") or "a"):
                add(el, fl.get("selectEpisodeLinksFromList"))
    else:
        nc = sc.get("selectorChannelFormatNoChannel") or {}
        if nc.get("selectEpisodes"):
            for el in soup.select(nc["selectEpisodes"]):
                add(el, nc.get("selectEpisodeLinks"))
    return out


def check_source(source, keyword="葬送的芙莉莲", timeout=15, session=None, ctx=None):
    """返回 dict(status, reason, ...)。status: ok / fail / blocked / unreachable / skipped。

    ok 时附带 episode_count / episode_url（第一集链接，供播放检测用）；
    搜索请求被跳转到别的域名且之后一切正常时附带 final_origin。
    ctx（可选）会被填入页面内容，供 repair.py 使用。"""
    session = session or requests.Session()
    ctx = ctx if ctx is not None else {}
    a = source["arguments"]
    sc = a.get("searchConfig", {})
    if source.get("factoryId") == "json-api" and isinstance(sc.get("search"), dict) and isinstance(sc.get("subject"), dict):
        return check_json_api(sc, keyword, session, timeout)
    if source.get("factoryId") != "web-selector" or "searchUrl" not in sc:
        return {"status": "skipped", "reason": "手写配置，不做自动检测"}
    ua = sc.get("userAgent") or None
    subs, bad = _search_subjects(sc, keyword, session, timeout, ctx, ua)
    ctx["subs"] = subs
    if bad:
        return {"status": bad[0], "reason": bad[1]}
    if not subs:
        return {"status": "fail", "reason": "搜索页能打开，但选择器没有选中任何结果", "stage": "search"}
    first = [x for x in subs if keyword[:3] in x[0]] or subs
    picks = (first + [x for x in subs if x not in first])[:3]   # 第一个条目的详情页打不开时，再试后面两个
    if not (sc.get("selectorChannelFormatNoChannel") or {}).get("selectEpisodes") \
            and not (sc.get("selectorChannelFormatFlattened") or {}).get("selectEpisodeLists"):
        return {"status": "skipped", "reason": "没有章节选择器，只验证了搜索"}
    jp = sc.get("selectorSubjectFormatJsonPathIndexed")
    # 条目链接模板不确定时，依次尝试几种写法
    variants = [None]
    if jp and source.get("_template_guess"):
        base = jp["linkTemplate"].rsplit("/", 1)[0]
        variants = [base + "/{value}.html", base + "/{value}", base + "/{value}/"]
    last = ""
    for pick in picks:
        for tpl in variants:
            url = pick[1]
            if tpl:
                id_val = _extract_id(sc, keyword, session, timeout, pick[0], ua)
                if id_val is None:
                    break
                url = urljoin(sc.get("rawBaseUrl") or sc["searchUrl"], tpl.replace("{value}", str(id_val)))
            ctx["detail_url"] = url
            try:
                r = _get(url, session, timeout, ua)
            except requests.RequestException as e:
                last = "详情页请求失败：%s" % type(e).__name__
                continue
            if r.status_code != 200:
                last = "详情页 HTTP %d（%s）" % (r.status_code, url)
                continue
            if _blocked(r.text):
                return {"status": "blocked", "reason": "详情页出现验证码/环境检查"}
            ctx["detail_html"] = r.text
            eps = extract_episodes(sc, r.text, r.url)
            if eps:
                res = {"status": "ok", "reason": "搜到 %d 个条目，详情页选出 %d 个剧集链接" % (len(subs), len(eps)),
                       "episode_count": len(eps), "episode_url": eps[0][1]}
                if tpl:
                    res["template"] = tpl
                if ctx.get("final_origin"):
                    res["final_origin"] = ctx["final_origin"]
                return res
            last = "详情页选择器没有选中剧集（%s）" % url
            ctx["stage"] = "episodes"
    return {"status": "fail", "reason": last or "详情页没有找到剧集", "stage": "episodes"}


def _extract_id(sc, keyword, session, timeout, name, ua=None):
    url = sc["searchUrl"].replace("{keyword}", quote(keyword))
    try:
        data = _get(url, session, timeout, ua).json()
        jp = sc["selectorSubjectFormatJsonPathIndexed"]
        ids = eval_simple_jsonpath(data, jp["selectLinks"])
        names = eval_simple_jsonpath(data, jp["selectNames"])
        for n, i in zip(names, ids):
            if str(n) == name:
                return i
        return ids[0] if ids else None
    except Exception:
        return None


# ---------------------------- json-api 数据源 ----------------------------

def _header_dict(text):
    out = {}
    for line in (text or "").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            if k.strip():
                out[k.strip()] = v.strip()
    return out


def _api_call(session, sc, req, repl, timeout, body_override=None):
    """按 json-api 的 request（url / method / body / headers）发请求。repl：{keyword}/{id}/{page}/{pageSize} 的值。
    url 里的值做 URL 编码；body 是 JSON 文本，字符串值做 JSON 转义，数字原样写进去。"""
    import json
    from urllib.parse import quote as q
    url, body = req.get("url", ""), req.get("body", "") if body_override is None else body_override
    for k, v in repl.items():
        url = url.replace("{%s}" % k, q(str(v), safe=""))
        body = body.replace("{%s}" % k, json.dumps(v)[1:-1] if isinstance(v, str) else str(v))
    if not re.match(r"^https?://", url):
        url = urljoin(sc.get("baseUrl", "") + "/", url.lstrip("/"))
    headers = dict(ua_mod.request_headers(None))
    headers.update(_header_dict(sc.get("headers")))
    headers.update(_header_dict(req.get("headers")))
    if str(req.get("method", "GET")).upper() == "POST":
        headers.setdefault("Content-Type", "application/json")
        return session.post(url, data=body.encode("utf-8"), headers=headers, timeout=timeout)
    return session.get(url, headers=headers, timeout=timeout)


def _api_json(r):
    """返回 (data, bad)；bad 是 (status, reason) 或 None。"""
    if r.status_code != 200:
        return None, ("blocked" if r.status_code in (403, 429, 503) else "fail", "HTTP %d" % r.status_code)
    try:
        return r.json(), None
    except ValueError:
        return None, ("blocked" if _blocked(r.text) else "fail", "返回的不是 JSON")


def _api_episodes(sc, data):
    """详情接口响应里的剧集：[(线路名, 剧集 id, 剧集名)]。"""
    sub = sc["subject"]
    ep = sub["episodes"]
    out = []
    if sub.get("channelFormatId") == "grouped":
        g = sub["channelFormatGrouped"]
        groups = []
        for chan in eval_simple_jsonpath(data, g["selectChannels"]):
            name = eval_simple_jsonpath(chan, g["selectChannelName"]) if g.get("selectChannelName") else []
            groups.append((str(name[0]) if name else "", chan))
    else:
        groups = [("", data)]
    for name, scope in groups:
        for e in eval_simple_jsonpath(scope, ep["selectEpisodes"]):
            ids = eval_simple_jsonpath(e, ep["selectId"]) if ep.get("selectId") else []
            names = eval_simple_jsonpath(e, ep["selectName"]) if ep.get("selectName") else []
            out.append((name, ids[0] if ids else None, str(names[0]) if names else ""))
    return out


def _count_api_episodes(sc, data):
    return len(_api_episodes(sc, data))


def _api_sample(sc, subject_id, data):
    """给「学 play」用的样本：条目 id、线路名、前几集的 id / 名称 / 播放页地址（优先同一条线路里的）。"""
    tpl = sc["subject"]["episodes"].get("episodeUrlTemplate", "")
    eps = [e for e in _api_episodes(sc, data) if e[1] is not None]
    if not eps:
        return {}
    first = [e for e in eps if e[0] == eps[0][0]]
    picked, seen = [], set()
    for chan, eid, name in first + eps:
        if str(eid) in seen:
            continue
        seen.add(str(eid))
        url = tpl.replace("{subjectId}", str(subject_id)).replace("{id}", str(eid))
        if url and not re.match(r"^https?://", url):
            url = urljoin(sc.get("baseUrl", "") + "/", url.lstrip("/"))
        picked.append({"id": eid, "name": name, "channel": chan, "url": url})
        if len(picked) == 3:
            break
    return {"subject_id": subject_id, "channels": list(dict.fromkeys(e[0] for e in eps if e[0])), "episodes": picked}


def check_json_api(sc, keyword, session, timeout=15):
    """json-api 数据源：搜索接口 -> 条目详情接口 -> 数出剧集。不做播放检测（Kazumi 规则里没有播放接口）。
    章节请求体里的 id 带引号被接口拒绝（4xx）时，自动试不带引号的写法，通过了就把修正后的 body 放在结果里（subject_body）。"""
    search, sub = sc["search"], sc["subject"]
    size = search.get("pageSize") or 24
    try:
        r = _api_call(session, sc, search["request"], {"keyword": keyword, "page": 1, "pageSize": size}, timeout)
    except requests.RequestException as e:
        return {"status": "unreachable", "reason": "请求失败：%s" % type(e).__name__}
    data, bad = _api_json(r)
    if bad:
        return {"status": bad[0], "reason": "搜索接口：" + bad[1]}
    try:   # selectName / selectId 是相对每个条目的路径
        ids, names = [], []
        for item in eval_simple_jsonpath(data, search["selectItems"]):
            i, n = eval_simple_jsonpath(item, search["selectId"]), eval_simple_jsonpath(item, search["selectName"])
            if i and n:
                ids.append(i[0]); names.append(n[0])
    except ValueError as e:
        return {"status": "fail", "reason": str(e)}
    if not ids:
        return {"status": "fail", "reason": "搜索接口能打开，但选择路径没有选中结果", "stage": "search"}
    order = [i for i, n in enumerate(names) if keyword[:3] in str(n)] or [0]
    picks = (order + [i for i in range(len(ids)) if i not in order])[:3]
    last = ""
    for i in picks:
        sid = ids[i]
        bodies = [None]
        body = sub["request"].get("body", "")
        if isinstance(sid, int) and '"{id}"' in body:
            bodies.append(body.replace('"{id}"', "{id}"))
        for variant in bodies:
            try:
                r = _api_call(session, sc, sub["request"], {"id": sid}, timeout, body_override=variant)
            except requests.RequestException as e:
                last = "详情接口请求失败：%s" % type(e).__name__
                continue
            data, bad = _api_json(r)
            if bad:
                last = "详情接口：" + bad[1]
                if bad[0] == "blocked":
                    return {"status": "blocked", "reason": last}
                continue
            try:
                n = _count_api_episodes(sc, data)
            except ValueError as e:
                return {"status": "fail", "reason": str(e)}
            if n:
                res = {"status": "ok", "reason": "搜到 %d 个条目，详情接口选出 %d 个剧集" % (len(ids), n),
                       "episode_count": n, "sample": _api_sample(sc, sid, data)}
                if variant is not None:
                    res["subject_body"] = variant
                return res
            last = "详情接口能打开，但选择路径没有选中剧集"
    return {"status": "fail", "reason": last or "详情接口没有返回剧集", "stage": "episodes"}
