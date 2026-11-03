"""站点图标：按浏览器的方式找到图标，存进仓库的 icons/，订阅里的 iconUrl 改指向自己仓库的 CDN 链接。

为什么要自己存一份：
  - 转换器给的图标常常是猜的（站点/favicon.ico），而浏览器是读首页 <link rel="icon"> 找图标的；
  - 有的图标放在图床上，带了防盗链（要求 Referer 是站点自己），Animeko 直接请求会被拒；
  - 站点换域名后，规则里的旧图标地址跟着失效；
  - 国内访问 jsDelivr 一般比访问各个小站更稳。

做法（只在联网检测时运行）：
  1. 取站点首页，按浏览器的顺序收集候选：<link rel="icon"/"shortcut icon"/"apple-touch-icon">（尺寸接近 64 的优先）
     → 订阅里原来的 iconUrl → /favicon.ico；
  2. 逐个下载（带站点自己的 Referer），确认文件头确实是 PNG / ICO / JPEG / GIF / WebP、且不超过 300KB；
  3. 存成 icons/<id>.<扩展名>，iconUrl 改成 <icon_base_url>/<id>.<扩展名>；
  4. 全部候选都拿不到时：沿用上次存的图标，没有就保留原来的 iconUrl。
manual/ 里的源图标不动。发布前用 `python icons.py --verify icons` 检查目录里只有合规的图片。
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


def _size_score(sizes):
    m = re.match(r"(\d+)x\d+", (sizes or "").strip().lower())
    return abs(int(m.group(1)) - 64) if m else 32   # 没写尺寸按 32 算（favicon 的常见大小）


def page_icons(html, base_url):
    """首页里声明的图标，按优先级排好：普通 icon（尺寸接近 64）在前，apple-touch-icon 在后。"""
    from bs4 import BeautifulSoup
    found = []
    for i, link in enumerate(BeautifulSoup(html or "", "lxml").find_all("link")):
        rel = [r.lower() for r in (link.get("rel") or [])]
        href = (link.get("href") or "").strip()
        if not href or href.startswith("data:") or not any("icon" in r for r in rel) or "mask-icon" in rel:
            continue
        apple = any(r.startswith("apple-touch-icon") for r in rel)
        found.append(((1 if apple else 0, _size_score(link.get("sizes")), i), urljoin(base_url, href)))
    return [u for _k, u in sorted(found)]


def candidates(origin, home_html, home_url, old_icon):
    seen, out = set(), []
    for u in page_icons(home_html, home_url or origin + "/") + ([old_icon] if old_icon else []) + [origin + "/favicon.ico"]:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


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


def resolve_icons(items, icons_dir, base_url, get_html, get_image, prune=True):
    """items: [(source, skip)]，source 是要输出的数据源（会被原地改 iconUrl）；skip 为 True 的不动。
    get_html(url) -> (text, final_url) 或 None；get_image(url, referer) -> bytes 或 None。
    返回 [(id, 状态, 说明)]，状态：new / same / cached / kept / skipped。"""
    os.makedirs(icons_dir, exist_ok=True)
    base_url = base_url.rstrip("/")
    results, keep = [], set()
    for source, skip in items:
        sid, a = source["id"], source["arguments"]
        if skip:
            results.append((sid, "skipped", "手动源，图标不动"))
            continue
        origin = site_origin(source)
        name, why = None, "没有可用的站点地址"
        if origin:
            home = get_html(origin + "/") or ("", origin + "/")
            tried = 0
            for url in candidates(origin, home[0], home[1], a.get("iconUrl")):
                tried += 1
                data = get_image(url, origin + "/")
                ext = sniff(data) if data and len(data) <= MAX_BYTES else None
                if ext:
                    before = _existing(icons_dir, sid)
                    name = _save(icons_dir, sid, ext, data)
                    results.append((sid, "new" if before != name else "same", url))
                    break
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
    import smoke

    def get_html(url):
        try:
            r = smoke._get(url, session, timeout)
            return (r.text, r.url) if r.status_code == 200 else None
        except Exception:
            return None

    def get_image(url, referer):
        data = None
        try:
            r = session.get(url, headers=dict(smoke.HEADERS, Referer=referer, Accept="image/*,*/*;q=0.8"),
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
    sys.exit("用法：python icons.py --verify <icons 目录>")
