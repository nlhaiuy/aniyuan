# 订阅转换报告

写入订阅 **28** 个数据源（候选 49 个，同站点合并后）。

## 同站点取舍

| 站点 | 最终 id | 采用 | 理由 | 候选（最后修改） |
|---|---|---|---|---|
| 2kdm.com | anibaka-2kdm | kazumi:mutefun | 更新（2026-10-15） | kazumi:mutefun(2026-10-15)<br>anibaka:2kdm(2026-09-30) |
| 5dm.dev | anibaka-5dm | anibaka:5dm | 只有这一个来源 | anibaka:5dm(2026-10-07) |
| 7sefun.top | anibaka-7sefun | baseline:7sefun | 更新（2026-09-30） | baseline:7sefun(2026-09-30)<br>kazumi:7sefun(2026-08-10) |
| agedm.io | anibaka-age | anibaka:age | 更新（2026-09-30） | anibaka:age(2026-09-30)<br>kazumi:AGE(2025-09-17) |
| akianime.cc | anibaka-akianime | anibaka:akianime | 更新（2026-09-30） | anibaka:akianime(2026-09-30)<br>kazumi:akianime(2026-08-17) |
| ani.girigirilove.com | anibaka-girigirilove | kazumi:giriGiriLove | 更新（2026-10-22） | kazumi:giriGiriLove(2026-10-22)<br>anibaka:girigirilove(2026-09-30) |
| ani.pekolove.net | anibaka-ani-pekolove | baseline:ani_pekolove | 只有这一个来源 | baseline:ani_pekolove(2026-10-07) |
| anime7.top | anibaka-anime7 | anibaka:anime7 | 只有这一个来源 | anibaka:anime7(2026-10-07) |
| animoe.org | anibaka-animoe | anibaka:animoe | 只有这一个来源 | anibaka:animoe(2026-09-30) |
| baimaodm.com | kazumi-baimao | kazumi:baimao | 只有这一个来源 | kazumi:baimao(2026-01-28) |
| cn.agekkkk.com | anibaka-agekkkk | baseline:agekkkk | 只有这一个来源 | baseline:agekkkk(2026-07-18) |
| cyfz.top | anibaka-cyfz | baseline:cyfz | 只有这一个来源 | baseline:cyfz(2026-09-30) |
| dcc3.com | kazumi-mxdm | kazumi:MXdm | 只有这一个来源 | kazumi:MXdm(2026-10-01) |
| didahd.pro | anibaka-didahd | baseline:didahd | 只有这一个来源 | baseline:didahd(2026-09-30) |
| dm1.xfdm.pro | kazumi-xfdmneo | kazumi:xfdmneo | 只有这一个来源 | kazumi:xfdmneo(2026-03-08) |
| dmbus.cc | anibaka-dm84 | anibaka:dm84 | 更新（2026-09-14） | anibaka:dm84(2026-09-14)<br>kazumi:DM84(2026-02-02) |
| ezdmw.org | anibaka-ezdmw | baseline:ezdmw | 更新（2026-10-07） | baseline:ezdmw(2026-10-07)<br>kazumi:ezdmw(2026-08-16) |
| gugu3.com | anibaka-gugu | anibaka:gugu | 只有这一个来源 | anibaka:gugu(2026-09-30) |
| ios.mifun.org | anibaka-ios-mifun | baseline:ios_mifun | 只有这一个来源 | baseline:ios_mifun(2026-09-30) |
| lm6.net | anibaka-lm6 | anibaka:lm6 | 只有这一个来源 | anibaka:lm6(2026-08-06) |
| lmm85.com | kazumi-lmm | kazumi:LMM | 只有这一个来源 | kazumi:LMM(2026-10-15) |
| mgnacg.com | anibaka-mgnacg | kazumi:mgnacg | 更新（2026-10-15） | kazumi:mgnacg(2026-10-15)<br>baseline:mgnacg(2026-07-18) |
| moonci.com | anibaka-moonci | kazumi:moonci | 更新（2026-10-19） | kazumi:moonci(2026-10-19)<br>anibaka:moonci(2026-09-30)<br>kazumi:aafun(2026-08-21) |
| next.xifanacg.com | kazumi-xfdmnext | kazumi:xfdmnext | 只有这一个来源 | kazumi:xfdmnext(2026-10-01) |
| sbdl.cc | anibaka-dalvdm | kazumi:dalvdm | 更新（2026-10-15） | kazumi:dalvdm(2026-10-15)<br>baseline:dalvdm(2026-10-07) |
| silisilifun.com | anibaka-silisili | anibaka:silisili | 只有这一个来源 | anibaka:silisili(2026-09-30) |
| sorani.net | anibaka-sorani | baseline:sorani | 更新（2026-10-07） | baseline:sorani(2026-10-07)<br>kazumi:sorani(2026-07-13) |
| xgcartoon.com | anibaka-xigua | baseline:xigua | 只有这一个来源 | baseline:xigua(2026-09-30) |

## 全部候选

| 来源 | 规则 | 版本 | 修改日期 | 转换 | 自动检测 | 采用 | 备注 |
|---|---|---|---|---|---|---|---|
| kazumi | 7sefun | 1.3 | 2026-08-10 | 有近似 | ok | 否 | 末尾 text() 已改为取元素全部文本 |
| kazumi | aafun | 1.2 | 2026-08-21 | 完整 | unreachable | 否 | 请求失败：SSLError |
| kazumi | AGE | 1.5 | 2025-09-17 | 完整 | blocked | 否 | HTTP 403 |
| kazumi | akianime | 1.4 | 2026-08-17 | 完整 | ok | 否 |  |
| kazumi | baimao | 1.0 | 2026-01-28 | 完整 | ok | 是 |  |
| kazumi | dalvdm | 1.2 | 2026-10-15 | 完整 | blocked | 是 | HTTP 403 |
| kazumi | DM84 | 1.4 | 2026-02-02 | 完整 | ok | 否 |  |
| kazumi | ezdmw | 1.2 | 2026-08-16 | 手写 | ok | 否 |  |
| kazumi | giriGiriLove | 2.6 | 2026-10-22 | 手写 | fail | 是 | 搜索页能打开，但选择器没有选中任何结果 |
| kazumi | LMM | 2.3 | 2026-10-15 | 完整 | blocked | 是 | HTTP 403 |
| kazumi | mgnacg | 1.2 | 2026-10-15 | 完整 | ok | 是 |  |
| kazumi | moonci | 1.1 | 2026-10-19 | 完整 | unreachable | 是 | 请求失败：SSLError |
| kazumi | mutefun | 1.4 | 2026-10-15 | 完整 | ok | 是 |  |
| kazumi | MXdm | 2.4 | 2026-10-01 | 完整 | ok | 是 |  |
| kazumi | sorani | 1.0 | 2026-07-13 | 手写 | skipped | 否 | 手写配置，不做自动检测 |
| kazumi | xfdmneo | 1.1 | 2026-03-08 | 完整 | ok | 是 |  |
| kazumi | xfdmnext | 1.1 | 2026-10-01 | 手写 | skipped | 是 | 手写配置，不做自动检测 |
| baseline | 7sefun | rev 8 | 2026-09-30 | 回退基线 | skipped | 是 | 回退到 baseline/anibaka.json：无法自动转换（搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等））；非 no-channel 章节格式，只验证了搜索 |
| baseline | cyfz | rev 6 | 2026-09-30 | 回退基线 | blocked | 是 | 回退到 baseline/anibaka.json：自动转换的搜索地址是推测的；HTTP 403 |
| anibaka | 5dm | rev 1 | 2026-10-07 | 完整 | blocked | 是 | HTTP 403 |
| baseline | ani_pekolove | rev 9 | 2026-10-07 | 回退基线 | blocked | 是 | 回退到 baseline/anibaka.json：无法自动转换（搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等））；搜索页出现验证码/环境检查 |
| anibaka | lm6 | rev 5 | 2026-08-06 | 有近似 | blocked | 是 | AniBaka 播放步骤用了 crypto 取直链；Animeko 只能靠 WebView 嗅探，可能拿不到视频；HTTP 403 |
| anibaka | aniwatch | rev 4 | 2026-09-30 | 无法转换 | - | 否 | 章节步骤无法转换（需要 episodes 操作，实际是：fetch, jsonEpisodes, regex, select, sniff）；baseline 里也没有这个源，已跳过 |
| anibaka | akianime | rev 6 | 2026-09-30 | 完整 | skipped | 是 | 非 no-channel 章节格式，只验证了搜索 |
| anibaka | animoe | rev 4 | 2026-09-30 | 有近似 | blocked | 是 | AniBaka 播放步骤不是嗅探（playerAaaa/regex），已改成 WebView 嗅探，请在 Animeko 里试播确认；HTTP 403 |
| anibaka | tvtfun | rev 12 | 2026-09-30 | 无法转换 | - | 否 | 章节步骤无法转换（需要 episodes 操作，实际是：json, jsonEpisodes, setVar, template）；baseline 里也没有这个源，已跳过 |
| baseline | ios_mifun | rev 6 | 2026-09-30 | 回退基线 | skipped | 是 | 回退到 baseline/anibaka.json：自动转换的搜索地址是推测的；非 no-channel 章节格式，只验证了搜索 |
| baseline | agekkkk | rev 2 | 2026-07-18 | 回退基线 | blocked | 是 | 回退到 baseline/anibaka.json：无法自动转换（搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等））；搜索页出现验证码/环境检查 |
| baseline | didahd | rev 6 | 2026-09-30 | 回退基线 | blocked | 是 | 回退到 baseline/anibaka.json：自动转换的搜索地址是推测的；HTTP 403 |
| anibaka | anime7 | rev 5 | 2026-10-07 | 完整 | blocked | 是 | HTTP 403 |
| anibaka | hanimeone | rev 6 | 2026-09-30 | 无法转换 | - | 否 | 搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等）；baseline 里也没有这个源，已跳过 |
| anibaka | girigirilove | rev 4 | 2026-09-30 | 完整 | fail | 否 | 搜索页能打开，但选择器没有选中任何结果 |
| anibaka | girigirilove_beta | rev 1 | 2026-10-07 | 无法转换 | - | 否 | 章节步骤无法转换（需要 episodes 操作，实际是：fetch, maccmsApiEpisodes, regex, template）；baseline 里也没有这个源，已跳过 |
| anibaka | xifanacg | rev 5 | 2026-09-30 | 无法转换 | - | 否 | 搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等）；baseline 里也没有这个源，已跳过 |
| anibaka | age | rev 6 | 2026-09-30 | 完整 | blocked | 是 | HTTP 403 |
| baseline | xigua | rev 8 | 2026-09-30 | 回退基线 | fail | 是 | 回退到 baseline/anibaka.json：无法自动转换（搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等））；详情页 HTTP 404（https://www.xgcartoon.com/detail/zangsongdefulilianzangsongzhefulilianriyu-shantianzhongren） |
| anibaka | 2kdm | rev 5 | 2026-09-30 | 完整 | blocked | 否 | 搜索页出现验证码/环境检查 |
| anibaka | gugu | rev 4 | 2026-09-30 | 完整 | fail | 是 | HTTP 404 |
| anibaka | anime1 | rev 2 | 2026-09-14 | 无法转换 | - | 否 | 搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等）；baseline 里也没有这个源，已跳过 |
| anibaka | dmhy | rev 4 | 2026-09-30 | 无法转换 | - | 否 | 搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等）；baseline 里也没有这个源，已跳过 |
| anibaka | mikan | rev 5 | 2026-09-30 | 无法转换 | - | 否 | 搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等）；baseline 里也没有这个源，已跳过 |
| anibaka | dm84 | rev 2 | 2026-09-14 | 有近似 | skipped | 是 | AniBaka 播放步骤不是嗅探（fetch/json/regex/replace/select/setVar/template），已改成 WebView 嗅探，请在 Animeko 里试播确认；非 no-channel 章节格式，只验证了搜索 |
| anibaka | fsdm02 | rev 3 | 2026-09-30 | 无法转换 | - | 否 | 搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等）；baseline 里也没有这个源，已跳过 |
| baseline | mgnacg | rev 1 | 2026-07-18 | 回退基线 | fail | 否 | 回退到 baseline/anibaka.json：自动转换的搜索地址是推测的；搜索页能打开，但选择器没有选中任何结果 |
| anibaka | moonci | rev 3 | 2026-09-30 | 完整 | unreachable | 否 | 请求失败：SSLError |
| anibaka | silisili | rev 1 | 2026-09-30 | 有近似 | fail | 是 | AniBaka 播放步骤用了 crypto 取直链；Animeko 只能靠 WebView 嗅探，可能拿不到视频；搜索页能打开，但选择器没有选中任何结果 |
| baseline | ezdmw | rev 4 | 2026-10-07 | 回退基线 | ok | 是 | 回退到 baseline/anibaka.json：无法自动转换（搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等）） |
| baseline | dalvdm | rev 9 | 2026-10-07 | 回退基线 | blocked | 否 | 回退到 baseline/anibaka.json：自动转换的搜索地址是推测的；HTTP 403 |
| baseline | sorani | rev 1 | 2026-10-07 | 回退基线 | skipped | 是 | 回退到 baseline/anibaka.json：无法自动转换（搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等））；手写配置，不做自动检测 |
