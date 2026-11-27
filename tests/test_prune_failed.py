"""长期失效的源自动移出订阅（prune_failed_after）的自测（不联网）。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aniyuan.check.health import update_health, prunable

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)


def cand(key, status, direct=None):
    src = {"id": "aniyuan-" + key, "factoryId": "web-selector", "version": 2,
           "arguments": {"name": key, "searchConfig": {"searchUrl": "https://%s.com/s?wd={keyword}" % key}, "iconUrl": ""}}
    c = dict(origin="anibaka", key=key, source=src, date=1, notes=[], smoke={"status": status, "reason": "x"})
    if direct:
        c["smoke_direct"] = {"status": direct}
    return c


def after_runs(key, statuses, hist=None, direct=None, threshold=2):
    """依次喂入几次检测结果，返回最后一次的候选。"""
    hist, c = dict(hist or {}), None
    for i, st in enumerate(statuses):
        c = cand(key, st, direct)
        hist = update_health([c], hist, 100 + i, threshold)
    return c, hist


c, _ = after_runs("a", ["fail"] * 7)
check("连续 7 次 fail、从没通过过：长期失效", prunable(c, 7))
c, _ = after_runs("a", ["fail"] * 6)
check("只失败 6 次：还没到 7 次，不移出", not prunable(c, 7))
c, _ = after_runs("a", ["fail"] * 30)
check("阈值设为 0：功能关闭", not prunable(c, 0) and not prunable(c, None))
c, _ = after_runs("a", ["fail"] * 7, direct="ok")
check("国内 fail 但海外直连通过：不算失败，不移出", not prunable(c, 7))
c, h = after_runs("a", ["fail"] * 7)
c = cand("a", "ok")
h = update_health([c], h, 999, 2)
check("中途通过一次：fails 清零，不移出", not prunable(c, 7) and h["anibaka:a"]["fails"] == 0)
c, h = after_runs("a", ["fail"] * 7)
c = cand("a", "unreachable")
update_health([c], h, 999, 2)
check("已经长期失效，这次只是打不开：不算恢复，继续移出", prunable(c, 7))
c, h = after_runs("a", ["fail"] * 7)
c = cand("a", "unreachable", "ok")
update_health([c], h, 999, 2)
check("国内打不开但海外直连通过：回到订阅", not prunable(c, 7))
c, _ = after_runs("a", ["unreachable"] * 30)
check("只是一直打不开、没明确失败过：不移出", not prunable(c, 7))
c, _ = after_runs("a", ["ok", "fail", "fail", "unreachable"])
check("通过后又确认失败，再打不开：旧成绩作废不沿用", not c["health"]["carry"])
c, _ = after_runs("a", ["ok", "fail", "unreachable"])
check("只失败 1 次（没到阈值）就打不开：仍沿用旧成绩", c["health"]["carry"])
c, _ = after_runs("a", ["ok", "fail"])
check("以前通过过、才失败一次（宽限期）：不移出", not prunable(c, 1))

print("\n全部通过" if not bad else "\n%d 项失败" % bad)
sys.exit(1 if bad else 0)
