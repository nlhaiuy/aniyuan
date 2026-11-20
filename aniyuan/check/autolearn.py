"""自动学习：没有任何来源能转成规则的站点，直接看真实页面，自己写一条 web-selector 规则。

哪些站点会被学：
  * 候选里「无法转换」（source 为空）、而且同一个站没有任何别的来源能用（没有 source，或站点域名不在已有候选里）；
  * config.learn_sites 手动指定的站点；
  * 磁力站（config.learn_exclude，默认 dmhy / mikan）不学：Animeko 的 Web 数据源不支持。

怎么学（MacCMS 一类模板站为主）：
  1. 拿站点域名，依次试一批常见的 GET 搜索地址（/index.php/vod/search.html?wd=… 等），
     搜索页能打开（不是验证码）就用 repair.find_search_selector 在页面上找出「命中关键词最多」的结果链接选择器；
  2. 打开第一个结果的详情页，用 repair.find_episode_selector 找剧集列表；
  3. 拼成 web-selector 规则（和转换器输出同一格式），交给 build.py 的联网检测（含播放检测）：
     检测通过才有机会被采用，所以学错了不会污染订阅。

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

from ..convert.kazumi import EPISODE_SORT, MATCH_VIDEO_URL
from . import smoke as smoke_mod
from .domains import host_of, registrable
from .repair import find_episode_selector, find_search_selector

# 常见的 GET 搜索地址（{keyword} 会被 URL 编码）。前面是 MacCMS 各版本的写法，后面是别的建站程序
SEARCH_PATHS = [
    "/index.php/vod/search.html?wd={keyword}",
    "/vodsearch/-------------.html?wd={keyword}",
    "/vodsearch/{keyword}-------------.html",
    "/search/-------------.html?wd={keyword}",
    "/search.php?searchword={keyword}",
    "/index.php/vod/search/wd/{keyword}.html",
    "/search?query={keyword}",
    "/search?q={keyword}",
    "/?s={keyword}",
]
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
    """按出口顺序取页面。返回 (text, final_url, exit_name, status) ；取不到 text 为 None。"""
    last = None
    for name, session in sessions:
        try:
            r = smoke_mod._get(url, session, timeout)
        except Exception as e:
            last = (None, url, name, type(e).__name__)
            continue
        text = r.text or ""
        if r.status_code == 200 and text and not smoke_mod._blocked(text):
            return text, getattr(r, "url", url) or url, name, 200
        last = (None, url, name, r.status_code if r.status_code != 200 else "blocked")
    return last or (None, url, "", "unreachable")


def build_source(key, name, origin, host, search_path, search_sel, ep_sel):
    sc = {
        "searchUrl": origin + search_path,
        "searchUseOnlyFirstWord": True,
        "searchRemoveSpecial": True,
        "searchUseSubjectNamesCount": 1,
        "rawBaseUrl": origin,
        "requestInterval": 3000,
        "subjectFormatId": "a",
        "selectorSubjectFormatA": {"selectLists": search_sel, "preferShorterName": True},
        "channelFormatId": "no-channel",
        "selectorChannelFormatNoChannel": {"selectEpisodes": ep_sel, "selectEpisodeLinks": "",
                                           "matchEpisodeSortFromName": EPISODE_SORT},
        "defaultResolution": "1080P",
        "defaultSubtitleLanguage": "CHS",
        "onlySupportsPlayers": [],
        "filterByEpisodeSort": True,
        "filterBySubjectName": True,
        "selectMedia": {"distinguishSubjectName": True, "distinguishChannelName": False},
        "matchVideo": {
            "enableNestedUrl": False, "matchNestedUrl": "$^", "matchVideoUrl": MATCH_VIDEO_URL,
            "cookies": "quality=1080", "addHeadersToVideo": {"referer": origin + "/"}, "scanDomMediaUrls": True,
        },
    }
    return {
        "id": "aniyuan-" + _label(host),
        "factoryId": "web-selector",
        "version": 2,
        "arguments": {
            "name": name,
            "description": "站点 %s。" % host,
            "iconUrl": origin + "/favicon.ico",
            "searchConfig": sc,
            "tier": 4,
            "channelTiers": {},
        },
    }


def learn_site(t, sessions, presets, keywords, sleep=1.0):
    """学一个站。返回 (source, 说明, 出口名) 或 (None, 原因, None)。"""
    origin = t["origin"]
    why = "搜索页都打不开或被拦"
    for kw in keywords:
        for path in SEARCH_PATHS:
            url = origin + path.replace("{keyword}", quote(kw))
            text, final, exit_name, status = _fetch(url, sessions)
            time.sleep(sleep)
            if text is None:
                why = "搜索页打不开（%s）" % status
                continue
            found = find_search_selector(text, kw, presets)
            if not found:
                why = "搜索页能打开，但在上面没找到合适的结果链接选择器"
                continue
            sel, hits, total, first = found
            detail_url = urljoin(final, first[1])
            dtext, _f, dexit, dstatus = _fetch(detail_url, sessions)
            time.sleep(sleep)
            if dtext is None:
                why = "搜到了结果，但详情页打不开（%s）" % dstatus
                continue
            ep = find_episode_selector(dtext, presets)
            if not ep:
                why = "详情页上没找到合适的剧集列表选择器"
                continue
            ep_sel, n, _first = ep
            real_origin = "%s://%s" % (urlparse(final).scheme, urlparse(final).netloc) if final else origin
            src = build_source(t["key"], t["name"], real_origin, host_of(real_origin), path, sel, ep_sel)
            note = "自动学习：搜索 %s（命中 %d/%d），剧集 %s（%d 集），在%s学到" % (
                sel, hits, total, ep_sel, n, exit_name)
            return src, note, exit_name
    return None, why, None


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
        src, note, exit_name = None, "", None
        if hit.get("source") and now - hit.get("at", 0) < CACHE_DAYS * 86400:
            src, note, exit_name = json.loads(json.dumps(hit["source"])), hit.get("note", "") + "（沿用上次学到的规则）", hit.get("exit")
        elif hit.get("fail") and now - hit.get("at", 0) < FAIL_DAYS * 86400:
            print("自动学习 %s：%d 天内学过但没成功（%s），先不重试" % (t["host"], FAIL_DAYS, hit["fail"]))
            continue
        else:
            try:
                src, note, exit_name = learn_site(t, sessions, presets, keywords)
            except Exception as e:   # 学习是锦上添花，任何意外都不能影响订阅
                src, note = None, "学习时出错：%s" % type(e).__name__
            if src is None:
                print("自动学习 %s：没学出来（%s）" % (t["host"], note))
                cache[reg] = {"fail": note, "at": now}
                continue
            cache[reg] = {"source": src, "note": note, "exit": exit_name, "at": now}
            print("自动学习 %s：%s" % (t["host"], note))
        notes = [note]
        if exit_name == "海外直连":
            notes.append("国内出口打不开、只在海外直连学到：国内是否能用看联网检测的国内出口结果")
        c = dict(origin="learned", key=t["key"], version="auto", source=src, status="partial", notes=notes, info=[],
                 guess=False, date=now, raw_hash=_digest(src), live_hosts=[host_of(src["arguments"]["searchConfig"]["rawBaseUrl"])],
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
