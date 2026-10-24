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


def fmt_date(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d") if ts else "未知"


def parse_iso(s):
    try:
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
    except Exception:
        return None


# ---------------------------------------------------------------- 收集候选
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
        c["version"] = str(rule.get("version", c["version"]))
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
        res = None
        if os.path.exists(path):
            res = convert_anx(load_json(path), e, config)
            c.update(source=res.source, status=res.status, notes=list(res.notes), guess=res.guess)
        else:
            c["notes"] = ["规则文件 %s 不存在" % e["ref"]]
        use_baseline = None
        if sid in baseline:
            if c["source"] is None:
                use_baseline = "无法自动转换（%s）" % ("；".join(c["notes"]) or "?")
            elif c["guess"]:
                use_baseline = "自动转换的搜索地址是推测的"
            elif key in config.get("prefer_baseline", []):
                use_baseline = "config.prefer_baseline 指定"
        if use_baseline:
            c.update(source=json.loads(json.dumps(baseline[sid])), status="baseline",
                     notes=["回退到 baseline/anibaka.json：" + use_baseline])
            c["origin"] = "baseline"
        elif c["source"] is None:
            c["notes"].append("baseline 里也没有这个源，已跳过")
        out.append(c)
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
            c = dict(origin="easybangumi", key=key, version=meta.get("versionName", ""), source=res.source,
                     status=res.status, notes=list(res.notes), info=res.info, guess=False,
                     date=git_date(repo, "%s/%s" % (sub, fn)))
            c["info"] = ["纯纯看番 %s 通道" % channel] + list(c["info"])
            out.append(c)
    return out


# ---------------------------------------------------------------- 合并
def merge(cands, config):
    aliases = config.get("site_aliases", {})
    prefer = config.get("prefer", {})
    prefer_working = config.get("prefer_working", False)
    groups = {}
    for c in cands:
        if c["source"] is None:
            c["site"] = None
            continue
        host = site_host(c["source"])
        host = aliases.get(host, host)
        c["site"] = host
        groups.setdefault(host, []).append(c)

    # 纯纯看番的 kazumi-*.js 只是 Kazumi 规则的外壳，它的 git 日期反映的是“发布提交”而不是规则改动，
    # 不能直接拿来和 Kazumi 比新旧。同站有 Kazumi 规则时改按版本号比：
    # 配置完全相同，或版本号不高于 Kazumi 的，不参与取新；版本号更高的才参与。
    def vt(v):
        nums = re.findall(r"\d+", str(v))
        return tuple(int(n) for n in nums) if nums else None

    for host, members in groups.items():
        kz = [c for c in members if c["origin"] == "kazumi"]
        for c in list(members):
            if c["origin"] != "easybangumi" or not kz:
                continue
            sc = c["source"]["arguments"]["searchConfig"]
            if any(k["source"]["arguments"]["searchConfig"] == sc for k in kz):
                why = "转换结果与 Kazumi 里同站规则完全相同"
            elif vt(c["version"]) and any(vt(k["version"]) and vt(c["version"]) <= vt(k["version"]) for k in kz):
                why = "版本 %s 不高于 Kazumi 里的同站规则（发布提交的日期不代表规则更新）" % c["version"]
            else:
                continue
            members.remove(c)
            c["redundant"] = True
            c["notes"].append(why + "，不参与取新")

    chosen, decisions = [], []
    for host, members in sorted(groups.items()):
        rank = {"kazumi": 2, "easybangumi": 1}   # 时间相同：Kazumi > 纯纯看番 > AniBaka
        members.sort(key=lambda c: (c["date"] or 0, rank.get(c["origin"], 0)), reverse=True)
        winner, reason = members[0], "更新（%s）" % fmt_date(members[0]["date"])
        if len(members) == 1:
            reason = "只有这一个来源"
        p = prefer.get(host)
        if p:
            forced = [c for c in members if (c["origin"] == "kazumi") == (p == "kazumi")]
            if forced:
                winner, reason = forced[0], "config.prefer 指定 %s" % p
        smoke_of = lambda c: (c.get("smoke") or {}).get("status")  # noqa: E731
        if len(members) > 1 and smoke_of(winner) in ("fail",):
            ok = [c for c in members if smoke_of(c) == "ok"]
            if ok:
                if prefer_working:
                    winner, reason = ok[0], "更新的那个自动检测未通过，改用能通过的（prefer_working）"
                else:
                    winner.setdefault("notes", []).append(
                        "更新的来源自动检测未通过，而 %s 的通过了；如想换用，在 config.json 的 prefer 里设置 %s" % (
                            ok[0]["origin"], host))
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
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    if not (args.kazumi or args.anibaka or args.easybangumi):
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

    if args.smoke:
        import requests
        from smoke import check_source
        session = requests.Session()
        for c in cands:
            if c["source"] is None:
                continue
            r = check_source(c["source"], config.get("smoke_keyword", "葬送的芙莉莲"), session=session)
            c["smoke"] = r
            if r.get("template"):
                c["source"]["arguments"]["searchConfig"]["selectorSubjectFormatJsonPathIndexed"]["linkTemplate"] = r["template"]
            time.sleep(1)

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

    label = {"ok": "完整", "partial": "有近似", "unsupported": "无法转换", "override": "手写", "missing": "缺文件",
             "baseline": "回退基线"}
    rep = ["# 订阅转换报告", "", "写入订阅 **%d** 个数据源（候选 %d 个，同站点合并后）。" % (len(sources), len(cands)), "",
           "## 同站点取舍", "", "| 站点 | 最终 id | 采用 | 理由 | 候选（最后修改） |", "|---|---|---|---|---|"]
    for d in decisions:
        rep.append("| %s | %s | %s | %s | %s |" % (d["site"], d["id"], d["winner"], d["reason"], "<br>".join(d["members"])))
    rep += ["", "## 全部候选", "", "| 来源 | 规则 | 版本 | 修改日期 | 转换 | 自动检测 | 采用 | 备注 |", "|---|---|---|---|---|---|---|---|"]
    for c in cands:
        sm = c.get("smoke") or {}
        remark = "；".join(c["notes"] + ([sm["reason"]] if sm.get("reason") and sm.get("status") != "ok" else []))
        rep.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            c["origin"], c["key"], c["version"], fmt_date(c["date"]), label.get(c["status"], c["status"]),
            sm.get("status", "-") + ("（已剔除）" if c.get("dropped") else ""),
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
