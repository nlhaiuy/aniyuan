"""选择器自动修复：翻译来的选择器失效（或是脆弱的位置式写法）时，直接看真实页面重新选。

做法：MacCMS 一类的站模板高度相似。用“常见模板的容器选择器 × 常见详情页路径”去试，
挑出在真实搜索页上命中最多、最精确的；再在详情页上用“常见播放列表选择器”挑剧集最多的。
候选库 = 内置的一批 + 从 AniBaka 规则里挖出来的（那些是人工维护、验证过的）。
修复结果必须重新通过冒烟测试才会被采用（见 build.py）。
"""
import json
import os
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

DEFAULT_PATTERNS = ["/voddetail/", "/vod-detail/", "/vod/detail/", "/detail/", "/bangumi/", "/media/", "/info/",
                    "/anime/", "/video/", "/vodshow/", "/GV", "/v/", "/vod/", "/dm/", "/cartoon/",
                    ""]   # "" = 不限制链接路径（站点用了没见过的详情页路径时的兜底；同分时排在有路径的后面）
DEFAULT_CONTAINERS = ["", ".module-card-item", ".module-item", ".module-search-item", ".module-poster-item",
                      ".search-list", ".vod-detail", ".public-list-box", ".stui-vodlist__box", ".stui-vodlist li",
                      ".hl-list-item", ".myui-vodlist__box", ".myui-vodlist__thumb", ".thumb-menu", ".video-item",
                      ".video-list li", ".item", ".card", ".list-item", "article", "li",
                      # 以“标题所在节点”为容器的常见写法（MacCMS 各模板的结果标题）
                      ".module-card-item-title", ".thumb-txt", ".hl-item-title", ".hl-item-thumb", ".stui-vodlist__detail",
                      ".video-info-header", ".detail-info", ".fed-part-eone", ".card-title", ".vod-title", ".title",
                      "h2", "h3", "h4", "#searchList li", "#search_list li", ".search-box .thumb-content"]
DEFAULT_LISTS = [".module-play-list-content", ".module-play-list", ".anthology-list-play", ".anthology-list-box",
                 ".stui-content__playlist", "ul.hl-plays-list", ".hl-plays-list", ".play_list", ".playlist",
                 ".player_list", ".episode-list", ".content_playlist", "#panel1", ".myui-content__list",
                 ".ep-list", ".video_detail_episode", ".play-list", ".tab-pane", ".play-pannel-list",
                 # 参考订阅里出现过的剧集列表容器
                 ".fed-play-item", ".fed-drop-boxs .fed-part-rows", ".jisu", ".movurl", ".videolist", ".lists",
                 "ul.list-unstyled", "#playsx", ".anime-episode", ".module-blocklist", ".play_source_list_item",
                 "#playlist1", ".playlist-box", ".vod-play-list", ".episode", ".ep-item"]
EP_TEXT = re.compile(r"第\s*[\d一二三四五六七八九十百]+\s*[话集]|^\s*\d{1,4}\s*$|^\s*(EP|ep|E)\s*\d+|[集话]$|^\d{1,4}\D*$|完结|全集|预告|SP|OVA|PV", re.I)


def mine_presets(anibaka_repo):
    """从 AniBakaRule 的规则里收集选择器/路径写法，补充到内置候选库。"""
    from ..convert.anibaka import _pipeline, _walk_ops, split_selectors
    pats, conts, lists = list(DEFAULT_PATTERNS), list(DEFAULT_CONTAINERS), list(DEFAULT_LISTS)
    if not anibaka_repo or not os.path.isdir(anibaka_repo):
        return dict(patterns=pats, containers=conts, lists=lists)
    for fn in sorted(os.listdir(anibaka_repo)):
        if not fn.endswith(".json") or fn == "index.json":
            continue
        try:
            rule = json.load(open(os.path.join(anibaka_repo, fn), encoding="utf-8"))
        except ValueError:
            continue
        p = _pipeline(rule)
        for o in _walk_ops(p.get("search")):
            if o.get("op") == "searchList":
                for sel in o.get("selectors") or []:
                    for piece in split_selectors(sel):
                        if " a" not in piece and not piece.startswith("a") and piece not in conts:
                            conts.append(piece)
                if o.get("detailPattern") and o["detailPattern"] not in pats:
                    pats.append(o["detailPattern"])
        for o in _walk_ops(p.get("detail")):
            if o.get("op") == "episodes":
                for sel in o.get("listSelectors") or []:
                    for piece in split_selectors(sel):
                        if piece not in lists:
                            lists.append(piece)
    return dict(patterns=pats, containers=conts, lists=lists)


def _anchors(soup, sel):
    try:
        els = soup.select(sel)
    except Exception:
        return []
    out, seen = [], set()
    for e in els:
        href = (e.get("href") or "").strip()
        text = e.get_text(" ", strip=True)
        if href and text and not href.startswith(("javascript", "#")) and href not in seen:
            seen.add(href)
            out.append((text, href))
    return out


def find_search_selector(html, keyword, presets):
    """返回 (selector, hits, total, 第一个命中的链接) 或 None。"""
    soup = BeautifulSoup(html, "lxml")
    key = keyword[:2]
    best, best_key = None, None
    for pat in presets["patterns"]:
        for cont in presets["containers"]:
            sel = (("%s a[href*='%s']" % (cont, pat)) if pat else ("%s a[href]" % cont)).strip()
            links = _anchors(soup, sel)
            hits = [l for l in links if key in l[0]]
            if not hits:
                continue
            # 命中率 > 命中数 > 限定了链接路径的（更不容易被改版误伤）> 选择器更短
            rank = (round(len(hits) / len(links), 3), len(hits), 1 if pat else 0, -len(sel))
            if best_key is None or rank > best_key:
                best, best_key = (sel, len(hits), len(links), hits[0]), rank
    return best


def find_episode_selector(html, presets):
    """返回 (selector, 剧集数, 第一集链接) 或 None。"""
    soup = BeautifulSoup(html, "lxml")
    best, best_key = None, None
    for lst in presets["lists"]:
        sel = "%s a" % lst
        links = [l for l in _anchors(soup, sel) if EP_TEXT.search(l[0])]
        if not links:
            continue
        rank = (len(links), -len(sel))
        if best_key is None or rank > best_key:
            best, best_key = (sel, len(links), links[0]), rank
    return best


def brittle(source):
    """位置式写法（多个 :nth-of-type）在网站稍微改版就会失效。"""
    return json.dumps(source["arguments"].get("searchConfig", {}), ensure_ascii=False).count(":nth-of-type") >= 3


def repair_source(source, ctx, keyword, presets, fetch, which):
    """which: "search" / "episodes" / "both"。fetch(url)->html|None。
    返回 (新 source, 说明) 或 (None, 原因)。"""
    new = json.loads(json.dumps(source))
    sc = new["arguments"]["searchConfig"]
    notes = []
    base = ctx.get("search_final_url") or ctx.get("search_url", "")
    detail_html = ctx.get("detail_html")
    if which in ("search", "both"):
        found = find_search_selector(ctx.get("search_html", ""), keyword, presets)
        if not found:
            return None, "在真实搜索页上没找到合适的结果链接选择器"
        sel, hits, total, first = found
        sc["subjectFormatId"] = "a"
        sc["selectorSubjectFormatA"] = {"selectLists": sel, "preferShorterName": True}
        notes.append("搜索选择器改为 %s（命中 %d/%d）" % (sel, hits, total))
        detail_html = fetch(urljoin(base, first[1]))
        if not detail_html:
            return None, "新的搜索选择器选出的条目打不开详情页"
        ctx["detail_url_repaired"] = urljoin(base, first[1])
    if which in ("episodes", "both") or which == "search":
        if not detail_html:
            return None, "没有详情页内容可用来修复剧集选择器"
        ep = find_episode_selector(detail_html, presets)
        if not ep and which != "search":
            return None, "在真实详情页上没找到合适的剧集列表选择器"
        if ep:
            sel, n, _first = ep
            sc["channelFormatId"] = "no-channel"
            sc["selectorChannelFormatNoChannel"] = {
                "selectEpisodes": sel, "selectEpisodeLinks": "",
                "matchEpisodeSortFromName": r"(第\s*(?<ep>.+?)\s*[话集])|(\d+)"}
            sc.pop("selectorChannelFormatFlattened", None)
            notes.append("剧集选择器改为 %s（%d 集）" % (sel, n))
    return new, "；".join(notes)


# ---------------------------------------------------------------- matchVideoUrl
# 这些不是视频，新写的 matchVideoUrl 一旦认得它们就说明写得太宽，整条候选作废
NOT_VIDEO = ["https://cdn.example.com/hls/seg001.ts", "https://cdn.example.com/hls/seg001.ts?t=1",
             "https://cdn.example.com/cover.jpg", "https://cdn.example.com/a.png", "https://www.example.com/static/app.js",
             "https://www.example.com/static/app.css", "https://www.example.com/player/index.html"]
EXT_RE = re.compile(r"\.(m3u8|mpd|mp4|m4v|mkv|webm|mov|flv|avi)(?:[?#]|$)", re.I)


def _compiles(pattern):
    from .playcheck import to_py_regex
    try:
        return re.compile(to_py_regex(pattern))
    except re.error:
        return None


def _derived_pattern(url):
    """按观察到的这个地址写一条限定了主机和后缀的正则（默认写法认不出时的兜底）。"""
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    if ":" in host:
        host = "[%s]" % host   # IPv6
    m = EXT_RE.search(url)
    if not host or not m:
        return None
    parts = host.split(".")
    if re.fullmatch(r"[\d.]+|\[[0-9a-fA-F:]+\]", host) or len(parts) < 2:
        reg, sub = host, ""   # IP 或单段主机名：整个固定
    else:
        reg, sub = ".".join(parts[-2:]), r"([^/]*\.)?"   # 只固定主域名，子域名（常常轮换）放开
    return r"^https?://(?!.*https?://)%s%s(:\d+)?/.*\.%s(\?.*)?$" % (sub, re.escape(reg), m.group(1).lower())


def propose_match_video(old, urls, default):
    """matchVideoUrl 认不出页面里实际出现的视频地址（播放检测 mismatch）时，给一条能认出来的。
    urls：页面里观察到的视频地址。old：原来的 matchVideoUrl。default：转换器的通用写法。
    顺序（越靠前越保守）：通用写法 → 原写法 + 通用写法 → 按观察到的地址限定主域名。
    每条都要认得出至少一个观察到的地址，并且认不得 .ts 分片、图片、脚本这类明显不是视频的地址，否则不采用。
    返回 (正则, 说明) 或 (None, 原因)。"""
    urls = [u for u in urls if u]
    if not urls:
        return None, "没有观察到的视频地址可供参考"
    cands = [("通用写法", default)]
    if (old or "").strip() and old != default and old != "$^":
        cands.append(("原写法并上通用写法", "(%s)|(%s)" % (old, default)))
    for u in urls:
        d = _derived_pattern(u)
        if d and d not in [c[1] for c in cands]:
            cands.append(("按观察到的地址限定主域名", d))
            break
    for label, pat in cands:
        rx = _compiles(pat)
        if rx is None:
            continue
        hit = [u for u in urls if rx.search(u)]
        if hit and not any(rx.search(n) for n in NOT_VIDEO):
            return pat, "matchVideoUrl 改为%s（认出 %d/%d 个视频地址，例：%s）" % (label, len(hit), len(urls), hit[0][:90])
    return None, "通用写法和按地址推出的写法都不合适（认不出，或写得太宽）"


def repair_match_video(source, urls, default):
    """返回 (新 source, 说明) 或 (None, 原因)；不改原对象。"""
    mv = ((source.get("arguments") or {}).get("searchConfig") or {}).get("matchVideo")
    if mv is None:
        return None, "这个源没有 matchVideo 配置"
    pat, why = propose_match_video(mv.get("matchVideoUrl"), urls, default)
    if not pat:
        return None, why
    new = json.loads(json.dumps(source))
    new["arguments"]["searchConfig"]["matchVideo"]["matchVideoUrl"] = pat
    new["arguments"]["description"] = "[匹配规则已自动修复] " + new["arguments"].get("description", "")
    return new, why
