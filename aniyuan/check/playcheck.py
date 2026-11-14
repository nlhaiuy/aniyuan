"""播放检测：用无头浏览器打开第一集的播放页，看能不能抓到视频地址。

和 Animeko 的 WebView 做的事类似：监听页面（含 iframe）发出的请求和 <video> 元素，
再用这个源自己的 matchVideoUrl 去匹配 —— 这样既验证了“能不能播”，
也验证了“这个源的视频地址正则写得对不对”。

结果 play 字段：
  ok        抓到了视频地址，并且被该源的 matchVideoUrl（或 scanDomMediaUrls）认出来了
  mismatch  页面里出现了视频地址，但该源的 matchVideoUrl 认不出来 —— 配置要改
  none      等了一段时间没出现视频地址（可能要点击/登录/被广告拦着，不一定是坏的）
  blocked   页面出现验证码/环境检查
  error     浏览器打开失败
"""
import glob
import re

from . import network
from . import ua as ua_mod

BLOCK_WORDS = ["验证码", "安全验证", "检查环境", "请输入验证", "Just a moment", "人机验证"]
MEDIA_RE = re.compile(r"\.(m3u8|mpd|mp4|m4v|mkv|webm|mov|flv|avi)(\?|$|#)|/video/tos/|mime_type=video", re.I)
CLICK_SELECTORS = ["video", ".dplayer-video-wrap", ".dplayer", ".art-video-player", "#player", "#playleft",
                   ".player", ".MacPlayer", "iframe"]


def to_py_regex(pattern):
    """Kotlin/Java 的命名分组 (?<name>…) 改成 Python 的 (?P<name>…)；后顾断言 (?<= (?<! 不动。"""
    return re.sub(r"\(\?<(?![=!])", "(?P<", pattern)


def _launch(pw, proxy=None):
    kw = dict(headless=True, args=["--no-sandbox", "--autoplay-policy=no-user-gesture-required"])
    if proxy:
        kw["proxy"] = proxy
    try:
        return pw.chromium.launch(**kw)
    except Exception:
        for exe in glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"):
            return pw.chromium.launch(executable_path=exe, **kw)
        raise


class PlayChecker:
    def __init__(self, proxy=None):
        """proxy：出口代理地址（见 network.py），给了就让浏览器的所有请求都走它。"""
        from playwright.sync_api import sync_playwright
        self._cm = sync_playwright()
        self._pw = self._cm.start()
        self.browser = _launch(self._pw, network.playwright_proxy(proxy))
        ua_mod.adopt_browser_version(self.browser.version)   # 统一 UA 的大版本以真实浏览器为准
        self._fetch_ctx = {}
        self._warmed = set()   # fetch_bytes 已经预热过的主机
        self._dead = set()     # fetch_bytes 连页面都打不开的主机

    def close(self):
        try:
            for c in self._fetch_ctx.values():
                try:
                    c.close()
                except Exception:
                    pass
            self.browser.close()
        finally:
            self._pw.stop()

    def new_context(self, ua=None):
        """所有浏览器上下文都从这里建：UA 统一，客户端提示（Sec-CH-UA）和 UA 同一个版本、不带 HeadlessChrome。"""
        return self.browser.new_context(user_agent=(ua or "").strip() or ua_mod.current(), ignore_https_errors=True,
                                        extra_http_headers={"Accept-Language": ua_mod.ACCEPT_LANGUAGE})

    def new_page(self, ctx, ua=None):
        page = ctx.new_page()
        hints = ua_mod.client_hints(ua)
        if hints:
            try:
                ctx.new_cdp_session(page).send("Emulation.setUserAgentOverride", {
                    "userAgent": (ua or "").strip() or ua_mod.current(), "userAgentMetadata": hints})
            except Exception:   # 拿不到 CDP 就退回只改 UA 字符串，不影响检测
                pass
        return page

    def _host_ctx(self, host, ua=None):
        key = (host, (ua or "").strip())
        if key not in self._fetch_ctx:
            self._fetch_ctx[key] = self.new_context(ua)
        return self._fetch_ctx[key]

    def fetch(self, url, timeout_ms=20000, ua=None):
        """requests 被 403/503（Cloudflare 一类）拦住时，用真浏览器取页面。同一个站复用同一个浏览器上下文，
        这样第一次过了检查拿到的 cookie 后面的页面也能用。返回 (状态码, 文本, 最终地址)。"""
        from urllib.parse import urlparse
        host = urlparse(url).netloc
        ctx = self._host_ctx(host, ua)
        page = self.new_page(ctx, ua)
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            for _ in range(8):   # 等“正在检查你的浏览器”之类的挑战页自己跳转
                if "Just a moment" not in page.title() and "请稍候" not in page.title():
                    break
                page.wait_for_timeout(1500)
            text = page.content()
            body = page.inner_text("body", timeout=2000) if "<pre" in text[:600] else ""
            if body.lstrip()[:1] and body.lstrip()[0] in "{[":
                text = body
            return (resp.status if resp else 0, text, page.url)
        finally:
            page.close()

    def fetch_bytes(self, url, referer="", timeout_ms=12000):
        """用真浏览器下载一个文件（图标）：requests 被 403 / 防盗链 / Cloudflare 拦住时的回退。
        图片和站点同一个主机时，先在同一个浏览器上下文里打开一次 referer 页面（拿到站点种的 cookie），
        再带 Referer 去请求图片，和人用浏览器打开页面时一样。
        整个站点连页面都打不开的，记下来，后面这个主机的请求直接返回 None，不再各等一遍超时。
        返回字节，失败返回 None。"""
        from urllib.parse import urlparse
        host = urlparse(url).netloc
        if host in self._dead:
            return None
        ctx = self._host_ctx(host)
        if referer and urlparse(referer).netloc == host and host not in self._warmed:
            self._warmed.add(host)
            page = self.new_page(ctx)
            try:
                page.goto(referer, wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_timeout(800)   # 让页面里的脚本有机会种 cookie
            except Exception:
                self._dead.add(host)
                return None
            finally:
                page.close()
        page = self.new_page(ctx)
        try:
            resp = page.goto(url, wait_until="load", timeout=timeout_ms, referer=referer or None)
            return resp.body() if resp is not None and resp.status == 200 else None
        except Exception:   # 超时、被当成下载、连接失败……都算没取到
            return None
        finally:
            page.close()

    def check(self, source, episode_url, wait_ms=20000):
        mv = source["arguments"]["searchConfig"].get("matchVideo", {})
        try:
            match = re.compile(to_py_regex(mv.get("matchVideoUrl") or r"$^"))
        except re.error:
            match = None
        scan_dom = bool(mv.get("scanDomMediaUrls"))
        seen = []
        src_ua = (source["arguments"]["searchConfig"].get("userAgent") or "").strip() or None
        ctx = self.new_context(src_ua)
        page = self.new_page(ctx, src_ua)
        page.on("request", lambda r: seen.append(r.url))
        try:
            try:
                page.goto(episode_url, wait_until="domcontentloaded", timeout=20000)
            except Exception as e:  # 超时也继续看已经抓到的
                if not seen:
                    return {"play": "error", "play_reason": "打开播放页失败：%s" % type(e).__name__}
            waited, clicked = 0, False
            while waited < wait_ms:
                page.wait_for_timeout(1500)
                waited += 1500
                found = self._found(page, seen, match, scan_dom)
                if found:
                    return found
                if not clicked and waited >= 4500:
                    clicked = True
                    self._click_play(page)
            try:
                text = page.inner_text("body", timeout=2000)[:6000]
            except Exception:
                text = ""
            if any(w in text for w in BLOCK_WORDS):
                return {"play": "blocked", "play_reason": "播放页出现验证码/环境检查"}
            generic = list(dict.fromkeys(u for u in seen if MEDIA_RE.search(u) and not u.startswith("data:")))
            if generic:
                return {"play": "mismatch", "play_reason": "页面出现了视频地址，但 matchVideoUrl 认不出来",
                        "media": generic[0][:200], "media_urls": [u[:400] for u in generic[:20]]}
            return {"play": "none", "play_reason": "等了 %d 秒没有出现视频地址" % (wait_ms // 1000)}
        finally:
            ctx.close()

    def capture(self, url, wait_ms=20000, ua=None, stop=None, max_text=1500000):
        """打开一个播放页，记录页面自己发出的 XHR / fetch 请求和响应（给「学 play」用）。
        每条：{url, method, post, headers, status, ctype, text}。stop(entries) 返回 True 就提前结束。
        和 check() 一样，过一会儿会点一下播放器，让需要点击才加载的页面也发请求。"""
        got, entries, done = [], [], [0]
        ctx = self.new_context(ua)
        page = self.new_page(ctx, ua)

        def on_resp(resp):
            try:
                if resp.request.resource_type in ("xhr", "fetch"):
                    got.append(resp)
            except Exception:
                pass

        def drain():
            while done[0] < len(got):
                resp = got[done[0]]
                done[0] += 1
                try:
                    req = resp.request
                    ctype = (resp.headers or {}).get("content-type", "")
                    text = resp.text() if resp.status < 400 else ""
                    entries.append({"url": req.url, "method": req.method, "post": req.post_data, "headers": dict(req.headers or {}),
                                    "status": resp.status, "ctype": ctype, "text": text[:max_text]})
                except Exception:   # 响应已经被丢弃 / 不是文本：忽略这一条
                    continue

        page.on("response", on_resp)
        try:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
            except Exception:
                if not got:
                    return entries
            waited, clicked = 0, False
            while waited < wait_ms:
                page.wait_for_timeout(1500)
                waited += 1500
                drain()
                if stop and stop(entries):
                    break
                if not clicked and waited >= 4500:
                    clicked = True
                    self._click_play(page)
            drain()
            return entries
        finally:
            ctx.close()

    def _found(self, page, seen, match, scan_dom):
        for u in seen:
            if match and match.search(u) and not u.startswith("data:"):
                return {"play": "ok", "play_reason": "抓到视频地址并被 matchVideoUrl 认出", "media": u[:200]}
        # <video> 元素（含所有 iframe）
        if scan_dom:
            for fr in page.frames:
                try:
                    src = fr.evaluate("() => { const v = document.querySelector('video'); return v ? (v.currentSrc || v.src || '') : ''; }")
                except Exception:
                    continue
                if src and not src.startswith(("blob:", "data:")):
                    return {"play": "ok", "play_reason": "scanDomMediaUrls 能从 <video> 取到地址", "media": src[:200]}
        return None

    def _click_play(self, page):
        for fr in page.frames:
            for sel in CLICK_SELECTORS:
                try:
                    el = fr.query_selector(sel)
                    if el:
                        el.click(timeout=1500, force=True)
                        return
                except Exception:
                    continue
