"""冒烟测试：真正请求站点，验证「搜得到 → 进得去详情页 → 剧集选择器有结果」。

注意：只能验证到剧集列表，验证不了播放（播放需要 Animeko 的网页加载）。
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
    m = re.match(r"^\$((?:\.[\w]+)*)(\[\*\])?(?:\['(\w+)'\])?$", path)
    if not m:
        raise ValueError("不支持的 JSONPath: " + path)
    cur = data
    for key in [k for k in m.group(1).split(".") if k]:
        cur = cur.get(key) if isinstance(cur, dict) else None
        if cur is None:
            return []
    items = cur if m.group(2) and isinstance(cur, list) else [cur]
    if m.group(3):
        items = [i.get(m.group(3)) for i in items if isinstance(i, dict)]
    return [i for i in items if i is not None]


def _search_subjects(sc, keyword, session, timeout):
    """返回 (subjects[(name, url)], reason|None)；reason 非空表示没成功。"""
    url = sc["searchUrl"].replace("{keyword}", quote(keyword))
    try:
        r = _get(url, session, timeout)
    except requests.RequestException as e:
        return [], ("unreachable", "请求失败：%s" % type(e).__name__)
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
        return [(str(n), urljoin(url, tpl.replace("{value}", str(i)))) for n, i in zip(names, ids)], None
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


def check_source(source, keyword="葬送的芙莉莲", timeout=15, session=None):
    """返回 dict(status, reason, template)。status: ok / fail / blocked / unreachable / skipped"""
    session = session or requests.Session()
    a = source["arguments"]
    sc = a.get("searchConfig", {})
    if source.get("factoryId") != "web-selector" or "searchUrl" not in sc:
        return {"status": "skipped", "reason": "手写配置，不做自动检测"}
    subs, bad = _search_subjects(sc, keyword, session, timeout)
    if bad:
        return {"status": bad[0], "reason": bad[1]}
    if not subs:
        return {"status": "fail", "reason": "搜索页能打开，但选择器没有选中任何结果"}
    pick = next((s for s in subs if keyword[:3] in s[0]), subs[0])
    nc = sc.get("selectorChannelFormatNoChannel") or {}
    sel = nc.get("selectEpisodes")
    if not sel:
        return {"status": "skipped", "reason": "非 no-channel 章节格式，只验证了搜索"}
    jp = sc.get("selectorSubjectFormatJsonPathIndexed")
    # 条目链接模板不确定时，依次尝试几种写法
    variants = [None]
    chosen = None
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
            url = urljoin(sc["searchUrl"], tpl.replace("{value}", str(id_val)))
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
        eps = BeautifulSoup(r.text, "lxml").select(sel)
        if eps:
            res = {"status": "ok", "reason": "搜到 %d 个条目，详情页选出 %d 个剧集链接" % (len(subs), len(eps))}
            if tpl:
                res["template"] = tpl
            return res
        last = "详情页选择器没有选中剧集（%s）" % url
    return {"status": "fail", "reason": last or "详情页没有找到剧集"}


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
