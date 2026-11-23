"""浏览器对比（重测失败候选）自测：不联网、不开浏览器。"""
import os, sys, tempfile, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from aniyuan.check import browser_compare as BC, browser_pick as BP, smoke as S

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)

def cand(k, st, src=True):
    return dict(key=k, origin="o", orig_site=k, source={"k": k} if src else None, smoke={"status": st})

cands = [cand("a", "ok"), cand("b", "blocked"), cand("b", "fail"), cand("c", "unreachable"), cand("d", "fail"), cand("e", "blocked", src=False)]
t = BC.pick_targets(cands)
check("只挑 blocked/fail、按站去重、跳过没有源的", [c["key"] for c in t] == ["b", "d"])
check("limit 生效", len(BC.pick_targets([cand(str(i), "fail") for i in range(20)], limit=5)) == 5)

# status 0（浏览器没取到）= unreachable
check("status 0 算 unreachable", S.status_kind(0) == "unreachable")

class PC:
    def __init__(self, proxy, name):
        if name == "webkit": raise RuntimeError("没装")
        self.name = name; self.closed = False
    def fetch(self, *a, **k): return (200, "", "")
    def close(self): self.closed = True

orig = BC.check_source
def fake_check(src, kw, session=None, ctx=None):
    assert S.FORCE_BROWSER and S.FETCHER, "对比时必须是浏览器优先"
    return {"status": "ok" if (src["k"] == "b" and fake_check.cur == "firefox") else "fail"}
fake_check.cur = None
def mk(proxy, name):
    fake_check.cur = name
    return PC(proxy, name)
BC.check_source = fake_check
try:
    cfg = {"browser_compare_wait": 0}
    res = BC.compare(cands, cfg, None, None, browsers=["chromium", "firefox", "webkit"], make_checker=mk)
finally:
    BC.check_source = orig
check("结果：targets 两个", len(res["targets"]) == 2)
check("firefox 救回 1 个，chromium 0 个", res["browsers"]["firefox"]["ok"] == 1 and res["browsers"]["chromium"]["ok"] == 0)
check("起不来的记原因、不计成绩", "没装" in res["browsers"]["webkit"]["error"] and "webkit" not in BC.to_scores(res))
check("状态已还原", S.FORCE_BROWSER is False and S.FETCHER is None)
check("报告里点名只有 firefox 通过", any("只有 firefox" in l for l in BC.summary_lines(res)))
check("没有失败候选：不启动浏览器", BC.compare([cand("a", "ok")], {}, None, None, make_checker=lambda *a: 1 / 0)["browsers"] == {})

# 成绩进 browser_pick：样本不足不动；够了且领先才换
tmp = os.path.join(tempfile.mkdtemp(), "b.json")
r = BP.pick_scores(BC.to_scores(res), tmp)
check("样本太少（2 个）不写 state", r[3] is False and not os.path.exists(tmp))
sc = {"chromium": {"sites": 5, "ok": 0, "media": 0}, "firefox": {"sites": 5, "ok": 3, "media": 3}}
r = BP.pick_scores(sc, tmp)
check("firefox 多救 3 个 → 选 firefox 并写 state", r[0] == "firefox" and json.load(open(tmp))["browser"] == "firefox")

print("\n%d 项未通过" % bad if bad else "\n全部通过")
sys.exit(1 if bad else 0)
