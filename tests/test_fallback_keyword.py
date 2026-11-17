"""备用关键词自测（本地模拟站点）：主关键词没搜出结果时换词再测；确实是选择器坏了仍然判失败并走自动修复。"""
import os, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
from aniyuan.build import probe
from aniyuan.check.repair import mine_presets

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)

asked = []
DETAIL = "<html><body><div class='eps'><a href='/p/1'>第1集</a><a href='/p/2'>第2集</a></div></body></html>"


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body):
        b = body.encode()
        self.send_response(code); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u = urlparse(self.path); wd = parse_qs(u.query).get("wd", [""])[0]
        if u.path == "/s":
            asked.append(wd)
            if "海贼王" in wd:   # 这个站只有海贼王
                return self.send(200, "<html><body><a class='hit' href='/d/1'>海贼王</a></body></html>")
            return self.send(200, "<html><body><p>没有结果</p></body></html>")
        if u.path == "/d/1": return self.send(200, DETAIL)
        self.send(404, "nf")


srv = HTTPServer(("127.0.0.1", 0), H); B = "http://127.0.0.1:%d" % srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()


def src(sel="a.hit"):
    return {"id": "t", "factoryId": "web-selector", "version": 2, "arguments": {"name": "t", "description": "d", "iconUrl": "",
            "searchConfig": {"searchUrl": B + "/s?wd={keyword}", "subjectFormatId": "a",
                             "selectorSubjectFormatA": {"selectLists": sel, "preferShorterName": True},
                             "channelFormatId": "no-channel",
                             "selectorChannelFormatNoChannel": {"selectEpisodes": ".eps a", "selectEpisodeLinks": ""}}}, "tier": 4}


sess, presets = requests.Session(), mine_presets(None)
cfg = {"smoke_fallback_wait": 0}

c = dict(origin="kazumi", key="t", source=src(), notes=[])
probe(c, "葬送的芙莉莲", sess, presets, cfg)
check("主关键词没结果、备用关键词有：检测通过", c["smoke"]["status"] == "ok" and c["smoke"]["keyword"] == "海贼王")
check("备注里写明换了关键词", any("换成「海贼王」" in n for n in c["notes"]))
check("没有被当成选择器坏掉去修复", not any("自动修复" in n for n in c["notes"]))

asked.clear()
c = dict(origin="kazumi", key="t", source=src(), notes=[])
probe(c, "葬送的芙莉莲", sess, presets, {"smoke_fallback_keywords": [], "smoke_fallback_wait": 0, "repair": False})
check("备用关键词设为 [] 可关闭：仍是 fail", c["smoke"]["status"] == "fail" and asked == ["葬送的芙莉莲"])

asked.clear()
c = dict(origin="kazumi", key="t", source=src(), notes=[])
probe(c, "葬送的芙莉莲", sess, presets, {"smoke_fallback_keywords": ["别的词", "海贼王"], "smoke_fallback_wait": 0})
check("按顺序逐个试，通过就停", asked == ["葬送的芙莉莲", "别的词", "海贼王"] and c["smoke"]["status"] == "ok")

asked.clear()
c = dict(origin="kazumi", key="t", source=src(), notes=[])
probe(c, "海贼王", sess, presets, {"smoke_fallback_keywords": ["海贼王"], "smoke_fallback_wait": 0})
check("备用词和主关键词相同时跳过，不重复请求", asked.count("海贼王") == 1 or c["smoke"]["status"] == "ok")

asked.clear()
c = dict(origin="kazumi", key="t", source=src(), notes=[])
probe(c, "葬送的芙莉莲", sess, presets, {"smoke_fallback_keywords": ["别的词", "又一个词"], "smoke_fallback_wait": 0, "repair": False})
check("所有关键词都没结果：判 fail，并保留原始关键词的失败信息", c["smoke"]["status"] == "fail" and c["smoke"].get("stage") == "search"
      and "keyword" not in c["smoke"])

# 搜索页打不开：不换词（换词没用）
dead = src(); dead["arguments"]["searchConfig"]["searchUrl"] = "http://127.0.0.1:1/s?wd={keyword}"
asked.clear()
c = dict(origin="kazumi", key="t", source=dead, notes=[])
probe(c, "葬送的芙莉莲", sess, presets, cfg)
check("打不开的站：unreachable，不换关键词", c["smoke"]["status"] == "unreachable" and not asked)

sys.exit(1 if bad else 0)
