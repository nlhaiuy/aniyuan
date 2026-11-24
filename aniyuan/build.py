#!/usr/bin/env python3
"""KazumiRules + AniBakaRule + 纯纯看番社区 JS 源 -> 一个 Animeko 订阅。

用法:
  python -m aniyuan --kazumi ./KazumiRules --anibaka ./AniBakaRule --out dist
  python -m aniyuan --kazumi ./KazumiRules --anibaka ./AniBakaRule --out dist --smoke

  --kazumi / --anibaka 都可以省略其中一个（只转换另一个）。
  两个仓库最好是完整克隆（fetch-depth: 0），才能取到每个规则文件的最后修改时间。

合并规则：
  1. 按“站点主机名”（去掉 www./m.，可在 config.json 的 site_aliases 里手动并站）分组；
  2. 同一站点在多个来源里都有，取最后修改时间更新的那个（并列时 Kazumi > 纯纯看番 > AniBaka）；
  3. 站点在 AniBaka 里有时，订阅里的 id 取自 AniBaka 的 key，否则取 Kazumi 规则名，输出时统一成 aniyuan-<站点名>；
     id 不随“谁赢了”变化，Animeko 里用户的启用状态才不会丢；
  4. AniBaka 规则转不了时，回退到 baseline/anibaka.json 里同 id 的现成配置。
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

from .convert.anibaka import convert_anx, site_host, source_id
from .convert.kazumi import convert_rule
from .convert.easybangumi import convert_extension
from .check.domains import follow_upstream, host_of
from .check import network, ua as ua_mod
from .check.health import (DEFAULT_CARRY_DAYS, abroad_ok, DEFAULT_THRESHOLD, auto_tier, blind_spots, confirmed_fail, smoke_tier,
                           update_health)
from .normalize import normalize_source
from .check.repair import (brittle, find_search_selector, mine_presets, repair_match_video, repair_source,
                           search_stats)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 仓库根目录（config.json、baseline/、state/ 等所在）
DEFAULT_FALLBACK_KEYWORDS = ["海贼王", "鬼灭之刃"]   # 主关键词搜不到时依次换用（config.smoke_fallback_keywords 可改，[] 关闭）


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def strip_private(source):
    s = json.loads(json.dumps(source))
    for k in [k for k in s if k.startswith("_")]:
        del s[k]
    return s


def git_date(repo, relpath):
    """文件最后一次提交的时间（epoch 秒）；取不到返回 None。"""
    try:
        out = subprocess.run(["git", "-C", repo, "log", "-1", "--format=%ct", "--", relpath],
                             capture_output=True, text=True, timeout=30).stdout.strip()
        return int(out) if out else None
    except Exception:
        return None


def file_hash(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def apply_state(cands, state, now):
    """用“内容哈希”判断规则什么时候真的改过，代替 git 提交日期（发布/整理提交也会动日期）。

    第一次见到（没有记录）：用 git 日期。之后哈希不变：沿用记录的日期，不管 git 日期怎么变；
    哈希变了：说明内容真的改了，取 git 日期（若它比记录新）否则取本次同步时间。
    返回新的 state（只保留这次出现的候选）。
    """
    new = {}
    for c in cands:
        key = "%s:%s" % ("anibaka" if c["origin"] == "baseline" else c["origin"], c["key"])
        h, git = c.get("raw_hash"), c.get("date")
        old = state.get(key)
        if not h:
            c["date_basis"] = "git"
            new[key] = old or {}
            continue
        if old and old.get("hash") == h and old.get("date"):
            c["date"], c["date_basis"] = old["date"], "内容未变"
        elif old and old.get("date"):
            c["date"] = git if git and git > old["date"] else now
            c["date_basis"] = "内容已变"
        else:
            c["date_basis"] = "首次记录"
        new[key] = {"hash": h, "date": c["date"]}
    return new


def fmt_date(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d") if ts else "未知"


def parse_iso(s):
    try:
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
    except Exception:
        return None


# ---------------------------------------------------------------- 收集候选
def rewrite_origin(source, old_origin, new_origin):
    """搜索被跳转到新域名、且之后一切正常时，把源里的旧域名整体换成新域名。"""
    from urllib.parse import urlparse
    old, new = urlparse(old_origin).netloc, urlparse(new_origin).netloc
    text = json.dumps(source, ensure_ascii=False).replace("://" + old, "://" + new)
    return json.loads(text)


def probe(c, keyword, session, presets, config):
    """联网检测一个候选：必要时换备用关键词、自动修复选择器、跟随域名跳转。结果写进 c["smoke"]。"""
    import time
    from .check.smoke import _blocked, check_source
    c.setdefault("orig_site", site_host(c["source"]))   # 域名跳转 / 跟随上游之前的站点，merge 分组时也要认它
    ctx = {}
    r = check_source(c["source"], keyword, session=session, ctx=ctx)
    # 搜索页能打开、但这个关键词没搜出结果：可能只是站里没这部番（或限制了搜索频率），先换备用关键词再下结论
    for alt in config.get("smoke_fallback_keywords", DEFAULT_FALLBACK_KEYWORDS):
        if not (r["status"] == "fail" and r.get("stage") == "search"):
            break
        if alt == keyword:
            continue
        time.sleep(config.get("smoke_fallback_wait", 1))
        ctx2 = {}
        r2 = check_source(c["source"], alt, session=session, ctx=ctx2)
        if r2["status"] == "ok":
            ctx.clear()
            ctx.update(ctx2)
            r = dict(r2, keyword=alt)
            keyword = alt   # 后面的修复 / 复检都用这个关键词
            c["notes"].append("搜索「%s」没有结果，换成「%s」检测通过" % (config.get("smoke_keyword", "葬送的芙莉莲"), alt))
            break

    def fetch(url):
        try:
            resp = session.get(url, headers=ua_mod.request_headers(c["source"]["arguments"]["searchConfig"].get("userAgent")),
                               timeout=15)
            return resp.text if resp.status_code == 200 and not _blocked(resp.text) else None
        except Exception:
            return None

    def try_repair(which, require_not_fewer=None):
        new, why = repair_source(c["source"], ctx, keyword, presets, fetch, which, c.get("search_hints") or ())
        if not new:
            return False, why
        if ctx.get("detail_url_repaired"):
            new["_probe_detail_url"] = ctx["detail_url_repaired"]
        ctx2 = {}
        r2 = check_source(new, keyword, session=session, ctx=ctx2)
        if r2["status"] != "ok":
            return False, "修复后的选择器仍未通过：" + r2["reason"]
        if require_not_fewer is not None and r2.get("episode_count", 0) < require_not_fewer:
            return False, "替换后剧集数更少，保留原配置"
        new.pop("_probe_detail_url", None)
        new["arguments"]["description"] = "[选择器已自动修复] " + new["arguments"].get("description", "")
        c["source"] = new
        c["notes"].append("已自动修复选择器：" + why)
        ctx.clear()
        ctx.update(ctx2)
        r2["repaired"] = why
        return True, r2

    if c["source"].get("factoryId") == "web-selector" and config.get("repair", True):
        if r["status"] == "fail" and r.get("stage") in ("search", "episodes"):
            ok, res = try_repair("both" if r["stage"] == "search" else "episodes")
            if ok:
                r = res
            else:
                r["reason"] += "（自动修复也失败：%s）" % res
        elif r["status"] == "ok" and config.get("replace_brittle", True) and brittle(c["source"]):
            ok, res = try_repair("both", require_not_fewer=r.get("episode_count", 0))
            if ok:
                r = res
        elif r["status"] == "ok" and c.get("loose_search") and config.get("calibrate_loose", True) \
                and ctx.get("search_html"):
            # AniBaka 规则没写 detailPattern：结果选择器是“猜的”，检测通过也可能混进了非结果链接。
            # 在真实搜索页上和（同站其它来源提供的）候选比命中率，明显更准才替换，且剧集数不能变少
            sel = (c["source"]["arguments"]["searchConfig"].get("selectorSubjectFormatA") or {}).get("selectLists", "")
            h0, t0 = search_stats(ctx["search_html"], sel, keyword) if sel else (0, 0)
            best = find_search_selector(ctx["search_html"], keyword, presets, c.get("search_hints") or ())
            if best and best[2] and best[1] / best[2] > (h0 / t0 if t0 else 0):
                ok, res = try_repair("both", require_not_fewer=r.get("episode_count", 0))
                if ok:
                    r = res
    fo = r.get("final_origin")
    if fo and r["status"] == "ok" and config.get("follow_redirects", True):
        from urllib.parse import urlparse
        sc = c["source"]["arguments"]["searchConfig"]
        old = "%s://%s" % (urlparse(sc["searchUrl"]).scheme, urlparse(sc["searchUrl"]).netloc)
        c["source"] = rewrite_origin(c["source"], old, fo)
        c["notes"].append("域名已跳转，改用新域名 %s（原 %s）" % (fo, old))
    c["smoke"] = r


def direct_pass(cands, config, session=None):
    """海外直连：用不经代理的 GitHub 海外出口，把每个候选再测一遍，结果写进 c["smoke_direct"]。
    只做搜索 + 详情这两步（不修复、不改源）。结果既用来在报告里对比两个出口，也真正参与排名：国内没通过、海外通过的照样采用（health.abroad_ok）。
    浏览器 403 回退走的是代理，必须关掉，否则会把国内视角混进“海外直连”的结果里。"""
    from .check import smoke as smoke_mod
    from .check.smoke import check_source
    session = session or network.new_session(None)
    keyword = config.get("smoke_keyword", "葬送的芙莉莲")
    prev = smoke_mod.FETCHER
    smoke_mod.set_browser_fetcher(None)
    try:
        for c in cands:
            if c.get("source") is None:
                continue
            try:
                r = check_source(c["source"], keyword, session=session)
                for alt in config.get("smoke_fallback_keywords", DEFAULT_FALLBACK_KEYWORDS):   # 和主检测同样的备用关键词规则
                    if not (r["status"] == "fail" and r.get("stage") == "search"):
                        break
                    if alt != keyword:
                        r2 = check_source(c["source"], alt, session=session)
                        if r2["status"] == "ok":
                            r = r2
                            break
            except Exception as e:   # 对照检测出任何问题都不能拖垮主流程
                r = {"status": "skipped", "reason": "对照检测出错：%s" % type(e).__name__}
            c["smoke_direct"] = {k: r[k] for k in ("status", "reason", "episode_count") if k in r}
            if c.get("needs_play") and r.get("sample"):   # 等着学 play 的 json-api 源：主出口没检测到条目时，学习要用这份样本
                c["smoke_direct"]["sample"] = r["sample"]
            if abroad_ok(c):
                c["notes"].append("国内出口检测%s，但 GitHub 海外直连通过，照样采用（排名低一级）" % c["smoke"]["status"])
            time.sleep(config.get("smoke_direct_wait", 0.5))
    finally:
        smoke_mod.set_browser_fetcher(prev)


# 两个出口的结果怎么归类：只看“有没有通过”，没通过的再看是被拦 / 打不开 / 选择器不对
EXIT_NOTE = {
    ("ok", "ok"): "两边都通过",
    ("ok", "blocked"): "国内通过、海外被拦（海外服务器常被站点拦，符合预期）",
    ("ok", "unreachable"): "国内通过、海外打不开",
    ("ok", "fail"): "国内通过、海外选择器没选中（站点对海外返回了不同页面）",
}


def exit_compare(cands):
    """两个出口的对比：返回 (分类计数, 差异清单)。只统计两边都有结果的候选。
    清单行：(候选, 国内状态, 海外状态, 说明, 是否入选)。"""
    cats = {"both_ok": 0, "cn_only": 0, "abroad_only": 0, "neither": 0}
    rows = []
    for c in cands:
        a, b = (c.get("smoke") or {}).get("status"), (c.get("smoke_direct") or {}).get("status")
        if not a or not b or c.get("source") is None:
            continue
        key = "%s:%s" % (c["origin"], c["key"])
        if a == "ok" and b == "ok":
            cats["both_ok"] += 1
        elif a == "ok":
            cats["cn_only"] += 1
            rows.append((key, a, b, EXIT_NOTE.get((a, b), "国内通过、海外没通过"), bool(c.get("chosen"))))
        elif b == "ok":
            cats["abroad_only"] += 1
            rows.append((key, a, b, "海外通过、国内出口没通过：已按海外直连的结果采用（排名低一级）；可能是代理线路问题，也可能站点限制国内访问，值得留意", bool(c.get("chosen"))))
        else:
            cats["neither"] += 1
            if a != b:
                rows.append((key, a, b, "两边都没通过，但原因不同", bool(c.get("chosen"))))
    rows.sort(key=lambda r: (not r[4], r[1] == "ok", r[0]))   # 入选的排前面，“海外通过、国内没通过”的排在“国内通过”前面
    return cats, rows


def _check(source, config, session):
    from .check.smoke import check_source
    return check_source(source, config.get("smoke_keyword", "葬送的芙莉莲"), session=session)


def run_browser_compare(cands, config, proxy, session, state_path):
    """每周（或环境变量 ANIYUAN_BROWSER_COMPARE=1 手动触发）：拿联网检测没通过的候选，每个浏览器各重测一遍，
    成绩交给 browser_pick 更新 state/browser.json。任何出错都只打印，不影响订阅。"""
    import datetime
    if not config.get("browser_compare", True):
        return
    day = config.get("browser_compare_weekday", 6)   # 0=周一 … 6=周日；None = 每次都比
    forced = os.environ.get("ANIYUAN_BROWSER_COMPARE") == "1"
    if not forced and day is not None and datetime.datetime.utcnow().weekday() != day:
        return
    try:
        from .check import browser_compare, browser_pick
        res = browser_compare.compare(cands, config, proxy, session)
        for line in browser_compare.summary_lines(res):
            print(line)
        sc = browser_compare.to_scores(res)
        if sc:
            choice, reason, _, wrote = browser_pick.pick_scores(sc, state_path)
            print("浏览器对比结论：%s（%s）%s" % (choice, reason, "已更新 %s" % state_path if wrote else "；没有变化"))
    except Exception as e:
        print("浏览器对比出错，已跳过：%s" % e, file=sys.stderr)


def run_playchecks(cands, config, pc):
    """对检测通过的候选逐个做无头浏览器播放检测（耗时，约 20~30 秒一个）。
    页面里出现了视频地址但 matchVideoUrl 认不出（mismatch）时，试着修 matchVideoUrl 并重新检测。"""
    from .convert.kazumi import MATCH_VIDEO_URL
    wait = config.get("play_wait_ms", 20000)
    todo = [c for c in cands if (c.get("smoke") or {}).get("status") == "ok" and c["smoke"].get("episode_url")]
    for c in todo[: config.get("play_check_max", 80)]:
        try:
            res = pc.check(c["source"], c["smoke"]["episode_url"], wait)
            if res.get("play") == "mismatch" and config.get("repair", True) and config.get("repair_match_video", True):
                new, why = repair_match_video(c["source"], res.get("media_urls") or [], MATCH_VIDEO_URL)
                if new:
                    res2 = pc.check(new, c["smoke"]["episode_url"], wait)   # 改完必须重新检测通过才采用
                    if res2.get("play") == "ok":
                        c["source"] = new
                        c["notes"].append("已自动修复 matchVideoUrl：" + why)
                        res2["repaired_match"] = why
                        res = res2
                    else:
                        res["play_reason"] += "（自动修复 matchVideoUrl 后重新检测仍是 %s，保持原样）" % res2.get("play")
                else:
                    res["play_reason"] += "（自动修复 matchVideoUrl 也失败：%s）" % why
            res.pop("media_urls", None)
            c["smoke"].update(res)
        except Exception as e:
            c["smoke"].update({"play": "error", "play_reason": "检测出错：%s" % type(e).__name__})


def collect_kazumi(repo, config):
    out = []
    index = load_json(os.path.join(repo, "index.json"))
    for item in index:
        name = item["name"]
        rel = name + ".json"
        path = os.path.join(repo, rel)
        c = dict(origin="kazumi", key=name, version=str(item.get("version", "")), source=None,
                 status="missing", notes=[], info=[], guess=False)
        date = git_date(repo, rel)
        if not date and item.get("lastUpdate"):
            date = int(item["lastUpdate"]) // 1000
        c["date"] = date
        if not os.path.exists(path):
            c["notes"] = ["index.json 里有，但仓库里没有这个规则文件"]
            out.append(c)
            continue
        rule = load_json(path)
        c["live_hosts"] = [h for h in (host_of(rule.get("baseURL", "")), host_of(rule.get("searchURL", ""))) if h]
        c["version"] = str(rule.get("version", c["version"]))
        c["raw_hash"] = file_hash(path)
        res = convert_rule(rule, config)
        if res.source is not None and getattr(res, "_template_guess", False):
            res.source["_template_guess"] = True
        c.update(source=res.source, status=res.status, notes=res.notes, info=res.info)
        out.append(c)
    return out


def collect_anibaka(repo, baseline, config):
    out = []
    index = load_json(os.path.join(repo, "index.json"))
    synced = parse_iso(index.get("synced", ""))
    for e in index.get("entries", []):
        key = e["key"]
        sid = source_id(key)
        c = dict(origin="anibaka", key=key, version="rev %s" % e.get("rev", "?"), source=None,
                 status="unsupported", notes=[], info=[], guess=False)
        c["date"] = git_date(repo, e["ref"]) or synced
        path = os.path.join(repo, e["ref"])
        c["raw_hash"] = file_hash(path)
        res = None
        if os.path.exists(path):
            full = load_json(path)
            c["live_hosts"] = [h for h in (host_of(full.get("baseUrl", "")), host_of(full.get("iconUrl", ""))) if h]
        if os.path.exists(path):
            res = convert_anx(load_json(path), e, config)
            c.update(source=res.source, status=res.status, notes=list(res.notes), guess=res.guess)
            c["loose_search"] = any("searchList 没有 detailPattern" in n for n in c["notes"])
        else:
            c["notes"] = ["规则文件 %s 不存在" % e["ref"]]
        base_c = None
        if sid in baseline:
            bsrc = json.loads(json.dumps(baseline[sid]))
            base_c = dict(origin="baseline", key=key, version=c["version"], source=bsrc, status="baseline",
                          notes=["用你原来的基线配置（baseline/anibaka.json），与自动转换的结果一起比较"], info=[],
                          guess=False, date=c["date"], raw_hash=c.get("raw_hash"), live_hosts=c.get("live_hosts"))
            if c["source"] is not None:   # 保留你在基线里设置的优先级
                c["source"]["arguments"]["tier"] = bsrc["arguments"].get("tier", c["source"]["arguments"]["tier"])
                if bsrc["arguments"].get("channelTiers"):
                    c["source"]["arguments"]["channelTiers"] = bsrc["arguments"]["channelTiers"]
        if c["source"] is None and base_c is None:
            c["notes"].append("baseline 里也没有这个源，已跳过")
        out.append(c)
        if base_c:
            out.append(base_c)
    return out


def collect_easybangumi(repo, config):
    """纯纯看番社区 JS 源：release 里是真机验证过的，dev 是未验证的（默认不收）。"""
    out, seen = [], set()
    for channel, sub in (("release", "extensions"), ("dev", "dev-extensions")):
        if channel not in config.get("easybangumi_channels", ["release"]):
            continue
        d = os.path.join(repo, sub)
        for fn in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if not fn.endswith(".js") or fn in seen:
                continue
            seen.add(fn)
            key = fn[:-3]
            res, meta = convert_extension(os.path.join(d, fn), config)
            c = dict(raw_hash=file_hash(os.path.join(d, fn)), origin="easybangumi", key=key, version=meta.get("versionName", ""), source=res.source,
                     status=res.status, notes=list(res.notes), info=res.info, guess=False,
                     date=git_date(repo, "%s/%s" % (sub, fn)))
            c["info"] = ["纯纯看番 %s 通道" % channel] + list(c["info"])
            from .convert.easybangumi import parse_extension
            c["live_hosts"] = [h for h in [host_of(parse_extension(os.path.join(d, fn))[1].get("DEFAULT_BASE_URL", ""))] if h]
            out.append(c)
    return out


# ---------------------------------------------------------------- 合并
def attach_search_hints(cands, config):
    """给“搜索选择器是猜的”（loose_search）的候选配上同站其它来源的结果选择器，作为修复/校准的候选。

    同站 = 站点主机名相同（认 site_aliases）。别的来源只提供候选，用不用由真实搜索页上的命中率决定。"""
    aliases = config.get("site_aliases", {})

    def host(c):
        h = site_host(c["source"])
        return aliases.get(h, h)

    by_host = {}
    for c in cands:
        if c["source"] is None or c["source"].get("factoryId") != "web-selector":
            continue
        sc = c["source"]["arguments"].get("searchConfig", {})
        sel = (sc.get("selectorSubjectFormatA") or {}).get("selectLists") if sc.get("subjectFormatId") == "a" else None
        if sel and not c.get("loose_search"):
            by_host.setdefault(host(c), []).append((c, sel))
    for c in cands:
        if not c.get("loose_search") or c["source"] is None:
            continue
        hints = []
        for other, sel in by_host.get(host(c), []):
            if other is not c and other["origin"] != c["origin"] and sel not in hints:
                hints.append(sel)
        if hints:
            c["search_hints"] = hints
            c["notes"].append("同站其它来源提供了 %d 个结果选择器，检测时一并比较" % len(hints))


def merge(cands, config):
    from .normalize import normalize_id
    aliases = config.get("site_aliases", {})
    by_smoke = config.get("select_by_smoke", True)
    # 分组：同主机名，或同一条 AniBaka 规则（key 相同，含基线配置）算同一个站；用并查集合并，
    # 这样基线配置的域名和上游不一样时也不会被拆成两个站（否则会出现重复 id）
    live = [c for c in cands if c["source"] is not None]
    parent = {id(c): id(c) for c in live}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    seen_key = {}
    for c in cands:
        if c["source"] is None:
            c["site"] = None
            continue
        host = site_host(c["source"])
        c["site"] = aliases.get(host, host)
        orig = c.get("orig_site")
        # 检测时被改写了域名（跳转 / 跟随上游）的候选，原来的域名也算它的站点：
        # 否则同一个站里只有一部分候选换了新域名，就会被拆成两组，各自产出同一个 id
        keys = ["h:" + c["site"]] + (["h:" + aliases.get(orig, orig)] if orig and orig != host else []) \
            + (["a:" + c["key"]] if c["origin"] in ("anibaka", "baseline") else [])
        for k in keys:
            if k in seen_key:
                parent[find(id(c))] = find(seen_key[k])
            else:
                seen_key[k] = id(c)
    comp = {}
    for c in live:
        comp.setdefault(find(id(c)), []).append(c)
    groups = {}
    for members in comp.values():
        label = next((m["site"] for m in members if m["origin"] != "baseline"), members[0]["site"])
        groups[label] = members

    chosen, decisions, scores = [], [], {}
    for host, members in sorted(groups.items()):
        rank = {"kazumi": 3, "easybangumi": 2, "anibaka": 1}   # 时间相同：Kazumi > 纯纯看番 > AniBaka > 基线
        smoke_of = lambda c: (c.get("smoke") or {}).get("status")  # noqa: E731
        # 实测优先：检测通过 > 没测出结论（无法访问/验证码/跳过） > 明确失败；同档内再比修改时间
        def tier(c):
            if not by_smoke:
                return 0.5 if c.get("guess") else 1
            t = smoke_tier(c)   # 通过 / 明确失败 / 宽限期内按上次成绩；其余没有结论
            if t is not None:
                return t
            return 0.5 if c.get("guess") else 1   # 搜索地址是推测的：没验证过就排在后面
        members.sort(key=lambda c: (tier(c), c["date"] or 0, rank.get(c["origin"], 0)), reverse=True)
        by_date = sorted(members, key=lambda c: (c["date"] or 0, rank.get(c["origin"], 0)), reverse=True)[0]
        winner, reason = members[0], "更新（%s）" % fmt_date(members[0]["date"])
        if len(members) == 1:
            reason = "只有这一个来源"
        elif winner is not by_date:
            if smoke_of(by_date) is None and by_date.get("guess"):
                reason = "%s:%s 的搜索地址是推测的、没联网验证过，改用 %s:%s" % (by_date["origin"], by_date["key"], winner["origin"], winner["key"])
            else:
                reason = "最新的 %s:%s 自动检测%s，改用检测结果更好的（%s）" % (
                    by_date["origin"], by_date["key"], {"fail": "未通过"}.get(smoke_of(by_date), "没有结论"), smoke_of(winner) or "-")
        if winner is by_date and (winner.get("health") or {}).get("grace"):
            reason += "；自动检测本次未通过，但以前通过过，暂不降级"
        ab = [c for c in members if c["origin"] in ("anibaka", "baseline")]
        kz = [c for c in members if c["origin"] == "kazumi"]
        stable_id = source_id(ab[0]["key"]) if ab else (kz[0]["source"]["id"] if kz else winner["source"]["id"])
        winner["source"]["id"] = stable_id
        winner["chosen"] = True
        scores[id(winner)] = (tier(winner), winner["date"] or 0, rank.get(winner["origin"], 0))
        chosen.append(winner)
        decisions.append(dict(site=host, winner="%s:%s" % (winner["origin"], winner["key"]), id=normalize_id(stable_id), reason=reason,
                              members=["%s:%s(%s)" % (c["origin"], c["key"], fmt_date(c["date"])) for c in members]))
    return dedupe_ids(chosen, decisions, scores)


def dedupe_ids(chosen, decisions, scores):
    """兜底：不同站点组最终输出的 id 相同（同名站点因为域名不一致没被分到一组）时，保留检测结果更好的那个，
    其余的并进它的“同站点取舍”记录。宁可合并，也不能让重复 id 把整个构建弄失败、订阅停在旧版本上。"""
    from .normalize import normalize_id
    by_id = {}
    for c, d in zip(chosen, decisions):
        by_id.setdefault(normalize_id(c["source"]["id"]), []).append((c, d))
    for items in by_id.values():
        if len(items) < 2:
            continue
        items.sort(key=lambda cd: scores.get(id(cd[0]), (0, 0, 0)), reverse=True)
        keep_c, keep_d = items[0]
        for c, d in items[1:]:
            chosen.remove(c)
            decisions.remove(d)
            c["chosen"] = False
            keep_d["members"] += d["members"]
            keep_d["reason"] += "；同名站点 %s 因域名不一致被分成了两组，已合并为一个（保留检测结果更好的 %s）" % (d["site"], keep_d["winner"])
    return chosen, decisions


def apply_auto_tier(chosen, config):
    """给最终入选的源按联网检测结果自动分档。baseline 里手调的档位不再固定（它只是个起点，一样按检测结果升降）；其它来源 tier 已经不是默认值的不动。
    config.auto_tier 设为 false 关闭。没有联网检测结果的源保持原样（基线手调的档位这时当作兜底）。"""
    if not config.get("auto_tier", True):
        return
    default = config.get("default_tier", 4)
    for c in chosen:
        a = c["source"]["arguments"]
        if a.get("tier", default) != default and c["origin"] != "baseline":
            continue
        tier, why = auto_tier(c)
        if tier is None or tier == a.get("tier"):
            continue
        a["tier"] = tier
        c["notes"].append("优先级自动设为 %d（%s）" % (tier, why))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kazumi", help="KazumiRules 仓库目录")
    ap.add_argument("--anibaka", help="AniBakaRule 仓库目录")
    ap.add_argument("--easybangumi", help="CommunityJsExtensionEasyBangumi 仓库目录")
    ap.add_argument("--official", help="官方订阅 animeko-subs 仓库目录（json-api 源缺 play 时借鉴它的写法；"
                                       "并和你的源去重互补，见 config.official_dedupe）")
    ap.add_argument("--learned-cache", default=os.path.join(ROOT, "state", "learned.json"),
                    help="自动学习出来的规则缓存（7 天内沿用；学不出来的站点 3 天内不重试）")
    ap.add_argument("--play-cache", default=os.path.join(ROOT, "state", "play.json"),
                    help="从播放页学到的 play 的缓存（接口指纹没变就直接沿用）")
    ap.add_argument("--out", default="dist")
    ap.add_argument("--prev", default=os.path.join(ROOT, "dist", "all.json"),
                    help="上一次发布的订阅（用来写报告里的「本次变化」）")
    ap.add_argument("--config", default=os.path.join(ROOT, "config.json"))
    ap.add_argument("--baseline", default=os.path.join(ROOT, "baseline", "anibaka.json"))
    ap.add_argument("--state", default=os.path.join(ROOT, "state", "seen.json"),
                    help="记录各规则内容哈希和“最后真正改动时间”的文件")
    ap.add_argument("--health", default=os.path.join(ROOT, "state", "health.json"),
                    help="记录各候选历次联网检测结果的文件（连续失败才降级）")
    ap.add_argument("--icons-dir", default=None,
                    help="站点图标存放目录（和 --smoke 一起用才会联网取图标；不给就不处理图标）")
    ap.add_argument("--browser-state", default=os.path.join(ROOT, "state", "browser.json"),
                    help="浏览器选择（browser=auto 时读它；每周对比失败候选后更新）")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--playcheck", action="store_true", help="在 --smoke 之后再用无头浏览器检测能否播放（需要 playwright）")
    args = ap.parse_args()
    if not (args.kazumi or args.anibaka or args.easybangumi):
        ap.error("至少给一个 --kazumi / --anibaka / --easybangumi")

    config = load_json(args.config) if os.path.exists(args.config) else {}
    ua_mod.reset()
    ua_mod.configure(config)
    proxy = network.proxy_url()
    ua_audit = []
    baseline = {}
    if os.path.exists(args.baseline):
        baseline = {s["id"]: s for s in load_json(args.baseline)["mediaSources"]}

    cands = []
    if args.kazumi:
        cands += collect_kazumi(args.kazumi, config)
    if args.anibaka:
        cands += collect_anibaka(args.anibaka, baseline, config)
    if args.easybangumi:
        cands += collect_easybangumi(args.easybangumi, config)

    from . import official as official_mod
    # json-api 必须有 play：先借官方的；借不到的留着，联网检测后从播放页学；都不行才不输出
    official_mod.apply(cands, official_mod.load(args.official) if args.official else [], final=False)
    official_sites = official_mod.load_sites(args.official) if args.official else []

    state = load_json(args.state) if os.path.exists(args.state) else {}
    new_state = apply_state(cands, state, int(time.time()))
    os.makedirs(os.path.dirname(os.path.abspath(args.state)), exist_ok=True)
    with open(args.state, "w", encoding="utf-8") as f:
        json.dump(new_state, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")

    pc = None
    learned_made, learned_cache = [], {}

    def cleanup():   # 浏览器要一直开到图标步骤结束（图标下载也会用它回退），所以不在这个块里关
        pass

    if args.smoke:
        from .check import smoke as smoke_mod
        session = network.new_session(proxy)
        if proxy:
            print("检测走出口代理：%s" % network.describe(proxy))
            from .check import health as health_mod
            health_mod.EXIT = "国内出口"
        presets = mine_presets(args.anibaka)
        if args.playcheck:   # 浏览器启动一次：既用于 403 回退，也用于播放检测
            try:
                from .check.playcheck import PlayChecker
                from .check import browser_pick
                bname = browser_pick.resolve(config)   # 具体名字 = 固定用它；auto = 读 state/browser.json（每周对比抓取自动更新）；空 = 环境变量 / chromium
                try:
                    pc = PlayChecker(proxy, bname)
                except Exception as e:
                    if bname and bname != browser_pick.DEFAULT:   # 选定的浏览器起不来（比如没装）：退回 chromium，别丢了播放检测
                        print("浏览器 %s 起不来（%s），退回 %s" % (bname, str(e).strip().splitlines()[0][:80] if str(e).strip() else type(e).__name__, browser_pick.DEFAULT), file=sys.stderr)
                        pc = PlayChecker(proxy, browser_pick.DEFAULT)
                    else:
                        raise
                print("播放检测用的浏览器：%s" % pc.browser_name)
                if config.get("browser_fallback", True):
                    smoke_mod.set_browser_fetcher(pc.fetch)
            except Exception as e:  # 没装浏览器就跳过，不影响其它流程
                print("浏览器不可用，跳过播放检测和 403 回退：%s" % e, file=sys.stderr)
        def cleanup():  # noqa: F811
            smoke_mod.set_browser_fetcher(None)
            if pc:
                pc.close()
        try:
            ua_audit = ua_mod.audit(pc)   # UA 体检：真的发请求，核对 requests 和浏览器发出去的 UA / 客户端提示一致
            for name, ok, detail in ua_audit:
                print("UA 体检 %s：%s（%s）" % ("通过" if ok else "未通过", name, detail), file=sys.stderr)
            if config.get("learn", True):   # 没有任何来源能转的站点：看真实页面自己写规则（学到的照样要过下面的联网检测）
                from .check import autolearn
                learned_cache = load_json(args.learned_cache) if os.path.exists(args.learned_cache) else {}
                try:
                    learned_made = autolearn.learn_cands(
                        cands, session, network.new_session(None) if proxy else None, presets, learned_cache,
                        int(time.time()), config)
                except Exception as e:   # 学习只是补充，出任何问题都不能影响已有的订阅
                    print("自动学习出错，已跳过：%s" % e, file=sys.stderr)
            attach_search_hints(cands, config)
            for c in cands:
                if c["source"] is None:
                    continue
                probe(c, config.get("smoke_keyword", "葬送的芙莉莲"), session, presets, config)
                r = c["smoke"]
                if r.get("template"):
                    c["source"]["arguments"]["searchConfig"]["selectorSubjectFormatJsonPathIndexed"]["linkTemplate"] = r["template"]
                if r.get("subject_body"):   # json-api：章节请求体里的 id 不带引号才通过
                    c["source"]["arguments"]["searchConfig"]["subject"]["request"]["body"] = r["subject_body"]
                    c["notes"].append("章节接口的 id 参数改成不带引号的写法（带引号被接口拒绝）")
                time.sleep(1)
            if config.get("follow_upstream_domains", True):
                for key, old, new, ok in follow_upstream(cands, lambda src: _check(src, config, session)):
                    print("域名跟随 %s：%s → %s %s" % (key, old, new, "已采用" if ok else "未通过，保持原样"))
            if proxy and config.get("smoke_both_exits", True):
                print("海外直连对照检测（不经代理）……")
                direct_pass(cands, config)
            if pc:
                run_playchecks(cands, config, pc)
            run_browser_compare(cands, config, proxy, session, args.browser_state)
        except BaseException:
            cleanup()
            raise

    if args.smoke and learned_made:   # 检测明确失败的学习结果清掉，下次重学
        from .check import autolearn
        autolearn.finalize_cache(learned_made, learned_cache, int(time.time()))
    if args.smoke and learned_cache:
        os.makedirs(os.path.dirname(os.path.abspath(args.learned_cache)), exist_ok=True)
        with open(args.learned_cache, "w", encoding="utf-8") as f:
            json.dump(learned_cache, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")

    if any(c.get("needs_play") for c in cands):   # 从播放页学 play（或沿用缓存），仍然没有的不输出
        from .check import playlearn
        play_cache = load_json(args.play_cache) if os.path.exists(args.play_cache) else {}
        try:
            playlearn.learn_plays(cands, pc, network.new_session(proxy), play_cache, int(time.time()),
                                  config.get("play_wait_ms", 20000))
        except BaseException:
            cleanup()
            raise
        os.makedirs(os.path.dirname(os.path.abspath(args.play_cache)), exist_ok=True)
        with open(args.play_cache, "w", encoding="utf-8") as f:
            json.dump(play_cache, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
    official_mod.finalize(cands)
    if args.smoke:   # json-api 源：重放 play 请求，看取不取得到视频地址
        from .check import playlearn
        playlearn.check_plays(cands, network.new_session(proxy))

    if args.smoke:   # 没联网检测时不动历史
        history = load_json(args.health) if os.path.exists(args.health) else {}
        new_health = update_health(cands, history, int(time.time()), config.get("fail_threshold", DEFAULT_THRESHOLD),
                                   config.get("blind_carry_days", DEFAULT_CARRY_DAYS))
        os.makedirs(os.path.dirname(os.path.abspath(args.health)), exist_ok=True)
        with open(args.health, "w", encoding="utf-8") as f:
            json.dump(new_health, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")

    chosen, decisions = merge(cands, config)
    apply_auto_tier(chosen, config)

    # 和官方订阅对一遍：官方已覆盖的同站源降档 / 剔除；官方那条失效而自有的能用就保留补位
    official_mode = config.get("official_dedupe", "demote")
    official_rows = []
    if official_sites and official_mode != "off":
        off_check = None
        if args.smoke:
            off_session = network.new_session(proxy)
            off_check = lambda src: _check(src, config, off_session)  # noqa: E731
        official_rows = official_mod.reconcile(chosen, official_sites, config, off_check)
        for r in official_rows:
            print("官方重叠 %s ↔ %s：%s（%s）" % (r["name"], r["official"], r["action"], r["note"]))

    sources = []
    for c in sorted(chosen, key=lambda c: c["source"]["id"]):
        if c.get("dropped"):   # 官方已覆盖、按 official_dedupe=exclude 剔除
            continue
        s = strip_private(c["source"])
        sm = c.get("smoke")
        warn = ""
        # 只有“能打开页面但选择器没选中”（fail）、且已连续失败到阈值的才在描述里警告；
        # blocked / unreachable 多半是 GitHub 海外服务器被拦或访问不了，国内用户未必有问题，
        # 原因只写在报告里；宽限期内（以前通过过、这次才第一次失败）也不警告、不剔除
        if sm and confirmed_fail(c):
            if config.get("drop_failed"):
                c["dropped"] = True
                continue
            warn = sm["reason"]
        sources.append(normalize_source(c, s, config, warn))
    icon_results = []
    if args.icons_dir and args.smoke and config.get("icons", True):
        from . import icons as icons_mod
        try:
            get_html, get_image = icons_mod.make_fetchers(
                network.new_session(proxy), browser_bytes=(pc.fetch_bytes if pc and config.get("browser_fallback", True) else None))
            icon_results = icons_mod.resolve_icons(
                sources, args.icons_dir,
                config.get("icon_base_url", "https://raw.githubusercontent.com/nlhaiuy/aniyuan/main/icons"),
                get_html, get_image)
        except BaseException:
            cleanup()
            raise
    cleanup()
    ids = [s["id"] for s in sources]
    assert len(ids) == len(set(ids)), "出现重复 id：%s" % sorted({i for i in ids if ids.count(i) > 1})

    os.makedirs(args.out, exist_ok=True)
    sub = {"schemaVersion": 2, "mediaSources": sources, "exportedMediaSourceDataList": {"mediaSources": sources}}
    from . import changes
    changed = None
    if os.path.exists(args.prev):   # 上一次发布的订阅读不出来（第一次运行 / 文件坏了）就不写这一节
        try:
            changed = changes.diff(load_json(args.prev)["mediaSources"], sources)
        except (OSError, ValueError, KeyError, TypeError):
            changed = None
    with open(os.path.join(args.out, "all.json"), "w", encoding="utf-8") as f:
        json.dump(sub, f, ensure_ascii=False, indent=2)
        f.write("\n")

    label = {"ok": "完整", "partial": "有近似", "unsupported": "无法转换", "override": "手写", "missing": "缺文件",
             "baseline": "回退基线", "learned": "自动学习"}
    rep = ["# 订阅转换报告", "", "写入订阅 **%d** 个数据源（候选 %d 个，同站点合并后）。" % (len(sources), len(cands)), ""]
    if args.smoke:
        both = bool(proxy and any(c.get("smoke_direct") for c in cands))
        rep += ["检测出口：%s。" % ("国内出口（代理 %s）%s" % (network.describe(proxy), "，并用 GitHub 海外服务器直连也测了一遍（国内没通过、海外通过的照样采用，排名低一级），见「国内外出口对比」" if both else "")
                                  if proxy else "GitHub 海外服务器（国内站可能打不开或被拦）"), ""]
    if changed is not None:
        rep += changes.section(changed)[1:] + [""]
    rep += [
           "## 同站点取舍", "", "| 站点 | 最终 id | 采用 | 理由 | 候选（最后修改） |", "|---|---|---|---|---|"]
    for d in decisions:
        rep.append("| %s | %s | %s | %s | %s |" % (d["site"], d["id"], d["winner"], d["reason"], "<br>".join(d["members"])))
    if official_sites and official_mode != "off":
        rep += official_mod.report_section(official_rows, len(chosen), official_mode)
    rep += ["", "## 全部候选", "", "| 来源 | 规则 | 版本 | 修改日期（依据） | 转换 | 自动检测 | 播放 | 采用 | 备注 |", "|---|---|---|---|---|---|---|---|---|"]
    for c in cands:
        sm = c.get("smoke") or {}
        remark = "；".join(c["notes"] + ([sm["reason"]] if sm.get("reason") and sm.get("status") != "ok" else [])
                           + ([sm["play_reason"]] if sm.get("play") not in (None, "ok") else []))
        rep.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            c["origin"], c["key"], c["version"], fmt_date(c["date"]) + ("（%s）" % c["date_basis"] if c.get("date_basis") else ""), label.get(c["status"], c["status"]),
            sm.get("status", "-") + ("（海外：%s）" % c["smoke_direct"]["status"] if c.get("smoke_direct") else "") + ("（已剔除）" if c.get("dropped") else ""), sm.get("play", "-"),
            "是" if c.get("chosen") else "否", remark.replace("|", "/")))
    if args.smoke:
        cats, diff = exit_compare(cands)
        if sum(cats.values()):
            rep += ["", "## 国内外出口对比", "",
                    "同一批候选分别用国内出口（代理）和 GitHub 海外服务器直连各测了一遍；表中「自动检测」列括号里是海外直连的结果。国内出口通过的按国内成绩排名；国内没通过、只有海外直连通过的也照样采用，只是排名和分档低一级。", "",
                    "| 国内 / 海外 | 个数 |", "|---|---|",
                    "| 两边都通过 | %d |" % cats["both_ok"], "| 只有国内通过 | %d |" % cats["cn_only"],
                    "| 只有海外通过 | %d |" % cats["abroad_only"], "| 两边都没通过 | %d |" % cats["neither"]]
            if diff:
                rep += ["", "| 候选 | 国内 | 海外 | 说明 | 入选 |", "|---|---|---|---|---|"]
                rep += ["| %s | %s | %s | %s | %s |" % (k, a, b, note, "是" if ch else "否") for k, a, b, note, ch in diff]
        blind = blind_spots([c for c in cands if c.get("chosen")])
        if blind:
            where = "国内出口" if proxy else "海外"
            rep += ["", "## %s盲区" % where,  "",
                    "最终入选的源里，有 %d 个这次在%s检测不出结论（被拦 / 打不开），不等于站点坏了：" % (len(blind), where), "",
                    "| 候选 | 状态 | 排名依据 |", "|---|---|---|"]
            rep += ["| %s | %s | %s |" % b for b in blind]
            if not proxy:
                why = (os.environ.get("ANIYUAN_PROXY_NOTE") or "").strip()
                rep += ["", ("出口代理没有启用：%s。" % why) if why else "想看到国内视角的结果：给工作流配置国内出口的代理（Secret `CLASH_NODE` 放 Clash 节点，或 `ANIYUAN_PROXY` 放 http / socks5 地址），见 README。"]
        if ua_audit:
            rep += ["", "## UA 体检", "", "| 检查项 | 结果 | 说明 |", "|---|---|---|"]
            rep += ["| %s | %s | %s |" % (n, "通过" if ok else "**未通过**", d.replace("|", "/")) for n, ok, d in ua_audit]
    if icon_results:
        names = {"new": "新存", "same": "没变", "cached": "沿用上次", "kept": "没取到（保留原地址）"}
        rep += ["", "## 站点图标", "", "| 源 | 结果 | 说明 |", "|---|---|---|"]
        for sid, st, why in sorted(icon_results, key=lambda r: (r[1] in ("new", "same"), r[0])):
            rep.append("| %s | %s | %s |" % (sid, names.get(st, st), why.replace("|", "/")))
    if changed is not None:   # 一句话摘要，给工作流写提交说明用
        with open(os.path.join(args.out, "summary.txt"), "w", encoding="utf-8") as f:
            f.write(changes.summary(changed, len(sources)) + "\n")
    with open(os.path.join(args.out, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(rep) + "\n")
    with open(os.path.join(args.out, "report.json"), "w", encoding="utf-8") as f:
        json.dump({"decisions": decisions, "official_overlap": official_rows,
                   "candidates": [{k: v for k, v in c.items() if k != "source"} for c in cands]},
                  f, ensure_ascii=False, indent=2)
    print("\n".join(rep))
    skipped = [c["key"] for c in cands if c["source"] is None]
    if skipped:
        print("\n没有生成数据源：", ", ".join(skipped))


if __name__ == "__main__":
    main()
