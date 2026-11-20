"""自动学习：没有任何来源能转成规则的站点，直接看真实页面，自己写一条 web-selector 规则。

哪些站点会被学：
  * 候选里「无法转换」（source 为空）、而且同一个站没有任何别的来源能用（没有 source，或站点域名不在已有候选里）；
  * config.learn_sites 手动指定的站点；
  * 磁力站（config.learn_exclude，默认 dmhy / mikan）不学：Animeko 的 Web 数据源不支持。

怎么学（MacCMS 一类模板站为主）：
  1. 拿站点域名，依次试一批常见的 GET 搜索地址（/index.php/vod/search.html?wd=… 等），
     搜索页能打开（不是验证码）就用 repair.find_search_selector 在页面上找出「命中关键词最多」的结果链接选择器；
     网页搜索都不行，再试 MacCMS 的 JSON 接口（ajax/suggest、api.php/provide/vod），学成 json-path-indexed；
  2. 打开第一个结果的详情页，用 repair.find_episode_selector 找剧集列表；
     页面上有几条线路、线路标签数量对得上时，学成 index-grouped（保留线路名），否则合并成一条；
  3. 拼成 web-selector 规则（和转换器输出同一格式，UA 用统一 UA），交给 build.py 的联网检测（含播放检测）：
     检测通过才有机会被采用，所以学错了不会污染订阅；
  4. 搜索页是 MacCMS 图片验证码（Animeko 有自动 solver）、页面学不了时：用 MacCMS 最常见的写法生成一条
     「猜测」候选（guess，没验证过，排在有实测的候选后面，描述里标明）。

出口：先走国内出口（代理，Animeko 用户的真实视角）；打不开再用 GitHub 海外直连试一次，
  只有海外能学到时会在备注里写明，国内是否可用由后面的联网检测决定。

缓存（state/learned.json）：学到的规则 7 天内直接沿用（只重新检测，不重新抓页面）；
  检测明确失败就清掉，下次重学；学不出来的站点 3 天内不再重试，免得每次构建都去敲人家的站。
"""
import hashlib
import json
import re
import time
from urllib.parse import quote, urljoin, urlparse

from bs4 import BeautifulSoup

from ..convert.kazumi import EPISODE_SORT, MATCH_VIDEO_URL
from . import smoke as smoke_mod
from . import ua as ua_mod
from .domains import host_of, registrable
from .repair import EP_TEXT, find_episode_selector, find_search_selector

# 常见的 GET 搜索地址（{keyword} 会被 URL 编码）。前面是 MacCMS 各版本的写法，后面是别的建站程序
SEARCH_PATHS = [
    "/index.php/vod/search.html?wd={keyword}",
    "/vodsearch/-------------.html?wd={keyword}",
    "/vodsearch/{keyword}-------------.html",
    "/vodsearch/{keyword}----------1---.html",
    "/search/-------------.html?wd={keyword}",
    "/search/{keyword}----------1---.html",
    "/search/{keyword}/",
    "/search.php?searchword={keyword}",
    "/index.php/vod/search/wd/{keyword}.html",
    "/index.php?m=vod-search&wd={keyword}",
    "/search/index.html?wd={keyword}",
    "/search?query={keyword}",
    "/search?q={keyword}",
    "/search.php?q={keyword}",
    "/search.php?keyword={keyword}",
    "/?s={keyword}",
]
# MacCMS 的 JSON 接口（网页搜索都学不出来时再试）：返回的 JSON 里有 id 和名称
JSON_PATHS = [
    "/index.php/ajax/suggest?mid=1&wd={keyword}",
    "/index.php/ajax/suggest?mid=1&wd={keyword}&limit=30",
    "/api.php/provide/vod/?ac=list&wd={keyword}",
    "/api.php/provide/vod?ac=detail&wd={keyword}",
]
# JSON 搜索只给 id，详情页地址要猜：按这几种 MacCMS 常见写法试，能打开详情页并找到剧集的才算
DETAIL_TEMPLATES = ["/index.php/vod/detail/id/{value}.html", "/voddetail/{value}.html", "/vod/detail/id/{value}.html",
                    "/detail/{value}.html", "/vod-detail-id-{value}.html", "/index.php/vod/detail/id/{value}/"]
ID_KEYS = ("id", "vod_id", "vodId", "slug", "vid")
NAME_KEYS = ("name", "title", "vod_name", "vodName")
# 线路标签的常见选择器（数量要和线路列表对得上才用）
TAB_SELECTORS = [".module-tab-item", ".anthology-tab a", ".hl-tabs a", ".hl-plays-from a", ".stui-pannel__head .nav li a",
                 ".myui-panel__head .nav li a", ".nav-tabs li a", ".nav-tabs li", ".play_source_tab a", ".tab-title a",
                 "#tab a", ".swiper-slide", ".tabs li", ".module-tab-items .tab-item", ".vod-play-tab a", ".player-tab a",
                 ".tab_list li", ".play-tab li"]
# MacCMS 验证码站的猜测写法（搜索页看不到、学不了时才用）：覆盖 MacCMS 三种常见详情 / 播放页链接
GUESS_SEARCH = "/index.php/vod/search.html?wd={keyword}"
GUESS_RESULT = "a[href*='/voddetail/'], a[href*='/vod/detail/'], a[href*='/vod-detail/']"
GUESS_EPISODES = "a[href*='/vodplay/'], a[href*='/vod/play/'], a[href*='/vod-play/']"
DEFAULT_EXCLUDE = ["dmhy.org", "mikanani.me", "mikanime.tv", "nyaa.si"]
CACHE_DAYS, FAIL_DAYS = 7, 3
DEFAULT_MAX_SITES = 8


# ------------------------------- 选站点 -------------------------------

def _label(host):
    """站点的短名：去掉 www./m. 后取主域名那一段，做 id 和名称用。"""
    h = re.sub(r"^(www|m|wap|cn|ani)\.", "", (host or "").lower())
    reg = registrable(h) or h
    return re.sub(r"[^a-z0-9]+", "", reg.split(".")[0]) or "site"


def targets(cands, config):
    """要学的站点：[{"key","name","origin","host"}]。"""
    exclude = [x.lower() for x in config.get("learn_exclude", DEFAULT_EXCLUDE)]
    covered = set()
    for c in cands:
        if c.get("source") is None:
            continue
        for h in (c.get("live_hosts") or []) + [c.get("orig_site")]:
            if h:
                covered.add(registrable(h))
        try:
            from ..convert.anibaka import site_host
            covered.add(registrable(site_host(c["source"])))
        except Exception:
            pass
    out, seen = [], set()

    def add(host, origin, name=None):
        reg = registrable(host)
        if not host or reg in covered or reg in seen or any(reg.endswith(x) for x in exclude):
            return
        seen.add(reg)
        out.append(dict(key=_label(host), name=name or _label(host), origin=origin, host=host))

    for site in config.get("learn_sites", []) or []:   # 手动指定的：{"url": "https://x.com", "name": "…"}
        u = site.get("url", "")
        if u:
            add(urlparse(u).netloc, "%s://%s" % (urlparse(u).scheme or "https", urlparse(u).netloc), site.get("name"))
    for c in cands:
        if c.get("source") is not None or c.get("status") != "unsupported" or c["origin"] == "baseline":
            continue
        hosts = c.get("live_hosts") or []
        if hosts:   # 第一个是规则的 baseUrl，后面的多半是图标 / CDN 域名
            add(hosts[0], "https://" + hosts[0], c["key"])
    return out[: config.get("learn_max_sites", DEFAULT_MAX_SITES)]


# ------------------------------- 学一个站 -------------------------------

def _fetch(url, sessions, timeout=15):
    """按出口顺序取页面。返回 (text, final_url, exit_name, status, captcha) ；取不到 text 为 None，
    captcha 是被验证码拦住时的类型（maccms / cloudflare / other），其余为空。"""
    last = None
    for name, session in sessions:
        try:
            r = smoke_mod._get(url, session, timeout)
        except Exception as e:
            last = last or (None, url, name, type(e).__name__, "")
            continue
        text = r.text or ""
        if r.status_code == 200 and text and not smoke_mod._blocked(text):
            return text, getattr(r, "url", url) or url, name, 200, ""
        if r.status_code == 200 and text:
            last = (None, url, name, "blocked", smoke_mod.captcha_kind(text))
        elif not (last and last[3] == "blocked"):
            last = (None, url, name, r.status_code, "")
    return last or (None, url, "", "unreachable", "")


def find_channels(html, ep_sel):
    """详情页上有多条线路、且线路标签数量对得上：返回 (标签选择器, 线路列表选择器)，否则 None。"""
    lst = re.sub(r"\s+a$", "", ep_sel)
    soup = BeautifulSoup(html, "lxml")
    try:
        conts = soup.select(lst)
    except Exception:
        return None
    good = [c for c in conts if any(a.get("href") and EP_TEXT.search(a.get_text(" ", strip=True)) for a in c.select("a"))]
    if len(good) < 2:
        return None
    for tsel in TAB_SELECTORS:
        try:
            tabs = [t.get_text(" ", strip=True) for t in soup.select(tsel)]
        except Exception:
            continue
        tabs = [t for t in tabs if t]
        if len(tabs) == len(good):
            return tsel, lst
    return None


def find_json_results(text, keyword):
    """JSON 搜索结果：找到「名称里含关键词、有 id」的对象列表。返回 (selectLinks, selectNames, 第一个 id) 或 None。"""
    try:
        data = json.loads(text)
    except ValueError:
        return None
    key = keyword[:2]

    def walk(obj, path, depth):
        if depth > 3:
            return None
        if isinstance(obj, list):
            items = [x for x in obj if isinstance(x, dict)]
            for idk in ID_KEYS:
                ids = [x.get(idk) for x in items]
                if not items or any(not isinstance(i, (int, str)) or isinstance(i, bool) or i == "" for i in ids):
                    continue
                for nk in list(NAME_KEYS) + [k for k in items[0] if k not in NAME_KEYS]:
                    names = [x.get(nk) for x in items]
                    if all(isinstance(n, str) for n in names) and any(key in n for n in names) \
                            and re.fullmatch(r"\w+", nk) and re.fullmatch(r"\w+", idk):
                        head = "$" + "".join("." + t for t in path) + "[*]"
                        first = next(i for i, n in zip(ids, names) if key in n)
                        return "%s['%s']" % (head, idk), "%s['%s']" % (head, nk), first
            return None
        if isinstance(obj, dict):
            for k, v in obj.items():
                if re.fullmatch(r"\w+", str(k)):
                    got = walk(v, path + (str(k),), depth + 1)
                    if got:
                        return got
        return None

    return walk(data, (), 0)


def build_source(key, name, origin, host, search_path, search_sel, ep_sel, channels=None, json_search=None,
                 guess=False):
    """channels: (标签选择器, 线路列表选择器) 或 None；json_search: (selectLinks, selectNames, linkTemplate) 或 None。"""
    sc = {
        "searchUrl": origin + search_path,
        "searchUseOnlyFirstWord": True,
        "searchRemoveSpecial": True,
        "searchUseSubjectNamesCount": 1,
        "rawBaseUrl": origin,
        "requestInterval": 3000,
    }
    if json_search:
        sc["subjectFormatId"] = "json-path-indexed"
        sc["selectorSubjectFormatJsonPathIndexed"] = {"selectLinks": json_search[0], "selectNames": json_search[1],
                                                       "linkTemplate": json_search[2], "preferShorterName": True}
    else:
        sc["subjectFormatId"] = "a"
        sc["selectorSubjectFormatA"] = {"selectLists": search_sel, "preferShorterName": True}
    if channels:
        sc["channelFormatId"] = "index-grouped"
        sc["selectorChannelFormatFlattened"] = {"selectChannelNames": channels[0], "selectEpisodeLists": channels[1],
                                                "selectEpisodesFromList": "a"}
    else:
        sc["channelFormatId"] = "no-channel"
        sc["selectorChannelFormatNoChannel"] = {"selectEpisodes": ep_sel, "selectEpisodeLinks": "",
                                                "matchEpisodeSortFromName": EPISODE_SORT}
    sc.update({
        "userAgent": ua_mod.current(),   # 验证码 cookie 和 UA 绑定：检测、验证、播放都用同一个 UA
        "defaultResolution": "1080P",
        "defaultSubtitleLanguage": "CHS",
        "onlySupportsPlayers": [],
        "filterByEpisodeSort": True,
        "filterBySubjectName": True,
        "selectMedia": {"distinguishSubjectName": True, "distinguishChannelName": bool(channels)},
        "matchVideo": {
            "enableNestedUrl": False, "matchNestedUrl": "$^", "matchVideoUrl": MATCH_VIDEO_URL,
            "cookies": "quality=1080", "addHeadersToVideo": {"referer": origin + "/"}, "scanDomMediaUrls": True,
        },
    })
    return {
        "id": "aniyuan-" + _label(host),
        "factoryId": "web-selector",
        "version": 2,
        "arguments": {
            "name": name,
            "description": ("[自动猜测，未验证] " if guess else "") + "站点 %s。" % host,
            "iconUrl": origin + "/favicon.ico",
            "searchConfig": sc,
            "tier": 4,
            "channelTiers": {},
        },
    }


def _episodes(detail_html, final, presets, base):
    """在详情页上找剧集：返回 (ep_sel, 集数, channels, 说明) 或 None。多线路对得上时用 index-grouped。"""
    ep = find_episode_selector(detail_html, presets)
    if not ep:
        return None
    ep_sel, n, _first = ep
    ch = find_channels(detail_html, ep_sel)
    if ch:
        probe_sc = {"channelFormatId": "index-grouped", "selectorChannelFormatFlattened": {
            "selectEpisodeLists": ch[1], "selectEpisodesFromList": "a"}}
        got = len(smoke_mod.extract_episodes(probe_sc, detail_html, final))
        if got >= n:   # 按线路取不比合并取少，才用
            return ep_sel, got, ch, "多线路（标签 %s）" % ch[0]
    return ep_sel, n, None, ""


def learn_site(t, sessions, presets, keywords, sleep=1.0):
    """学一个站。返回 (source, 说明, 出口名, 是否猜测) 或 (None, 原因, None, False)。"""
    origin = t["origin"]
    why, captcha = "搜索页都打不开或被拦", ""
    dead = set()   # 第一个关键词就 404 / 打不开的地址，换关键词也不会好，别再敲
    for kw in keywords:
        for path in SEARCH_PATHS:
            if path in dead:
                continue
            url = origin + path.replace("{keyword}", quote(kw))
            text, final, exit_name, status, cap = _fetch(url, sessions)
            time.sleep(sleep)
            if text is None:
                why = "搜索页打不开（%s）" % status
                captcha = captcha or cap
                if not cap:
                    dead.add(path)
                continue
            found = find_search_selector(text, kw, presets)
            if not found:
                why = "搜索页能打开，但在上面没找到合适的结果链接选择器"
                continue
            sel, hits, total, first = found
            detail_url = urljoin(final, first[1])
            dtext, dfinal, _dexit, dstatus, _c = _fetch(detail_url, sessions)
            time.sleep(sleep)
            if dtext is None:
                why = "搜到了结果，但详情页打不开（%s）" % dstatus
                continue
            eps = _episodes(dtext, dfinal, presets, origin)
            if not eps:
                why = "详情页上没找到合适的剧集列表选择器"
                continue
            ep_sel, n, ch, ch_note = eps
            real_origin = "%s://%s" % (urlparse(final).scheme, urlparse(final).netloc) if final else origin
            src = build_source(t["key"], t["name"], real_origin, host_of(real_origin), path, sel, ep_sel, channels=ch)
            note = "自动学习：搜索 %s（命中 %d/%d），剧集 %s（%d 集%s），在%s学到" % (
                sel, hits, total, ep_sel, n, "，" + ch_note if ch_note else "", exit_name)
            return src, note, exit_name, False
        # 网页搜索都不行：试 MacCMS 的 JSON 接口
        for path in JSON_PATHS:
            if path in dead:
                continue
            url = origin + path.replace("{keyword}", quote(kw))
            text, final, exit_name, status, cap = _fetch(url, sessions)
            time.sleep(sleep)
            if text is None:
                if not cap:
                    dead.add(path)
                captcha = captcha or cap
                continue
            got = find_json_results(text, kw)
            if not got:
                continue
            links, names, first_id = got
            for tpl in DETAIL_TEMPLATES:
                dtext, dfinal, _de, _ds, _c = _fetch(urljoin(final, tpl.replace("{value}", str(first_id))), sessions)
                time.sleep(sleep)
                if dtext is None:
                    continue
                eps = _episodes(dtext, dfinal, presets, origin)
                if not eps:
                    continue
                ep_sel, n, ch, ch_note = eps
                real_origin = "%s://%s" % (urlparse(final).scheme, urlparse(final).netloc) if final else origin
                src = build_source(t["key"], t["name"], real_origin, host_of(real_origin), path, "", ep_sel,
                                   channels=ch, json_search=(links, names, tpl))
                note = "自动学习：JSON 搜索接口 %s（%s），详情页 %s，剧集 %s（%d 集%s），在%s学到" % (
                    path.split("?")[0], links, tpl, ep_sel, n, "，" + ch_note if ch_note else "", exit_name)
                return src, note, exit_name, False
            why = "JSON 接口搜得到，但猜不出详情页地址"
    if captcha == "maccms":   # 搜索页是 MacCMS 图片验证码，页面学不了：用最常见的写法猜一条，等联网检测 / Animeko 自动验证来定
        src = build_source(t["key"], t["name"], origin, host_of(origin), GUESS_SEARCH, GUESS_RESULT, GUESS_EPISODES, guess=True)
        return src, "搜索页是 MacCMS 图片验证码（Animeko 有自动 solver），学不了页面，按 MacCMS 最常见的写法猜了一条", "", True
    return None, why, None, False


# ------------------------------- 接进构建 -------------------------------

def _digest(source):
    return hashlib.sha256(json.dumps(source, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def learn_cands(cands, proxy_session, direct_session, presets, cache, now, config):
    """对要学的站点出候选（追加进 cands，同时返回）。cache 是 state/learned.json 读出来的 dict，原地更新。"""
    sessions = [("国内出口", proxy_session)] if direct_session is not None else [("直连", proxy_session)]
    if direct_session is not None:
        sessions.append(("海外直连", direct_session))
    keywords = [config.get("smoke_keyword", "葬送的芙莉莲")] + [k for k in config.get("smoke_fallback_keywords", ["海贼王"])
                                                         if k != config.get("smoke_keyword", "葬送的芙莉莲")][:1]
    made = []
    for t in targets(cands, config):
        reg = registrable(t["host"])
        hit = cache.get(reg) or {}
        src, note, exit_name, guess = None, "", None, False
        if hit.get("source") and now - hit.get("at", 0) < CACHE_DAYS * 86400:
            src, note, exit_name, guess = (json.loads(json.dumps(hit["source"])), hit.get("note", "") + "（沿用上次学到的规则）",
                                           hit.get("exit"), bool(hit.get("guess")))
        elif hit.get("fail") and now - hit.get("at", 0) < FAIL_DAYS * 86400:
            print("自动学习 %s：%d 天内学过但没成功（%s），先不重试" % (t["host"], FAIL_DAYS, hit["fail"]))
            continue
        else:
            try:
                src, note, exit_name, guess = learn_site(t, sessions, presets, keywords)
            except Exception as e:   # 学习是锦上添花，任何意外都不能影响订阅
                src, note, guess = None, "学习时出错：%s" % type(e).__name__, False
            if src is None:
                print("自动学习 %s：没学出来（%s）" % (t["host"], note))
                cache[reg] = {"fail": note, "at": now}
                continue
            cache[reg] = {"source": src, "note": note, "exit": exit_name, "guess": guess, "at": now}
            print("自动学习 %s：%s" % (t["host"], note))
        notes = [note]
        if exit_name == "海外直连":
            notes.append("国内出口打不开、只在海外直连学到：国内是否能用看联网检测的国内出口结果")
        c = dict(origin="learned", key=t["key"], version="auto", source=src, status="partial", notes=notes, info=[],
                 guess=guess, date=now, raw_hash=_digest(src), live_hosts=[host_of(src["arguments"]["searchConfig"]["rawBaseUrl"])],
                 date_basis="自动学习", learned=True)
        made.append(c)
    cands.extend(made)
    return made


def finalize_cache(made, cache, now):
    """联网检测之后：检测明确失败的学习结果清掉（下次重学）；没结论（被拦 / 打不开）的保留。"""
    for c in made:
        sm = c.get("smoke") or {}
        reg = registrable(host_of(c["source"]["arguments"]["searchConfig"]["rawBaseUrl"]))
        if sm.get("status") == "fail" and reg in cache:
            cache[reg] = {"fail": "学到的规则检测未通过：%s" % sm.get("reason", ""), "at": now}
