"""站点图标的自测（不联网：用假的抓取函数）。"""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from icons import candidates, page_icons, resolve_icons, sniff, verify_dir

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)


PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 40
ICO = b"\x00\x00\x01\x00" + b"x" * 40
HTML_ERR = b"<html>403 Forbidden</html>"

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

    items = [(src("aniyuan-a"), False)]
    r = resolve_icons(items, d, BASE, get_html, get_image)
    s = items[0][0]
    check("按页面声明的图标下载，带站点自己的 Referer", r[0][1] == "new" and any(u.endswith("/fav.ico") and ref == "https://www.x.com/" for u, ref in calls))
    check("图标存进目录，iconUrl 改成自己仓库的链接", os.path.exists(os.path.join(d, "aniyuan-a.png")) and s["arguments"]["iconUrl"] == BASE + "/aniyuan-a.png")

    r = resolve_icons([(src("aniyuan-a"), False)], d, BASE, get_html, get_image)
    check("再跑一次内容没变：same", r[0][1] == "same")

    # 这次站点打不开：沿用上次存的
    it = [(src("aniyuan-a"), False)]
    r = resolve_icons(it, d, BASE, lambda u: None, lambda u, ref: None)
    check("这次取不到：沿用上次存的图标", r[0][1] == "cached" and it[0][0]["arguments"]["iconUrl"] == BASE + "/aniyuan-a.png")

    # 从没取到过：保留原来的 iconUrl，不写目录
    it = [(src("aniyuan-b"), False)]
    r = resolve_icons(it, d, BASE, lambda u: None, lambda u, ref: HTML_ERR)
    check("从没取到过：保留原 iconUrl", r[0][1] == "kept" and it[0][0]["arguments"]["iconUrl"] == "https://old.com/i.png" and not os.path.exists(os.path.join(d, "aniyuan-b.png")))

    # 拿到的是 HTML 错误页 / 超大文件 都不算图片
    it = [(src("aniyuan-c"), False)]
    resolve_icons(it, d, BASE, lambda u: None, lambda u, ref: HTML_ERR)
    check("HTML 错误页不会被当成图标存下来", not any(f.startswith("aniyuan-c.") for f in os.listdir(d)))
    it = [(src("aniyuan-c"), False)]
    resolve_icons(it, d, BASE, lambda u: None, lambda u, ref: PNG + b"x" * (300 * 1024))
    check("超过 300KB 不存", not any(f.startswith("aniyuan-c.") for f in os.listdir(d)))

    # 手动源不动；不在订阅里的旧图标会清掉；类型变了清掉旧扩展名
    it = [(src("aniyuan-m"), True)]
    r = resolve_icons(it, d, BASE, get_html, get_image)
    check("manual 源：图标不动", r[0][1] == "skipped" and it[0][0]["arguments"]["iconUrl"] == "https://old.com/i.png")
    check("不在订阅里的源，图标被清掉", not os.path.exists(os.path.join(d, "aniyuan-a.png")))
    resolve_icons([(src("aniyuan-t"), False)], d, BASE, lambda u: None, lambda u, ref: PNG)
    resolve_icons([(src("aniyuan-t"), False)], d, BASE, lambda u: None, lambda u, ref: ICO)
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
sys.exit(1 if bad else 0)
