"""自动分线路：把“所有线路合并成一条”（no-channel）的源升级成 Animeko 的 index-grouped。

为什么要做：Kazumi / 纯纯看番的规则没有线路名，转出来只能合并成一条。Animeko 里就分不清、也没法换线路，
而且资源 id 由“条目名 + 线路名 + 集名”拼成，不同线路的同一集会撞 id。

怎么保证不改坏：按 Animeko 引擎的实际算法模拟解析（见 simulate），只有分组后拿到的剧集链接
和原来合并写法的**完全一样**（一集不多、一集不少、各线路不重叠），并且线路标签像线路名时才采用。

Animeko 的算法（SelectorChannelFormatIndexGrouped.select）：page.select(线路标签) 和 page.select(剧集列表)
按位置一一配对；标签文字为空、或不匹配 matchChannelName 的，对应的整个列表被丢掉。
"""
import copy
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .playcheck import to_py_regex

# Animeko 在配置里没写 matchChannelName 时的默认值（会吃掉末尾数字，“线路1”“线路2”都变成“线路”）
DEFAULT_MATCH_CHANNEL = r"^(?<ch>.+?)(\d+)?$"
FULL_NAME = r"^(?<ch>.+)$"                  # 整个标签就是线路名
STRIP_COUNT = r"^(?<ch>.+?)\s*\d+$"         # 标签末尾带集数角标（“线路一12”）

# 常见建站模板的剧集列表容器 / 线路标签。官方订阅里人工验证过的写法会自动排在这些前面（见 official_presets）
LIST_SELECTORS = [".module-play-list-content", ".module-play-list", ".anthology-list-box", ".hl-plays-list",
                  ".stui-content__playlist", ".myui-content__list", ".vod-play-list-container", ".module-blocklist",
                  "#playlist .hl-tabs-box", ".playlist", ".play-list", ".play_list_box", ".episode-list", ".video_list"]
TAB_SELECTORS = ["#y-playList .module-tab-item span", "#y-playList .module-tab-item",
                 ".module-tab-items-box .module-tab-item", ".module-tab-item.tab-item",
                 ".anthology-tab > .swiper-wrapper a", ".anthology-tab a", ".hl-plays-from .hl-tabs-btn",
                 ".hl-plays-from a", ".hl-tabs a", ".chat-stream-bfqs > li", ".stui-pannel__head .nav li a",
                 ".myui-panel__head .nav li a", ".play_source_tab a", ".vod-play-tab a", ".player-tab a",
                 ".module-tab-items .tab-item", ".play-tab li", ".tab_list li", ".tab-title a", "#tab a",
                 ".nav-tabs li a", ".nav-tabs li", ".module-tab-item", ".swiper-slide", ".tabs li"]
# 标签开头的图标字体字符（私有区，Animeko 里显示成方框）和空白不算进线路名。写法同时兼容 Java 和 Python 正则
ICON_PREFIX = r"^[\ue000-\uf8ff\s]*"
ICON_RE = re.compile("^[\ue000-\uf8ff]")
MAX_CHANNELS = 20
MAX_LABEL = 24
# 整个标签就是这些词的，是网站导航 / 详情页内容切换，不是线路
NOT_CHANNEL = re.compile(
    r"^(首页|主页|电影|电视剧|剧集|综艺|动漫|动画|番剧|国漫|日漫|美漫|剧场版|最新|最热|热门|热播|排行榜?|专题|留言|评论.*|"
    r"(剧情)?简介|剧情介绍|详情|演职员|相关.*|猜你喜欢.*|(同类|相似)?推荐|下载(地址)?|周[一二三四五六日天]|星期[一二三四五六日天]|"
    r"\d+\s*[-~至]\s*\d+(\s*[集话話])?|第\s*[\d一二三四五六七八九十]+\s*[集话話])\s*\d*$")


def text_of(el):
    """和 Jsoup 的 text() 一样：行内元素之间不额外加空格，空白压成一个。"""
    return re.sub(r"\s+", " ", el.get_text()).strip()


def _select(node, sel):
    try:
        return node.select(sel)
    except Exception:
        return []


def _links(container, item_sel, link_sel, base):
    """一个剧集列表里的 [(集名, 绝对链接)]；没有可用链接的忽略。"""
    items = _select(container, item_sel or "a")
    extra = [e.get("href", "") for e in _select(container, link_sel) if e.get("href")] if link_sel else None
    out = []
    for i, el in enumerate(items):
        href = (extra[i] if extra is not None and i < len(extra) else el.get("href", "")) or ""
        href = href.strip()
        if not href or href.startswith(("javascript", "#")):
            continue
        out.append((el.get_text(" ", strip=True) or (el.get("title") or "").strip(), urljoin(base, href)))
    return out


def simulate(fl, html, base):
    """按 Animeko 的算法解析 index-grouped：返回 [(线路名, [(集名, 链接)])]。html 可以是字符串或 BeautifulSoup。"""
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "lxml")
    pattern = fl.get("matchChannelName", DEFAULT_MATCH_CHANNEL)
    rx = None
    if pattern:
        try:
            rx = re.compile(to_py_regex(pattern))
        except re.error:
            return []   # 正则写错：Animeko 认为整个配置无效
    names = []
    for el in _select(soup, fl.get("selectChannelNames") or ""):
        text = text_of(el)
        if not text:
            names.append(None)
        elif rx is None:
            names.append(text)
        else:
            m = rx.search(text)
            names.append(None if not m else (m.groupdict().get("ch") or text))
    groups = []
    for box, name in zip(_select(soup, fl.get("selectEpisodeLists") or ""), names):
        if name is not None:
            groups.append((name, _links(box, fl.get("selectEpisodesFromList"), fl.get("selectEpisodeLinksFromList"), base)))
    return groups


def flat_links(sc, soup, base):
    """合并写法（no-channel）选出的剧集链接。"""
    nc = sc.get("selectorChannelFormatNoChannel") or {}
    out = []
    for el in _select(soup, nc.get("selectEpisodes") or ""):
        link = el.select_one(nc["selectEpisodeLinks"]) if nc.get("selectEpisodeLinks") else el
        href = (link.get("href") or "").strip() if link is not None else ""
        if href and not href.startswith(("javascript", "#")):
            out.append((el, urljoin(base, href)))
    return out


def official_presets(sites):
    """官方订阅里人工验证过的分线路写法 -> (列表选择器, 标签选择器)。官方源更新，这里自动跟着更新。"""
    lists, tabs = [], []
    for s in sites or ():
        sc = ((s.get("source") or {}).get("arguments") or {}).get("searchConfig") or {}
        if sc.get("channelFormatId") != "index-grouped":
            continue
        fl = sc.get("selectorChannelFormatFlattened") or {}
        for value, bag in ((fl.get("selectEpisodeLists"), lists), (fl.get("selectChannelNames"), tabs)):
            if value and value not in bag:
                bag.append(value)
    return lists, tabs


def _derived_lists(anchors):
    """从剧集链接往上找：祖先元素的 class 也是列表容器的候选（模板不在常见清单里时靠这个）。"""
    out = []
    node = anchors[0].parent
    for _ in range(5):
        if node is None or node.name in (None, "body", "html", "[document]"):
            break
        for cls in node.get("class") or []:
            if re.fullmatch(r"[A-Za-z_-][\w-]*", cls):
                out.append("%s.%s" % (node.name, cls))
        node = node.parent
    return out


def _split(soup, list_sel, wanted, base):
    """list_sel 能把合并写法的剧集恰好分成几份吗？能就返回 (容器, 各容器链接)。"""
    boxes = _select(soup, list_sel)
    if not 2 <= len(boxes) <= MAX_CHANNELS:
        return None
    parts = [[u for _, u in _links(b, "a", "", base)] for b in boxes]
    seen = set()
    for urls in parts:
        s = set(urls)
        if not s or s & seen:   # 空列表 / 两个列表有相同链接（嵌套、手机和电脑各一份）
            return None
        seen |= s
    return (boxes, parts) if seen == wanted else None


def _label_pattern(labels, sizes):
    counted = all(re.search(r"\D\s*%d$" % n, t) for t, n in zip(labels, sizes))
    return STRIP_COUNT if counted else FULL_NAME


def _tabs_for(soup, tab_sel, boxes, sizes):
    """tab_sel 选出的标签能和这些列表一一配对吗？能就返回 (matchChannelName, 线路名)。"""
    tabs = _select(soup, tab_sel)
    if len(tabs) != len(boxes):
        return None
    inside = {id(d) for b in boxes for d in [b] + b.find_all(True)}
    if any(id(t) in inside for t in tabs):
        return None
    labels = [text_of(t) for t in tabs]
    if any(not t or len(t) > MAX_LABEL or NOT_CHANNEL.match(t) for t in labels):
        return None
    pattern = _label_pattern(labels, sizes)
    if any(ICON_RE.match(t) for t in labels):
        pattern = ICON_PREFIX + pattern[1:]
    rx = re.compile(to_py_regex(pattern))
    names = [rx.search(t).group("ch") for t in labels]
    return (pattern, names) if len(set(names)) == len(names) else None


def infer(sc, html, base, presets=((), ())):
    """在详情页上推断分线路写法。返回 selectorChannelFormatFlattened 的内容，推断不出返回 None。"""
    soup = BeautifulSoup(html, "lxml")
    flat = flat_links(sc, soup, base)
    wanted = {u for _, u in flat}
    if len(wanted) < 2:
        return None
    flat_sel = (sc.get("selectorChannelFormatNoChannel") or {}).get("selectEpisodes", "")
    lists = list(presets[0]) + LIST_SELECTORS + [re.sub(r"\s*>?\s+a(\[[^\]]*\])?$", "", flat_sel)] \
        + _derived_lists([el for el, _ in flat])
    tabs = list(presets[1]) + [t for t in TAB_SELECTORS if t not in presets[1]]
    tried = set()
    for list_sel in lists:
        if not list_sel or list_sel in tried:
            continue
        tried.add(list_sel)
        split = _split(soup, list_sel, wanted, base)
        if not split:
            continue
        boxes, parts = split
        sizes = [len(p) for p in parts]
        for tab_sel in tabs:
            found = _tabs_for(soup, tab_sel, boxes, sizes)
            if not found:
                continue
            fl = {"selectChannelNames": tab_sel, "matchChannelName": found[0], "selectEpisodeLists": list_sel,
                  "selectEpisodesFromList": "a", "selectEpisodeLinksFromList": "",
                  "matchEpisodeSortFromName": (sc.get("selectorChannelFormatNoChannel") or {}).get("matchEpisodeSortFromName")
                  or r"第\s*(?<ep>.+)\s*[话集]"}
            if verify(fl, soup, wanted, base):
                return fl
    return None


def verify(fl, soup, wanted, base):
    """模拟 Animeko 解析，剧集链接必须和 wanted 完全一致。"""
    groups = simulate(fl, soup, base)
    return bool(groups) and {u for _, eps in groups for _, u in eps} == wanted


def with_channels(source, fl):
    """返回换成分线路写法的源副本（合并写法的配置留着，Animeko 只看 channelFormatId）。"""
    new = copy.deepcopy(source)
    sc = new["arguments"]["searchConfig"]
    sc["channelFormatId"] = "index-grouped"
    sc["selectorChannelFormatFlattened"] = dict(fl)
    sc.setdefault("selectMedia", {})["distinguishChannelName"] = True
    return new


def lines_of(sc, html, base):
    """分线路源的 [(线路名, 第一集链接)]，同名线路只留第一个。"""
    if sc.get("channelFormatId") != "index-grouped":
        return []
    out, seen = [], set()
    for name, eps in simulate(sc.get("selectorChannelFormatFlattened") or {}, html, base):
        if eps and name not in seen:
            seen.add(name)
            out.append((name, eps[0][1]))
    return out


def upgrade(source, html, base, cached=None, presets=((), ())):
    """能分线路就返回 (新 source, 写法)，否则 (None, None)。cached：上次用过的写法，仍然对得上就沿用
    （线路写法不随当天的页面细节来回换，只有一条线路的番剧也不会让它退回合并写法）。"""
    sc = (source.get("arguments") or {}).get("searchConfig") or {}
    if source.get("factoryId") != "web-selector" or sc.get("channelFormatId") != "no-channel" or not html:
        return None, None
    soup = BeautifulSoup(html, "lxml")
    wanted = {u for _, u in flat_links(sc, soup, base)}
    if cached and wanted and verify(cached, soup, wanted, base):
        return with_channels(source, cached), cached
    fl = infer(sc, html, base, presets)
    return (with_channels(source, fl), fl) if fl else (None, None)


BAD_LINE_TIER = 5


def channel_tiers(line_play, tier):
    """逐线路播放检测结果 -> channelTiers。只在“有的能播、有的没验证出能播”时写：把后者排到后面；
    能播的不写，沿用源自己的档位（所以和官方重叠而降档的源，这里不会把它抬回去）。"""
    if not line_play or "ok" not in line_play.values():
        return {}
    bad = max(BAD_LINE_TIER, (tier or 0) + 1)
    return {name: bad for name, st in line_play.items() if name and st != "ok"}
