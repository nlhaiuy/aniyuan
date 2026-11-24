"""站点图标：按浏览器的方式找到图标，存进仓库的 icons/，订阅里的 iconUrl 改指向自己仓库的 CDN 链接。

为什么要自己存一份：
  - 转换器给的图标常常是猜的（站点/favicon.ico），而浏览器是读首页 <link rel="icon"> 找图标的；
  - 有的图标放在图床上，带了防盗链（要求 Referer 是站点自己），Animeko 直接请求会被拒；
  - 站点换域名后，规则里的旧图标地址跟着失效；

做法（只在联网检测时运行）：
  1. 取站点首页，收集候选：首页 <link rel="icon"/"apple-touch-icon">（声明的尺寸大的优先，
     apple-touch-icon 没写尺寸按 180 算）→ 订阅里原来的 iconUrl → /favicon.ico；
  2. 逐个下载（带站点自己的 Referer），确认文件头确实是 PNG / ICO / JPEG / GIF / WebP、且不超过 300KB；
  3. 不是拿到第一张能用的就停：解码后比较真实像素，挑短边最大的那张（ICO 取里面最大的一帧；已经 >=128px 就不再往下试）；
  4. 装了 Pillow 时统一存成方形 PNG（非方形补透明边，大于 256px 缩到 256），存成 icons/<id>.png；
     没装 Pillow 就原样存；iconUrl 改成 <icon_base_url>/<文件名>；
  5. 全部候选都拿不到时：沿用上次存的图标，没有就保留原来的 iconUrl。
发布前用 `python -m aniyuan.icons --verify icons` 检查目录里只有合规的图片。
"""
import os
import re
import sys
from urllib.parse import urljoin, urlparse

# 注意：这个文件在 CI 的发布任务里也会运行（icons.py --verify），那个任务不装第三方依赖，
# 所以顶层只能用标准库；bs4 / requests 都在用到的函数里再导入。

MAX_BYTES = 300 * 1024
EXTS = ("png", "ico", "jpg", "gif", "webp")


def sniff(data):
    """按文件头判断图片类型，返回扩展名；不是支持的图片返回 None（HTML 错误页、SVG 等都会被挡掉）。"""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"\x00\x00\x01\x00":
        return "ico"
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:4] == b"GIF8":
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def site_origin(source):
    a = source.get("arguments", {})
    sc = a.get("searchConfig", {})
    for u in (sc.get("searchUrl"), sc.get("rawBaseUrl"), a.get("iconUrl")):
        p = urlparse(u or "")
        if p.scheme in ("http", "https") and p.netloc:
            return "%s://%s" % (p.scheme, p.netloc)
    return None


MAX_TRIES = 8        # 每个站最多试几个候选地址
GOOD_ENOUGH = 128    # 短边达到这个像素就不再往下试
TARGET = 256         # 输出 PNG 的最大边长


def _declared_size(sizes, apple):
    """<link sizes="..."> 里声明的最大边长；没写：apple-touch-icon 按 180（iOS 的惯例），其它按 0（不知道）。"""
    nums = [int(n) for n in re.findall(r"(\d+)\s*x\s*\d+", (sizes or "").lower())]
    return max(nums) if nums else (180 if apple else 0)


def page_icons(html, base_url):
    """首页里声明的图标，按声明的尺寸从大到小排（同尺寸保持页面里的先后）。"""
    from bs4 import BeautifulSoup
    found = []
    for i, link in enumerate(BeautifulSoup(html or "", "lxml").find_all("link")):
        rel = [r.lower() for r in (link.get("rel") or [])]
        href = (link.get("href") or "").strip()
        if not href or href.startswith("data:") or not any("icon" in r for r in rel) or "mask-icon" in rel:
            continue
        apple = any(r.startswith("apple-touch-icon") for r in rel)
        found.append(((-_declared_size(link.get("sizes"), apple), i), urljoin(base_url, href)))
    return [u for _k, u in sorted(found)]


def candidates(origin, home_html, home_url, old_icon, extra=()):
    seen, out = set(), []
    for u in list(extra) + page_icons(home_html, home_url or origin + "/") + ([old_icon] if old_icon else []) + [origin + "/favicon.ico"]:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def decode(data):
    """用 Pillow 读出图片（ICO 取里面最大的一帧）。没装 Pillow 或读不出来返回 None。"""
    try:
        import io
        from PIL import Image
        im = Image.open(io.BytesIO(data))
        if im.format == "ICO" and im.info.get("sizes"):
            im.size = max(im.info["sizes"], key=lambda s: s[0] * s[1])
        im.load()
        return im
    except Exception:
        return None


def to_png(im, target=TARGET):
    """转成方形 RGBA PNG：非方形补透明边，大于 target 的用 LANCZOS 缩小；超过 300KB 就再缩。"""
    import io
    from PIL import Image
    im = im.convert("RGBA")
    w, h = im.size
    side = max(w, h)
    if w != h:
        canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        canvas.paste(im, ((side - w) // 2, (side - h) // 2))
        im = canvas
    if side > target:
        im = im.resize((target, target), Image.LANCZOS)
    for _ in range(4):
        buf = io.BytesIO()
        im.save(buf, "PNG", optimize=True)
        if buf.tell() <= MAX_BYTES:
            return buf.getvalue()
        im = im.resize((im.width * 3 // 4, im.width * 3 // 4), Image.LANCZOS)
    return None


def _existing(icons_dir, sid):
    for ext in EXTS:
        p = os.path.join(icons_dir, "%s.%s" % (sid, ext))
        if os.path.exists(p):
            return "%s.%s" % (sid, ext)
    return None


def _save(icons_dir, sid, ext, data):
    name = "%s.%s" % (sid, ext)
    for e in EXTS:   # 类型变了就清掉旧的
        old = os.path.join(icons_dir, "%s.%s" % (sid, e))
        if e != ext and os.path.exists(old):
            os.remove(old)
    p = os.path.join(icons_dir, name)
    if not (os.path.exists(p) and open(p, "rb").read() == data):
        with open(p, "wb") as f:
            f.write(data)
    return name


def resolve_icons(sources, icons_dir, base_url, get_html, get_image, prune=True):
    """sources：要输出的数据源列表（会被原地改 iconUrl）。
    get_html(url) -> (text, final_url) 或 None；get_image(url, referer) -> bytes 或 None。
    返回 [(id, 状态, 说明)]，状态：new / same / cached / kept。"""
    os.makedirs(icons_dir, exist_ok=True)
    base_url = base_url.rstrip("/")
    results, keep = [], set()
    for source in sources:
        sid, a = source["id"], source["arguments"]
        origin = site_origin(source)
        name, why = None, "没有可用的站点地址"
        if origin:
            home = get_html(origin + "/") or ("", origin + "/")
            tried, best = 0, None   # best = (短边像素, 序号, 地址, 数据, 扩展名, 解码后的图)
            for url in candidates(origin, home[0], home[1], a.get("iconUrl"))[:MAX_TRIES]:
                tried += 1
                data = get_image(url, origin + "/")
                ext = sniff(data) if data and len(data) <= MAX_BYTES else None
                if not ext:
                    continue
                im = decode(data)
                side = min(im.size) if im else 0
                if best is None or side > best[0]:
                    best = (side, tried, url, data, ext, im)
                if side >= GOOD_ENOUGH:
                    break
            if best:
                side, _n, url, data, ext, im = best
                png = to_png(im) if im else None
                if png:
                    data, ext = png, "png"
                before = _existing(icons_dir, sid)
                name = _save(icons_dir, sid, ext, data)
                results.append((sid, "new" if before != name or before is None else "same",
                                "%s%s" % (url, "（%d×%d）" % im.size if im else "")))
            else:
                why = "试了 %d 个候选地址都不是可用的图片" % tried
        if name is None:
            cached = _existing(icons_dir, sid)
            if cached:
                name = cached
                results.append((sid, "cached", "这次没取到，沿用上次存的图标（%s）" % why))
            else:
                results.append((sid, "kept", "%s，保留原来的 iconUrl" % why))
        if name:
            keep.add(name)
            a["iconUrl"] = "%s/%s" % (base_url, name)
    if prune:   # 不在订阅里的源，图标也清掉
        for fn in os.listdir(icons_dir):
            if fn.rsplit(".", 1)[-1] in EXTS and fn not in keep:
                os.remove(os.path.join(icons_dir, fn))
    return results


def verify_dir(path):
    """发布前的检查：目录里只能有合规的小图片。返回问题列表。"""
    problems = []
    for fn in sorted(os.listdir(path)):
        p = os.path.join(path, fn)
        ext = fn.rsplit(".", 1)[-1] if "." in fn else ""
        if ext not in EXTS or not re.match(r"^[a-z0-9][a-z0-9-]*\.[a-z]+$", fn):
            problems.append("%s：文件名或类型不合规" % fn)
            continue
        data = open(p, "rb").read()
        if len(data) > MAX_BYTES:
            problems.append("%s：超过 %dKB" % (fn, MAX_BYTES // 1024))
        elif sniff(data) != ext:
            problems.append("%s：文件头和扩展名对不上" % fn)
    return problems


def make_fetchers(session, timeout=15, browser_bytes=None):
    """真实网络用的两个抓取函数（测试里换成假的）。
    browser_bytes(url, referer) -> bytes|None：requests 没拿到真图片时的回退（用真浏览器，见 playcheck.PlayChecker.fetch_bytes）。"""
    from .check import smoke
    from .check import ua as ua_mod

    def get_html(url):
        try:
            r = smoke._get(url, session, timeout)
            return (r.text, r.url) if r.status_code == 200 else None
        except Exception:
            return None

    def get_image(url, referer):
        data = None
        try:
            r = session.get(url, headers=dict(ua_mod.request_headers(), Referer=referer, Accept="image/*,*/*;q=0.8"),
                            timeout=timeout, allow_redirects=True, stream=True)
            if r.status_code == 200:
                data = r.raw.read(MAX_BYTES + 1, decode_content=True)
        except Exception:
            data = None
        if not (data and sniff(data)) and browser_bytes:   # 403 / 防盗链 / 返回的是挑战页：改用真浏览器再试一次
            try:
                data = browser_bytes(url, referer)
            except Exception:
                data = None
        return data
    return get_html, get_image


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--verify":
        bad = verify_dir(sys.argv[2]) if os.path.isdir(sys.argv[2]) else []
        for b in bad:
            print("图标检查未通过：" + b)
        sys.exit(1 if bad else 0)
    sys.exit("用法：python -m aniyuan.icons --verify <icons 目录>")
