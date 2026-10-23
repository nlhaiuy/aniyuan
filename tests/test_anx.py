"""AniBaka 转换器 + 同站点合并的自测（不联网）。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from anx2animeko import convert_anx, split_selectors, site_host, source_id
from build import merge

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
k["smoke"], a["smoke"] = {"status": "fail"}, {"status": "ok"}
ch, _ = merge([a, k], {"prefer_working": True})
check("prefer_working：新的没过就用能过的", ch[0]["origin"] == "anibaka")
ch, _ = merge([a, k], {})
check("默认：新的没过仍取新的，但在备注里提示", ch[0]["origin"] == "kazumi" and any("自动检测未通过" in n for n in ch[0]["notes"]))
z = cand("kazumi", "Zed", "zed.com", 1, "kazumi-zed")
ch, _ = merge([z], {})
check("只有 Kazumi 的站点沿用 kazumi-<name>", ch[0]["source"]["id"] == "kazumi-zed")
ch, _ = merge([cand("kazumi", "A", "a1.com", 1, "i1"), cand("anibaka", "B", "b1.com", 1, "anibaka-b")], {"site_aliases": {"a1.com": "b1.com"}})
check("site_aliases 手动并站", len(ch) == 1)
sys.exit(1 if bad else 0)
