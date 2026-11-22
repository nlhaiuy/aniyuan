"""自动选浏览器（browser_pick）的自测：评分、决策保护、state 读写、config 解析、命令行。不联网、不开浏览器。"""
import io, json, os, sys, tempfile, contextlib, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from aniyuan.check import browser_pick as B

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)


def make(root, data):
    """data: {浏览器: {站点: (XHR 总数, 带视频地址条数) 或 None（没走到播放页）}}"""
    for b, sites in data.items():
        for site, v in sites.items():
            d = os.path.join(root, b, site); os.makedirs(d)
            meta = {"key": site, "browser": b}
            if v is not None:
                meta["play_xhr"] = {"count": v[0], "media": v[1]}
            json.dump(meta, open(os.path.join(d, "meta.json"), "w"))


def S(**kw):   # 快速造评分：S(chromium=(站数, 成功站数))
    return {b: dict(sites=v[0], ok=v[1], media=v[1]) for b, v in kw.items()}


# ---------- 评分 ----------
tmp = tempfile.mkdtemp()
make(tmp, {"chromium": {"a": (3, 0), "b": (5, 1), "c": None, "d": (2, 0)},
           "chrome": {"a": (4, 1), "b": (5, 2), "c": (1, 0), "d": (2, 1)}})
os.makedirs(os.path.join(tmp, "firefox"))                       # 空目录：起不来的浏览器
json.dump({}, open(os.path.join(tmp, "INDEX.md.json"), "w"))     # 杂文件不影响
sc = B.scores(tmp)
check("评分：没走到播放页的站不算；成功站数 / 视频地址条数", sc["chromium"] == dict(sites=3, ok=1, media=1) and sc["chrome"] == dict(sites=4, ok=3, media=4))
check("评分：没有数据的浏览器（空目录）不出现", "firefox" not in sc)
single = tempfile.mkdtemp(); make(single, {})
os.makedirs(os.path.join(single, "a")); json.dump({"play_xhr": {"count": 1, "media": 1}}, open(os.path.join(single, "a", "meta.json"), "w"))
check("评分：单浏览器抓取（不分浏览器子目录）返回空", B.scores(single) == {} and B.scores("/不存在的目录") == {})
bad_meta = tempfile.mkdtemp(); os.makedirs(os.path.join(bad_meta, "chromium", "x")); open(os.path.join(bad_meta, "chromium", "x", "meta.json"), "w").write("{坏")
check("评分：坏的 meta.json 跳过，不崩", B.scores(bad_meta) == {})

# ---------- 决策 ----------
c, why = B.decide(S(chromium=(5, 1)), "chromium")
check("数据不足（没有别的浏览器）：保持原样", c == "chromium" and "数据不足" in why)
c, why = B.decide(S(chromium=(5, 1), chrome=(5, 4)), "firefox")
check("数据不足时保持的是「现在的选择」，不是默认值", B.decide(S(chromium=(5, 1)), "firefox")[0] == "firefox" and c == "chrome")
c, why = B.decide(S(chromium=(2, 0), chrome=(2, 2)), "chromium")
check("chromium 只走到 2 个站（样本太少）：不做决定", c == "chromium" and "至少要 3" in why)
c, why = B.decide(S(chromium=(5, 2), chrome=(5, 3)), "chromium")
check("只比 chromium 多 1 个站：不够门槛，不换", c == "chromium" and "没有浏览器" in why)
c, why = B.decide(S(chromium=(5, 2), chrome=(5, 4)), "chromium")
check("多 2 个站：换成 chrome，原因里写明数字", c == "chrome" and "多 2 个站" in why and "4 个站" in why)
c, _ = B.decide(S(chromium=(5, 1), chrome=(5, 3), firefox=(5, 4)), "chromium")
check("几个都够格：取多的那个（firefox 多 3 个站）", c == "firefox")
c, _ = B.decide(S(chromium=(5, 1), chrome=(5, 4), firefox=(5, 4)), "chromium")
check("并列：按 chrome > firefox 的顺序", c == "chrome")
c, why = B.decide(S(chromium=(5, 3), chrome=(5, 4)), "chrome")
check("已经选了 chrome、优势没有了：换回 chromium", c == "chromium")
c, _ = B.decide(S(chromium=(5, 1), chrome=(5, 4)), "chrome")
check("已经选了 chrome、优势还在：继续 chrome", c == "chrome")
check("现在的选择是乱写的名字：当成 chromium", B.decide(S(chromium=(5, 1)), "edge")[0] == "chromium")

# ---------- pick：写 state，没变化不重写，数据不足不动它 ----------
cap = tempfile.mkdtemp()
make(cap, {"chromium": {"a": (3, 0), "b": (5, 1), "c": (1, 0)}, "chrome": {"a": (4, 1), "b": (5, 2), "c": (1, 1)}})
st = os.path.join(tempfile.mkdtemp(), "state", "browser.json")
choice, why, sc, wrote = B.pick(cap, st, today=datetime.date(2026, 11, 22))
d = json.load(open(st, encoding="utf-8"))
check("pick：chrome 多 2 个站 → 选 chrome，写出 state（含日期、评分、原因）",
      choice == "chrome" and wrote and d["browser"] == "chrome" and d["decided"] == "2026-11-22" and d["scores"]["chromium"]["ok"] == 1 and "chrome" in d["reason"])
mtime = os.path.getmtime(st)
choice, why, sc, wrote = B.pick(cap, st, today=datetime.date(2026, 11, 29))
check("pick：结果没变就不重写（不会只有日期变的空提交）", not wrote and os.path.getmtime(st) == mtime and json.load(open(st, encoding="utf-8"))["decided"] == "2026-11-22")
thin = tempfile.mkdtemp(); make(thin, {"chromium": {"a": (1, 0)}, "chrome": {"a": (1, 1)}})
choice, why, sc, wrote = B.pick(thin, st)
check("pick：数据不足不动 state，保持上次的 chrome", choice == "chrome" and not wrote and json.load(open(st, encoding="utf-8"))["browser"] == "chrome")
choice, why, sc, wrote = B.pick(single, st)
check("pick：给的是单浏览器抓取：不动 state", choice == "chrome" and not wrote)
cap2 = tempfile.mkdtemp(); make(cap2, {"chromium": {"a": (3, 1), "b": (5, 1), "c": (1, 1)}, "chrome": {"a": (4, 1), "b": (5, 1), "c": (1, 1)}})
choice, why, sc, wrote = B.pick(cap2, st, today=datetime.date(2026, 12, 6))
check("pick：之后优势没有了 → 换回 chromium 并写 state", choice == "chromium" and wrote and json.load(open(st, encoding="utf-8"))["browser"] == "chromium")

# ---------- resolve ----------
good = os.path.join(tempfile.mkdtemp(), "b.json"); json.dump({"browser": "firefox"}, open(good, "w"))
check("resolve：auto 读 state", B.resolve({"browser": "auto"}, good) == "firefox")
check("resolve：auto 但没有 state 文件 → chromium（行为不变）", B.resolve({"browser": "auto"}, "/没有/这个文件.json") == "chromium")
junk = os.path.join(tempfile.mkdtemp(), "b.json"); json.dump({"browser": "edge"}, open(junk, "w"))
check("resolve：auto 但 state 里是不认识的名字 → chromium", B.resolve({"browser": "auto"}, junk) == "chromium")
open(junk, "w").write("[1,2")
check("resolve：auto 但 state 文件坏了 → chromium", B.resolve({"browser": "AUTO"}, junk) == "chromium")
check("resolve：写了具体名字就固定用它，不看 state", B.resolve({"browser": "Chrome"}, good) == "chrome")
check("resolve：留空 / 没写 → None（交给环境变量 / 默认）", B.resolve({"browser": ""}, good) is None and B.resolve({}, good) is None and B.resolve(None, good) is None)

# ---------- 命令行 ----------
cfg = os.path.join(tempfile.mkdtemp(), "c.json"); json.dump({"browser": "auto"}, open(cfg, "w"))
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = B.main(["resolve", "--config", cfg, "--state", good])
check("命令行 resolve：打印该用的浏览器（给工作流装浏览器用）", rc == 0 and buf.getvalue().strip() == "firefox")
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    B.main(["resolve", "--config", "/没有.json", "--state", good])
check("命令行 resolve：config 读不到 → chromium", buf.getvalue().strip() == "chromium")
st2 = os.path.join(tempfile.mkdtemp(), "browser.json")
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = B.main(["pick", cap, "--state", st2])
out = buf.getvalue()
check("命令行 pick：打印每个浏览器的成绩和选择", rc == 0 and "chromium" in out and "选择：chrome" in out and os.path.exists(st2))

# ---------- 仓库里的 config 现在的设置：auto，且没有 state 时是 chromium ----------
cfg_real = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
check("config.json：browser 是 auto", cfg_real.get("browser") == "auto")
check("仓库里没有 state/browser.json 时 auto = chromium（合并后行为不变）",
      os.path.exists(B.STATE_PATH) or B.resolve(cfg_real) == "chromium")

print("\n%d 项未通过" % bad if bad else "\n全部通过")
sys.exit(1 if bad else 0)
