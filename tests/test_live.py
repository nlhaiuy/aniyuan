"""联网检测相关的自测（用本地模拟站点，不访问外网）：自动修复选择器、替换脆弱写法、
跟随域名跳转、无头浏览器播放检测。"""
import json, os, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
from build import probe, rewrite_origin, merge
from convert import MATCH_VIDEO_URL
from repair import mine_presets
from playcheck import PlayChecker, to_py_regex

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)

SEARCH = """<html><body><div class="module-card-item"><div class="module-card-item-title"><a href="/voddetail/1.html"><strong>葬送的芙莉莲</strong></a></div></div>
<div class="module-card-item"><div class="module-card-item-title"><a href="/voddetail/2.html"><strong>别的番</strong></a></div></div></body></html>"""
DETAIL = """<html><body><div class="module-play-list-content"><a href="/play/1-1.html">第1集</a><a href="/play/1-2.html">第2集</a><a href="/play/1-3.html">第3集</a></div></body></html>"""
PAGES = {
    "/p/direct": "<html><body>x<script>setTimeout(()=>fetch('/m/1.m3u8'),300)</script></body></html>",
    "/p/iframe": "<html><body><iframe src='/p/inner'></iframe></body></html>",
    "/p/inner": "<html><body><script>setTimeout(()=>fetch('/m/2.mp4'),300)</script></body></html>",
    "/p/none": "<html><body>什么都没有</body></html>",
    "/p/captcha": "<html><body>请输入验证码</body></html>",
    "/p/mismatch": "<html><body><script>setTimeout(()=>fetch('/m/3.mp4?x=1'),300)</script></body></html>",
    "/p/dom": "<html><body><video src='/m/4.mp4'></video></body></html>",
}

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, body, ctype="text/html; charset=utf-8", headers=None):
        b = body.encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b)))
        for k, v in (headers or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/s": return self._send(200, SEARCH)
        if path == "/s2":   # 第一个条目的详情页是 404
            return self._send(200, "<html><body><a href='/voddetail/9.html'>葬送的芙莉莲 旧</a><a href='/voddetail/1.html'>葬送的芙莉莲</a></body></html>")
        if path == "/sb":   # 像 Cloudflare 一样拦非浏览器（真 Chromium 会带 Sec-Ch-Ua）
            if not self.headers.get("Sec-Ch-Ua"): return self._send(403, "forbidden")
            return self._send(200, SEARCH)
        if path == "/jump":
            return self._send(302, "", headers={"Location": "http://127.0.0.2:%d/s?wd=x" % self.server.server_address[1]})
        if path == "/voddetail/1.html": return self._send(200, DETAIL)
        if path in PAGES: return self._send(200, PAGES[path])
        if path.startswith("/m/"): return self._send(200, "data", "application/octet-stream")
        self._send(404, "nf")

srv = HTTPServer(("0.0.0.0", 0), H); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
B = "http://127.0.0.1:%d" % port

def src(search_sel, ep_sel, search_url=None):
    return {"id": "t", "factoryId": "web-selector", "version": 2, "arguments": {"name": "t", "description": "d", "iconUrl": "",
        "searchConfig": {"searchUrl": (search_url or B + "/s?wd={keyword}"), "subjectFormatId": "a",
                         "selectorSubjectFormatA": {"selectLists": search_sel, "preferShorterName": True},
                         "channelFormatId": "no-channel",
                         "selectorChannelFormatNoChannel": {"selectEpisodes": ep_sel, "selectEpisodeLinks": ""},
                         "matchVideo": {"matchVideoUrl": MATCH_VIDEO_URL, "matchNestedUrl": "$^", "enableNestedUrl": False,
                                        "scanDomMediaUrls": False, "addHeadersToVideo": {"referer": ""}}}}, "tier": 4}

sess, presets = requests.Session(), mine_presets(None)
cfg = {}

# 1. 选择器完全失效 -> 自动修复
c = dict(origin="kazumi", key="t", source=src(".nope a", ".nope2 a"), notes=[])
probe(c, "葬送的芙莉莲", sess, presets, cfg)
sc = c["source"]["arguments"]["searchConfig"]
check("失效选择器被自动修复并重新通过检测", c["smoke"]["status"] == "ok" and "repaired" in c["smoke"] and c["smoke"]["episode_count"] == 3)
check("修复后选择器指向真实结构", "/voddetail/" in sc["selectorSubjectFormatA"]["selectLists"]
      and "module-play-list-content" in sc["selectorChannelFormatNoChannel"]["selectEpisodes"])
check("修复后描述带标记", c["source"]["arguments"]["description"].startswith("[选择器已自动修复]"))
# 2. 只有剧集选择器坏
c = dict(origin="kazumi", key="t", source=src("a[href*='/voddetail/']", ".nope2 a"), notes=[])
probe(c, "葬送的芙莉莲", sess, presets, cfg)
check("只修坏的那一半（剧集），搜索选择器保持原样", c["smoke"]["status"] == "ok"
      and c["source"]["arguments"]["searchConfig"]["selectorSubjectFormatA"]["selectLists"] == "a[href*='/voddetail/']")
# 3. 能用但脆弱的位置式写法 -> 替换
brit = src("div:nth-of-type(1) > div:nth-of-type(1) > a:nth-of-type(1)", "div:nth-of-type(1) > a")
c = dict(origin="kazumi", key="t", source=brit, notes=[])
probe(c, "葬送的芙莉莲", sess, presets, cfg)
check("位置式写法被更稳的选择器替换（剧集数不少于原来）", c["smoke"]["status"] == "ok" and any("自动修复" in n for n in c["notes"])
      and c["smoke"]["episode_count"] >= 3)
c = dict(origin="kazumi", key="t", source=json.loads(json.dumps(brit)), notes=[])
probe(c, "葬送的芙莉莲", sess, presets, {"replace_brittle": False})
check("replace_brittle=false 时不动", not c["notes"] and "div:nth-of-type" in json.dumps(c["source"]))
# 4. 修不好的保持 fail
dead = src(".nope a", ".nope2 a", B + "/404?wd={keyword}")
c = dict(origin="kazumi", key="t", source=dead, notes=[])
probe(c, "葬送的芙莉莲", sess, presets, cfg)
check("搜索页都打不开：保持原状态，不乱改", c["smoke"]["status"] in ("fail", "blocked") and c["source"] is dead)
# 5. 域名跳转
c = dict(origin="kazumi", key="t", source=src("a[href*='/voddetail/']", ".module-play-list-content a", B + "/jump?wd={keyword}"), notes=[])
c["source"]["arguments"]["iconUrl"] = B + "/favicon.ico"
probe(c, "葬送的芙莉莲", sess, presets, cfg)
check("搜索被跳转到新域名且通过检测：整体换成新域名", c["smoke"]["status"] == "ok"
      and "127.0.0.2" in c["source"]["arguments"]["searchConfig"]["searchUrl"] and "127.0.0.2" in c["source"]["arguments"]["iconUrl"])
check("rewrite_origin 只换域名", rewrite_origin({"a": "http://x.com/p?u=http://y.com"}, "http://x.com", "http://z.com")["a"] == "http://z.com/p?u=http://y.com")

# 5b. 第一个条目详情页打不开 -> 试后面的
c = dict(origin="kazumi", key="t", source=src("a[href*='/voddetail/']", ".module-play-list-content a", B + "/s2?wd={keyword}"), notes=[])
probe(c, "葬送的芙莉莲", sess, presets, cfg)
check("第一个条目详情页 404：自动试下一个", c["smoke"]["status"] == "ok" and c["smoke"]["episode_count"] == 3)

# 5c. 403 -> 浏览器回退
import smoke as smoke_mod
c = dict(origin="kazumi", key="t", source=src("a[href*='/voddetail/']", ".module-play-list-content a", B + "/sb?wd={keyword}"), notes=[])
probe(c, "葬送的芙莉莲", sess, presets, {"repair": False})
check("没有浏览器：被 403 拦住就是 blocked", c["smoke"]["status"] == "blocked")
pc0 = PlayChecker()
smoke_mod.set_browser_fetcher(pc0.fetch)
try:
    c = dict(origin="kazumi", key="t", source=src("a[href*='/voddetail/']", ".module-play-list-content a", B + "/sb?wd={keyword}"), notes=[])
    probe(c, "葬送的芙莉莲", sess, presets, {"repair": False})
    check("403 回退到无头浏览器后通过检测", c["smoke"]["status"] == "ok")
finally:
    smoke_mod.set_browser_fetcher(None)
    pc0.close()

# 6. 播放检测
check("Kotlin 命名分组转成 Python 写法", to_py_regex("(?<v>a)(?<=b)(?<!c)") == "(?P<v>a)(?<=b)(?<!c)")
pc = PlayChecker()
def play(path, scan=False, mv=None):
    s = src("a", "a"); m = s["arguments"]["searchConfig"]["matchVideo"]; m["scanDomMediaUrls"] = scan
    if mv: m["matchVideoUrl"] = mv
    return pc.check(s, B + path, wait_ms=7000)["play"]
try:
    check("直接请求 m3u8 -> ok", play("/p/direct") == "ok")
    check("iframe 里的 mp4 -> ok", play("/p/iframe") == "ok")
    check("什么都没有 -> none", play("/p/none") == "none")
    check("验证码 -> blocked", play("/p/captcha") == "blocked")
    check("出现视频地址但正则认不出 -> mismatch", play("/p/mismatch", mv=r"never\.flv") == "mismatch")
    check("scanDomMediaUrls 能从 <video> 取到 -> ok", play("/p/dom", scan=True, mv=r"$^") == "ok")
finally:
    pc.close()

# 7. 合并时播放结果的优先级
def cand(origin, date, sm):
    return dict(origin=origin, key=origin, date=date, notes=[], smoke=sm, source={"id": origin, "factoryId": "web-selector", "version": 2,
                "arguments": {"name": origin, "iconUrl": "", "searchConfig": {"searchUrl": "https://z.com/s?wd={keyword}"}}})
new = cand("anibaka", 200, {"status": "ok", "play": "none"}); old = cand("kazumi", 100, {"status": "ok", "play": "ok"})
ch, _ = merge([new, old], {})
check("都通过检测时，能播的优先于没抓到视频的", ch[0]["origin"] == "kazumi")
new = cand("anibaka", 200, {"status": "ok", "play": "ok"}); old = cand("kazumi", 100, {"status": "ok", "play": "ok"})
ch, _ = merge([new, old], {})
check("同样能播：取新", ch[0]["origin"] == "anibaka")
sys.exit(1 if bad else 0)
