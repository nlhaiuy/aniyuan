"""抓取（capture.py）的自测：用假页面代替网络，不联网、不开浏览器。"""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aniyuan import capture as C
from aniyuan.check import smoke as smoke_mod

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)

class Resp:
    def __init__(self, status, text, url):
        self.status_code, self.text, self.url = status, text, url

SEARCH = '<html><body>' + ''.join('<div class="module-card-item-title"><a href="/voddetail/%d.html">%s</a></div>' % (i, "葬送的芙莉莲" if i == 1 else "别的%d" % i) for i in range(1, 4)) + '<p>' + 'x' * 600 + '</p></body></html>'
DETAIL = '<html><body><div class="module-play-list-content"><a href="/vodplay/1-1-1.html">第1集</a><a href="/vodplay/1-1-2.html">第2集</a></div>' + '<p>' + 'y' * 1600 + '</p></body></html>'
CAPTCHA = '<html><p>请输入验证码</p><img src="/index.php/verify/index.html?"><input name="verify"></html>'

def getter(mode):
    def _get(url, session, timeout, ua=None):
        if "/voddetail/1.html" in url: return Resp(200, DETAIL, url)
        if "/vodplay/1-1-1.html" in url: return Resp(200, "<html>player</html>", url)
        if "/index.php/vod/search.html" in url:
            return Resp(200, ("<html>空</html>" if "zqxjkv" in url else SEARCH) if mode == "ok" else CAPTCHA, url)
        return Resp(404, "", url)
    return _get

orig = smoke_mod._get
try:
    out = tempfile.mkdtemp()
    smoke_mod._get = getter("ok")
    cap = C.Capturer("s", None, None, out, sleep=0)
    m = cap.site(dict(key="t1", origin="https://t1.example.com"), ["葬送的芙莉莲"])
    d = os.path.join(out, "t1")
    check("抓到搜索页、详情页、播放页并存成文件", m["result"] == "ok" and all(os.path.exists(os.path.join(d, f)) for f in ["search-1.html", "detail.html", "play-page.html", "meta.json"]))
    check("记录详情页链接、剧集链接、剧集选择器", m["detail_url"].endswith("/voddetail/1.html") and m["episode_url"].endswith("/vodplay/1-1-1.html") and m["episode_selector"]["count"] == 2)
    check("每个请求的状态都记在 meta 里（包括 404 的）", any(s.get("status") == 404 for s in m["steps"]) and any(s.get("status") == 200 for s in m["steps"]))
    check("meta.json 能读回来、不含代理地址", "socks5" not in open(os.path.join(d, "meta.json"), encoding="utf-8").read())

    smoke_mod._get = getter("captcha")
    m2 = cap.site(dict(key="t2", origin="https://t2.example.com"), ["葬送的芙莉莲"])
    d2 = os.path.join(out, "t2")
    check("被验证码拦住：存下验证页（认出类型），说明没拿到搜索结果", "search-captcha.html" in m2["files"] and m2["result"].startswith("没有拿到")
          and any(s.get("blocked") == "maccms" for s in m2["steps"]))

    # 海外直连对照：第一个搜索地址再试一次直连
    smoke_mod._get = getter("ok")
    cap3 = C.Capturer("s", "direct", None, out, sleep=0)
    m3 = cap3.site(dict(key="t3", origin="https://t3.example.com"), ["葬送的芙莉莲"])
    check("有直连会话时记录海外出口的对照结果", any(s["step"] == "search-overseas" for s in m3["steps"]))

    # 整个 main：--only 指定站点 + 写 INDEX.md（不开浏览器）
    sites = os.path.join(out, "sites.json")
    json.dump([dict(key="a", origin="https://a.example.com")], open(sites, "w"))
    smoke_mod._get = getter("ok")
    out2 = os.path.join(out, "o2")
    rc = C.main(["--sites", sites, "--out", out2, "--no-browser"])
    check("main：写出 INDEX.md 和各站目录", rc == 0 and os.path.exists(os.path.join(out2, "INDEX.md")) and os.path.exists(os.path.join(out2, "a", "meta.json")))
finally:
    smoke_mod._get = orig
sys.exit(1 if bad else 0)
