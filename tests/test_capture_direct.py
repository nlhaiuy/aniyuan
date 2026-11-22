"""抓取的「直接模式」自测：站点配置里给了 play_urls（播放页地址）/ fetch_urls（要原样保存的地址）时，
不猜搜索页 / 详情页，只抓播放页发出的请求和这些地址的原始响应。不联网、不开浏览器。"""
import json, os, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from aniyuan import capture as C
from aniyuan.check import smoke as smoke_mod

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)


class Resp:
    def __init__(self, status, text, url): self.status_code, self.text, self.url = status, text, url

REQUESTED = []
DETAIL_JSON = json.dumps({"data": {"id": 828, "episodes": [{"id": 9604, "episodeLabel": "第1集", "episodeOrder": 1.0}]}}, ensure_ascii=False)

def fake_get(url, session, timeout, ua=None):
    REQUESTED.append(url)
    if url == "https://api.demo.cc/video/828":
        return Resp(200, DETAIL_JSON, url)
    return Resp(404, "", url)

MEDIA = json.dumps({"data": {"url": "https://cdn.demo.com/v/index.m3u8"}})

class FakePC:
    browser_name = "chromium"
    def __init__(self): self.opened = []
    def capture(self, url, wait_ms=20000, **k):
        self.opened.append(url)
        return [dict(url="https://api.demo.cc/video/episode/9604/play?line=1", method="GET", post=None, headers={}, status=200, ctype="", text=MEDIA),
                dict(url="https://api.demo.cc/auth/session", method="GET", post=None, headers={}, status=200, ctype="", text="{}")]
    def fetch(self, *a, **k): raise AssertionError("直接模式不该用浏览器取页面")


orig = smoke_mod._get
tmp = tempfile.mkdtemp()
try:
    smoke_mod._get = fake_get

    # 1) 两个播放页 + 一个原样保存的地址
    pc = FakePC()
    cap = C.Capturer("s", None, pc, os.path.join(tmp, "a"), sleep=0)
    spec = dict(key="demo", origin="https://www.demo.net", fetch_urls=["https://api.demo.cc/video/828"],
                play_urls=["https://www.demo.net/anime/828/episode/1.0", "https://www.demo.net/anime/828/episode/2.0"])
    m = cap.site(spec, ["葬送的芙莉莲"])
    d = os.path.join(tmp, "a", "demo")
    check("直接模式：结果 ok，没有去猜搜索页 / 详情页", m["result"] == "ok" and REQUESTED == ["https://api.demo.cc/video/828"])
    check("fetch_urls：原样保存响应（JSON）", json.load(open(os.path.join(d, "fetch-1.json"), encoding="utf-8"))["data"]["episodes"][0]["id"] == 9604)
    check("play_urls：每个播放页各存一份请求（play-xhr.json / play-xhr-2.json）",
          os.path.exists(os.path.join(d, "play-xhr.json")) and os.path.exists(os.path.join(d, "play-xhr-2.json"))
          and pc.opened == spec["play_urls"])
    x = json.load(open(os.path.join(d, "play-xhr.json"), encoding="utf-8"))
    check("请求里带响应正文（写 play 要看视频地址在哪）", "m3u8" in x[0]["text"] and x[0]["url"].endswith("play?line=1"))
    check("meta：episode_url 是第一个播放页；play_xhr 只按第一个算（总数 / 带视频地址）",
          m["episode_url"] == spec["play_urls"][0] and m["play_xhr"] == {"count": 2, "media": 1})
    check("meta：steps 记着每一步", [s["step"] for s in m["steps"]] == ["fetch", "play-xhr", "play-xhr"])

    # 2) 最多抓 3 个播放页
    pc2 = FakePC()
    cap2 = C.Capturer("s", None, pc2, os.path.join(tmp, "b"), sleep=0)
    cap2.site(dict(key="many", origin="https://x.net", play_urls=["https://x.net/%d" % i for i in range(6)]), ["k"])
    check("play_urls 最多抓 3 个", len(pc2.opened) == 3)

    # 3) 没有浏览器
    cap3 = C.Capturer("s", None, None, os.path.join(tmp, "c"), sleep=0)
    m3 = cap3.site(dict(key="only-play", origin="https://x.net", play_urls=["https://x.net/p"]), ["k"])
    check("没有浏览器、只给了播放页：说明没抓到内容，不崩", m3["result"] == "没有抓到内容")
    m3b = cap3.site(dict(key="only-fetch", origin="https://x.net", fetch_urls=["https://api.demo.cc/video/828"]), ["k"])
    check("没有浏览器、给了要保存的地址：照样能保存", m3b["result"] == "ok" and os.path.exists(os.path.join(tmp, "c", "only-fetch", "fetch-1.json")))
    m3c = cap3.site(dict(key="dead", origin="https://x.net", fetch_urls=["https://api.demo.cc/gone"]), ["k"])
    check("要保存的地址 404：没抓到内容，不写空文件", m3c["result"] == "没有抓到内容" and not os.path.exists(os.path.join(tmp, "c", "dead", "fetch-1.json")))

    # 4) 不是 http 开头的条目被忽略；两个都没有时走原来的搜索流程
    del REQUESTED[:]
    cap4 = C.Capturer("s", None, None, os.path.join(tmp, "d"), sleep=0)
    m4 = cap4.site(dict(key="plain", origin="https://plain.example.com", play_urls=["javascript:x", ""], fetch_urls=["ftp://x"]), ["k"])
    check("play_urls / fetch_urls 里没有有效地址：回到原来的搜索流程", any("plain.example.com" in u for u in REQUESTED) and m4["result"] != "ok")

    # 5) 仓库里 capture_sites.json 的新条目格式正确，key 不重复
    sites = json.load(open(os.path.join(ROOT, "capture_sites.json"), encoding="utf-8"))
    keys = [s["key"] for s in sites]
    check("capture_sites.json：key 不重复", len(keys) == len(set(keys)))
    by = {s["key"]: s for s in sites}
    check("capture_sites.json：xfdmnext 是对照组（有两个播放页，没有要搜索的地址）", len(by["xfdmnext"]["play_urls"]) == 2)
    check("capture_sites.json：每个条目都有 key / origin",
          all(s.get("key") and str(s.get("origin", "")).startswith("http") for s in sites))
finally:
    smoke_mod._get = orig

print("\n%d 项未通过" % bad if bad else "\n全部通过")
sys.exit(1 if bad else 0)
