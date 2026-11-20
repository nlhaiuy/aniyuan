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
            return Resp(200, SEARCH, url)
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
    src, note, ex = AL.learn_site(T, [("国内出口", "cn"), ("海外直连", "us")], PRESETS, ["葬送的芙莉莲"])
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
    src, note, ex = AL.learn_site(T, [("国内出口", "cn"), ("海外直连", "us")], PRESETS, ["葬送的芙莉莲"])
    check("国内打不开时换海外直连学到", src is not None and ex == "海外直连")

    # 3) 两边都打不开：学不出来，给出原因
    smoke_mod._get = fake_get({"cn": False, "us": False}, [])
    src, why, ex = AL.learn_site(T, [("国内出口", "cn"), ("海外直连", "us")], PRESETS, ["葬送的芙莉莲"])
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
finally:
    smoke_mod._get, AL.time.sleep = orig_get, orig_sleep

sys.exit(1 if bad else 0)
