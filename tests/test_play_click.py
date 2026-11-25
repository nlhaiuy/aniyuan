"""播放检测：多点几轮、点播放按钮、有播放器时多等一会儿的自测（用本地模拟站点，不访问外网）。"""
import os, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aniyuan.convert.kazumi import MATCH_VIDEO_URL
from aniyuan.check.playcheck import PlayChecker

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)

PAGES = {
    # 点了播放按钮才请求视频（按钮是 video.js 的类名，不在旧的点击列表里）
    "/p/button": "<html><body><div class='vjs-big-play-button' style='width:200px;height:100px' onclick=\"fetch('/m/1.m3u8')\">play</div></body></html>",
    # 第一次点击只是“关广告”，第二次才真的开始播放
    "/p/second": "<html><body><div class='vjs-big-play-button' style='width:200px;height:100px' "
                 "onclick=\"window.n=(window.n||0)+1; if(window.n>=2) fetch('/m/2.m3u8')\">play</div></body></html>",
    # 页面上有播放器（video），但视频请求 9 秒后才发出
    "/p/slow": "<html><body><video></video><script>setTimeout(()=>fetch('/m/3.m3u8'),9000)</script></body></html>",
    # 页面上没有任何播放器元素，9 秒后才发请求：不该为它多等
    "/p/slow_noplayer": "<html><body>没有播放器<script>setTimeout(()=>fetch('/m/4.m3u8'),9000)</script></body></html>",
}

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        path = self.path.split("?")[0]
        if path in PAGES: body, ctype = PAGES[path].encode(), "text/html; charset=utf-8"
        elif path.startswith("/m/"): body, ctype = b"data", "application/octet-stream"
        else: body, ctype = b"nf", "text/html"
        self.send_response(200 if path in PAGES or path.startswith("/m/") else 404)
        self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

srv = HTTPServer(("0.0.0.0", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
B = "http://127.0.0.1:%d" % srv.server_address[1]

def src():
    return {"id": "t", "factoryId": "web-selector", "version": 2, "arguments": {"name": "t", "description": "d", "iconUrl": "",
        "searchConfig": {"searchUrl": B + "/s?wd={keyword}", "matchVideo": {
            "matchVideoUrl": MATCH_VIDEO_URL, "matchNestedUrl": "$^", "enableNestedUrl": False,
            "scanDomMediaUrls": False, "addHeadersToVideo": {"referer": ""}}}}, "tier": 4}

pc = PlayChecker()
def play(path, wait_ms, extra_ms=0):
    return pc.check(src(), B + path, wait_ms=wait_ms, extra_ms=extra_ms)["play"]

try:
    check("点具体的播放按钮（.vjs-big-play-button）才出视频 -> ok", play("/p/button", 7000) == "ok")
    check("要点第二下才开始播放 -> ok（隔几秒再点一轮）", play("/p/second", 13500) == "ok")
    check("视频 9 秒后才出现、只等 6 秒、不加时 -> none", play("/p/slow", 6000) == "none")
    check("同一页：有播放器，加时 9 秒 -> ok", play("/p/slow", 6000, 9000) == "ok")
    r = pc.check(src(), B + "/p/slow_noplayer", wait_ms=6000, extra_ms=9000)
    check("页面上没有播放器：不加时，仍是 none，且没多等", r["play"] == "none" and "6 秒" in r["play_reason"])
finally:
    pc.close()

print("\n全部通过" if not bad else "\n%d 项失败" % bad)
sys.exit(1 if bad else 0)
