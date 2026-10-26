#!/usr/bin/env python3
"""KazumiRules + AniBakaRule + 纯纯看番社区 JS 源 -> 一个 Animeko 订阅。

用法:
  python build.py --kazumi ./KazumiRules --anibaka ./AniBakaRule --out dist
  python build.py --kazumi ./KazumiRules --anibaka ./AniBakaRule --out dist --smoke

  --kazumi / --anibaka 都可以省略其中一个（只转换另一个）。
  两个仓库最好是完整克隆（fetch-depth: 0），才能取到每个规则文件的最后修改时间。

合并规则：
  1. 按“站点主机名”（去掉 www./m.，可在 config.json 的 site_aliases 里手动并站）分组；
  2. 同一站点在多个来源里都有，取最后修改时间更新的那个（并列时 Kazumi > 纯纯看番 > AniBaka）；
  3. 站点在 AniBaka 里有时，订阅里的 id 固定为 anibaka-<key>，否则为 kazumi-<name>；
     id 不随“谁赢了”变化，Animeko 里用户的启用状态才不会丢；
  4. AniBaka 规则转不了时，回退到 baseline/anibaka.json 里同 id 的现成配置。
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from anx2animeko import convert_anx, site_host, source_id  # noqa: E402
from convert import convert_rule  # noqa: E402
from ebjs import convert_extension  # noqa: E402
from domains import follow_upstream, host_of  # noqa: E402
from repair import brittle, mine_presets, repair_source  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


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
    """联网检测一个候选：必要时自动修复选择器、跟随域名跳转。结果写进 c["smoke"]。"""
    from smoke import HEADERS, _blocked, check_source
    ctx = {}
    r = check_source(c["source"], keyword, session=session, ctx=ctx)

    def fetch(url):
        try:
            resp = session.get(url, headers=HEADERS, timeout=15)
            return resp.text if resp.status_code == 200 and not _blocked(resp.text) else None
        except Exception:
            return None

    def try_repair(which, require_not_fewer=None):
        new, why = repair_source(c["source"], ctx, keyword, presets, fetch, which)
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

    # 亲测可用的配置（manual）：不自动改选择器，只允许跟随域名跳转
    if c["origin"] != "manual" and c["source"].get("factoryId") == "web-selector" and config.get("repair", True):
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
    fo = r.get("final_origin")
    if fo and r["status"] == "ok" and config.get("follow_redirects", True):
        from urllib.parse import urlparse
        sc = c["source"]["arguments"]["searchConfig"]
        old = "%s://%s" % (urlparse(sc["searchUrl"]).scheme, urlparse(sc["searchUrl"]).netloc)
        c["source"] = rewrite_origin(c["source"], old, fo)
        c["notes"].append("域名已跳转，改用新域名 %s（原 %s）" % (fo, old))
    c["smoke"] = r


def collect_manual(dirpath):
    """manual/ 里是你亲自验证过可用的源（订阅文件或单个源 JSON），同站时永远优先。"""
    out = []
    if not dirpath or not os.path.isdir(dirpath):
        return out
    for fn in sorted(os.listdir(dirpath)):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(dirpath, fn)
        data = load_json(path)
        srcs = data["mediaSources"] if isinstance(data, dict) and "mediaSources" in data else [data]
        for i, src in enumerate(srcs):
            src = json.loads(json.dumps(src))
            if not src.get("id"):
                src["id"] = "manual-%s%s" % (os.path.splitext(fn)[0], "" if len(srcs) == 1 else "-%d" % i)
            out.append(dict(origin="manual", key=src["id"], version="", source=src, status="manual", notes=[],
                            info=["manual/%s 手动维护" % fn], guess=False, raw_hash=file_hash(path),
                            date=int(os.path.getmtime(path))))
    return out


def _check(source, config, session):
    from smoke import check_source
    return check_source(source, config.get("smoke_keyword", "葬送的芙莉莲"), session=session)


def run_playchecks(cands, config, pc):
    """对检测通过的候选逐个做无头浏览器播放检测（耗时，约 20~30 秒一个）。"""
    todo = [c for c in cands if (c.get("smoke") or {}).get("status") == "ok" and c["smoke"].get("episode_url")]
    for c in todo[: config.get("play_check_max", 80)]:
        try:
            c["smoke"].update(pc.check(c["source"], c["smoke"]["episode_url"], config.get("play_wait_ms", 20000)))
        except Exception as e:
            c["smoke"].update({"play": "error", "play_reason": "检测出错：%s" % type(e).__name__})


def collect_kazumi(repo, config, overrides_dir):
    out = []
    index = load_json(os.path.join(repo, "index.json"))
    exclude = set(config.get("exclude", []))
    for item in index:
        name = item["name"]
        if name in exclude:
            continue
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
        ov_path = os.path.join(overrides_dir, name + ".json")
        if os.path.exists(ov_path):
            ov = load_json(ov_path)
            if str(ov.get("_kazumiVersion", "")) != c["version"]:
                c["notes"].append("手写配置基于 Kazumi v%s，规则已更新到 v%s，请核对是否需要同步修改" % (
                    ov.get("_kazumiVersion", "?"), c["version"]))
            c.update(source=ov, status="override", info=["使用 overrides/%s.json 手写配置" % name])
        else:
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
    exclude = set(config.get("exclude_anibaka", []))
    for e in index.get("entries", []):
        key = e["key"]
        if key in exclude:
            continue
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
            if key in config.get("prefer_baseline", []):
                c["source"] = None
                c["notes"].append("config.prefer_baseline 指定只用基线")
        if c["source"] is None and base_c is None:
            c["notes"].append("baseline 里也没有这个源，已跳过")
        out.append(c)
        if base_c:
            out.append(base_c)
    return out


def collect_easybangumi(repo, config):
    """纯纯看番社区 JS 源：release 里是真机验证过的，dev 是未验证的（默认不收）。"""
    out, seen = [], set()
    exclude = set(config.get("exclude_easybangumi", []))
    for channel, sub in (("release", "extensions"), ("dev", "dev-extensions")):
        if channel not in config.get("easybangumi_channels", ["release"]):
            continue
        d = os.path.join(repo, sub)
        for fn in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if not fn.endswith(".js") or fn in seen:
                continue
            seen.add(fn)
            key = fn[:-3]
            if key in exclude:
                continue
            res, meta = convert_extension(os.path.join(d, fn), config)
            c = dict(raw_hash=file_hash(os.path.join(d, fn)), origin="easybangumi", key=key, version=meta.get("versionName", ""), source=res.source,
                     status=res.status, notes=list(res.notes), info=res.info, guess=False,
                     date=git_date(repo, "%s/%s" % (sub, fn)))
            c["info"] = ["纯纯看番 %s 通道" % channel] + list(c["info"])
            from ebjs import parse_extension
            c["live_hosts"] = [h for h in [host_of(parse_extension(os.path.join(d, fn))[1].get("DEFAULT_BASE_URL", ""))] if h]
            out.append(c)
    return out


# ---------------------------------------------------------------- 合并
def merge(cands, config):
    aliases = config.get("site_aliases", {})
    prefer = config.get("prefer", {})
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
        keys = ["h:" + c["site"]] + (["a:" + c["key"]] if c["origin"] in ("anibaka", "baseline") else [])
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

    chosen, decisions = [], []
    for host, members in sorted(groups.items()):
        rank = {"kazumi": 3, "easybangumi": 2, "anibaka": 1}   # 时间相同：Kazumi > 纯纯看番 > AniBaka > 基线
        smoke_of = lambda c: (c.get("smoke") or {}).get("status")  # noqa: E731
        # 实测优先：检测通过 > 没测出结论（无法访问/验证码/跳过） > 明确失败；同档内再比修改时间
        def tier(c):
            if not by_smoke:
                return 0.5 if c.get("guess") else 1
            sm = c.get("smoke") or {}
            if sm.get("status") == "ok":   # 播放检测过的：能播 > 没检测 > 没抓到 > 地址认不出
                return {"ok": 3, "error": 2, "none": 1.8, "blocked": 1.6, "mismatch": 1.5}.get(sm.get("play"), 2)
            if sm.get("status") == "fail":
                return 0
            return 0.5 if (c.get("guess") and sm.get("status") != "ok") else 1   # 搜索地址是推测的：没验证过就排在后面
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
        manual = [c for c in members if c["origin"] == "manual"]
        if manual:
            winner, reason = manual[0], "manual/ 里手动维护的源，优先于自动转换"
            if smoke_of(winner) in ("fail",):
                winner["notes"].append("手动源自动检测未通过（%s），但仍优先使用；可能是检测环境访问不了" % winner["smoke"].get("reason", ""))
        p = prefer.get(host)
        if p and not manual:
            forced = [c for c in members if (("anibaka" if c["origin"] == "baseline" else c["origin"]) == p)]
            if forced:
                winner, reason = forced[0], "config.prefer 指定 %s" % p
        ab = [c for c in members if c["origin"] in ("anibaka", "baseline")]
        kz = [c for c in members if c["origin"] == "kazumi"]
        stable_id = source_id(ab[0]["key"]) if ab else (kz[0]["source"]["id"] if kz else winner["source"]["id"])
        winner["source"]["id"] = stable_id
        winner["chosen"] = True
        chosen.append(winner)
        decisions.append(dict(site=host, winner="%s:%s" % (winner["origin"], winner["key"]), id=stable_id, reason=reason,
                              members=["%s:%s(%s)" % (c["origin"], c["key"], fmt_date(c["date"])) for c in members]))
    return chosen, decisions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kazumi", help="KazumiRules 仓库目录")
    ap.add_argument("--anibaka", help="AniBakaRule 仓库目录")
    ap.add_argument("--easybangumi", help="CommunityJsExtensionEasyBangumi 仓库目录")
    ap.add_argument("--out", default="dist")
    ap.add_argument("--config", default=os.path.join(HERE, "config.json"))
    ap.add_argument("--overrides", default=os.path.join(HERE, "overrides"))
    ap.add_argument("--baseline", default=os.path.join(HERE, "baseline", "anibaka.json"))
    ap.add_argument("--state", default=os.path.join(HERE, "state", "seen.json"),
                    help="记录各规则内容哈希和“最后真正改动时间”的文件")
    ap.add_argument("--manual", default=os.path.join(HERE, "manual"), help="手动维护（亲测可用）的源所在目录")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--playcheck", action="store_true", help="在 --smoke 之后再用无头浏览器检测能否播放（需要 playwright）")
    args = ap.parse_args()
    if not (args.kazumi or args.anibaka or args.easybangumi or os.path.isdir(args.manual)):
        ap.error("至少给一个 --kazumi / --anibaka / --easybangumi")

    config = load_json(args.config) if os.path.exists(args.config) else {}
    baseline = {}
    if os.path.exists(args.baseline):
        baseline = {s["id"]: s for s in load_json(args.baseline)["mediaSources"]}

    cands = []
    if args.kazumi:
        cands += collect_kazumi(args.kazumi, config, args.overrides)
    if args.anibaka:
        cands += collect_anibaka(args.anibaka, baseline, config)
    if args.easybangumi:
        cands += collect_easybangumi(args.easybangumi, config)
    cands += collect_manual(args.manual)

    state = load_json(args.state) if os.path.exists(args.state) else {}
    new_state = apply_state(cands, state, int(time.time()))
    os.makedirs(os.path.dirname(os.path.abspath(args.state)), exist_ok=True)
    with open(args.state, "w", encoding="utf-8") as f:
        json.dump(new_state, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")

    if args.smoke:
        import requests
        import smoke as smoke_mod
        session = requests.Session()
        presets = mine_presets(args.anibaka)
        pc = None
        if args.playcheck:   # 浏览器启动一次：既用于 403 回退，也用于播放检测
            try:
                from playcheck import PlayChecker
                pc = PlayChecker()
                if config.get("browser_fallback", True):
                    smoke_mod.set_browser_fetcher(pc.fetch)
            except Exception as e:  # 没装浏览器就跳过，不影响其它流程
                print("浏览器不可用，跳过播放检测和 403 回退：%s" % e, file=sys.stderr)
        try:
            for c in cands:
                if c["source"] is None:
                    continue
                probe(c, config.get("smoke_keyword", "葬送的芙莉莲"), session, presets, config)
                r = c["smoke"]
                if r.get("template"):
                    c["source"]["arguments"]["searchConfig"]["selectorSubjectFormatJsonPathIndexed"]["linkTemplate"] = r["template"]
                time.sleep(1)
            if config.get("follow_upstream_domains", True):
                for key, old, new, ok in follow_upstream(cands, lambda src: _check(src, config, session)):
                    print("域名跟随 %s：%s → %s %s" % (key, old, new, "已采用" if ok else "未通过，保持原样"))
            if pc:
                run_playchecks(cands, config, pc)
        finally:
            smoke_mod.set_browser_fetcher(None)
            if pc:
                pc.close()

    chosen, decisions = merge(cands, config)

    sources = []
    for c in sorted(chosen, key=lambda c: c["source"]["id"]):
        s = strip_private(c["source"])
        sm = c.get("smoke")
        if sm and sm["status"] in ("fail", "blocked", "unreachable"):
            if config.get("drop_failed") and sm["status"] == "fail":
                c["dropped"] = True
                continue
            s["arguments"]["description"] = "[自动检测未通过：%s] " % sm["reason"] + s["arguments"].get("description", "")
        sources.append(s)
    ids = [s["id"] for s in sources]
    assert len(ids) == len(set(ids)), "出现重复 id：%s" % sorted({i for i in ids if ids.count(i) > 1})

    os.makedirs(args.out, exist_ok=True)
    sub = {"schemaVersion": 2, "mediaSources": sources, "exportedMediaSourceDataList": {"mediaSources": sources}}
    with open(os.path.join(args.out, "all.json"), "w", encoding="utf-8") as f:
        json.dump(sub, f, ensure_ascii=False, indent=2)
        f.write("\n")

    label = {"manual": "手动", "ok": "完整", "partial": "有近似", "unsupported": "无法转换", "override": "手写", "missing": "缺文件",
             "baseline": "回退基线"}
    rep = ["# 订阅转换报告", "", "写入订阅 **%d** 个数据源（候选 %d 个，同站点合并后）。" % (len(sources), len(cands)), "",
           "## 同站点取舍", "", "| 站点 | 最终 id | 采用 | 理由 | 候选（最后修改） |", "|---|---|---|---|---|"]
    for d in decisions:
        rep.append("| %s | %s | %s | %s | %s |" % (d["site"], d["id"], d["winner"], d["reason"], "<br>".join(d["members"])))
    rep += ["", "## 全部候选", "", "| 来源 | 规则 | 版本 | 修改日期（依据） | 转换 | 自动检测 | 播放 | 采用 | 备注 |", "|---|---|---|---|---|---|---|---|---|"]
    for c in cands:
        sm = c.get("smoke") or {}
        remark = "；".join(c["notes"] + ([sm["reason"]] if sm.get("reason") and sm.get("status") != "ok" else [])
                           + ([sm["play_reason"]] if sm.get("play") not in (None, "ok") else []))
        rep.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            c["origin"], c["key"], c["version"], fmt_date(c["date"]) + ("（%s）" % c["date_basis"] if c.get("date_basis") else ""), label.get(c["status"], c["status"]),
            sm.get("status", "-") + ("（已剔除）" if c.get("dropped") else ""), sm.get("play", "-"),
            "是" if c.get("chosen") else "否", remark.replace("|", "/")))
    with open(os.path.join(args.out, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(rep) + "\n")
    with open(os.path.join(args.out, "report.json"), "w", encoding="utf-8") as f:
        json.dump({"decisions": decisions,
                   "candidates": [{k: v for k, v in c.items() if k != "source"} for c in cands]},
                  f, ensure_ascii=False, indent=2)
    print("\n".join(rep))
    skipped = [c["key"] for c in cands if c["source"] is None]
    if skipped:
        print("\n没有生成数据源（可在 overrides/ 或 baseline/ 里手写）：", ", ".join(skipped))


if __name__ == "__main__":
    main()
