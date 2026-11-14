"""从播放页学 play：纯函数 + 本机模拟站点（用真的 Chromium 打开播放页，不联网）。"""
import copy, json, os, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import requests
from aniyuan.check import playlearn as pl

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)

# ---------- 纯函数 ----------
data = {"candidates": [{"source_name": "线路1", "url": "https://cdn.x.com/a/index.m3u8"}, {"source_name": "线路2", "url": "https://cdn.x.com/b.mp4"}]}
paths = pl.find_media_paths(data)
check("找到视频地址在列表里的位置", paths[0][0] == ("candidates", "[*]", "url"))
check("路径 -> selectCandidates / selectVideoUrl", pl.selectors_for(paths[0][0]) == ("$.candidates[*]", "$.url"))
check("不在列表里：selectCandidates 为空，从根取", pl.selectors_for(("data", "play", "url")) == ("", "$.data.play.url"))
check("带连字符的键名不支持", pl.selectors_for(("a-b", "url")) is None)
check("两层列表不支持", pl.selectors_for(("a", "[*]", "b", "[*]", "url")) is None)
check("线路字段：值等于详情里的线路名优先", pl.pick_channel_field(data["candidates"][0], ["线路1"]) == "$.source_name")
check("线路字段：没有线路名时按常见字段名猜", pl.pick_channel_field({"line": "x", "url": "u"}, []) == "$.line")
check("线路字段：猜不到就空", pl.pick_channel_field({"url": "u"}, []) == "")
check("普通网页链接不算视频地址", not pl.is_media("https://a.com/play/5"))

t, un = pl.template_json('{"action":"get","episode_id":5,"page":1}', 5, '{"action":"get","episode_id":6,"page":1}', 6)
check("请求体：id 数字换成 {id}（不带引号），常量保持原样", t == '{"action":"get","episode_id":{id},"page":1}' and not un)
t, un = pl.template_json('{"id":"5"}', 5, '{"id":"6"}', 6)
check("请求体：字符串 id 换成 \"{id}\"", t == '{"id":"{id}"}')
t, un = pl.template_json('{"id":5,"page":5}', 5, '{"id":6,"page":5}', 6)
check("请求体：page 碰巧等于第一集的 id，两集对比后不会被误换", t == '{"id":{id},"page":5}')
t, un = pl.template_json('{"id":5,"ts":111}', 5, '{"id":6,"ts":222}', 6)
check("请求体：每次都变的值被识别出来", un == [111])
check("地址模板：{id} 只换整段数字（15 里的 5 不动）", pl.template_text("https://a/p/5?x=15", 5, "https://a/p/6?x=15", 6) == "https://a/p/{id}?x=15")
check("地址模板：两集对不上返回 None", pl.template_text("https://a/p/5", 5, "https://b/p/6", 6) is None)
h = pl.learned_headers({"apikey": "k", "user-agent": "x", "sec-ch-ua": "y", "x-tok": "1", "referer": "r"},
                       {"apikey": "k", "x-tok": "2"}, "")
check("请求头：只留两次一致、不是浏览器常规头的", h == "apikey: k")
check("请求头：公共请求头里已有的不重复抄", pl.learned_headers({"apikey": "k"}, {"apikey": "k"}, "apikey: k") == "")

# ---------- 模拟站点 ----------
MODE = {"api": "stable"}   # stable / timestamp / none
HITS = {"play": 0}

PAGE = """<!doctype html><html><body><div id=player>play</div><script>
const ep = location.pathname.split('/').pop();
fetch('/api/config').then(r => r.json());
if (%(mode)r !== 'none') {
  const body = {action: 'get', episode_id: Number(ep), page: 1};
  if (%(mode)r === 'timestamp') body.ts = Date.now() + Math.random();
  fetch('/api/play', {method: 'POST', headers: {apikey: 'k', 'Content-Type': 'application/json'}, body: JSON.stringify(body)});
}
</script></body></html>"""

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, obj, ctype="application/json"):
        raw = (obj if isinstance(obj, str) else json.dumps(obj)).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(raw)))
        self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        if self.path.startswith("/anime/"):
            return self._send(200, PAGE % {"mode": MODE["api"]}, "text/html; charset=utf-8")
        if self.path == "/api/config":
            return self._send(200, {"theme": "dark"})
        self._send(404, {})
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.path == "/api/play":
            HITS["play"] += 1
            if self.headers.get("apikey") != "k":
                return self._send(401, {"error": "key"})
            ep = body.get("episode_id")
            return self._send(200, {"candidates": [{"source_name": "线路1", "url": "https://cdn.example.com/%s/index.m3u8" % ep},
                                                   {"source_name": "线路2", "url": "https://cdn.example.com/%s/b.mp4" % ep}]})
        self._send(404, {})

srv = HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d" % srv.server_port
sample = {"subject_id": 1, "channels": ["线路1", "线路2"], "episodes": [
    {"id": 5 + i, "name": "第%d集" % (i + 1), "channel": "线路1", "url": "%s/anime/1/play/%d" % (base, 5 + i)} for i in range(3)]}

def new_source(headers=""):
    return {"id": "kazumi-demo", "factoryId": "json-api", "arguments": {"name": "demo", "searchConfig": {
        "baseUrl": base, "headers": headers,
        "subject": {"request": {"url": base + "/detail", "method": "GET", "body": "", "headers": ""},
                    "episodes": {"selectId": "$.id", "episodeUrlTemplate": base + "/anime/{subjectId}/play/{id}"}}}}}

from aniyuan.check.playcheck import PlayChecker
s = requests.Session(); s.trust_env = False
pc = PlayChecker()
try:
    # 1) 正常：学到、验证通过
    MODE["api"] = "stable"
    sc = new_source("")["arguments"]["searchConfig"]
    play, note = pl.learn(pc, sc, sample, s, wait_ms=9000)
    print("   ", note)
    check("学到了 play 且重放验证通过", play is not None and "重放验证" in note)
    if play:
        check("请求：地址 / 方法 / 请求体里的剧集 id 换成 {id}",
              play["request"]["url"] == base + "/api/play" and play["request"]["method"] == "POST"
              and play["request"]["body"] == '{"action":"get","episode_id":{id},"page":1}')
        check("请求头：公共请求头里没有 apikey 时抄过来", play["request"]["headers"] == "apikey: k")
        check("候选 / 视频地址 / 线路字段", play["selectCandidates"] == "$.candidates[*]" and play["selectVideoUrl"] == "$.url"
              and play["selectCandidateChannel"] == "$.source_name" and play["fallbackToFirstCandidate"] is False)

    # 2) 公共请求头里已经有 apikey：不重复
    sc2 = new_source("apikey: k")["arguments"]["searchConfig"]
    play2, _ = pl.learn(pc, sc2, sample, s, wait_ms=9000)
    check("公共请求头已有 apikey：play 里不重复", play2 is not None and play2["request"]["headers"] == "")

    # 3) 请求体里有每次都变的值：学不了，给出原因
    MODE["api"] = "timestamp"
    p3, why = pl.learn(pc, new_source("")["arguments"]["searchConfig"], sample, s, wait_ms=9000)
    check("请求体带时间戳：学不了并说明原因", p3 is None and "每次都会变" in why)

    # 4) 页面根本不发接口请求
    MODE["api"] = "none"
    p4, why = pl.learn(pc, new_source("")["arguments"]["searchConfig"], sample, s, wait_ms=4000)
    check("页面没有带视频地址的接口：学不了并说明原因", p4 is None and "没有发出带视频地址的 JSON 接口" in why)

    # 5) learn_plays：学到后写缓存；第二次只用缓存（不开浏览器）
    MODE["api"] = "stable"
    cand = {"source": new_source(""), "needs_play": True, "notes": ["Kazumi 规则里没有播放接口"], "status": "partial",
            "smoke": {"status": "ok", "sample": sample}}
    cache = {}
    pl.learn_plays([cand], pc, s, cache, 1000, wait_ms=9000)
    sc5 = cand["source"]["arguments"]["searchConfig"]
    check("learn_plays：写进 play、清掉待学标记、写缓存",
          sc5.get("play") and not cand["needs_play"] and "kazumi-demo" in cache and cache["kazumi-demo"]["learned"] == 1000)
    check("learn_plays：备注写明来源", any(n.startswith("播放接口（play）") for n in cand["notes"]) and not any("没有播放接口" in n for n in cand["notes"]))

    before = HITS["play"]
    cand2 = {"source": new_source(""), "needs_play": True, "notes": [], "status": "partial", "smoke": {"status": "ok", "sample": sample}}
    pl.learn_plays([cand2], None, s, cache, 2000)   # 没有浏览器
    check("缓存命中：不用浏览器，只重放验证一次", cand2["source"]["arguments"]["searchConfig"].get("play") and HITS["play"] == before + 1
          and any("沿用" in n for n in cand2["notes"]))

    MODE["api"] = "none"
    cand3 = {"source": new_source(""), "needs_play": True, "notes": [], "status": "partial", "smoke": {"status": "ok", "sample": sample}}
    cache3 = {"kazumi-demo": {"fp": "stale", "play": cache["kazumi-demo"]["play"], "learned": 1}}
    pl.learn_plays([cand3], pc, s, cache3, 3000, wait_ms=4000)
    check("接口指纹变了：缓存作废，重新学（这次学不到，保持待学）",
          cand3["needs_play"] and not cand3["source"]["arguments"]["searchConfig"].get("play") and any("学习 play 失败" in n for n in cand3["notes"]))

    cand4 = {"source": new_source(""), "needs_play": True, "notes": [], "status": "partial", "smoke": {"status": "blocked"}}
    cache4 = {"kazumi-demo": {"fp": pl.fingerprint(cand4["source"]["arguments"]["searchConfig"]), "play": cache["kazumi-demo"]["play"], "learned": 1}}
    pl.learn_plays([cand4], None, s, cache4, 4000)
    check("本次没检测到条目（被拦）：沿用缓存的 play，备注写明未验证",
          cand4["source"]["arguments"]["searchConfig"].get("play") and any("未验证" in n for n in cand4["notes"]))

    # 6) check_plays：带 play 的 json-api 源每次重放验证，写进 smoke.play
    MODE["api"] = "stable"
    good = {"source": new_source(""), "smoke": {"status": "ok", "sample": sample}}
    good["source"]["arguments"]["searchConfig"]["play"] = cache["kazumi-demo"]["play"]
    broken = copy.deepcopy(good)
    broken["source"]["arguments"]["searchConfig"]["play"]["request"]["url"] = base + "/api/gone"
    no_play = {"source": new_source(""), "smoke": {"status": "ok", "sample": sample}}
    web = {"source": {"factoryId": "web-selector", "arguments": {"searchConfig": {}}}, "smoke": {"status": "ok"}}
    pl.check_plays([good, broken, no_play, web], s)
    check("check_plays：play 能取到视频地址 -> ok", good["smoke"]["play"] == "ok" and "cdn.example.com" in good["smoke"]["play_reason"])
    check("check_plays：play 接口失效 -> none，写明原因", broken["smoke"]["play"] == "none" and "404" in broken["smoke"]["play_reason"])
    check("check_plays：没有 play / 不是 json-api 的不动", "play" not in no_play["smoke"] and "play" not in web["smoke"])
finally:
    pc.close()
    srv.shutdown()

print("\n%d 项未通过" % bad if bad else "\n全部通过")
sys.exit(1 if bad else 0)
