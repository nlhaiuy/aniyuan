"""报告总览部分（aniyuan/report.py）的自测（不联网）。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aniyuan import report

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)


def entry(name, tier, smoke, health=None, lines=None, line_play=None, grouped=False):
    src = {"id": "aniyuan-" + name, "factoryId": "web-selector",
           "arguments": {"name": name, "tier": tier, "searchConfig": {"channelFormatId": "index-grouped" if grouped else "no-channel"}}}
    c = dict(smoke=smoke, health=health or {}, lines=lines or [], line_play=line_play)
    return c, src


good = entry("good", 1, {"status": "ok", "play": "ok"}, lines=[1, 2, 3, 4, 5], line_play={"A": "ok", "B": "none"}, grouped=True)
held = entry("held", 1, {"status": "ok", "play": "ok", "play_raw": "none"})
unsure = entry("unsure", 2, {"status": "ok", "play": "none"})
carried = entry("carried", 1, {"status": "unreachable"}, {"carry": True, "play": "ok", "carry_age": 3.0})
unknown = entry("unknown", 3, {"status": "blocked"})
failed = entry("failed", 4, {"status": "fail"}, {"grace": False})
entries = [failed, unknown, carried, unsure, held, good]

check("实测能播和按旧成绩算的分开", [report.play_state(c)[0] for c, _ in entries]
      == ["failed", "unknown", "assumed", "unsure", "assumed", "verified"])
check("线路列：能播数 / 试播数（总数）", report.line_state(*good) == "1/2 能播（共 5 条）" and report.line_state(*held) == "合并")

rows = [{"id": "aniyuan-good", "official": "官方好", "action": "demote"}]
text = "\n".join(report.overview(entries, [], rows, [("UA", True, "")], True))
check("总览数字以订阅里的源为准", "| 订阅里的源 | 6 |" in text and "| 这次实测能播 | 1 |" in text
      and "| 网页源里分了线路的 | 1 / 6 |" in text and "UA 体检全部通过" in text)
att = "\n".join(report.attention(entries, True))
check("需要关注：列出失败、没确认、看不到的", "failed" in att and "unsure" in att and "unknown" in att and "good" not in att)
check("没有问题时明说", "没有需要处理的源" in "\n".join(report.attention([good], True)))
table = report.source_table(entries, rows, True)
order = [line.split("|")[1].strip() for line in table if line.startswith("| ") and not line.startswith("| 源 ")]
check("源表按档位、名字排序，带官方同站源", order == ["carried", "good", "held", "unsure", "unknown", "failed"]
      and any("官方好" in line for line in table))
folded = report.fold(["", "## 全部候选", "", "| a |", "|---|"])
check("明细折叠，标题留在外面", folded[1] == "## 全部候选" and "<details>" in folded[3] and folded[-1] == "</details>")
check("没做联网检测：不编总览", report.overview(entries, [], rows, [], False) == [] and report.attention(entries, False) == [])

print("\n全部通过" if not bad else "\n%d 项失败" % bad)
sys.exit(1 if bad else 0)
