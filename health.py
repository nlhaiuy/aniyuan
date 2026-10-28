"""检测历史：避免一次偶发的检测失败就让订阅换来源、或给描述加警告。

每个候选（来源:规则）在 state/health.json 里记录：
  fails    连续“明确失败”（status=fail：页面能打开但选择器没选中）的次数，通过一次就清零
  last_ok  最近一次检测通过的时间
  play     最近一次检测通过时的播放检测结果（用来在宽限期内维持原来的排名）
blocked / unreachable / skipped / 没检测 都不算失败，也不会清零，记录原样保留。

宽限期（grace）：这次 fail，但以前通过过，且连续失败次数还没到阈值（config.fail_threshold，默认 2）。
宽限期内按“上次通过”的成绩排名、不加警告前缀、不被 drop_failed 剔除；到阈值才真正降级。
一直没通过过的候选（没有 last_ok）第一次失败就算数。
"""

DEFAULT_THRESHOLD = 2
# 检测通过后按播放检测结果排名：能播 > 没检测 > 没抓到 > 认不出（和 build.merge 里一致）
PLAY_TIER = {"ok": 3, "error": 2, "none": 1.8, "blocked": 1.6, "mismatch": 1.5}
KEEP = ("fails", "last_ok", "last_fail", "play", "last")


def cand_key(c):
    return "%s:%s" % (c["origin"], c["key"])


def update_health(cands, history, now, threshold=DEFAULT_THRESHOLD):
    """按这次的检测结果更新历史，并给每个候选写上 c["health"]。返回新的历史（只保留这次出现的候选）。"""
    new = {}
    for c in cands:
        if c.get("source") is None:
            continue
        key = cand_key(c)
        rec = {k: v for k, v in (history.get(key) or {}).items() if k in KEEP}
        sm = c.get("smoke") or {}
        st = sm.get("status")
        if st == "ok":
            rec.update(fails=0, last_ok=now, play=sm.get("play"))
        elif st == "fail":
            rec["fails"] = int(rec.get("fails", 0)) + 1
            rec["last_fail"] = now
        if st:
            rec["last"] = st
        grace = bool(st == "fail" and rec.get("last_ok") and rec["fails"] < threshold)
        c["health"] = dict(rec, grace=grace)
        if grace:
            c["notes"].append("自动检测未通过（连续 %d/%d 次），以前通过过，暂不降级、不加警告" % (rec["fails"], threshold))
        if rec:
            new[key] = rec
    return new


def confirmed_fail(c):
    """检测明确失败，并且已经不在宽限期内。"""
    return (c.get("smoke") or {}).get("status") == "fail" and not (c.get("health") or {}).get("grace")


def smoke_tier(c):
    """给 merge 用的“实测档位”：通过的按播放结果分档；明确失败为 0；宽限期内按上次通过的成绩；
    其余（没有结论 / 没检测）为 1。"""
    sm = c.get("smoke") or {}
    st = sm.get("status")
    if st == "ok":
        return PLAY_TIER.get(sm.get("play"), 2)
    if st == "fail":
        h = c.get("health") or {}
        return PLAY_TIER.get(h.get("play"), 2) if h.get("grace") else 0
    return None   # 交给调用方：推测的搜索地址排后面，其余为 1
