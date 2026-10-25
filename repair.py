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
                    "/anime/", "/video/", "/vodshow/", "/GV", "/v/", "/vod/", "/dm/", "/cartoon/"]
DEFAULT_CONTAINERS = ["", ".module-card-item", ".module-item", ".module-search-item", ".module-poster-item",
                      ".search-list", ".vod-detail", ".public-list-box", ".stui-vodlist__box", ".stui-vodlist li",
                      ".hl-list-item", ".myui-vodlist__box", ".myui-vodlist__thumb", ".thumb-menu", ".video-item",
                      ".video-list li", ".item", ".card", ".list-item", "article", "li"]
DEFAULT_LISTS = [".module-play-list-content", ".module-play-list", ".anthology-list-play", ".anthology-list-box",
                 ".stui-content__playlist", "ul.hl-plays-list", ".hl-plays-list", ".play_list", ".playlist",
                 ".player_list", ".episode-list", ".content_playlist", "#panel1", ".myui-content__list",
                 ".ep-list", ".video_detail_episode", ".play-list", ".tab-pane", ".play-pannel-list"]
EP_TEXT = re.compile(r"第\s*[\d一二三四五六七八九十百]+\s*[话集]|^\s*\d{1,4}\s*$|^\s*(EP|ep|E)\s*\d+|[集话]$|^\d{1,4}\D*$|完结|全集|预告|SP|OVA|PV", re.I)


def mine_presets(anibaka_repo):
    """从 AniBakaRule 的规则里收集选择器/路径写法，补充到内置候选库。"""
    from anx2animeko import _pipeline, _walk_ops, split_selectors
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
            sel = ("%s a[href*='%s']" % (cont, pat)).strip()
            links = _anchors(soup, sel)
            hits = [l for l in links if key in l[0]]
            if not hits:
                continue
            rank = (round(len(hits) / len(links), 3), len(hits), -len(sel))
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
