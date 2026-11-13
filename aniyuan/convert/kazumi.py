"""Kazumi 规则 -> Animeko 数据源（订阅格式）的转换。

只做“能确定地转”的部分；转不了的返回 status="unsupported" 和原因，
由 build.py 改用 overrides/ 里手写的配置，或在报告里列出。
"""
import json
import re
from urllib.parse import urlparse

from .xpath2css import xpath_to_css, join_relative, Unsupported

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


def _scalar(v):
    """查询参数里的值：布尔写成 true/false（str(True) 会得到 True，接口认不出）。"""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def _query_string(query):
    parts = []
    for k, v in (query or {}).items():
        v = _scalar(v).replace("@keyword", "{keyword}")
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
        return convert_api_rule(rule, config, res, origin)

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
    desc = ""   # Kazumi 规则没有站点简介；“来源”说明由 build.py 统一生成（见 normalize.py）
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


# ====================== 接口型规则 -> Animeko 的 json-api 数据源 ======================
#
# Kazumi 的“接口取章节”规则（searchMode/chapterMode = api）没有网页选择器可转，
# 对应 Animeko 的 json-api 数据源（官方订阅 animeko-subs 的 subs/api/ 就是这种格式）。
# 下面的映射是通用规则，不针对某个站点；从官方源里借鉴的通用写法：
#   * 请求头写成 "名字: 值" 逐行一条的字符串；
#   * 接口域名和网站域名不同时补一条 Origin（接口常常按它做跨域校验）；
#   * 搜索条目用 {id} 拼出详情页地址，剧集用 {subjectId}/{id} 拼出播放页地址；
#   * 带线路的接口用 grouped 通道，没有线路名的用 no-channel；
#   * 剧集类型映射 typeMapping、名称模板 nameTemplate、autoMatch 用官方一致的默认值。
# 转不了的（如章节是 "a$b#c$d" 这种分隔字符串）明确写出原因。
# json-api 必须有 play（取视频地址的请求），这里补不出来，由 official.py 借官方订阅里同一接口的源。

DEFAULT_PAGE_SIZE = 24
EPISODE_TYPE_MAPPING = "main=MainStory\nsp=SP\nova=OVA\noad=OAD\nmovie=MainStory\nex=SP"
_SORT_FIELD = re.compile(r"(order|number|num|index|sort|seq|episode)$", re.I)
_SIZE_KEYS = ("items_per_page", "pageSize", "page_size", "size", "limit", "per_page")


def _headers_string(headers, extra=None):
    items = dict(headers or {})
    for k, v in (extra or {}).items():
        if not any(k.lower() == x.lower() for x in items):
            items[k] = v
    return "\n".join("%s: %s" % (k, v) for k, v in items.items())


def _template(text):
    return (text or "").replace("@keyword", "{keyword}").replace("@source", "{id}")


def _request(req, origin, site_origin, with_keyword):
    """Kazumi 的 request -> json-api 的 request（url / method / body / headers）。"""
    method = str(req.get("method", "GET")).upper()
    if method not in ("GET", "POST"):
        raise ValueError("接口方法 %s 暂不支持" % method)
    url = req.get("url", "")
    if not url:
        raise ValueError("缺少接口地址")
    qs = _query_string(req.get("query")).replace("@source", "{id}")
    if qs:
        url += ("&" if "?" in url else "?") + qs
    body = ""
    if req.get("body") not in (None, "", {}):
        if req.get("bodyType", "json") != "json":
            raise ValueError("接口请求体类型 %s 暂不支持" % req.get("bodyType"))
        body = _template(json.dumps(req["body"], ensure_ascii=False, separators=(",", ":")))
    return {"url": url.replace("@keyword", "{keyword}").replace("@source", "{id}"),
            "method": method, "body": body, "headers": ""}


def _page_size(req):
    for src in (req.get("body") or {}, req.get("query") or {}):
        for k in _SIZE_KEYS:
            if isinstance(src.get(k), int) and src[k] > 0:
                return src[k]
    return DEFAULT_PAGE_SIZE


def _join_path(prefix, path):
    """单线路时，剧集路径是接在线路路径后面的：$.data + $.episodes[*] -> $.data.episodes[*]。"""
    if not prefix or prefix == "$":
        return path
    return prefix.rstrip(".") + "." + path[2:] if path.startswith("$.") else prefix + path


def convert_api_rule(rule, config, res, origin):
    config = config or {}
    if rule.get("searchMode") != "api" and not rule.get("searchApiConfig"):
        return res.fail("章节来自接口，但搜索是网页：json-api 数据源两步都要走接口")
    sapi = rule.get("searchApiConfig") or {}
    capi = rule.get("chapterApiConfig") or {}
    fmt = capi.get("format", "nested")
    if fmt != "nested":
        return res.fail("章节接口格式是 %s（分隔字符串等），Animeko 的 json-api 没有对应的解析方式" % fmt)
    for key in ("episodesPath", "episodeNamePath", "episodeUrlPath"):
        if not capi.get(key):
            return res.fail("章节接口缺少 %s" % key)

    api_origin = _origin(sapi.get("request", {}).get("url", ""))
    if not api_origin:
        return res.fail("搜索接口地址不是完整的 http(s) 地址")
    extra = {"Origin": origin} if api_origin != origin else {}
    try:
        search_req = _request(sapi.get("request", {}), api_origin, origin, True)
        subject_req = _request(capi.get("request", {}), api_origin, origin, False)
    except ValueError as e:
        return res.fail(str(e))
    if "{keyword}" not in search_req["url"] + search_req["body"]:
        return res.fail("搜索接口里没有找到关键词参数")
    if "{id}" not in subject_req["url"] + subject_req["body"]:
        return res.fail("章节接口里没有找到条目 id 参数")
    list_path, name_path, id_path = sapi.get("listPath"), sapi.get("namePath"), sapi.get("sourcePath")
    if not (list_path and name_path and id_path):
        return res.fail("搜索接口缺少 listPath / namePath / sourcePath")

    headers = {}
    headers.update(sapi.get("request", {}).get("headers") or {})
    headers.update(capi.get("request", {}).get("headers") or {})

    page = capi.get("episodePage") or {}
    page_url = page.get("url", "")
    if page_url:
        q = _query_string(page.get("query")).replace("@episodeUrl", "{id}").replace("@source", "{subjectId}")
        ep_tpl = page_url.replace("@episodeUrl", "{id}").replace("@source", "{subjectId}")
        if q:
            ep_tpl += ("&" if "?" in ep_tpl else "?") + q
        cut = page_url.find("@source")
        subject_tpl = (page_url[:cut + len("@source")] if cut >= 0 else origin + "/").replace("@source", "{id}")
    else:
        ep_tpl, subject_tpl = "{id}", origin + "/"
        res.notes.append("章节接口没有 episodePage，剧集地址直接用 id")

    roads, road_name = capi.get("roadsPath") or "", capi.get("roadNamePath") or ""
    sort_field = None
    m = re.match(r"^\$\.(\w+)$", capi.get("episodeUrlPath", ""))
    if m and _SORT_FIELD.search(m.group(1)):
        sort_field = capi["episodeUrlPath"]
    episodes = {
        "selectName": capi["episodeNamePath"],
        "selectId": capi["episodeUrlPath"],
        "selectSort": sort_field or "",
        "selectType": "",
        "episodeUrlTemplate": ep_tpl,
    }
    if sort_field:
        episodes["nameTemplate"] = "{sort} {name}"
    else:
        res.notes.append("接口里没有明确的剧集序号字段，序号只能靠剧集名称识别，请在 Animeko 里确认选集顺序")
    if roads.endswith("[*]") and road_name:
        subject = {"channelFormatId": "grouped",
                   "channelFormatGrouped": {"selectChannels": roads, "selectChannelName": road_name}}
        episodes["selectEpisodes"] = capi["episodesPath"]
    else:
        subject = {"channelFormatId": "no-channel"}
        episodes["selectEpisodes"] = _join_path(roads, capi["episodesPath"])
        res.info.append("接口没有线路名，所有剧集合并为一条")
    subject_req_full = dict(subject_req)
    subject.update({"request": subject_req_full, "episodes": episodes})

    name = rule.get("name", "")
    tier = (config.get("tiers") or {}).get(name, config.get("default_tier", 4))
    res.notes.append("Kazumi 规则里没有播放接口（没有 play）；build 会去官方订阅里找同一接口的源借 play，借不到就不输出")
    res.source = {
        "id": "kazumi-" + slugify(name),
        "factoryId": "json-api",
        "version": 1,
        "arguments": {
            "name": name,
            "description": "",
            "iconUrl": origin + "/favicon.ico",
            "searchConfig": {
                "baseUrl": api_origin,
                "headers": _headers_string(headers, extra),
                "requestInterval": 1000,
                "searchCacheTtl": 7200000,
                "defaultResolution": "1080P",
                "defaultSubtitleLanguage": "CHS",
                "autoMatch": {"enabled": True, "searchUseSubjectNamesCount": 3},
                "search": {
                    "request": search_req,
                    "pageSize": _page_size(sapi.get("request", {})),
                    "selectItems": list_path,
                    "selectName": name_path,
                    "selectId": id_path,
                    "subjectUrlTemplate": subject_tpl,
                },
                "subject": subject,
            },
            "tier": tier,
        },
    }
    res.status = "partial"
    return res
