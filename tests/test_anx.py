"""AniBaka 转换器 + 同站点合并的自测（不联网）。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from anx2animeko import convert_anx, split_selectors, site_host, source_id
from build import merge, apply_state, collect_manual
from smoke import eval_simple_jsonpath
import domains as D

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)

html = {"id": "t1", "name": "T1", "baseUrl": "https://a.example.com", "headers": {"Referer": "https://a.example.com/"},
        "search": [{"op": "fetch", "url": "/s?wd={keyword}"},
                   {"op": "searchList", "selectors": [".item, .card", "a.x"], "detailPattern": "/v/"}],
        "detail": [{"op": "follow"}, {"op": "episodes", "tabSelectors": [".tab li"], "listSelectors": ["ul.list"]}],
        "play": [{"op": "sniff", "goal": "video"}]}
r = convert_anx(html, {"key": "t1", "rev": 3})
sc = r.source["arguments"]["searchConfig"]
check("html 搜索转成 a 格式", r.status == "ok" and sc["subjectFormatId"] == "a" and sc["searchUrl"] == "https://a.example.com/s?wd={keyword}")
check("容器选择器补 a[href*]，本身是 a 的不重复补",
      sc["selectorSubjectFormatA"]["selectLists"] == ".item a[href*='/v/'], .card a[href*='/v/'], a.x[href*='/v/']")
check("有线路 -> index-grouped", sc["channelFormatId"] == "index-grouped" and sc["selectorChannelFormatFlattened"]["selectChannelNames"] == ".tab li")
check("播放走 WebView 嗅探 + referer", sc["matchVideo"]["scanDomMediaUrls"] and sc["matchVideo"]["addHeadersToVideo"]["referer"] == "https://a.example.com/")
check("id 稳定为 anibaka-<key>（下划线换连字符）", r.source["id"] == "anibaka-t1" and source_id("ios_mifun") == "anibaka-ios-mifun")
check("逗号切分不切方括号/引号里的", split_selectors('a[href*="a,b"], .x:not(.y, .z), .w') == ['a[href*="a,b"]', ".x:not(.y, .z)", ".w"])

# first 分支：HTML 优先于 suggest；只有 suggest 时标记为推测
both = dict(html, search=[{"op": "first", "branches": [[{"op": "maccmsSuggest", "detailUrlTemplate": "/d/{id}.html"}],
            [{"op": "fetch", "url": "/s?wd={keyword}"}, {"op": "searchList", "selectors": [".i"], "detailPattern": "/d/"}]]}])
r2 = convert_anx(both, {"key": "t2"})
check("first 分支里 HTML 优先", r2.source["arguments"]["searchConfig"]["subjectFormatId"] == "a" and not r2.guess)
only = dict(html, search=[{"op": "maccmsSuggest", "detailUrlTemplate": "/d/{id}.html"}])
r3 = convert_anx(only, {"key": "t3"})
jp = r3.source["arguments"]["searchConfig"]["selectorSubjectFormatJsonPathIndexed"]
check("仅 suggest：json-path-indexed + linkTemplate + guess", r3.guess and jp["linkTemplate"] == "/d/{value}.html" and jp["selectLinks"] == "$.list[*]['id']")
js = dict(html, search=[{"op": "fetch", "url": "/api?q={keyword}"}, {"op": "jsonSeries", "listPath": "data.list", "idKey": "id", "nameKey": "title", "detailUrlTemplate": "/a/{id}"}])
check("fetch+jsonSeries 转 JSONPath", convert_anx(js, {"key": "t4"}).source["arguments"]["searchConfig"]["selectorSubjectFormatJsonPathIndexed"]["selectNames"] == "$.data.list[*]['title']")

# 转不了的必须明确报 unsupported
post = dict(html, search=[{"op": "fetch", "url": "/x", "method": "POST", "body": "{}"}, {"op": "jsonSeries", "idKey": "id", "nameKey": "t"}])
check("POST 搜索 -> unsupported", convert_anx(post, {"key": "p"}).status == "unsupported")
torrent = dict(html, detail=[{"op": "torrentRecords"}])
check("磁力站 -> unsupported", convert_anx(torrent, {"key": "q"}).status == "unsupported")
je = dict(html, detail=[{"op": "jsonEpisodes"}])
check("jsonEpisodes -> unsupported", convert_anx(je, {"key": "q"}).status == "unsupported")
crypto = dict(html, play=[{"op": "crypto", "algo": "md5"}])
rc = convert_anx(crypto, {"key": "c"})
check("播放用 crypto -> partial 并提示", rc.status == "partial" and any("crypto" in n for n in rc.notes))
nest = {"id": "n", "name": "N", "baseUrl": "https://n.example.com", "pipeline": {k: html[k] for k in ("search", "detail", "play")}}
check("akianime 式 pipeline 嵌套", convert_anx(nest, {"key": "n"}).source is not None)

# ---- 合并 ----
def cand(origin, key, host, date, sid, smoke=None):
    src = {"id": sid, "factoryId": "web-selector", "version": 2,
           "arguments": {"name": key, "searchConfig": {"searchUrl": "https://%s/s?wd={keyword}" % host}, "iconUrl": ""}}
    c = dict(origin=origin, key=key, source=src, date=date, notes=[])
    if smoke: c["smoke"] = {"status": smoke}
    return c
check("site_host 去掉 www./m.", site_host(cand("a", "k", "www.x.com", 1, "i")["source"]) == "x.com" == site_host(cand("a", "k", "m.x.com", 1, "i")["source"]))
a = cand("anibaka", "foo", "foo.com", 200, "anibaka-foo"); k = cand("kazumi", "Foo", "www.foo.com", 100, "kazumi-foo")
ch, _ = merge([a, k], {})
check("同站点取更新：AniBaka 新", len(ch) == 1 and ch[0]["origin"] == "anibaka")
a["date"], k["date"] = 100, 200
ch, _ = merge([a, k], {})
check("同站点取更新：Kazumi 新，但 id 仍为 anibaka-foo", ch[0]["origin"] == "kazumi" and ch[0]["source"]["id"] == "anibaka-foo")
a["date"] = k["date"] = 100
ch, _ = merge([a, k], {})
check("时间相同取 Kazumi", ch[0]["origin"] == "kazumi")
a["date"], k["date"] = 100, 200
ch, _ = merge([a, k], {"prefer": {"foo.com": "anibaka"}})
check("prefer 强制", ch[0]["origin"] == "anibaka")
z = cand("kazumi", "Zed", "zed.com", 1, "kazumi-zed")
ch, _ = merge([z], {})
check("只有 Kazumi 的站点沿用 kazumi-<name>", ch[0]["source"]["id"] == "kazumi-zed")
ch, _ = merge([cand("kazumi", "A", "a1.com", 1, "i1"), cand("anibaka", "B", "b1.com", 1, "anibaka-b")], {"site_aliases": {"a1.com": "b1.com"}})
check("site_aliases 手动并站", len(ch) == 1)

# ---- 纯纯看番 JS 源 ----
import tempfile
from ebjs import convert_extension
js = ('// @key kazumi.demo\n// @label demo\n// @versionName 1.2.1\n// @cover https://d.example.com/f.ico\n\n'
      'var DEFAULT_BASE_URL = "https://d.example.com/";\nvar SEARCH_URL = "https://d.example.com/s?wd=@keyword";\n'
      'var SEARCH_LIST_XPATH = "//ul/li";\nvar SEARCH_NAME_XPATH = "//h3/a";\nvar SEARCH_RESULT_XPATH = "//h3/a";\n'
      'var CHAPTER_ROADS_XPATH = "//div[@id=\\"p\\"]";\nvar CHAPTER_RESULT_XPATH = "//li/a";\nvar USER_AGENT = "";\nvar REFERER = "";\n'
      'var USE_POST = false;\nvar USE_LEGACY_PARSER = false;\n')
d = tempfile.mkdtemp(); p = os.path.join(d, "kazumi-demo.js"); open(p, "w", encoding="utf-8").write(js)
re_, meta = convert_extension(p)
check("JS 外壳还原成 Kazumi 规则并转换", re_.source is not None and re_.source["arguments"]["iconUrl"] == "https://d.example.com/f.ico"
      and re_.source["arguments"]["searchConfig"]["searchUrl"] == "https://d.example.com/s?wd={keyword}" and re_.source["id"] == "kazumi-demo")
p2 = os.path.join(d, "custom.js"); open(p2, "w").write("// @key a\n// @label A\nfunction x(){}\n")
check("手写 JS 逻辑 -> unsupported", convert_extension(p2)[0].source is None)
open(os.path.join(d, "post.js"), "w").write(js.replace("USE_POST = false", "USE_POST = true"))
check("POST 的 JS 外壳 -> unsupported", convert_extension(os.path.join(d, "post.js"))[0].source is None)

def eb(key, host, date, ver, sid, origin="easybangumi", conf="x"):
    c = cand(origin, key, host, date, sid); c["version"] = ver
    c["source"]["arguments"]["searchConfig"]["sel"] = conf
    return c
kz = eb("K", "s.com", 100, "1.3", "kazumi-s", "kazumi", "new"); ex = eb("e", "s.com", 999, "1.2.1", "kazumi-s", "easybangumi", "old")
ch, _ = merge([kz, ex], {})
check("不同来源只看修改时间、不看版本号：版本更旧但日期更新的胜出", ch[0]["origin"] == "easybangumi")
ab = cand("anibaka", "s", "s.com", 100, "anibaka-s"); ex = eb("e", "s.com", 100, "1.0", "kazumi-s", "easybangumi")
ch, _ = merge([ab, ex], {})
check("日期相同：纯纯看番 > AniBaka，id 仍为 anibaka-s", ch[0]["origin"] == "easybangumi" and ch[0]["source"]["id"] == "anibaka-s")

# ---- 实测优先 ----
a1 = cand("anibaka", "a", "t.com", 200, "anibaka-a", "fail"); k1 = cand("kazumi", "A", "t.com", 100, "kazumi-a", "ok")
ch, d = merge([a1, k1], {})
check("最新的检测明确失败、旧的通过 -> 默认改用通过的", ch[0]["origin"] == "kazumi" and "改用" in d[0]["reason"])
a1 = cand("anibaka", "a", "t.com", 200, "anibaka-a", "unreachable"); k1 = cand("kazumi", "A", "t.com", 100, "kazumi-a", "ok")
ch, _ = merge([a1, k1], {})
check("没有结论（无法访问）的排在通过的后面", ch[0]["origin"] == "kazumi")
a1 = cand("anibaka", "a", "t.com", 200, "anibaka-a", "blocked"); k1 = cand("kazumi", "A", "t.com", 100, "kazumi-a", "unreachable")
ch, _ = merge([a1, k1], {})
check("都没有结论：回到按修改时间", ch[0]["origin"] == "anibaka")
a1 = cand("anibaka", "a", "t.com", 200, "anibaka-a", "fail"); k1 = cand("kazumi", "A", "t.com", 100, "kazumi-a", "ok")
ch, _ = merge([a1, k1], {"select_by_smoke": False})
check("select_by_smoke=false：只看时间", ch[0]["origin"] == "anibaka")
a1 = cand("anibaka", "a", "t.com", 200, "anibaka-a", "fail"); k1 = cand("kazumi", "A", "t.com", 100, "kazumi-a", "ok")
ch, _ = merge([a1, k1], {"prefer": {"t.com": "anibaka"}})
check("prefer 优先于实测", ch[0]["origin"] == "anibaka")

# ---- 内容哈希日期 ----
def hc(origin, key, h, git):
    return dict(origin=origin, key=key, raw_hash=h, date=git)
c1 = [hc("kazumi", "x", "h1", 100)]
st = apply_state(c1, {}, 5000)
check("首次记录：用 git 日期", c1[0]["date"] == 100 and st["kazumi:x"] == {"hash": "h1", "date": 100})
c2 = [hc("kazumi", "x", "h1", 999)]
st2 = apply_state(c2, st, 6000)
check("内容没变：沿用旧日期，不被新的 git 日期（整理提交）带偏", c2[0]["date"] == 100)
c3 = [hc("kazumi", "x", "h2", 300)]
apply_state(c3, st, 6000)
check("内容变了：用更新的 git 日期", c3[0]["date"] == 300)
c4 = [hc("kazumi", "x", "h2", 50)]
apply_state(c4, st, 6000)
check("内容变了但 git 日期不比记录新：用本次同步时间", c4[0]["date"] == 6000)
c5 = [hc("baseline", "y", "h", 10)]
check("baseline 与 anibaka 共用记录", "anibaka:y" in apply_state(c5, {}, 1))

# ---- manual/ ----
m1 = cand("manual", "girigiri", "api.t.com", 1, "manual-g"); k1 = cand("kazumi", "G", "t2.com", 999, "kazumi-g"); ab = cand("anibaka", "g", "t2.com", 500, "anibaka-g")
ch, d = merge([m1, k1, ab], {"site_aliases": {"api.t.com": "t2.com"}})
check("manual 即使更旧也优先，id 仍沿用 AniBaka 的稳定 id", ch[0]["origin"] == "manual" and ch[0]["source"]["id"] == "anibaka-g")
m1 = cand("manual", "g", "t2.com", 1, "manual-g"); a2 = cand("anibaka", "g", "t2.com", 5, "anibaka-g", "ok"); m1["smoke"] = {"status": "fail", "reason": "x"}
ch, _ = merge([m1, a2], {})
check("manual 检测没过也保留，只写备注", ch[0]["origin"] == "manual" and any("仍优先" in n for n in ch[0]["notes"]))
import tempfile, json as _j
td = tempfile.mkdtemp(); open(os.path.join(td, "a.json"), "w").write(_j.dumps({"mediaSources": [{"factoryId": "web-selector", "arguments": {"name": "N", "searchConfig": {"searchUrl": "https://q.com/s?{keyword}"}}}]}))
cm = collect_manual(td)
check("collect_manual 读订阅文件，缺 id 时补 manual-<文件名>", len(cm) == 1 and cm[0]["source"]["id"] == "manual-a" and cm[0]["origin"] == "manual")
check("jsonpath 支持 $.a.b[*].field", eval_simple_jsonpath({"info": {"rows": [{"vod_id": 1}, {"vod_id": 2}]}}, "$.info.rows[*].vod_id") == [1, 2])
check("jsonpath 原有 ['field'] 写法不受影响", eval_simple_jsonpath({"list": [{"id": 7}]}, "$.list[*]['id']") == [7])

# ---- 跟随上游域名 ----
check("registrable：常见后缀", D.registrable("ani.girigirilove.com") == "girigirilove.com" and D.registrable("a.b.example.co.jp") == "example.co.jp")
check("sld：名字部分与后缀无关", D.sld("ani.girigirilove.xyz") == "girigirilove")
def st(urls, origin="manual"):
    return dict(origin=origin, key="m", status="manual", notes=[], date=1, live_hosts=None, source={"id": "i", "factoryId": "web-selector",
        "arguments": {"name": "n", "iconUrl": urls[2], "searchConfig": {"searchUrl": urls[0], "rawBaseUrl": urls[1]}}})
def up(host, date=1):
    return dict(origin="anibaka", key=host, status="ok", notes=[], date=date, live_hosts=[host], source=None)
m = st(["https://m3u8.girigirilove.com/api?q={keyword}", "https://bg.girigirilove.com", "https://ani.girigirilove.com/i.png"])
cur = D.current_domains([up("ani.girigirilove.xyz"), up("girigirilove.xyz"), up("ani.girigirilove.com")])
check("多数上游换了主域名 -> 取多数", cur == {"girigirilove": "girigirilove.xyz"})
check("票数相同取最近改动的", D.current_domains([up("a.x.com", 1), up("a.x.net", 9)]) == {"x": "x.net"})
ch = D.follow_upstream([m, up("ani.girigirilove.xyz"), up("girigirilove.xyz")], lambda s: {"status": "ok"})
sc = m["source"]["arguments"]["searchConfig"]
check("检测通过：主域名整体替换且保留子域名前缀", ch and ch[0][3] and sc["searchUrl"].startswith("https://m3u8.girigirilove.xyz/api")
      and sc["rawBaseUrl"] == "https://bg.girigirilove.xyz" and m["source"]["arguments"]["iconUrl"].startswith("https://ani.girigirilove.xyz/"))
m = st(["https://m3u8.girigirilove.com/api?q={keyword}", "https://bg.girigirilove.com", "https://ani.girigirilove.com/i.png"])
ch = D.follow_upstream([m, up("ani.girigirilove.xyz"), up("girigirilove.xyz")], lambda s: {"status": "fail", "reason": "x"})
check("检测没通过：保持原样并留备注", ch and not ch[0][3] and "girigirilove.com" in m["source"]["arguments"]["searchConfig"]["searchUrl"] and m["notes"])
m = st(["https://m3u8.girigirilove.com/api?q={keyword}", "https://bg.girigirilove.com", "https://ani.girigirilove.com/i.png"], "kazumi"); m["status"] = "ok"
check("自动转换出来的（非静态）源不被这个机制改", D.follow_upstream([m, up("ani.girigirilove.xyz")], lambda s: {"status": "ok"}) == [])
m = st(["https://m3u8.girigirilove.com/api?q={keyword}", "https://bg.girigirilove.com", "https://ani.girigirilove.com/i.png"])
check("上游没换：不动", D.follow_upstream([m, up("ani.girigirilove.com")], lambda s: {"status": "ok"}) == [])
check("rewrite_domain 不误伤别的域名", D.rewrite_domain({"a": "https://x.girigirilove.com/p?u=https://girigirilove.com.cn/z https://other-girigirilove.com"},
      "girigirilove.com", "girigirilove.xyz")["a"] == "https://x.girigirilove.xyz/p?u=https://girigirilove.com.cn/z https://other-girigirilove.com")
sys.exit(1 if bad else 0)
