"""用本地模拟站点把整条流水线跑一遍：转换 -> 冒烟测试 -> 订阅文件 -> 报告。"""
import json, os, subprocess, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

HTML_SEARCH = """<html><body><div class="search-box"><ul>
<li><h3><a href="/detail/1/">葬送的芙莉莲</a></h3></li><li><h3><a href="/detail/2/">别的番</a></h3></li></ul></div></body></html>"""
HTML_DETAIL = """<html><body><div class="playlist"><div class="row"><ul>
<li><a href="/play/1-1">第1集</a></li><li><a href="/play/1-2">第2集</a></li></ul></div></div></body></html>"""
HTML_VOD = """<html><body><div class="module-play-list-content"><a class="module-play-list-link" href="/p/1">第1集</a></div></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, code, body, ctype="text/html; charset=utf-8"):
        b = body.encode()
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == "/search/":
            return self.send(200, HTML_SEARCH)
        if u.path == "/detail/1/":
            return self.send(200, HTML_DETAIL)
        if u.path == "/api/suggest":
            return self.send(200, json.dumps({"list": [{"id": 7, "name": "葬送的芙莉莲"}]}), "application/json")
        if u.path == "/voddetail/7.html":   # 注意：/voddetail/7 不存在
            return self.send(200, HTML_VOD)
        if u.path == "/cap/search":
            return self.send(200, "<html><body>系统安全验证：请输入验证码</body></html>")
        if u.path == "/empty/search":
            return self.send(200, "<html><body><p>没有结果</p></body></html>")
        self.send(404, "nf")


def main():
    srv = HTTPServer(("0.0.0.0", 0), H)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % port
    tmp = tempfile.mkdtemp()
    rules = os.path.join(tmp, "rules"); os.makedirs(rules)
    ov = os.path.join(tmp, "ov"); os.makedirs(ov)
    counter = [1]
    def w(name, obj):
        # 每条规则用不同的回环地址（127.0.0.N），避免被“同站点合并”当成同一个站
        counter[0] += 1
        text = json.dumps(obj, ensure_ascii=False).replace("127.0.0.1:%d" % port, "127.0.0.%d:%d" % (counter[0], port))
        open(os.path.join(rules, name + ".json"), "w", encoding="utf-8").write(text)
    w("html1", {"name": "html1", "version": "1.0", "baseURL": base + "/", "searchURL": base + "/search/?wd=@keyword",
                "searchList": "//div[contains(@class,'search-box')]/ul/li", "searchName": "//h3/a", "searchResult": "//h3/a",
                "chapterRoads": "//div[@class='playlist']/div[@class='row']/ul", "chapterResult": "//li/a", "referer": ""})
    w("api1", {"name": "api1", "version": "1.1", "baseURL": base + "/voddetail/", "searchMode": "api", "chapterMode": "xpath",
               "searchApiConfig": {"request": {"method": "GET", "url": base + "/api/suggest", "query": {"mid": "1", "wd": "@keyword"}},
                                   "listPath": "$.list[*]", "namePath": "$.name", "sourcePath": "$.id"},
               "chapterRoads": "//div[contains(@class,'module-play-list-content')]", "chapterResult": ".//a[contains(@class,'module-play-list-link')]"})
    w("blocked1", {"name": "blocked1", "version": "1.0", "baseURL": base + "/", "searchURL": base + "/cap/search?wd=@keyword",
                   "searchList": "//ul/li", "searchName": "//a", "searchResult": "//a", "chapterRoads": "//ul", "chapterResult": "//li/a"})
    w("empty1", {"name": "empty1", "version": "1.0", "baseURL": base + "/", "searchURL": base + "/empty/search?wd=@keyword",
                 "searchList": "//ul/li", "searchName": "//a", "searchResult": "//a", "chapterRoads": "//ul", "chapterResult": "//li/a"})
    w("post1", {"name": "post1", "version": "1.0", "baseURL": base + "/", "usePost": True, "searchURL": base + "/x",
                "searchList": "//li", "searchName": "//a", "searchResult": "//a", "chapterRoads": "//ul", "chapterResult": "//li/a"})
    w("down1", {"name": "down1", "version": "1.0", "baseURL": "http://127.0.0.1:1/", "searchURL": "http://127.0.0.1:1/s?wd=@keyword",
                "searchList": "//li", "searchName": "//a", "searchResult": "//a", "chapterRoads": "//ul", "chapterResult": "//li/a"})
    json.dump([{"name": n, "version": "1"} for n in ("html1", "api1", "blocked1", "empty1", "post1", "down1", "gone1")], open(os.path.join(rules, "index.json"), "w"))
    out = os.path.join(tmp, "dist")
    r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "build.py"), "--kazumi", rules, "--baseline", os.path.join(tmp, "none.json"), "--out", out, "--overrides", ov, "--smoke"],
                       capture_output=True, text=True)
    print(r.stdout[-2500:], r.stderr[-1500:])
    rep = {e["key"]: e for e in json.load(open(os.path.join(out, "report.json")))["candidates"]}
    sub = json.load(open(os.path.join(out, "all.json")))
    ids = [s["id"] for s in sub["mediaSources"]]
    exp = [s["id"] for s in sub["exportedMediaSourceDataList"]["mediaSources"]]
    checks = [
        ("html1 冒烟通过", rep["html1"]["smoke"]["status"] == "ok"),
        ("api1 自动选中 .html 以外的链接写法（/voddetail/{value}.html 才存在）", rep["api1"]["smoke"]["status"] == "ok" and rep["api1"]["smoke"].get("template", "").endswith("/{value}.html")),
        ("blocked1 识别为验证码拦截", rep["blocked1"]["smoke"]["status"] == "blocked"),
        ("empty1 识别为选择器无结果", rep["empty1"]["smoke"]["status"] == "fail"),
        ("down1 识别为无法访问", rep["down1"]["smoke"]["status"] == "unreachable"),
        ("post1 标为无法转换", rep["post1"]["status"] == "unsupported" and "post1" not in str(ids)),
        ("gone1 标为缺文件", rep["gone1"]["status"] == "missing"),
        ("订阅里两处列表一致", ids == exp),
        ("失败项只标记、不剔除", "kazumi-blocked1" in ids and "kazumi-empty1" in ids),
        ("失败项描述带前缀", any(s["arguments"]["description"].startswith("[自动检测未通过") for s in sub["mediaSources"])),
        ("订阅里没有以下划线开头的内部字段", all(not any(k.startswith("_") for k in s) for s in sub["mediaSources"])),
    ]
    bad = 0
    for name, ok in checks:
        print(("OK  " if ok else "BAD ") + name)
        bad += (not ok)
    sys.exit(1 if bad or r.returncode else 0)


if __name__ == "__main__":
    main()
