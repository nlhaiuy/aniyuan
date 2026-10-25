"""冒烟测试：真正请求站点，验证「搜得到 → 进得去详情页 → 剧集选择器有结果」。

只验证到剧集列表；能不能播放由 playcheck.py 用无头浏览器另行检测。
GitHub Actions 的服务器在海外，部分国内站点可能访问不了，
这种情况会标成 unreachable（不是配置错误），默认不会被剔除。
"""
import re
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BLOCK_WORDS = ["验证码", "安全验证", "检查环境", "请输入验证", "Just a moment", "cf-challenge", "人机验证"]
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
           "Accept-Language": "zh-CN,zh;q=0.9"}


def _get(url, session, timeout):
    return session.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)


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


def _search_subjects(sc, keyword, session, timeout, ctx=None):
    """返回 (subjects[(name, url)], reason|None)；reason 非空表示没成功。"""
    ctx = ctx if ctx is not None else {}
    url = sc["searchUrl"].replace("{keyword}", quote(keyword))
    ctx["search_url"] = url
    try:
        r = _get(url, session, timeout)
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
    if source.get("factoryId") != "web-selector" or "searchUrl" not in sc:
        return {"status": "skipped", "reason": "手写配置，不做自动检测"}
    subs, bad = _search_subjects(sc, keyword, session, timeout, ctx)
    ctx["subs"] = subs
    if bad:
        return {"status": bad[0], "reason": bad[1]}
    if not subs:
        return {"status": "fail", "reason": "搜索页能打开，但选择器没有选中任何结果", "stage": "search"}
    pick = next((s for s in subs if keyword[:3] in s[0]), subs[0])
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
    for tpl in variants:
        url = pick[1]
        if tpl:
            id_val = _extract_id(sc, keyword, session, timeout, pick[0])
            if id_val is None:
                break
            url = urljoin(sc.get("rawBaseUrl") or sc["searchUrl"], tpl.replace("{value}", str(id_val)))
        ctx["detail_url"] = url
        try:
            r = _get(url, session, timeout)
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


def _extract_id(sc, keyword, session, timeout, name):
    url = sc["searchUrl"].replace("{keyword}", quote(keyword))
    try:
        data = _get(url, session, timeout).json()
        jp = sc["selectorSubjectFormatJsonPathIndexed"]
        ids = eval_simple_jsonpath(data, jp["selectLinks"])
        names = eval_simple_jsonpath(data, jp["selectNames"])
        for n, i in zip(names, ids):
            if str(n) == name:
                return i
        return ids[0] if ids else None
    except Exception:
        return None
