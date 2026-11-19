"""国内 / 海外两个出口的对照检测：海外直连不能借用走代理的浏览器回退；结果只用于对比，不影响主检测。"""
import os, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aniyuan.build import direct_pass, exit_compare
from aniyuan.check import smoke as smoke_mod

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)

SEARCH = "<html><body><a class='hit' href='/d/1'>葬送的芙莉莲</a></body></html>"
DETAIL = "<html><body><div class='eps'><a href='/p/1'>第1集</a><a href='/p/2'>第2集</a></div></body></html>"

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body="x"):
        b = body.encode(); self.send_response(code); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/kw/s":
            from urllib.parse import unquote
            return self.send(200, SEARCH.replace("/d/1", "/ok/d") if "海贼王" in unquote(self.path) else "<html><body>无结果</body></html>")
        if p == "/ok/s": return self.send(200, SEARCH.replace("/d/1", "/ok/d"))
        if p == "/ok/d": return self.send(200, DETAIL)
        if p == "/blocked/s": return self.send(403, "Forbidden")          # 海外服务器被拦
        if p == "/dead/s": return self.send(502)
        self.send(404)

srv = HTTPServer(("127.0.0.1", 0), H); B = "http://127.0.0.1:%d" % srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

def cand(name, path, status="ok", source=True):
    src = {"id": name, "factoryId": "web-selector", "version": 2, "arguments": {"name": name, "description": "", "iconUrl": "",
           "searchConfig": {"searchUrl": B + path + "?wd={keyword}", "subjectFormatId": "a",
                            "selectorSubjectFormatA": {"selectLists": "a.hit", "preferShorterName": True},
                            "channelFormatId": "no-channel",
                            "selectorChannelFormatNoChannel": {"selectEpisodes": ".eps a", "selectEpisodeLinks": ""}}}}
    return dict(origin="kazumi", key=name, notes=[], smoke={"status": status}, source=src if source else None)

smoke_mod.RETRY_WAIT = 0
fetched = []
def fake_browser(url, ua=None):          # 代表“走代理的浏览器”：如果被海外对照借用，403 的站就会被它救活
    fetched.append(url); return SEARCH
smoke_mod.set_browser_fetcher(fake_browser)

cands = [cand("good", "/ok/s"), cand("blk", "/blocked/s"), cand("dead", "/dead/s"), cand("nosrc", "/x", source=False)]
direct_pass(cands, {"smoke_direct_wait": 0, "smoke_fallback_keywords": []})
st = {c["key"]: (c.get("smoke_direct") or {}).get("status") for c in cands}
check("海外直连：能通的是 ok", st["good"] == "ok" and cands[0]["smoke_direct"]["episode_count"] == 2)
check("海外直连：403 判 blocked，没有借浏览器回退（浏览器是走代理的）", st["blk"] == "blocked" and not fetched)
check("海外直连：502 判 unreachable（站点出错没结论）", st["dead"] == "unreachable")
check("没有源的候选跳过", st["nosrc"] is None and "smoke_direct" not in cands[3])
check("浏览器回退在对照结束后恢复原样", smoke_mod.FETCHER is fake_browser)
check("主检测的结果和排名字段不被改动", all(c["smoke"] == {"status": "ok"} for c in cands) and all(not c["notes"] for c in cands))

# 出错也不能拖垮主流程
orig = smoke_mod.check_source
def boom(*a, **k): raise RuntimeError("x")
smoke_mod.check_source = boom
bs = [cand("a", "/ok/s")]
try:
    direct_pass(bs, {"smoke_direct_wait": 0}); ok = bs[0]["smoke_direct"]["status"] == "skipped"
except Exception:
    ok = False
smoke_mod.check_source = orig
check("对照检测出错：记为 skipped，不抛出", ok and smoke_mod.FETCHER is fake_browser)
smoke_mod.set_browser_fetcher(None)

# 备用关键词：站里没有“葬送的芙莉莲”，但搜“海贼王”有结果
kw = cand("kw", "/kw/s")
direct_pass([kw], {"smoke_direct_wait": 0})
check("海外对照也用备用关键词：换词后通过", kw["smoke_direct"]["status"] == "ok" and kw["smoke_direct"]["episode_count"] == 2)
kw = cand("kw", "/kw/s")
direct_pass([kw], {"smoke_direct_wait": 0, "smoke_fallback_keywords": []})
check("备用关键词设为 [] 时不换词：判 fail", kw["smoke_direct"]["status"] == "fail")

# ---- exit_compare ----
def c2(key, a, b, chosen=False, src=True):
    return dict(origin="kazumi", key=key, source={} if src else None, chosen=chosen, smoke={"status": a} if a else {}, **({"smoke_direct": {"status": b}} if b else {}))
cs = [c2("p", "ok", "ok"), c2("q", "ok", "blocked", True), c2("r", "unreachable", "ok", True), c2("s", "blocked", "unreachable"),
      c2("t", "fail", "fail"), c2("u", "ok", None), c2("v", None, "ok"), c2("w", "ok", "ok", src=False), c2("x", "ok", "fail")]
cats, rows = exit_compare(cs)
check("分类计数：两边都通过 / 只国内 / 只海外 / 都没通过", cats == {"both_ok": 1, "cn_only": 2, "abroad_only": 1, "neither": 2})
check("缺一边结果的、没有源的不统计", sum(cats.values()) == 6)
keys = [r[0] for r in rows]
check("差异清单：入选的排前面；两边都没通过且原因相同的不列", keys[:2] == ["kazumi:r", "kazumi:q"] and "kazumi:t" not in keys and "kazumi:s" in keys)
check("“海外通过、国内没通过”单独点明", "国内出口没通过" in dict((r[0], r[3]) for r in rows)["kazumi:r"])
check("“国内通过、海外被拦”标为符合预期", "符合预期" in dict((r[0], r[3]) for r in rows)["kazumi:q"])
cats, rows = exit_compare([c2("a", "ok", None)])
check("没做对照时：空结果", sum(cats.values()) == 0 and not rows)
sys.exit(1 if bad else 0)
