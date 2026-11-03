"""站点图标的自测（不联网：用假的抓取函数）。"""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aniyuan.icons import candidates, page_icons, resolve_icons, sniff, verify_dir

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)


PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 40
ICO = b"\x00\x00\x01\x00" + b"x" * 40
HTML_ERR = b"<html>403 Forbidden</html>"

# ---- CI 发布任务不装第三方依赖：python -m aniyuan.icons --verify 必须只靠标准库 ----
import subprocess
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, "aniyuan-x.png"), "wb").write(PNG)
    code = ("import sys; sys.modules['bs4'] = None; sys.modules['requests'] = None; sys.modules['lxml'] = None; "
            "sys.argv = ['aniyuan.icons', '--verify', %r]; "
            "import runpy; runpy.run_module('aniyuan.icons', run_name='__main__')" % d)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=here)
check("没有 bs4 / requests / lxml 也能跑 python -m aniyuan.icons --verify（发布任务的环境）", r.returncode == 0)

# ---- 文件头判断 ----
check("PNG / ICO / JPEG / GIF / WebP 都认得", [sniff(PNG), sniff(ICO), sniff(b"\xff\xd8\xff\xe0xx"), sniff(b"GIF89a.."), sniff(b"RIFF\0\0\0\0WEBPxx")] == ["png", "ico", "jpg", "gif", "webp"])
check("HTML 错误页 / SVG / 空内容不当图片", sniff(HTML_ERR) is None and sniff(b"<svg xmlns=...>") is None and sniff(b"") is None)

# ---- 首页里声明的图标，和浏览器一样按 <link rel=icon> 找 ----
HOME = """<html><head>
<link rel="apple-touch-icon" href="/apple.png">
<link rel="icon" href="/img/big.png" sizes="192x192">
<link rel="shortcut icon" href="/img/fav.ico">
<link rel="icon" sizes="64x64" href="//cdn.x.com/64.png">
<link rel="mask-icon" href="/mask.svg"><link rel="icon" href="data:image/png;base64,AAAA">
<link rel="stylesheet" href="/a.css"></head></html>"""
got = page_icons(HOME, "https://www.x.com/")
check("接近 64 的优先，apple-touch-icon 排最后，data: 和 mask-icon 跳过",
      got == ["https://cdn.x.com/64.png", "https://www.x.com/img/fav.ico", "https://www.x.com/img/big.png", "https://www.x.com/apple.png"])
c = candidates("https://www.x.com", HOME, "https://www.x.com/", "https://img.old.com/o.png")
check("候选顺序：页面声明 → 原来的 iconUrl → /favicon.ico，且去重",
      c[-2:] == ["https://img.old.com/o.png", "https://www.x.com/favicon.ico"] and len(c) == len(set(c)))
check("首页打不开也有候选（原 iconUrl 和 /favicon.ico）",
      candidates("https://a.com", "", None, "") == ["https://a.com/favicon.ico"])


def src(sid, url="https://www.x.com/s?wd={keyword}", icon="https://old.com/i.png"):
    return {"id": sid, "arguments": {"name": sid, "iconUrl": icon, "searchConfig": {"searchUrl": url}}}


BASE = "https://cdn.example/icons"

with tempfile.TemporaryDirectory() as d:
    calls = []
    # 站点首页声明了 /fav.ico；这个图标要求 Referer 是站点自己（防盗链），原 iconUrl 的图床拒绝一切
    def get_html(url):
        return (HOME.replace("/img/fav.ico", "/fav.ico"), url) if "x.com" in url else None
    def get_image(url, referer):
        calls.append((url, referer))
        return PNG if url.endswith("/fav.ico") and referer == "https://www.x.com/" else None

    items = [src("aniyuan-a")]
    r = resolve_icons(items, d, BASE, get_html, get_image)
    s = items[0]
    check("按页面声明的图标下载，带站点自己的 Referer", r[0][1] == "new" and any(u.endswith("/fav.ico") and ref == "https://www.x.com/" for u, ref in calls))
    check("图标存进目录，iconUrl 改成自己仓库的链接", os.path.exists(os.path.join(d, "aniyuan-a.png")) and s["arguments"]["iconUrl"] == BASE + "/aniyuan-a.png")

    r = resolve_icons([src("aniyuan-a")], d, BASE, get_html, get_image)
    check("再跑一次内容没变：same", r[0][1] == "same")

    # 这次站点打不开：沿用上次存的
    it = [src("aniyuan-a")]
    r = resolve_icons(it, d, BASE, lambda u: None, lambda u, ref: None)
    check("这次取不到：沿用上次存的图标", r[0][1] == "cached" and it[0]["arguments"]["iconUrl"] == BASE + "/aniyuan-a.png")

    # 从没取到过：保留原来的 iconUrl，不写目录
    it = [src("aniyuan-b")]
    r = resolve_icons(it, d, BASE, lambda u: None, lambda u, ref: HTML_ERR)
    check("从没取到过：保留原 iconUrl", r[0][1] == "kept" and it[0]["arguments"]["iconUrl"] == "https://old.com/i.png" and not os.path.exists(os.path.join(d, "aniyuan-b.png")))

    # 拿到的是 HTML 错误页 / 超大文件 都不算图片
    it = [src("aniyuan-c")]
    resolve_icons(it, d, BASE, lambda u: None, lambda u, ref: HTML_ERR)
    check("HTML 错误页不会被当成图标存下来", not any(f.startswith("aniyuan-c.") for f in os.listdir(d)))
    it = [src("aniyuan-c")]
    resolve_icons(it, d, BASE, lambda u: None, lambda u, ref: PNG + b"x" * (300 * 1024))
    check("超过 300KB 不存", not any(f.startswith("aniyuan-c.") for f in os.listdir(d)))

    # 不在订阅里的旧图标会清掉；类型变了清掉旧扩展名
    resolve_icons([src("aniyuan-keep")], d, BASE, get_html, get_image)
    check("不在订阅里的源，图标被清掉", not os.path.exists(os.path.join(d, "aniyuan-a.png")))
    resolve_icons([src("aniyuan-t")], d, BASE, lambda u: None, lambda u, ref: PNG)
    resolve_icons([src("aniyuan-t")], d, BASE, lambda u: None, lambda u, ref: ICO)
    check("图标类型变了：旧扩展名不残留", sorted(os.listdir(d)) == ["aniyuan-t.ico"])

# ---- 发布前检查 ----
with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, "aniyuan-ok.png"), "wb").write(PNG)
    check("合规目录通过检查", verify_dir(d) == [])
    open(os.path.join(d, "aniyuan-fake.png"), "wb").write(HTML_ERR)
    open(os.path.join(d, "run.sh"), "wb").write(b"echo hi")
    open(os.path.join(d, "Bad Name.png"), "wb").write(PNG)
    p = verify_dir(d)
    check("检查挡住伪装成图片的文件、脚本、不合规文件名", len(p) == 3)

# ---- 浏览器回退：图片要 cookie（首页脚本种的）+ Referer，requests 拿不到，真浏览器能拿到 ----
try:
    from aniyuan.check.playcheck import PlayChecker
    import playwright  # noqa: F401
    have_browser = True
except Exception as e:
    print("跳过浏览器回退测试（没有 playwright）：%s" % e)
    have_browser = False

if have_browser:
    import threading, requests
    from http.server import BaseHTTPRequestHandler, HTTPServer
    os.environ["NO_PROXY"] = os.environ["no_proxy"] = "127.0.0.1"

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            port = self.server.server_port
            ok = "pass=1" in (self.headers.get("Cookie") or "") and (self.headers.get("Referer") or "").startswith("http://127.0.0.1:%d" % port)
            if self.path == "/":
                body = b'<html><head><link rel="icon" href="/logo.png"><script>document.cookie="pass=1; path=/"</script></head><body>hi</body></html>'
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers(); self.wfile.write(body)
            elif self.path == "/logo.png" and ok:
                self.send_response(200); self.send_header("Content-Type", "image/png"); self.end_headers(); self.wfile.write(PNG)
            else:
                self.send_response(403); self.end_headers(); self.wfile.write(b"forbidden")
    srv = HTTPServer(("127.0.0.1", 0), H); port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    site = "http://127.0.0.1:%d" % port
    dead = "http://127.0.0.1:1"   # 没人监听：连接立刻被拒绝

    pc = PlayChecker()
    try:
        from aniyuan.icons import make_fetchers
        gh0, gi0 = make_fetchers(requests.Session())
        plain = gi0(site + "/logo.png", site + "/")
        check("对照：只用 requests，要 cookie 的图片拿不到", plain is None)

        gh1, gi1 = make_fetchers(requests.Session(), browser_bytes=pc.fetch_bytes)
        data = gi1(site + "/logo.png", site + "/")
        check("浏览器回退：先打开首页拿 cookie，再带 Referer 拿到图片", data == PNG)

        # 端到端：resolve_icons 全流程（首页 200，所以不走页面回退；图标靠浏览器回退拿到）
        with tempfile.TemporaryDirectory() as d:
            s = src("aniyuan-b1", url=site + "/s?wd={keyword}", icon="")
            r = resolve_icons([s], d, BASE, gh1, gi1)
            check("端到端：取到图标并改写 iconUrl", r[0][1] == "new" and s["arguments"]["iconUrl"] == BASE + "/aniyuan-b1.png")
            s2 = src("aniyuan-b2", url=site + "/s?wd={keyword}", icon="")
            r = resolve_icons([s2], d, BASE, gh0, gi0)
            check("端到端对照：没有浏览器回退时取不到，保留原地址", r[0][1] == "kept")

        # 连页面都打不开的主机：只试一次就标记为不可达，后面直接返回
        import time
        t0 = time.time()
        a = pc.fetch_bytes(dead + "/a.png", dead + "/"); b = pc.fetch_bytes(dead + "/b.png", dead + "/")
        check("打不开的主机：返回 None，并记入不可达", a is None and b is None and "127.0.0.1:1" in pc._dead)
        check("打不开的主机：第二次不再等待", time.time() - t0 < 10)
    finally:
        pc.close(); srv.shutdown()
sys.exit(1 if bad else 0)
