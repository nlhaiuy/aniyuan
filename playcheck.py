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

BLOCK_WORDS = ["验证码", "安全验证", "检查环境", "请输入验证", "Just a moment", "人机验证"]
MEDIA_RE = re.compile(r"\.(m3u8|mpd|mp4|m4v|mkv|webm|mov|flv|avi)(\?|$|#)|/video/tos/|mime_type=video", re.I)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0.0.0 Safari/537.36")
CLICK_SELECTORS = ["video", ".dplayer-video-wrap", ".dplayer", ".art-video-player", "#player", "#playleft",
                   ".player", ".MacPlayer", "iframe"]


def to_py_regex(pattern):
    """Kotlin/Java 的命名分组 (?<name>…) 改成 Python 的 (?P<name>…)；后顾断言 (?<= (?<! 不动。"""
    return re.sub(r"\(\?<(?![=!])", "(?P<", pattern)


def _launch(pw):
    try:
        return pw.chromium.launch(headless=True, args=["--no-sandbox", "--autoplay-policy=no-user-gesture-required"])
    except Exception:
        for exe in glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"):
            return pw.chromium.launch(headless=True, executable_path=exe,
                                      args=["--no-sandbox", "--autoplay-policy=no-user-gesture-required"])
        raise


class PlayChecker:
    def __init__(self):
        from playwright.sync_api import sync_playwright
        self._cm = sync_playwright()
        self._pw = self._cm.start()
        self.browser = _launch(self._pw)
        self._fetch_ctx = {}

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

    def fetch(self, url, timeout_ms=20000):
        """requests 被 403/503（Cloudflare 一类）拦住时，用真浏览器取页面。同一个站复用同一个浏览器上下文，
        这样第一次过了检查拿到的 cookie 后面的页面也能用。返回 (状态码, 文本, 最终地址)。"""
        from urllib.parse import urlparse
        host = urlparse(url).netloc
        ctx = self._fetch_ctx.setdefault(host, self.browser.new_context(user_agent=UA, ignore_https_errors=True))
        page = ctx.new_page()
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

    def check(self, source, episode_url, wait_ms=20000):
        mv = source["arguments"]["searchConfig"].get("matchVideo", {})
        try:
            match = re.compile(to_py_regex(mv.get("matchVideoUrl") or r"$^"))
        except re.error:
            match = None
        scan_dom = bool(mv.get("scanDomMediaUrls"))
        seen = []
        ctx = self.browser.new_context(user_agent=UA, ignore_https_errors=True)
        page = ctx.new_page()
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
            generic = [u for u in seen if MEDIA_RE.search(u)]
            if generic:
                return {"play": "mismatch", "play_reason": "页面出现了视频地址，但 matchVideoUrl 认不出来",
                        "media": generic[0][:200]}
            return {"play": "none", "play_reason": "等了 %d 秒没有出现视频地址" % (wait_ms // 1000)}
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
