"""自动学习（check/autolearn.py）的自测：用假页面代替网络，不联网。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aniyuan.check import autolearn as AL
from aniyuan.check import smoke as smoke_mod
from aniyuan.check.repair import DEFAULT_PATTERNS, DEFAULT_CONTAINERS, DEFAULT_LISTS

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)

PRESETS = dict(patterns=list(DEFAULT_PATTERNS), containers=list(DEFAULT_CONTAINERS), lists=list(DEFAULT_LISTS))

SEARCH = """<html><body>
<div class="module-card-item"><div class="module-card-item-title"><a href="/voddetail/101.html">葬送的芙莉莲</a></div></div>
<div class="module-card-item"><div class="module-card-item-title"><a href="/voddetail/102.html">别的番剧</a></div></div>
</body></html>"""
DETAIL = """<html><body><div class="module-play-list-content">
<a href="/vodplay/101-1-1.html">第1集</a><a href="/vodplay/101-1-2.html">第2集</a><a href="/vodplay/101-1-3.html">第3集</a>
</div></body></html>"""


class Resp:
    def __init__(self, status, text, url):
        self.status_code, self.text, self.url = status, text, url


def fake_get(site_ok, calls):
    """site_ok: {session 名: 能不能打开}；只有 /index.php/vod/search.html 搜得出结果。"""
    def _get(url, session, timeout, ua=None):
        calls.append((session, url))
        if not site_ok.get(session):
            raise OSError("unreachable")
        if "/index.php/vod/search.html" in url:
            return Resp(200, "<html><body>没有结果</body></html>" if "zqxjkv" in url else SEARCH, url)
        if "/voddetail/101" in url:
            return Resp(200, DETAIL, url)
        return Resp(404, "", url)
    return _get


T = dict(key="gpjda", name="gpjda", origin="https://www.gpjda.com", host="www.gpjda.com")
orig_get, orig_sleep = smoke_mod._get, AL.time.sleep
AL.time.sleep = lambda s: None
try:
    # 1) 国内出口能打开：直接学出规则，出口是国内
    calls = []
    smoke_mod._get = fake_get({"cn": True, "us": True}, calls)
    src, note, ex, guess = AL.learn_site(T, [("国内出口", "cn"), ("海外直连", "us")], PRESETS, ["葬送的芙莉莲"])
    sc = (src or {"arguments": {"searchConfig": {}}})["arguments"]["searchConfig"]
    check("学出搜索地址（第一个就对，后面的不用再试）", sc.get("searchUrl") == "https://www.gpjda.com/index.php/vod/search.html?wd={keyword}"
          and all(s == "cn" for s, _ in calls))
    check("搜索选择器命中关键词、限定 /voddetail/", "a[href*='/voddetail/']" in sc["selectorSubjectFormatA"]["selectLists"])
    check("剧集选择器选到 3 集的列表", sc["selectorChannelFormatNoChannel"]["selectEpisodes"].startswith(".module-play-list-content"))
    check("格式：web-selector、id 带 aniyuan-、有 matchVideo", src["factoryId"] == "web-selector" and src["id"] == "aniyuan-gpjda"
          and sc["matchVideo"]["scanDomMediaUrls"] and sc["rawBaseUrl"] == "https://www.gpjda.com")
    check("备注写明在国内出口学到", ex == "国内出口" and "国内出口" in note)

    # 2) 国内出口打不开、海外直连能：换出口学到，备注里说明
    calls = []
    smoke_mod._get = fake_get({"cn": False, "us": True}, calls)
    src, note, ex, guess = AL.learn_site(T, [("国内出口", "cn"), ("海外直连", "us")], PRESETS, ["葬送的芙莉莲"])
    check("国内打不开时换海外直连学到", src is not None and ex == "海外直连")

    # 3) 两边都打不开：学不出来，给出原因
    smoke_mod._get = fake_get({"cn": False, "us": False}, [])
    src, why, ex, guess = AL.learn_site(T, [("国内出口", "cn"), ("海外直连", "us")], PRESETS, ["葬送的芙莉莲"])
    check("两边都打不开 -> 学不出来并给原因", src is None and "打不开" in why)

    # 4) 选站点：已有可用来源的站、磁力站不学；规则里第一个域名（baseUrl）才是站点
    def cand(origin, key, source, status, hosts):
        return dict(origin=origin, key=key, source=source, status=status, live_hosts=hosts, notes=[], info=[])
    ok_src = {"id": "x", "factoryId": "web-selector", "arguments": {"searchConfig": {"searchUrl": "https://www.covered.com/s?wd={keyword}"}}}
    cands = [
        cand("anibaka", "covered", ok_src, "ok", ["www.covered.com"]),
        cand("easybangumi", "kazumi-covered", None, "unsupported", ["www.covered.com"]),   # 同站已有来源
        cand("anibaka", "gpjda", None, "unsupported", ["www.gpjda.com", "cdn.img.com"]),
        cand("anibaka", "dmhy", None, "unsupported", ["share.dmhy.org"]),                 # 磁力站
        cand("easybangumi", "yhw", None, "unsupported", []),                              # 没有域名线索
        cand("baseline", "zzz", None, "baseline", ["www.zzz.com"]),
    ]
    ts = AL.targets(cands, {})
    check("只学没有来源可用的站：gpjda", [t["host"] for t in ts] == ["www.gpjda.com"] and ts[0]["origin"] == "https://www.gpjda.com")
    ts = AL.targets(cands, {"learn_sites": [{"url": "https://www.manual.org", "name": "手动站"}]})
    check("config.learn_sites 手动指定的站也学", [t["host"] for t in ts] == ["www.manual.org", "www.gpjda.com"] and ts[0]["name"] == "手动站")
    check("不像域名的（版本号 / IP / 没有点）不学", not any(AL._is_hostname(h) for h in ["0.6", "1.2.3.4", "localhost", "", None, "a_b.com"])
          and all(AL._is_hostname(h) for h in ["www.gpjda.com", "dm.fsdm02.com", "hanimeone.me"]))
    bogus = AL.targets([cand("kazumi", "v", None, "unsupported", ["0.6"])], {})
    check("live_hosts 里是 0.6 这种东西 -> 没有要学的站", bogus == [])
    check("learn_max_sites 限制个数", len(AL.targets(cands, {"learn_max_sites": 0})) == 0)

    # 5) learn_cands：出候选、写缓存；缓存沿用；失败有负缓存；检测失败清缓存
    calls = []
    smoke_mod._get = fake_get({"cn": True}, calls)
    cache, cs = {}, [cand("anibaka", "gpjda", None, "unsupported", ["www.gpjda.com"])]
    made = AL.learn_cands(cs, "cn", None, PRESETS, cache, 1000, {})
    c = made[0] if made else {}
    check("出一个 learned 候选并追加进候选表", len(made) == 1 and c["origin"] == "learned" and c["source"] is not None and cs[-1] is c)
    check("候选带来源说明 / 日期 / 域名，guess 为假", c["date"] == 1000 and c["date_basis"] == "自动学习" and not c["guess"]
          and c["live_hosts"] == ["www.gpjda.com"])
    check("写进缓存（按主域名）", "gpjda.com" in cache and cache["gpjda.com"]["source"]["id"] == "aniyuan-gpjda")
    n = len(calls)
    cs2 = [cand("anibaka", "gpjda", None, "unsupported", ["www.gpjda.com"])]
    made2 = AL.learn_cands(cs2, "cn", None, PRESETS, cache, 1000 + 86400, {})
    check("7 天内沿用缓存、不再抓页面", len(made2) == 1 and len(calls) == n and "沿用" in made2[0]["notes"][0])
    made3 = AL.learn_cands([cand("anibaka", "gpjda", None, "unsupported", ["www.gpjda.com"])], "cn", None, PRESETS, cache,
                           1000 + 8 * 86400, {})
    check("超过 7 天重新学", len(made3) == 1 and len(calls) > n)

    smoke_mod._get = fake_get({"cn": False}, [])
    cache2 = {}
    AL.learn_cands([cand("anibaka", "gpjda", None, "unsupported", ["www.gpjda.com"])], "cn", None, PRESETS, cache2, 1000, {})
    check("学不出来记负缓存", "fail" in cache2.get("gpjda.com", {}))
    calls = []
    smoke_mod._get = fake_get({"cn": True}, calls)
    m = AL.learn_cands([cand("anibaka", "gpjda", None, "unsupported", ["www.gpjda.com"])], "cn", None, PRESETS, cache2, 1000 + 86400, {})
    check("3 天内不重试失败的站", m == [] and calls == [])
    m = AL.learn_cands([cand("anibaka", "gpjda", None, "unsupported", ["www.gpjda.com"])], "cn", None, PRESETS, cache2, 1000 + 4 * 86400, {})
    check("3 天后重试", len(m) == 1)

    made[0]["smoke"] = {"status": "fail", "reason": "选择器没选中"}
    AL.finalize_cache(made, cache, 2000)
    check("检测明确失败 -> 缓存改成失败记录，下次重学", "fail" in cache["gpjda.com"] and "source" not in cache["gpjda.com"])
    made3[0]["smoke"] = {"status": "blocked", "reason": "HTTP 403"}
    cache3 = {"gpjda.com": {"source": made3[0]["source"], "at": 1}}
    AL.finalize_cache(made3, cache3, 2000)
    check("被拦 / 打不开（没结论）不清缓存", "source" in cache3["gpjda.com"])

    # ---------------- 扩展：JSON suggest 接口 / 多线路 / 验证码猜测 / UA / 验证码分类 ----------------
    import json as _json
    SUGGEST = _json.dumps({"code": 1, "list": [{"id": 777, "name": "葬送的芙莉莲", "en": "x"}, {"id": 778, "name": "别的", "en": "y"}]})
    def fake_json(calls):
        def _get(url, session, timeout, ua=None):
            calls.append(url)
            if "/index.php/ajax/suggest?mid=1&wd=" in url and "limit" not in url:
                return Resp(200, SUGGEST, url)
            if "/voddetail/777.html" in url:
                return Resp(200, DETAIL, url)
            return Resp(404, "", url)
        return _get
    calls = []
    smoke_mod._get = fake_json(calls)
    src, note, ex, guess = AL.learn_site(T, [("国内出口", "cn")], PRESETS, ["葬送的芙莉莲"])
    jp = ((src or {}).get("arguments", {}).get("searchConfig", {}).get("selectorSubjectFormatJsonPathIndexed")) or {}
    check("网页搜索都 404 时试 suggest 接口，学成 json-path-indexed",
          src is not None and src["arguments"]["searchConfig"]["subjectFormatId"] == "json-path-indexed"
          and jp.get("selectLinks") == "$.list[*]['id']" and jp.get("selectNames") == "$.list[*]['name']")
    check("详情页地址从常见写法里试出来（/voddetail/{value}.html）", jp.get("linkTemplate") == "/voddetail/{value}.html")
    check("JSON 搜索源的搜索地址带 {keyword}", "{keyword}" in src["arguments"]["searchConfig"]["searchUrl"]
          and "ajax/suggest" in src["arguments"]["searchConfig"]["searchUrl"])
    # 学出来的 JSON 选择器要能被检测代码解析（和 smoke 同一套解析）
    ids = smoke_mod.eval_simple_jsonpath(_json.loads(SUGGEST), jp["selectLinks"])
    check("JSON 选择器能被检测代码解析", ids == [777, 778])
    calls404 = []
    def all404(url, session, timeout, ua=None):
        calls404.append(url)
        return Resp(404, "", url)
    smoke_mod._get = all404
    r404 = AL.learn_site(T, [("国内出口", "cn")], PRESETS, ["葬送的芙莉莲", "海贼王"])
    check("全 404：学不出来，且换关键词不重复敲 404 的地址（每个地址只请求一次）",
          r404[0] is None and len(calls404) == len(AL.SEARCH_PATHS) + len(AL.JSON_PATHS) and len(set(calls404)) == len(calls404))
    smoke_mod._get = fake_json([])

    # 多线路：两条线路 + 两个标签
    MULTI = """<html><body>
<div class="module-tab-items"><div class="module-tab-item"><span>线路一</span></div><div class="module-tab-item"><span>线路二</span></div></div>
<div class="module-play-list-content"><a href="/vodplay/101-1-1.html">第1集</a><a href="/vodplay/101-1-2.html">第2集</a></div>
<div class="module-play-list-content"><a href="/vodplay/101-2-1.html">第1集</a><a href="/vodplay/101-2-2.html">第2集</a></div>
</body></html>"""
    ch = AL.find_channels(MULTI, ".module-play-list-content a")
    check("线路标签数量和线路列表对得上 -> 多线路", ch == (".module-tab-item", ".module-play-list-content"))
    check("只有一条线路 -> 不分线路", AL.find_channels(DETAIL, ".module-play-list-content a") is None)
    check("标签数量对不上 -> 不分线路", AL.find_channels(MULTI.replace('<div class="module-tab-item"><span>线路二</span></div>', ""), ".module-play-list-content a") is None)
    eps = AL._episodes(MULTI, "https://x.com/vod/1", PRESETS, "https://x.com")
    check("多线路：按线路取到 4 集（线路 URL 不同）", eps is not None and eps[1] == 4 and eps[2] is not None)
    src2 = AL.build_source("k", "K", "https://x.com", "x.com", "/s?wd={keyword}", "a.x", ".module-play-list-content a", channels=eps[2])
    sc2 = src2["arguments"]["searchConfig"]
    check("多线路源：index-grouped + 区分线路名", sc2["channelFormatId"] == "index-grouped"
          and sc2["selectorChannelFormatFlattened"]["selectChannelNames"] == ".module-tab-item"
          and sc2["selectMedia"]["distinguishChannelName"] is True)
    check("学到的规则带统一 UA", sc2["userAgent"].startswith("Mozilla/5.0"))
    check("单线路规则 distinguishChannelName 为假", AL.build_source("k", "K", "https://x.com", "x.com", "/s", "a", "b")["arguments"]["searchConfig"]["selectMedia"]["distinguishChannelName"] is False)

    # JSON 结果识别的边界
    check("嵌套在 data.list 里也能找到", AL.find_json_results(_json.dumps({"data": {"list": [{"vod_id": 5, "vod_name": "葬送的芙莉莲"}]}}), "葬送的芙莉莲")
          == ("$.data.list[*]['vod_id']", "$.data.list[*]['vod_name']", 5))
    check("名称里没有关键词 -> 不是搜索结果", AL.find_json_results(_json.dumps({"list": [{"id": 1, "name": "别的"}]}), "葬送的芙莉莲") is None)
    check("不是 JSON -> None", AL.find_json_results("<html>", "葬送的芙莉莲") is None)

    # 验证码：分类、猜测候选
    MACCMS_CAPTCHA = '<html><body><p>请输入验证码</p><img src="/index.php/verify/index.html?"><input name="verify"></body></html>'
    CF = "<html><title>Just a moment...</title><div id='cf-challenge'></div></html>"
    check("MacCMS 图片验证码被认出来", smoke_mod.captcha_kind(MACCMS_CAPTCHA) == "maccms")
    check("Cloudflare 挑战被认出来", smoke_mod.captcha_kind(CF) == "cloudflare")
    check("GoEdge 防火墙验证归 waf", smoke_mod.captcha_kind('<title>系统安全验证</title><img src="/WAF/VERIFY/CAPTCHA/x">') == "waf")
    check("首页兜底被认出（乱关键词页面一样）", AL.is_catch_all('<a href="/a">1</a><a href="/b">2</a>', '<a href="/a">1</a><a href="/b">2</a>')
          and not AL.is_catch_all('<a href="/a">1</a>', '<a href="/z">2</a>'))
    check("别的验证页归 other", smoke_mod.captcha_kind("<html>请完成安全验证</html>") == "other")
    check("拦截原因里写明类型", "自动 solver" in smoke_mod.blocked_reason(MACCMS_CAPTCHA) and "Cloudflare" in smoke_mod.blocked_reason(CF, "详情页"))

    def fake_captcha(kind_html):
        def _get(url, session, timeout, ua=None):
            return Resp(200, kind_html, url)
        return _get
    smoke_mod._get = fake_captcha(MACCMS_CAPTCHA)
    src, note, ex, guess = AL.learn_site(T, [("国内出口", "cn")], PRESETS, ["葬送的芙莉莲"])
    sc3 = (src or {"arguments": {"searchConfig": {}}})["arguments"]["searchConfig"]
    check("MacCMS 验证码站：页面学不了，给一条猜测候选", src is not None and guess is True and "猜" in note
          and sc3["searchUrl"].endswith("/index.php/vod/search.html?wd={keyword}") and "/voddetail/" in sc3["selectorSubjectFormatA"]["selectLists"])
    check("猜测候选的描述里标明未验证", src["arguments"]["description"].startswith("[自动猜测，未验证]"))
    smoke_mod._get = fake_captcha(CF)
    src, note, ex, guess = AL.learn_site(T, [("国内出口", "cn")], PRESETS, ["葬送的芙莉莲"])
    check("Cloudflare 站：不猜，直接学不出来", src is None and guess is False)
    smoke_mod._get = fake_captcha(MACCMS_CAPTCHA)
    cache4, cs4 = {}, [cand("anibaka", "gpjda", None, "unsupported", ["www.gpjda.com"])]
    made4 = AL.learn_cands(cs4, "cn", None, PRESETS, cache4, 1000, {})
    check("猜测候选的 guess 标记带进候选和缓存（排在有实测的后面）", len(made4) == 1 and made4[0]["guess"] is True
          and cache4["gpjda.com"]["guess"] is True)

    # ---------------- 合理性检查（真实站点上出过：搜索选到 87 条里命中 1 条、剧集选到 2360 条） ----------------
    WIDE_SEARCH = "<html><body>" + "".join('<h4><a href="/voddetail/%d.html">%s</a></h4>' % (i, "葬送的芙莉莲" if i == 0 else "别的番%d" % i)
                                           for i in range(70)) + "</body></html>"
    MANY_EPS = '<html><body><div class="tab-pane">' + "".join('<a href="/vodplay/1-1-%d.html">第%d集</a>' % (i, i) for i in range(1, 121)) + "</div></body></html>"
    def fake_wide(search_html, detail_html):
        def _get(url, session, timeout, ua=None):
            if "/index.php/vod/search.html" in url:
                return Resp(200, "<html><body>没有结果</body></html>" if "zqxjkv" in url else search_html, url)
            if "/voddetail/" in url:
                return Resp(200, detail_html, url)
            return Resp(404, "", url)
        return _get
    smoke_mod._get = fake_wide(WIDE_SEARCH, DETAIL)
    src, why, ex, guess = AL.learn_site(T, [("国内出口", "cn")], PRESETS, ["葬送的芙莉莲"])
    check("搜索选择器选到太多条（把页面所有链接都选进来）-> 不采用", src is None and "太宽" in why)
    smoke_mod._get = fake_wide(SEARCH, MANY_EPS)
    src, why, ex, guess = AL.learn_site(T, [("国内出口", "cn")], PRESETS, ["葬送的芙莉莲"])
    check("葬送的芙莉莲不可能有 120 集 -> 剧集选择器太宽，不采用", src is None and "太宽" in why)
    check("合理性函数：已知关键词按 80、其它按 1500", AL.plausible_episodes(28, "葬送的芙莉莲") and not AL.plausible_episodes(81, "葬送的芙莉莲")
          and AL.plausible_episodes(1100, "海贼王") and not AL.plausible_episodes(2360, "海贼王") and not AL.plausible_episodes(0, "x"))
    smoke_mod._get = fake_get({"cn": True}, [])
    old_entry = {"gpjda.com": {"source": {"id": "aniyuan-gpjda", "factoryId": "web-selector", "arguments": {"searchConfig": {"rawBaseUrl": "https://www.gpjda.com"}}},
                               "note": "旧版本学的", "exit": "国内出口", "at": 1000}}   # 没有 v：旧版本（没有合理性检查）写的
    made5 = AL.learn_cands([cand("anibaka", "gpjda", None, "unsupported", ["www.gpjda.com"])], "cn", None, PRESETS, old_entry, 1000 + 3600, {})
    check("旧版本缓存不沿用：重新学（学出来的是新规则，不是旧缓存里的）",
          len(made5) == 1 and "沿用" not in made5[0]["notes"][0] and old_entry["gpjda.com"].get("v") == AL.CACHE_VERSION)
finally:
    smoke_mod._get, AL.time.sleep = orig_get, orig_sleep

sys.exit(1 if bad else 0)
