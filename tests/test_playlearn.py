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
            if MODE["api"] == "login":   # 像 sorani：接口 200，但 canPlay=false、没有视频地址，说请先登录
                return self._send(200, {"code": 200, "data": {"episodeId": ep, "canPlay": False, "message": "请先登录", "playUrl": None}})
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

    # 4b) 播放接口说要先登录（canPlay=false、请先登录）：明确说放弃，不让人手写
    MODE["api"] = "login"
    p4b, why4b = pl.learn(pc, new_source("")["arguments"]["searchConfig"], sample, s, wait_ms=4000)
    check("播放接口要求登录：学不了，原因明确写「要求登录」并说不用手写", p4b is None and "要求登录" in why4b and "不用手写" in why4b and "请先登录" in why4b)
    check("要求登录的原因里不再给「抓到的请求」线索（没有手写的必要）", "抓到的请求" not in why4b)
    c4b = {"source": new_source(""), "needs_play": True, "notes": [], "status": "partial", "smoke": {"status": "ok", "sample": sample}}
    pl.learn_plays([c4b], pc, s, {}, 4500, wait_ms=4000)
    check("learn_plays：备注里写着要求登录，源保持待学", c4b["needs_play"] and any("要求登录" in n for n in c4b["notes"]))
    MODE["api"] = "stable"

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

    # 5b) 主出口没检测到条目、海外直连有样本：用海外样本学
    MODE["api"] = "stable"
    cand5 = {"source": new_source(""), "needs_play": True, "notes": [], "status": "partial",
             "smoke": {"status": "fail", "reason": "打不开"}, "smoke_direct": {"status": "ok", "sample": sample}}
    cache5 = {}
    pl.learn_plays([cand5], pc, s, cache5, 5000, wait_ms=9000)
    check("海外样本回退：主出口没样本时用海外直连的样本学到 play，备注写明来源",
          cand5["source"]["arguments"]["searchConfig"].get("play") and not cand5["needs_play"]
          and any("海外直连检测" in n for n in cand5["notes"]) and "kazumi-demo" in cache5)
    cand5b = {"source": new_source(""), "needs_play": True, "notes": [], "status": "partial", "smoke": {"status": "fail"}, "smoke_direct": {"status": "fail"}}
    pl.learn_plays([cand5b], pc, s, {}, 5001, wait_ms=4000)
    check("主出口和海外都没样本：保持待学，备注说明两边都没有",
          cand5b["needs_play"] and any("主出口和海外直连都没有" in n for n in cand5b["notes"]))
    cand5c = {"source": new_source(""), "needs_play": True, "notes": [], "status": "partial",
              "smoke": {"status": "ok", "sample": sample}, "smoke_direct": {"status": "ok", "sample": {"episodes": [{"id": 999, "url": "x"}]}}}
    check("主出口有样本时优先用主出口的（不被海外样本覆盖）", (lambda c_: (pl.learn_plays([c_], pc, s, {}, 1, wait_ms=9000), c_["source"]["arguments"]["searchConfig"].get("play"))[1])(cand5c)
          and not any("海外直连检测" in n for n in cand5c["notes"]))

    # 5c) 手写 play（play_overrides）
    good_play = copy.deepcopy(cache["kazumi-demo"]["play"])
    c6 = {"source": new_source(""), "needs_play": True, "notes": ["Kazumi 规则里没有播放接口"], "status": "partial", "origin": "kazumi", "key": "demo",
          "smoke": {"status": "ok", "sample": sample}}
    cache6 = {}
    before = HITS["play"]
    pl.learn_plays([c6], None, s, cache6, 6000, overrides={"kazumi:demo": good_play})   # 键用「来源:站点」，没有浏览器也能用
    check("手写 play：用「来源:站点」做键，重放验证通过后采用，备注写明", c6["source"]["arguments"]["searchConfig"].get("play") and not c6["needs_play"]
          and any("手写的 play" in n and "已重放验证" in n for n in c6["notes"]) and HITS["play"] == before + 1)
    check("手写 play 不进缓存（删掉手写项就回到自动学习）", cache6 == {})
    c6b = {"source": new_source(""), "needs_play": True, "notes": [], "status": "partial", "origin": "kazumi", "key": "demo", "smoke": {"status": "ok", "sample": sample}}
    pl.learn_plays([c6b], None, s, {}, 6001, overrides={"kazumi-demo": good_play})
    check("手写 play：也可以用源 id 做键", c6b["source"]["arguments"]["searchConfig"].get("play") is not None)

    bad_play = copy.deepcopy(good_play); bad_play["request"]["url"] = base + "/api/gone"
    c7 = {"source": new_source(""), "needs_play": True, "notes": [], "status": "partial", "origin": "kazumi", "key": "demo", "smoke": {"status": "ok", "sample": sample}}
    cache7 = {}
    pl.learn_plays([c7], pc, s, cache7, 7000, wait_ms=9000, overrides={"kazumi:demo": bad_play})
    check("手写 play 重放不通过：忽略它，说明原因，改用自动学习",
          any("手写的 play 重放没通过" in n for n in c7["notes"]) and c7["source"]["arguments"]["searchConfig"]["play"]["request"]["url"] == base + "/api/play"
          and "kazumi-demo" in cache7)
    c8 = {"source": new_source(""), "needs_play": True, "notes": [], "status": "partial", "origin": "kazumi", "key": "demo", "smoke": {"status": "ok", "sample": sample}}
    pl.learn_plays([c8], None, s, {}, 8000, overrides={"kazumi:demo": {"request": {"url": "ftp://x"}}})
    check("手写 play 写法不对：忽略并说明，源保持待学", c8["needs_play"] and any("写法不对" in n for n in c8["notes"]))
    c9 = {"source": new_source(""), "needs_play": True, "notes": [], "status": "partial", "origin": "kazumi", "key": "demo", "smoke": {"status": "blocked"}}
    pl.learn_plays([c9], None, s, {}, 9000, overrides={"kazumi:demo": good_play})
    check("本次没检测到条目：手写 play 照用，备注写明未验证", c9["source"]["arguments"]["searchConfig"].get("play") and any("未验证" in n for n in c9["notes"]))
    c10 = {"source": new_source(""), "needs_play": True, "notes": [], "status": "partial", "origin": "anibaka", "key": "demo", "smoke": {"status": "ok", "sample": sample}}
    pl.learn_plays([c10], None, s, {}, 10000, overrides={"kazumi:demo": good_play})
    check("手写 play 只对键对得上的来源生效（anibaka:demo 不吃 kazumi:demo 的）", c10["needs_play"])

    vp, why = pl.valid_play({"request": {"url": "https://a.b/x"}, "selectVideoUrl": "$.url"})
    check("valid_play：缺的可选项补默认值（GET、空请求体、回退第一个候选）",
          vp and vp["request"] == {"url": "https://a.b/x", "method": "GET", "body": "", "headers": ""} and vp["fallbackToFirstCandidate"] is True and vp["selectCandidates"] == "")
    check("valid_play：缺 selectVideoUrl / 方法不对 / 不是对象 都拒绝",
          all(pl.valid_play(x)[0] is None for x in ({"request": {"url": "https://a.b"}}, {"request": {"url": "https://a.b", "method": "PUT"}, "selectVideoUrl": "$.u"}, "x", None, {"selectVideoUrl": "$.u"})))

    # 5d0) login_hint 单元：只看路径像播放的接口
    check("login_hint：播放接口响应里写着请先登录",
          "请先登录" in (pl.login_hint([{"url": "https://a.b/api/video/episode/1/play", "method": "GET", "status": 200, "text": '{"message":"请先登录"}'}]) or ""))
    check("login_hint：响应里的中文被转义成 \\uXXXX 也能识别",
          "请先登录" in (pl.login_hint([{"url": "https://a.b/play", "method": "GET", "status": 200, "text": json.dumps({"message": "请先登录"})}]) or ""))
    check("login_hint：评论 / 统计接口说请登录不算", pl.login_hint([{"url": "https://a.b/api/comment/list", "method": "GET", "status": 200, "text": '{"message":"请登录后评论"}'}]) is None)
    check("login_hint：播放接口 401 也算；403（可能是防火墙）不算",
          "401" in (pl.login_hint([{"url": "https://a.b/play", "method": "GET", "status": 401, "text": ""}]) or "")
          and pl.login_hint([{"url": "https://a.b/play", "method": "GET", "status": 403, "text": ""}]) is None)
    check("login_hint：正常响应 / 空列表 / None 都是 None",
          pl.login_hint([{"url": "https://a.b/play", "method": "GET", "status": 200, "text": '{"url":"x.m3u8"}'}]) is None and pl.login_hint([]) is None and pl.login_hint(None) is None)

    # 5d) 学不出来时，备注里带上播放页发出的请求，给手写 play 当线索
    MODE["api"] = "none"
    p5, why5 = pl.learn(pc, new_source("")["arguments"]["searchConfig"], sample, s, wait_ms=4000)
    check("学不出 play：原因里列出播放页发出的请求（方法 + 地址）", p5 is None and "抓到的请求：" in why5 and "play_overrides" in why5)
    MODE["api"] = "stable"

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
