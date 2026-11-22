"""根据多浏览器抓取的对比结果，挑日常构建用的浏览器。

数据来源：capture 用 --browsers 抓出来的 <目录>/<浏览器>/<站点>/meta.json，里面的 play_xhr 记着
「播放页抓到几条 XHR、其中几条响应里带视频地址」。写 play、学 play 要的就是带视频地址的那条，
所以一个浏览器在越多的站上抓到它，越适合当默认浏览器。

决定规则（保守，宁可不换）：
  * 默认浏览器是 chromium。只有 chromium 和至少一个别的浏览器都有数据，并且 chromium 至少走到了 MIN_SITES 个站的播放页，才做决定，
    否则保持原来的选择不动（数据不足不改）。
  * 别的浏览器要在至少 MARGIN 个站上比 chromium 多抓到视频地址才换；几个都够格，取站点数最多的，
    并列时按 PREFERENCE 的顺序（chrome 和 chromium 同内核、UA 处理一致，优先）。
  * 否则就用 chromium：已经选了别的浏览器、但它的优势没有了（不再比 chromium 多 MARGIN 个站），自动换回 chromium。
  * 一个浏览器起不来 / 没有数据，就不参与比较。

config.json 的 browser 设为 "auto" 时，构建读 state/browser.json 里的选择；文件不存在或内容不对就是 chromium。
设成具体的名字就固定用它，不受这里影响。

命令行：
  python -m aniyuan.check.browser_pick pick <抓取目录> [--state state/browser.json]   # 评分并更新选择
  python -m aniyuan.check.browser_pick resolve [--config config.json] [--state state/browser.json]   # 打印构建该用哪个浏览器
"""
import argparse
import datetime
import json
import os
import sys

DEFAULT = "chromium"
PREFERENCE = ("chrome", "firefox", "webkit")   # 非默认浏览器并列时的先后
BROWSERS = ("chromium", "chrome", "firefox", "webkit")
MARGIN = 2        # 比 chromium 至少多几个站抓到视频地址才换
MIN_SITES = 3     # chromium 至少走到几个站的播放页，样本太少不做决定
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE_PATH = os.path.join(ROOT, "state", "browser.json")


def scores(captures_dir):
    """读多浏览器抓取目录，返回 {浏览器: {"sites": 走到播放页的站数, "ok": 抓到视频地址的站数, "media": 带视频地址的 XHR 总条数}}。
    只认 <目录>/<浏览器名>/<站点>/meta.json 这种布局（单浏览器抓取不分子目录，没有对比意义，返回空）。"""
    out = {}
    if not os.path.isdir(captures_dir):
        return out
    for b in BROWSERS:
        bdir = os.path.join(captures_dir, b)
        if not os.path.isdir(bdir):
            continue
        row = dict(sites=0, ok=0, media=0)
        for site in sorted(os.listdir(bdir)):
            mp = os.path.join(bdir, site, "meta.json")
            if not os.path.isfile(mp):
                continue
            try:
                px = (json.load(open(mp, encoding="utf-8")).get("play_xhr")) or {}
            except (OSError, ValueError):
                continue
            if "count" not in px:   # 没走到播放页
                continue
            row["sites"] += 1
            row["ok"] += 1 if px.get("media") else 0
            row["media"] += int(px.get("media") or 0)
        if row["sites"]:
            out[b] = row
    return out


def _decide(sc, current=DEFAULT):
    """返回 (选择, 原因, 是否做出了决定)。数据不足时第三项是 False，选择就是 current。"""
    if current not in BROWSERS:
        current = DEFAULT
    base = sc.get(DEFAULT)
    others = {b: r for b, r in sc.items() if b != DEFAULT}
    if not base or not others:
        return current, "数据不足（需要 chromium 加至少一个别的浏览器都有结果），保持 %s" % current, False
    if base["sites"] < MIN_SITES:
        return current, "chromium 只走到 %d 个站的播放页（至少要 %d 个才做决定），保持 %s" % (base["sites"], MIN_SITES, current), False
    better = {b: r["ok"] - base["ok"] for b, r in others.items() if r["ok"] - base["ok"] >= MARGIN}
    if not better:
        return DEFAULT, "没有浏览器在至少 %d 个站上比 chromium（%d 个站抓到视频地址）更好，用 chromium" % (MARGIN, base["ok"]), True
    pref = {b: i for i, b in enumerate(PREFERENCE)}
    best = sorted(better, key=lambda b: (-better[b], pref.get(b, 99), b))[0]
    return best, "%s 在 %d 个站抓到视频地址，chromium 是 %d 个（多 %d 个站，达到 %d 的门槛）" % (best, sc[best]["ok"], base["ok"], better[best], MARGIN), True


def decide(sc, current=DEFAULT):
    """返回 (选择, 原因)。sc 是 scores() 的结果，current 是现在的选择（数据不足时原样保留）。"""
    return _decide(sc, current)[:2]


def read_state(path=STATE_PATH):
    try:
        d = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def resolve(config=None, state_path=STATE_PATH):
    """构建该用哪个浏览器：config 里写了具体名字就用它；"auto" 读 state；留空返回 None（交给环境变量 / 默认）。"""
    want = ((config or {}).get("browser") or "").strip().lower()
    if want == "auto":
        got = str(read_state(state_path).get("browser") or "").strip().lower()
        return got if got in BROWSERS else DEFAULT
    return want or None


def pick(captures_dir, state_path=STATE_PATH, today=None):
    """评分、决定、写 state。返回 (选择, 原因, 评分, 是否写了文件)。数据不足时不写文件（保持原样）。"""
    sc = scores(captures_dir)
    prev = read_state(state_path)
    current = str(prev.get("browser") or DEFAULT)
    choice, reason, decided = _decide(sc, current)
    if not decided:
        return choice, reason, sc, False
    new = dict(browser=choice, reason=reason, decided=(today or datetime.date.today()).isoformat(), scores=sc)
    if prev.get("browser") == choice and prev.get("scores") == sc:
        return choice, reason, sc, False   # 没变化，不重写（避免只有日期变的空提交）
    os.makedirs(os.path.dirname(os.path.abspath(state_path)), exist_ok=True)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(new, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return choice, reason, sc, True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("pick")
    a.add_argument("captures")
    a.add_argument("--state", default=STATE_PATH)
    b = sub.add_parser("resolve")
    b.add_argument("--config", default=os.path.join(ROOT, "config.json"))
    b.add_argument("--state", default=STATE_PATH)
    args = ap.parse_args(argv)
    if args.cmd == "pick":
        choice, reason, sc, wrote = pick(args.captures, args.state)
        for name, r in sc.items():
            print("%-9s 走到播放页 %d 个站，抓到视频地址 %d 个站（共 %d 条）" % (name, r["sites"], r["ok"], r["media"]))
        print("选择：%s（%s）%s" % (choice, reason, "" if wrote else "；state 没有变化"))
        return 0
    try:
        config = json.load(open(args.config, encoding="utf-8"))
    except (OSError, ValueError):
        config = {}
    print(resolve(config, args.state) or DEFAULT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
