"""Kazumi 规则 -> Animeko 数据源（订阅格式）的转换。

只做“能确定地转”的部分；转不了的返回 status="unsupported" 和原因，
由 build.py 改用 overrides/ 里手写的配置，或在报告里列出。
"""
import re
from urllib.parse import urlparse

from xpath2css import xpath_to_css, join_relative, Unsupported

# 视频地址匹配：与 Animeko 官方订阅里同类站点的通用写法一致
MATCH_VIDEO_URL = (
    r"(^http(s)?:\/\/(?!.*http).+\.(mp4|m3u8|flv|mkv))"
    r"|(url=(?<v>http(s)?:\/\/.+\.(mp4|m3u8|flv|mkv)))"
    r"|(^http(s)?:\/\/(?!.*http).+(sign\.bytetos|sign\.byteimg|mcloud\.139|cloudflarestorage|tos-cn)\.com(?!.*\.ts).+(-expires|-signature))"
    r"|((bilivideo|akamaized|szbdyd)\.com(?!.*\.ts))"
    r"|(\/video\/tos\/alisg\/)|(\/video\/.*mime_type=video)"
)
MATCH_NESTED_LEGACY = r"^.+(m3u8|vip|xigua\.php).+\?"
EPISODE_SORT = r"(第\s*(?<ep>.+?)\s*[话集])|(\d+)"
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


class Result:
    def __init__(self, name, version=""):
        self.name = name
        self.version = version
        self.source = None
        self.status = "unsupported"   # ok / partial / unsupported
        self.notes = []   # 需要留意的近似转换
        self.info = []    # 常规说明，不影响状态

    def fail(self, why):
        self.status = "unsupported"
        self.notes.append(why)
        return self


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "rule"


def _origin(url):
    p = urlparse(url)
    return "%s://%s" % (p.scheme, p.netloc) if p.scheme and p.netloc else ""


def _simple_json_field(path):
    """'$.id' -> 'id'；只支持单层字段。"""
    m = re.match(r"^\$\.([A-Za-z_][\w]*)$", path or "")
    return m.group(1) if m else None


def _query_string(query):
    parts = []
    for k, v in (query or {}).items():
        v = str(v).replace("@keyword", "{keyword}")
        parts.append("%s=%s" % (k, v))
    return "&".join(parts)


def convert_rule(rule, config=None):
    config = config or {}
    name = rule.get("name", "")
    res = Result(name, str(rule.get("version", "")))
    base = rule.get("baseURL", "") or ""
    origin = _origin(base)
    if not origin:
        return res.fail("缺少 baseURL")
    if rule.get("usePost"):
        return res.fail("规则使用 POST 搜索，Animeko 的 Web 数据源不支持")
    if rule.get("chapterMode") == "api" or rule.get("chapterApiConfig"):
        return res.fail("章节来自接口（chapterApiConfig），无法推出 Animeko 需要的播放接口，需要手写 override")

    sc = {
        "searchUseOnlyFirstWord": True,
        "searchRemoveSpecial": True,
        "searchUseSubjectNamesCount": 1,
        "rawBaseUrl": "",
        "requestInterval": 3000,
    }
    if rule.get("userAgent"):
        sc["userAgent"] = rule["userAgent"]

    # ---------- 搜索 ----------
    if rule.get("searchMode") == "api" or rule.get("searchApiConfig"):
        api = rule.get("searchApiConfig") or {}
        req = api.get("request", {})
        if str(req.get("method", "GET")).upper() != "GET":
            return res.fail("搜索接口为 %s，需要手写 override" % req.get("method"))
        url = req.get("url", "")
        qs = _query_string(req.get("query"))
        if not url:
            return res.fail("缺少搜索接口地址")
        sc["searchUrl"] = url + (("?" + qs) if qs else "")
        if "{keyword}" not in sc["searchUrl"]:
            return res.fail("搜索接口里没有找到关键词参数")
        lp = api.get("listPath", "")
        nf, sf = _simple_json_field(api.get("namePath")), _simple_json_field(api.get("sourcePath"))
        if not lp or not nf or not sf:
            return res.fail("接口 JSONPath 过于复杂：%s / %s / %s" % (lp, api.get("namePath"), api.get("sourcePath")))
        tpl = api.get("sourceTemplate") or ""
        template_guess = False
        if tpl:
            link_tpl = tpl.replace("@source", "{value}")
            if _origin(link_tpl) == origin:
                link_tpl = link_tpl[len(origin):]
        else:
            path = urlparse(base).path or "/"
            link_tpl = path.rstrip("/") + "/{value}.html"
            template_guess = True
            res.info.append("规则没有 sourceTemplate，条目链接按 %s 猜测，冒烟测试会尝试其他写法" % link_tpl)
        sc["subjectFormatId"] = "json-path-indexed"
        sc["selectorSubjectFormatJsonPathIndexed"] = {
            "selectLinks": "%s['%s']" % (lp, sf),
            "selectNames": "%s['%s']" % (lp, nf),
            "linkTemplate": link_tpl,
            "preferShorterName": True,
        }
        res._template_guess = template_guess
    else:
        surl = rule.get("searchURL", "")
        if not surl:
            return res.fail("缺少 searchURL")
        sc["searchUrl"] = surl.replace("@keyword", "{keyword}")
        try:
            lst, n1 = xpath_to_css(rule.get("searchList"))
            nm, n2 = xpath_to_css(rule.get("searchName"))
            rs, n3 = xpath_to_css(rule.get("searchResult"))
        except Unsupported as e:
            return res.fail("搜索 XPath 无法转换：%s" % e)
        res.notes += n1 + n2 + n3
        if rule.get("searchName") == rule.get("searchResult"):
            sc["subjectFormatId"] = "a"
            sc["selectorSubjectFormatA"] = {"selectLists": join_relative(lst, nm), "preferShorterName": True}
        else:
            sc["subjectFormatId"] = "indexed"
            sc["selectorSubjectFormatIndexed"] = {
                "selectNames": join_relative(lst, nm),
                "selectLinks": join_relative(lst, rs),
                "preferShorterName": True,
            }

    # ---------- 章节 ----------
    try:
        roads_xp = (rule.get("chapterRoads") or "").strip()
        roads, n4 = ("", []) if roads_xp == "//" else xpath_to_css(roads_xp)
        ep, n5 = xpath_to_css(rule.get("chapterResult"))
    except Unsupported as e:
        return res.fail("章节 XPath 无法转换：%s" % e)
    res.notes += n4 + n5
    sc["channelFormatId"] = "no-channel"
    sc["selectorChannelFormatNoChannel"] = {
        "selectEpisodes": ep if rule.get("chapterRoads", "").strip() == "//" else join_relative(roads, ep),
        "selectEpisodeLinks": "",
        "matchEpisodeSortFromName": EPISODE_SORT,
    }
    res.info.append("Kazumi 规则没有线路名，所有线路合并为一条")

    # ---------- 播放 ----------
    legacy = bool(rule.get("useLegacyParser"))
    referer = rule.get("referer") or ""
    sc.update({
        "defaultResolution": "1080P",
        "defaultSubtitleLanguage": "CHS",
        "onlySupportsPlayers": [],
        "filterByEpisodeSort": True,
        "filterBySubjectName": True,
        "selectMedia": {"distinguishSubjectName": True, "distinguishChannelName": False},
        "matchVideo": {
            "enableNestedUrl": legacy,
            "matchNestedUrl": MATCH_NESTED_LEGACY if legacy else "$^",
            "matchVideoUrl": MATCH_VIDEO_URL,
            "cookies": "quality=1080",
            "addHeadersToVideo": {"referer": referer},
            "scanDomMediaUrls": not legacy,
        },
    })

    tier = (config.get("tiers") or {}).get(name, config.get("default_tier", 4))
    desc = "由 Kazumi 规则 %s v%s 自动转换" % (name, rule.get("version", "?"))
    if rule.get("lastUpdate"):
        desc += "（规则更新于 %s）" % rule["lastUpdate"]
    res.source = {
        "id": "kazumi-" + slugify(name),
        "factoryId": "web-selector",
        "version": 2,
        "arguments": {
            "name": name,
            "description": desc,
            "iconUrl": origin + "/favicon.ico",
            "searchConfig": sc,
            "tier": tier,
            "channelTiers": {},
        },
    }
    res.status = "partial" if res.notes else "ok"
    return res
