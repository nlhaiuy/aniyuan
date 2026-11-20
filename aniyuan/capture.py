"""抓取：把写规则要用的原始数据存下来（只抓取，不学习、不改订阅）。

对 capture_sites.json 里的每个站，走国内出口（ANIYUAN_PROXY，和联网检测同一条线路；拿不到的页面再用无头浏览器）：
  1. 搜索：试一批常见的搜索地址（和自动学习同一份），保存搜索页 / 搜索接口的原始内容
     （前几个能打开的、第一个被验证码拦住的，各存一份），同时记录每个地址的状态码；
  2. 详情页：从搜索结果里取第一个结果（网页看链接，JSON 接口按常见详情页写法试）；
  3. 播放页：取详情页里第一个剧集，保存页面原始 HTML，并用浏览器打开它，记录它自己发出的 XHR / fetch
     请求和响应（json-api 的 play 就是从这里找）；
  4. 海外出口：第一个搜索地址再用 GitHub 海外直连试一次，只记状态，用来对照。

输出到 <out>/<站点>/ ：meta.json（每一步的状态）、search-*.html|json、detail.html、play-page.html、play-xhr.json，
  以及 <out>/INDEX.md。内容都是公开页面；代理地址 / 密码不会写进任何文件。

用法：python -m aniyuan.capture [--sites capture_sites.json] [--only key1,key2] [--out captures]
环境：ANIYUAN_PROXY（国内出口，可选）。
"""
import argparse
import json
import os
import re
import sys
import time
from urllib.parse import quote, urljoin, urlparse

from bs4 import BeautifulSoup

from .check import network, smoke as smoke_mod, ua as ua_mod
from .check.autolearn import DETAIL_TEMPLATES, JSON_PATHS, NONSENSE, SEARCH_PATHS, find_json_results, is_catch_all
from .check.repair import DEFAULT_CONTAINERS, DEFAULT_LISTS, DEFAULT_PATTERNS, EP_TEXT, find_episode_selector, find_search_selector

MAX_BODY = 600_000        # 每个文件最多存这么多字符
MAX_XHR_TEXT = 6000       # 每条 XHR 响应最多存这么多字符
MAX_XHR = 60
PRESETS = dict(patterns=list(DEFAULT_PATTERNS), containers=list(DEFAULT_CONTAINERS), lists=list(DEFAULT_LISTS))
DEFAULT_KEYWORDS = ["葬送的芙莉莲", "海贼王"]


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text[:MAX_BODY])
    return os.path.basename(path)


def _kind(text):
    return "json" if (text or "").lstrip()[:1] in "{[" else "html"


class Capturer:
    def __init__(self, session, direct, pc, out, sleep=0.8):
        self.session, self.direct, self.pc, self.out, self.sleep = session, direct, pc, out, sleep

    # --- 单个请求：和联网检测同一套（requests，被 403/503 拦时换浏览器） ---
    def get(self, url, session=None):
        t0 = time.time()
        try:
            r = smoke_mod._get(url, session or self.session, 20)
        except Exception as e:
            return dict(url=url, status=type(e).__name__, text="", final=url, secs=round(time.time() - t0, 1))
        text = r.text or ""
        info = dict(url=url, status=r.status_code, final=getattr(r, "url", url), size=len(text), secs=round(time.time() - t0, 1))
        if r.status_code == 200 and smoke_mod._blocked(text):
            info["blocked"] = smoke_mod.captcha_kind(text)
        info["text"] = text
        return info

    def site(self, spec, keyword_list):
        key, origin = spec["key"], spec["origin"].rstrip("/")
        d = os.path.join(self.out, key)
        os.makedirs(d, exist_ok=True)
        meta = dict(key=key, origin=origin, note=spec.get("note", ""), steps=[], files=[])
        saved = dict(ok=0, blocked=0, empty=0)

        def rec(step, info, **extra):
            row = {k: v for k, v in info.items() if k != "text"}
            row.update(step=step, **extra)
            meta["steps"].append(row)

        def keep(name, text):
            meta["files"].append(_write(os.path.join(d, name), text))

        # 1) 搜索
        best = None    # (info, keyword, 路径)
        urls = [(u, "") for u in spec.get("search_urls", [])] + [(p, p) for p in SEARCH_PATHS + JSON_PATHS]
        first_exit_checked = False
        for kw in keyword_list:
            for path, tag in urls:
                u = (path if path.startswith("http") else origin + path).replace("{keyword}", quote(kw))
                info = self.get(u)
                time.sleep(self.sleep)
                if not first_exit_checked and self.direct is not None:   # 海外直连只对第一个地址试一次，对照用
                    first_exit_checked = True
                    o = self.get(u, self.direct)
                    rec("search-overseas", o)
                text = info["text"]
                has_kw = info["status"] == 200 and kw[:2] in text and not info.get("blocked")
                if has_kw and tag in SEARCH_PATHS:   # 乱写的关键词搜出来一样 = 首页兜底，不是真搜索
                    nt = self.get(u.replace(quote(kw), quote(NONSENSE)))
                    time.sleep(self.sleep)
                    if nt["status"] == 200 and is_catch_all(text, nt["text"]):
                        has_kw = False
                        rec("search", info, keyword=kw, found_keyword=False, catch_all=True)
                        continue
                rec("search", info, keyword=kw, found_keyword=bool(has_kw))
                if info.get("blocked") and saved["blocked"] < 1:
                    saved["blocked"] += 1
                    keep("search-captcha.html", text)
                elif has_kw and saved["ok"] < 3:
                    saved["ok"] += 1
                    keep("search-%d.%s" % (saved["ok"], _kind(text)), text)
                elif info["status"] == 200 and not info.get("blocked") and len(text) > 500 and saved["empty"] < 1:
                    saved["empty"] += 1
                    keep("search-no-keyword.%s" % _kind(text), text)
                if has_kw and best is None:
                    best = (info, kw, path)
                if best and saved["ok"] >= 2:
                    break
            if best:
                break
        # 静态请求都没拿到：浏览器渲染一次搜索页（JS 渲染的站）
        if best is None and self.pc is not None:
            kw = keyword_list[0]
            u = origin + SEARCH_PATHS[0].replace("{keyword}", quote(kw))
            try:
                status, text, final = self.pc.fetch(u, timeout_ms=25000)
            except Exception as e:
                status, text, final = type(e).__name__, "", u
            meta["steps"].append(dict(step="search-browser", url=u, status=status, final=final, size=len(text),
                                      found_keyword=kw[:2] in text))
            if text:
                keep("search-browser.%s" % _kind(text), text)
                if kw[:2] in text and not smoke_mod._blocked(text):
                    best = (dict(url=u, final=final, text=text, status=status), kw, SEARCH_PATHS[0])
        if best is None:
            meta["result"] = "没有拿到带关键词的搜索结果"
            return self._finish(d, meta)

        info, kw, path = best
        final = info.get("final") or info["url"]
        text = info["text"]

        # 2) 详情页
        detail_url, how = None, ""
        if _kind(text) == "json":
            got = find_json_results(text, kw)
            if got:
                for tpl in DETAIL_TEMPLATES:
                    u = urljoin(final, tpl.replace("{value}", str(got[2])))
                    di = self.get(u)
                    time.sleep(self.sleep)
                    rec("detail-guess", di, template=tpl)
                    if di["status"] == 200 and not di.get("blocked") and len(di["text"]) > 1500:
                        detail_url, how = u, "json:" + tpl
                        break
        else:
            found = find_search_selector(text, kw, PRESETS)
            if found:
                detail_url, how = urljoin(final, found[3][1]), "selector:" + found[0]
            else:   # 找不到合适的选择器：取第一个文字里带关键词的链接
                soup = BeautifulSoup(text, "lxml")
                for a in soup.select("a[href]"):
                    if kw[:2] in a.get_text(" ", strip=True) and not a["href"].startswith(("#", "javascript")):
                        detail_url, how = urljoin(final, a["href"]), "first-anchor"
                        break
        meta["detail_url"], meta["detail_how"] = detail_url, how
        if not detail_url:
            meta["result"] = "搜到了结果但找不到详情页链接"
            return self._finish(d, meta)
        di = self.get(detail_url)
        rec("detail", di)
        dhtml = di["text"]
        if (di["status"] != 200 or di.get("blocked") or len(dhtml) < 1500) and self.pc is not None:
            try:
                st, dhtml, dfinal = self.pc.fetch(detail_url, timeout_ms=25000)
                meta["steps"].append(dict(step="detail-browser", url=detail_url, status=st, final=dfinal, size=len(dhtml)))
            except Exception as e:
                meta["steps"].append(dict(step="detail-browser", url=detail_url, status=type(e).__name__))
        if not dhtml:
            meta["result"] = "详情页没取到"
            return self._finish(d, meta)
        keep("detail.html", dhtml)

        # 3) 播放页
        ep_url = None
        ep = find_episode_selector(dhtml, PRESETS)
        soup = BeautifulSoup(dhtml, "lxml")
        if ep:
            ep_url = urljoin(detail_url, ep[2][1])
            meta["episode_selector"] = {"selector": ep[0], "count": ep[1]}
        else:
            for a in soup.select("a[href]"):
                if re.search(r"play|watch|video|player", a["href"], re.I) or EP_TEXT.search(a.get_text(" ", strip=True)):
                    ep_url = urljoin(detail_url, a["href"])
                    break
        meta["episode_url"] = ep_url
        if not ep_url:
            meta["result"] = "详情页上找不到剧集链接"
            return self._finish(d, meta)
        pi = self.get(ep_url)
        rec("play-page", pi)
        if pi["text"]:
            keep("play-page.html", pi["text"])
        if self.pc is not None:
            try:
                entries = self.pc.capture(ep_url, wait_ms=20000)
            except Exception as e:
                entries = []
                meta["steps"].append(dict(step="play-xhr", error=type(e).__name__))
            slim = [dict(e, text=(e.get("text") or "")[:MAX_XHR_TEXT]) for e in entries[:MAX_XHR]]
            meta["steps"].append(dict(step="play-xhr", url=ep_url, count=len(entries)))
            keep("play-xhr.json", json.dumps(slim, ensure_ascii=False, indent=1))
        meta["result"] = "ok"
        return self._finish(d, meta)

    def _finish(self, d, meta):
        _write(os.path.join(d, "meta.json"), json.dumps(meta, ensure_ascii=False, indent=1))
        return meta


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sites", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "capture_sites.json"))
    ap.add_argument("--only", default="", help="只抓这几个站（key，逗号分隔）；也可以直接给域名，如 https://x.com")
    ap.add_argument("--out", default="captures")
    ap.add_argument("--no-browser", action="store_true", help="不用无头浏览器（只用 requests）")
    args = ap.parse_args(argv)

    specs = json.load(open(args.sites, encoding="utf-8")) if os.path.exists(args.sites) else []
    only = [x.strip() for x in args.only.split(",") if x.strip()]
    if only:
        byk = {s["key"]: s for s in specs}
        picked = []
        for o in only:
            if o in byk:
                picked.append(byk[o])
            elif o.startswith("http"):
                h = urlparse(o)
                picked.append(dict(key=re.sub(r"[^a-z0-9]+", "", h.netloc.split(".")[-2] if h.netloc.count(".") else h.netloc), origin="%s://%s" % (h.scheme, h.netloc)))
        specs = picked
    proxy = network.proxy_url()
    session = network.new_session(proxy)
    direct = network.new_session(None) if proxy else None
    ua_mod.configure({})
    pc = None
    if not args.no_browser:
        try:
            from .check.playcheck import PlayChecker
            pc = PlayChecker(proxy)
            smoke_mod.set_browser_fetcher(pc.fetch)
        except Exception as e:
            print("浏览器没起来，只用 requests：%s" % e, file=sys.stderr)
    cap = Capturer(session, direct, pc, args.out)
    os.makedirs(args.out, exist_ok=True)
    rows = []
    try:
        for spec in specs:
            print("== %s %s" % (spec["key"], spec["origin"]), flush=True)
            try:
                meta = cap.site(spec, spec.get("keywords") or DEFAULT_KEYWORDS)
            except Exception as e:   # 一个站出错不影响别的站
                meta = dict(key=spec["key"], origin=spec["origin"], result="出错：%s: %s" % (type(e).__name__, e), files=[])
                _write(os.path.join(args.out, spec["key"], "meta.json"), json.dumps(meta, ensure_ascii=False, indent=1))
            print("   %s；文件 %s" % (meta.get("result"), ", ".join(meta.get("files", []))), flush=True)
            rows.append(meta)
    finally:
        smoke_mod.set_browser_fetcher(None)
        if pc is not None:
            pc.close()
    lines = ["# 抓取索引", "", "出口：%s" % ("国内出口（代理）" if proxy else "GitHub 海外出口（没有配置国内代理）"), "",
             "| 站点 | 结果 | 详情页 | 剧集页 | 文件 |", "|---|---|---|---|---|"]
    for m in rows:
        lines.append("| %s | %s | %s | %s | %s |" % (m["key"], m.get("result", ""), m.get("detail_url") or "", m.get("episode_url") or "",
                                                     " ".join(m.get("files", []))))
    _write(os.path.join(args.out, "INDEX.md"), "\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
