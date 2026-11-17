"""联网检测的容错自测（本地模拟站点）：偶发错误会重试；站点网关错误（5xx）算“没结论”而不是“选择器失败”。"""
import os, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
from aniyuan.check import smoke
from aniyuan.check.smoke import check_source, status_kind, transient_code

smoke.RETRY_WAIT = 0   # 测试里不等

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)

hits = {}
SEARCH = "<html><body><a href='%s'>葬送的芙莉莲</a></body></html>"
DETAIL = "<html><body><div class='eps'><a href='/p/1'>第1集</a><a href='/p/2'>第2集</a></div></body></html>"


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body="x", ctype="text/html; charset=utf-8"):
        b = body.encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        p = self.path.split("?")[0]
        hits[p] = hits.get(p, 0) + 1
        if p == "/flaky": return self.send(502 if hits[p] == 1 else 200, SEARCH % "/d/ok")
        if p == "/down": return self.send(502)
        if p == "/cf": return self.send(523)
        if p == "/gone": return self.send(404)
        if p == "/s-ok": return self.send(200, SEARCH % "/d/ok")
        if p == "/s-502": return self.send(200, SEARCH % "/d/502")
        if p == "/s-404": return self.send(200, SEARCH % "/d/404")
        if p == "/s-mixed": return self.send(200, SEARCH % "/d/flaky")
        if p == "/d/ok": return self.send(200, DETAIL)
        if p == "/d/502": return self.send(502)
        if p == "/d/404": return self.send(404)
        if p == "/d/flaky": return self.send(504 if hits[p] == 1 else 200, DETAIL)
        if p == "/api/s": return self.send(200, '{"list":[{"id":1,"name":"葬送的芙莉莲"}]}', "application/json")
        if p == "/api/d502": return self.send(502)
        if p == "/api/dflaky": return self.send(502 if hits[p] == 1 else 200, '{"eps":[{"id":1,"name":"第1集"}]}', "application/json")
        if p == "/api/search502": return self.send(502)
        self.send(404, "nf")
    do_POST = do_GET


srv = HTTPServer(("127.0.0.1", 0), H); B = "http://127.0.0.1:%d" % srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()


def web(search_path):
    return {"id": "t", "factoryId": "web-selector", "version": 2, "arguments": {"name": "t", "description": "", "iconUrl": "",
            "searchConfig": {"searchUrl": B + search_path + "?wd={keyword}", "subjectFormatId": "a",
                             "selectorSubjectFormatA": {"selectLists": "a", "preferShorterName": True},
                             "channelFormatId": "no-channel",
                             "selectorChannelFormatNoChannel": {"selectEpisodes": ".eps a", "selectEpisodeLinks": ""}}}, "tier": 4}


def api(search_path, detail_path):
    return {"id": "t", "factoryId": "json-api", "version": 1, "arguments": {"name": "t", "description": "", "iconUrl": "",
            "searchConfig": {"baseUrl": B, "search": {"request": {"url": search_path + "?k={keyword}", "method": "GET"},
                             "pageSize": 10, "selectItems": "$.list[*]", "selectName": "$.name", "selectId": "$.id"},
                             "subject": {"request": {"url": detail_path + "?id={id}", "method": "GET"},
                                         "episodes": {"selectEpisodes": "$.eps[*]", "selectName": "$.name", "selectId": "$.id"},
                                         "channelFormatId": "no-channel"}}}, "tier": 4}


check("状态码分类：502/504/523 是站点出错", all(transient_code(c) for c in (500, 502, 504, 520, 523, 524)))
check("状态码分类：403/429/503 是被拦，404 是地址不对", status_kind(403) == "blocked" and status_kind(503) == "blocked"
      and status_kind(429) == "blocked" and status_kind(404) == "fail" and status_kind(502) == "unreachable")

sess = requests.Session()
r = check_source(web("/flaky"), session=sess)
check("搜索页第一次 502、重试后 200：检测通过", r["status"] == "ok" and hits["/flaky"] == 2)
r = check_source(web("/down"), session=sess)
check("搜索页一直 502：没结论（unreachable），不是 fail", r["status"] == "unreachable" and "502" in r["reason"] and hits["/down"] == 2)
r = check_source(web("/cf"), session=sess)
check("Cloudflare 523：没结论", r["status"] == "unreachable")
r = check_source(web("/gone"), session=sess)
check("搜索地址 404：仍然是 fail（地址本身不对）", r["status"] == "fail")
r = check_source(web("/s-ok"), session=sess)
check("正常的源不受影响", r["status"] == "ok" and r["episode_count"] == 2)
r = check_source(web("/s-502"), session=sess)
check("详情页一直 502：没结论，不触发选择器自动修复", r["status"] == "unreachable" and "stage" not in r)
r = check_source(web("/s-404"), session=sess)
check("详情页 404：仍然是 fail", r["status"] == "fail" and r.get("stage") == "episodes")
r = check_source(web("/s-mixed"), session=sess)
check("详情页第一次 504、重试后通过", r["status"] == "ok")

r = check_source(api("/api/search502", "/api/dflaky"), session=sess)
check("json-api：搜索接口 502 -> 没结论", r["status"] == "unreachable")
r = check_source(api("/api/s", "/api/d502"), session=sess)
check("json-api：详情接口一直 502 -> 没结论", r["status"] == "unreachable")
r = check_source(api("/api/s", "/api/dflaky"), session=sess)
check("json-api：详情接口第一次 502、重试后通过", r["status"] == "ok" and r["episode_count"] == 1)

# 连接被拒：重试一次后仍然是 unreachable
dead = web("/x"); dead["arguments"]["searchConfig"]["searchUrl"] = "http://127.0.0.1:1/s?wd={keyword}"
r = check_source(dead, session=sess)
check("连接被拒：unreachable", r["status"] == "unreachable")

sys.exit(1 if bad else 0)
