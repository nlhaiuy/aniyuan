# 订阅转换报告

写入订阅 **26** 个数据源（候选 72 个，同站点合并后）。

检测出口：国内出口（代理 socks5h://127.0.0.1:7890），并用 GitHub 海外服务器直连也测了一遍（国内没通过、海外通过的照样采用，排名低一级），见「国内外出口对比」。


## 总览

| 项目 | 数量 |
|---|---|
| 订阅里的源 | 26 |
| 这次实测能播 | 16 |
| 按以前的成绩 / 海外结果算能用 | 3 |
| 能打开但播放没确认 | 1 |
| 这次看不到、也没有近期记录 | 6 |
| 检测失败 | 0 |
| 网页源里分了线路的 | 16 / 25 |
| 和官方订阅重复 | 5 |
| 长期失效、已移出 | 5 |

UA 体检全部通过。

## 需要关注

- **能打开但播放没确认（1）**：E站弹幕网
- **这次看不到、也没有近期的通过记录（6）**：mutefun (mutedm.com)、五弹幕 (5DM)、AGE动漫、4K动漫、佩可爱动漫 (peko.love)、omofun03

## 本次变化

和上次发布的订阅相比没有变化。

## 订阅里的源

按档位排序（数字越小，Animeko 越优先）。

| 源 | 档位 | 现状 | 线路 | 官方同站源 |
|---|---|---|---|---|
| 9ciyuan (jcydm1.com) | 1 | 这次打不开，0.5 天前实测能播 | 分线路 |  |
| Animoe动漫 | 1 | ✅ 实测能播 | 4/4 能播 |  |
| ant (mayi520.org) | 1 | ✅ 实测能播 | 合并 |  |
| baimao (bmddm.com) | 1 | ✅ 实测能播 | 合并 |  |
| dalvdm (sbdl.cc) | 1 | ✅ 实测能播 | 1/4 能播 |  |
| DM84 (dmbus.cc) | 1 | ✅ 实测能播 | 1 条 |  |
| Mgnacg 橘子动漫 | 1 | ✅ 实测能播 | 3/4 能播（共 5 条） |  |
| MiFun | 1 | ✅ 实测能播 | 4/4 能播 |  |
| moonci | 1 | ✅ 实测能播 | 1/3 能播 |  |
| MXdm (dcc3.com) | 1 | ✅ 实测能播 | 合并 |  |
| 次元番 | 1 | 这次打不开，9.4 天前实测能播 | 分线路 |  |
| 萌番 AkiAnime | 1 | ✅ 实测能播 | 1/3 能播 |  |
| 西瓜卡通 | 1 | ✅ 实测能播 | 合并 |  |
| 路漫漫动漫 | 1 | ✅ 实测能播 | 2/2 能播 |  |
| E站弹幕网 | 2 | ❓ 能搜到、能出剧集，没抓到视频地址 | 合并 |  |
| TvTFun | 2 | 国内出口没通过，海外直连通过 | 合并 |  |
| 4K动漫 | 3 | ❔ 这次打不开，没有近期的通过记录 | 分线路 |  |
| AGE动漫 | 3 | ❔ 这次打不开，没有近期的通过记录 | 分线路 |  |
| omofun03 | 3 | ❔ 这次打不开，没有近期的通过记录 | 合并 |  |
| 五弹幕 (5DM) | 3 | ❔ 这次被拦，没有近期的通过记录 | 分线路 |  |
| 佩可爱动漫 (peko.love) | 3 | ❔ 这次被拦，没有近期的通过记录 | 合并 |  |
| Anime7 动画线上看 | 4 | ✅ 实测能播 | 1 条 | Anime7 |
| LMM | 4 | ✅ 实测能播 | 2/2 能播 | 路漫漫 |
| mutefun (mutedm.com) | 4 | ❔ 这次被拦，没有近期的通过记录 | 合并 | 2k动漫 |
| xfdmnext (next.xifanacg.com) | 4 | ✅ 实测能播 | - | 稀饭动漫 Next |
| 七色番 | 4 | ✅ 实测能播 | 2/2 能播 | 七色番 |

## 与官方订阅的重叠

你同时订阅官方源时，同一个站会出现两次。这次入选的 26 个源里 **5 个**和官方订阅重复，**21 个**是官方没有的（自有独有）。处理方式：`official_dedupe` = `demote`。

| 自有源 | 官方同站源（档位） | 官方检测 | 处理 | 说明 |
|---|---|---|---|---|
| 七色番 | 七色番（T2） | ok | 已降档 | 官方同站源检测通过 |
| Anime7 动画线上看 | Anime7（T3） | ok | 已降档 | 官方同站源检测通过 |
| LMM | 路漫漫（T2） | ok | 已降档 | 官方同站源检测通过 |
| mutefun | 2k动漫（T1） | ok | 已降档 | 官方同站源检测通过 |
| xfdmnext | 稀饭动漫 Next（T0） | ok | 已降档 | 官方同站源检测通过 |

## 长期失效、已自动移出订阅

这些站点连续 7 次以上明确检测失败（页面能打开但选不出结果，或直接 404）、之后一次都没通过过，已不写进订阅；它们仍会每次检测，通过一次就自动回到订阅里（只是变成打不开 / 被拦不算）。

| 来源:规则 | 站点 | 连续失败 | 原因 |
|---|---|---|---|
| anibaka:didahd | didahd.xyz | 38 | 详情页 HTTP 404（https://www.didahd.xyz/detail/1185.html）（自动修复也失败：没有详情页内容可用来修复剧集选择器） |
| anibaka:gugu | gugu3.com | 63 | HTTP 404 |
| anibaka:silisili | silisilifun.com | 60 | 搜索页能打开，但选择器没有选中任何结果（自动修复也失败：在真实搜索页上没找到合适的结果链接选择器） |
| kazumi:xfdmneo | dm1.xfdm.pro | 19 | 请求失败：SSLError |
| easybangumi:kazumi-ylsp | ylys.cc | 26 | HTTP 523 |

## 国内出口盲区

最终入选的源里，有 9 个这次在国内出口检测不出结论（被拦 / 打不开），不等于站点坏了：

| 候选 | 状态 | 排名依据 |
|---|---|---|
| kazumi:mutefun | blocked | 从没检测通过过，没有可沿用的成绩 |
| anibaka:5dm | blocked | 从没检测通过过，没有可沿用的成绩 |
| anibaka:age | unreachable | 从没检测通过过，没有可沿用的成绩 |
| anibaka:agekkkk | unreachable | 从没检测通过过，没有可沿用的成绩 |
| anibaka:ani_pekolove | blocked | 从没检测通过过，没有可沿用的成绩 |
| anibaka:cyfz | unreachable | 沿用 9.4 天前通过时的成绩 |
| easybangumi:kazumi-9ciyuan | unreachable | 沿用 0.5 天前通过时的成绩 |
| easybangumi:kazumi-omofun03 | unreachable | 从没检测通过过，没有可沿用的成绩 |
| kazumi:TvTFun | unreachable | 沿用 0.5 天前通过时的成绩 |

## 同站点取舍

<details><summary>展开查看</summary>

只列有多个来源、需要挑一个的站点。

| 站点 | 最终 id | 采用 | 理由 | 候选（最后修改） |
|---|---|---|---|---|
| 7sefun.top | aniyuan-7sefun | anibaka:7sefun | 更新（2026-11-01） | anibaka:7sefun(2026-11-01)<br>easybangumi:kazumi-7sefun(2026-10-20)<br>kazumi:7sefun(2026-08-10) |
| agedm.io | aniyuan-age | anibaka:age | 更新（2026-11-01） | anibaka:age(2026-11-01)<br>kazumi:AGE(2026-10-28) |
| akianime.com | aniyuan-akianime | anibaka:akianime | 只有这一个来源；同名站点 akianime.cc 因域名不一致被分成了两组，已合并为一个（保留检测结果更好的 anibaka:akianime） | anibaka:akianime(2026-11-15)<br>kazumi:akianime(2026-08-17) |
| anime7.top | aniyuan-anime7 | anibaka:anime7 | 更新（2026-11-15） | anibaka:anime7(2026-11-15)<br>easybangumi:kazumi-anime7(2026-10-20) |
| baimaodm.com | aniyuan-baimao | easybangumi:kazumi-baimao | 更新（2026-10-20） | easybangumi:kazumi-baimao(2026-10-20)<br>kazumi:baimao(2026-01-28) |
| dcc3.com | aniyuan-mxdm | easybangumi:kazumi-mxdm | 更新（2026-10-20） | easybangumi:kazumi-mxdm(2026-10-20)<br>kazumi:MXdm(2026-10-01) |
| dmbus.cc | aniyuan-dm84 | anibaka:dm84 | 更新（2026-11-01） | anibaka:dm84(2026-11-01)<br>kazumi:DM84(2026-02-02) |
| mgnacg.com | aniyuan-mgnacg | anibaka:mgnacg | 更新（2026-11-01） | anibaka:mgnacg(2026-11-01)<br>kazumi:mgnacg(2026-10-15) |
| moonci.com | aniyuan-moonci | kazumi:moonci | 最新的 anibaka:moonci 自动检测没有结论，改用检测结果更好的（ok） | kazumi:moonci(2026-10-19)<br>kazumi:aafun(2026-08-21)<br>anibaka:moonci(2026-11-15) |
| mutedm.com | aniyuan-2kdm | kazumi:mutefun | 最新的 anibaka:2kdm 自动检测未通过，改用检测结果更好的（blocked） | kazumi:mutefun(2026-10-31)<br>anibaka:2kdm(2026-11-01) |
| sbdl.cc | aniyuan-dalvdm | kazumi:dalvdm | 更新（2026-10-15） | kazumi:dalvdm(2026-10-15)<br>anibaka:dalvdm(2026-10-07) |

</details>

## 全部候选

<details><summary>展开查看</summary>

| 来源 | 规则 | 版本 | 修改日期（依据） | 转换 | 自动检测 | 播放 | 采用 | 备注 |
|---|---|---|---|---|---|---|---|---|
| kazumi | 7sefun | 1.3 | 2026-08-10（内容未变） | 有近似 | ok（海外：ok） | ok | 否 | 末尾 text() 已改为取元素全部文本；自动分线路（2 条：七色A线、七色B线）；逐线路播放检测：七色A线=ok、七色B线=ok |
| kazumi | aafun | 1.2 | 2026-08-21（内容未变） | 完整 | ok（海外：ok） | ok | 否 | 已自动修复选择器：搜索选择器改为 .hl-item-title a[href*='/anime/']（命中 2/2）；剧集选择器改为 .hl-plays-list a（30 集）；自动分线路（3 条：X.1、X.2、X.3）；逐线路播放检测：X.1=ok、X.2=none、X.3=none |
| kazumi | AGE | 1.6 | 2026-10-28（内容未变） | 完整 | unreachable（海外：blocked） | - | 否 | 请求失败：SSLError |
| kazumi | akianime | 1.4 | 2026-08-17（内容未变） | 完整 | ok（海外：ok） | ok | 否 | 已自动修复选择器：搜索选择器改为 .vod-detail a[href]（命中 2/31）；剧集选择器改为 .anthology-list-box a（84 集）；自动分线路（3 条：超高画三线、中画-不要相信视频里的广告、【高画2】B站片源-App专享）；逐线路播放检测：超高画三线=none、中画-不要相信视频里的广告=ok、【高画2】B站片源-App专享=none |
| kazumi | baimao | 1.0 | 2026-01-28（内容未变） | 完整 | unreachable（海外：ok） | - | 否 | 国内出口检测unreachable，但 GitHub 海外直连通过，照样采用（排名低一级）；国内出口检测打不开（连续 1 次），0 天前通过过，暂按上次的成绩排名；请求失败：SSLError |
| kazumi | dalvdm | 1.2 | 2026-10-15（内容未变） | 完整 | ok（海外：blocked） | ok | 是 | 自动分线路（4 条：默认线路、高速线路、高速线路2、超清专线）；逐线路播放检测：默认线路=none、高速线路=ok、高速线路2=none、超清专线=none；优先级自动设为 1（检测通过，播放检测：ok） |
| kazumi | DM84 | 1.4 | 2026-02-02（内容未变） | 完整 | ok（海外：ok） | ok | 否 |  |
| kazumi | ezdmw | 1.2 | 2026-08-16（内容未变） | 无法转换 | - | - | 否 | 章节 XPath 无法转换：并集 / |
| kazumi | giriGiriLove | 2.7 | 2026-11-13（内容未变） | 无法转换 | - | - | 否 | 章节接口格式是 delimited（分隔字符串等），Animeko 的 json-api 没有对应的解析方式 |
| kazumi | LMM | 2.4 | 2026-11-13（内容未变） | 完整 | ok（海外：ok） | ok | 是 | 自动分线路（2 条：dev云播、聚合线路）；逐线路播放检测：dev云播=ok、聚合线路=ok；优先级自动设为 1（检测通过，播放检测：ok）；官方订阅里已有同一个站的源「路漫漫」，优先级降到 4（官方同站源检测通过） |
| kazumi | mgnacg | 1.2 | 2026-10-15（内容未变） | 完整 | ok（海外：ok） | ok | 否 | 自动分线路（5 条：云端线路、新番线路、Mahoo、存储线路、本地线路（已下线））；逐线路播放检测：云端线路=ok、新番线路=none、Mahoo=ok、存储线路=ok |
| kazumi | moonci | 1.1 | 2026-10-19（内容未变） | 完整 | ok（海外：ok） | ok | 是 | 自动分线路（3 条：X.1、X.2、X.3）；逐线路播放检测：X.1=ok、X.2=none、X.3=none；优先级自动设为 1（检测通过，播放检测：ok） |
| kazumi | mutefun | 1.6 | 2026-10-31（内容未变） | 完整 | blocked（海外：blocked） | - | 是 | 优先级自动设为 3（检测没有结论（blocked））；官方订阅里已有同一个站的源「2k动漫」，优先级降到 4（官方同站源检测通过）；HTTP 403 |
| kazumi | MXdm | 2.4 | 2026-10-01（内容未变） | 完整 | ok（海外：ok） | ok | 否 |  |
| kazumi | sorani | 1.0 | 2026-07-13（内容未变） | 无法转换 | -（海外：ok） | - | 否 | 从播放页学习 play 失败：播放页没有发出带视频地址的 JSON 接口请求（共抓到 0 个 XHR/fetch；视频地址可能在页面 HTML / iframe 里，或需要登录 / 点击）；json-api 数据源必须有 play（取视频地址的请求）：Kazumi 规则里没有，官方订阅里没有同一接口的源，也没能从播放页学出来，没法自动补 |
| kazumi | TvTFun | 1.3 | 2026-10-28（内容未变） | 完整 | unreachable（海外：ok） | - | 是 | 国内出口检测unreachable，但 GitHub 海外直连通过，照样采用（排名低一级）；国内出口检测打不开（连续 1 次），0 天前通过过，暂按上次的成绩排名；优先级自动设为 2（国内出口unreachable，GitHub 海外直连通过，照样采用（排名低一级））；请求失败：SSLError |
| kazumi | xfdmneo | 1.1 | 2026-03-08（内容未变） | 完整 | unreachable（海外：unreachable）（已剔除） | - | 是 | 优先级自动设为 3（检测没有结论（unreachable））；官方订阅里已有同一个站的源「稀饭动漫」，优先级降到 4（官方同站源检测没有结论（unreachable））；请求失败：SSLError |
| kazumi | xfdmnext | 1.1 | 2026-10-01（内容未变） | 有近似 | ok（海外：ok） | ok | 是 | 播放接口（play）借鉴自官方订阅里同一接口的源「稀饭动漫 Next」；搜索请求体改用官方写法；详情请求体改用官方写法；剧集序号 / 类型字段借鉴官方；优先级自动设为 1（检测通过，播放检测：ok）；官方订阅里已有同一个站的源「稀饭动漫 Next」，优先级降到 4（官方同站源检测通过） |
| anibaka | 7sefun | rev 9 | 2026-11-01（内容未变） | 完整 | ok（海外：ok） | ok | 是 | 自动分线路（2 条：七色A线、七色B线）；逐线路播放检测：七色A线=ok、七色B线=none；这次没抓到视频、但以前能播的线路暂不降级：七色B线（1/3）；优先级自动设为 1（检测通过，播放检测：ok）；官方订阅里已有同一个站的源「七色番」，优先级降到 4（官方同站源检测通过） |
| anibaka | cyfz | rev 9 | 2026-11-16（内容未变） | 完整 | unreachable（海外：blocked） | - | 是 | 国内出口检测打不开（连续 30 次），9 天前通过过，暂按上次的成绩排名；优先级自动设为 1（国内出口检测打不开，沿用 9.4 天前通过时的成绩，播放检测：ok）；请求失败：SSLError |
| anibaka | 5dm | rev 1 | 2026-10-07（内容未变） | 完整 | blocked（海外：blocked） | - | 是 | 优先级自动设为 3（检测没有结论（blocked））；HTTP 403 |
| anibaka | ani_pekolove | rev 10 | 2026-11-15（内容未变） | 有近似 | blocked（海外：blocked） | - | 是 | searchList 没有 detailPattern，条目里的所有链接都会被当作结果（已启用 preferShorterName）；XPath 里按文字过滤的条件（contains(text(), ..)）转不了，已去掉，可能多选到非剧集链接；AniBaka 规则没有线路名，所有线路合并为一条；AniBaka 播放步骤不是嗅探（fetch/query/regex/replace/select/setMediaHeaders/setVar），已改成 WebView 嗅探，请在 Animeko 里试播确认；优先级自动设为 3（检测没有结论（blocked））；搜索页出现验证码/环境检查（验证码 / 环境检查，Animeko 会弹验证浏览器让用户通过） |
| anibaka | lm6 | rev 6 | 2026-11-16（内容未变） | 有近似 | ok（海外：ok） | ok | 是 | AniBaka 播放步骤用了 crypto 取直链；Animeko 只能靠 WebView 嗅探，可能拿不到视频；自动分线路（2 条：dev云播、聚合线路）；逐线路播放检测：dev云播=ok、聚合线路=ok；优先级自动设为 1（检测通过，播放检测：ok） |
| anibaka | aniwatch | rev 5 | 2026-11-01（内容未变） | 无法转换 | - | - | 否 | 章节步骤无法转换（需要 episodes 操作，实际是：fetch, jsonEpisodes, regex）；无法转换，已跳过 |
| anibaka | akianime | rev 8 | 2026-11-15（内容未变） | 有近似 | ok（海外：ok） | ok | 是 | searchList 没有 detailPattern，条目里的所有链接都会被当作结果（已启用 preferShorterName）；逐线路播放检测：超高画三线=none、中画-不要相信视频里的广告=ok、【高画2】B站片源-App专享=none；优先级自动设为 1（检测通过，播放检测：ok） |
| anibaka | animoe | rev 5 | 2026-11-01（内容未变） | 有近似 | ok（海外：blocked） | ok | 是 | AniBaka 播放步骤不是嗅探（playerAaaa/regex），已改成 WebView 嗅探，请在 Animeko 里试播确认；逐线路播放检测：字幕组=ok、动画疯=ok、BiliBili国际=ok、其他=ok；优先级自动设为 1（检测通过，播放检测：ok） |
| anibaka | tvtfun | rev 13 | 2026-11-01（内容未变） | 无法转换 | - | - | 否 | 章节步骤无法转换（需要 episodes 操作，实际是：fetch, jsonEpisodes, regex）；无法转换，已跳过 |
| anibaka | ios_mifun | rev 9 | 2026-11-15（内容未变） | 完整 | ok（海外：ok） | ok | 是 | 逐线路播放检测：快看云=ok、特快云=ok、非凡云=ok、柚子云=ok；优先级自动设为 1（检测通过，播放检测：ok） |
| anibaka | agekkkk | rev 3 | 2026-11-01（内容未变） | 有近似 | unreachable（海外：blocked） | - | 是 | 搜索用到 maccmsVerify（MacCMS 图片验证码），Animeko 有自动 solver，通常能自动通过，通不过时会弹验证浏览器；searchList 没有 detailPattern，条目里的所有链接都会被当作结果（已启用 preferShorterName）；优先级自动设为 3（检测没有结论（unreachable））；请求失败：SSLError |
| anibaka | didahd | rev 7 | 2026-11-01（内容未变） | 有近似 | fail（海外：fail）（已剔除） | - | 是 | AniBaka 播放步骤用了 maccmsVerify 取直链；Animeko 只能靠 WebView 嗅探，可能拿不到视频；详情页 HTTP 404（https://www.didahd.xyz/detail/1185.html）（自动修复也失败：没有详情页内容可用来修复剧集选择器） |
| anibaka | anime7 | rev 6 | 2026-11-15（内容未变） | 有近似 | ok（海外：ok） | ok | 是 | searchList 没有 detailPattern，条目里的所有链接都会被当作结果（已启用 preferShorterName）；优先级自动设为 1（检测通过，播放检测：ok）；官方订阅里已有同一个站的源「Anime7」，优先级降到 4（官方同站源检测通过） |
| anibaka | hanimeone | rev 7 | 2026-11-01（内容未变） | 无法转换 | - | - | 否 | 章节步骤无法转换（需要 episodes 操作，实际是：jsonEpisodes, template）；无法转换，已跳过 |
| anibaka | girigirilove | rev 5 | 2026-11-01（内容未变） | 无法转换 | - | - | 否 | 章节步骤无法转换（需要 episodes 操作，实际是：fetch, maccmsApiEpisodes, regex, template）；无法转换，已跳过 |
| anibaka | girigirilove_beta | rev 2 | 2026-11-01（内容未变） | 无法转换 | - | - | 否 | 章节步骤无法转换（需要 episodes 操作，实际是：fetch, maccmsApiEpisodes, regex, template）；无法转换，已跳过 |
| anibaka | xifanacg | rev 5 | 2026-09-30（内容未变） | 无法转换 | - | - | 否 | 搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等）；无法转换，已跳过 |
| anibaka | age | rev 7 | 2026-11-01（内容未变） | 有近似 | unreachable（海外：blocked） | - | 是 | searchList 没有 detailPattern，条目里的所有链接都会被当作结果（已启用 preferShorterName）；同站其它来源提供了 1 个结果选择器，检测时一并比较；优先级自动设为 3（检测没有结论（unreachable））；请求失败：SSLError |
| anibaka | xigua | rev 9 | 2026-11-15（内容未变） | 有近似 | ok（海外：ok） | ok | 是 | searchList 没有 detailPattern，条目里的所有链接都会被当作结果（已启用 preferShorterName）；AniBaka 播放步骤不是嗅探（json/regex/template），已改成 WebView 嗅探，请在 Animeko 里试播确认；域名已跳转，改用新域名 https://cn1.xgcartoon.com（原 https://www.xgcartoon.com）；优先级自动设为 1（检测通过，播放检测：ok） |
| anibaka | 2kdm | rev 6 | 2026-11-01（内容未变） | 完整 | fail（海外：fail） | - | 否 | HTTP 404 |
| anibaka | gugu | rev 4 | 2026-09-30（内容未变） | 完整 | fail（海外：fail）（已剔除） | - | 是 | HTTP 404 |
| anibaka | anime1 | rev 3 | 2026-11-01（内容未变） | 无法转换 | - | - | 否 | 搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等）；无法转换，已跳过 |
| anibaka | dmhy | rev 5 | 2026-11-01（内容未变） | 无法转换 | - | - | 否 | 搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等）；无法转换，已跳过 |
| anibaka | mikan | rev 6 | 2026-11-01（内容未变） | 无法转换 | - | - | 否 | 搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等）；无法转换，已跳过 |
| anibaka | dm84 | rev 3 | 2026-11-01（内容未变） | 有近似 | ok（海外：ok） | ok | 是 | searchList 没有 detailPattern，条目里的所有链接都会被当作结果（已启用 preferShorterName）；AniBaka 播放步骤不是嗅探（fetch/json/regex/replace/select/setVar/template），已改成 WebView 嗅探，请在 Animeko 里试播确认；同站其它来源提供了 1 个结果选择器，检测时一并比较；优先级自动设为 1（检测通过，播放检测：ok） |
| anibaka | fsdm02 | rev 3 | 2026-09-30（内容未变） | 无法转换 | - | - | 否 | 搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等）；无法转换，已跳过 |
| anibaka | mgnacg | rev 2 | 2026-11-01（内容未变） | 有近似 | ok（海外：ok） | ok | 是 | AniBaka 播放步骤用了 playerDecrypt 取直链；Animeko 只能靠 WebView 嗅探，可能拿不到视频；逐线路播放检测：云端线路=ok、新番线路=none、Mahoo=ok、存储线路=ok；优先级自动设为 1（检测通过，播放检测：ok） |
| anibaka | moonci | rev 5 | 2026-11-15（内容未变） | 有近似 | unreachable（海外：ok） | - | 否 | searchList 没有 detailPattern，条目里的所有链接都会被当作结果（已启用 preferShorterName）；AniBaka 播放步骤用了 crypto 取直链；Animeko 只能靠 WebView 嗅探，可能拿不到视频；同站其它来源提供了 1 个结果选择器，检测时一并比较；国内出口检测unreachable，但 GitHub 海外直连通过，照样采用（排名低一级）；国内出口检测打不开（连续 1 次），0 天前通过过，暂按上次的成绩排名；请求失败：SSLError |
| anibaka | silisili | rev 2 | 2026-11-01（内容未变） | 有近似 | fail（海外：fail）（已剔除） | - | 是 | searchList 没有 detailPattern，条目里的所有链接都会被当作结果（已启用 preferShorterName）；AniBaka 播放步骤用了 crypto 取直链；Animeko 只能靠 WebView 嗅探，可能拿不到视频；搜索页能打开，但选择器没有选中任何结果（自动修复也失败：在真实搜索页上没找到合适的结果链接选择器） |
| anibaka | ezdmw | rev 5 | 2026-11-01（内容未变） | 有近似 | ok（海外：ok） | none | 是 | searchList 没有 detailPattern，条目里的所有链接都会被当作结果（已启用 preferShorterName）；AniBaka 规则没有线路名，所有线路合并为一条；AniBaka 播放步骤不是嗅探（fetch/query/regex/select/setMediaHeaders/videoUrl），已改成 WebView 嗅探，请在 Animeko 里试播确认；优先级自动设为 2（检测通过，播放检测：none）；等了 36 秒没有出现视频地址 |
| anibaka | dalvdm | rev 9 | 2026-10-07（内容未变） | 有近似 | ok（海外：blocked） | ok | 否 | 搜索用 MacCMS 的 suggest 接口（https://www.sbdl.cc/index.php/ajax/suggest?mid=1&wd={keyword}&limit=30，路径是按 MacCMS 默认值推的，AniBaka 里没写）；AniBaka 播放步骤用了 crypto 取直链；Animeko 只能靠 WebView 嗅探，可能拿不到视频；逐线路播放检测：默认线路=none、高速线路=ok、超清专线=none |
| anibaka | sorani | rev 1 | 2026-10-07（内容未变） | 无法转换 | - | - | 否 | 搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等）；无法转换，已跳过 |
| easybangumi | Jellyfin_v1.8_lib7 | 1.7 | 2025-10-12（内容未变） | 无法转换 | - | - | 否 | 手写 JS 逻辑，没有可提取的 Kazumi 规则常量（缺 SEARCH_URL/SEARCH_LIST_XPATH） |
| easybangumi | age | 1.0 | 2026-07-15（内容未变） | 无法转换 | - | - | 否 | 手写 JS 逻辑，没有可提取的 Kazumi 规则常量（缺 SEARCH_URL/SEARCH_LIST_XPATH） |
| easybangumi | girigirilove-beta | 1.0 | 2026-10-14（内容未变） | 无法转换 | - | - | 否 | 手写 JS 逻辑，没有可提取的 Kazumi 规则常量（缺 SEARCH_URL/SEARCH_LIST_XPATH） |
| easybangumi | girigirilove-v2 | 1.6 | 2026-10-25（内容未变） | 无法转换 | - | - | 否 | 手写 JS 逻辑，没有可提取的 Kazumi 规则常量（缺 SEARCH_URL/SEARCH_LIST_XPATH） |
| easybangumi | girigirilove | 1.5 | 2026-07-15（内容未变） | 无法转换 | - | - | 否 | 手写 JS 逻辑，没有可提取的 Kazumi 规则常量（缺 SEARCH_URL/SEARCH_LIST_XPATH） |
| easybangumi | kazumi-7sefun | 1.2.1 | 2026-10-20（内容未变） | 有近似 | ok（海外：ok） | ok | 否 | 末尾 text() 已改为取元素全部文本 |
| easybangumi | kazumi-9ciyuan | 1.3.1 | 2026-10-20（内容未变） | 完整 | unreachable（海外：blocked） | - | 是 | 这次没拿到页面，沿用上次验证过的分线路配置；国内出口检测打不开（连续 1 次），0 天前通过过，暂按上次的成绩排名；优先级自动设为 1（国内出口检测打不开，沿用 0.5 天前通过时的成绩，播放检测：ok）；请求失败：SSLError |
| easybangumi | kazumi-anime7 | 1.0.1 | 2026-10-20（内容未变） | 完整 | ok（海外：ok） | ok | 否 | 已自动修复选择器：搜索选择器改为 .hl-item-title a[href*='/vod-detail/']（命中 3/3）；剧集选择器改为 .hl-plays-list a（10 集） |
| easybangumi | kazumi-ant | 0.0.3 | 2026-10-20（内容未变） | 完整 | ok（海外：unreachable） | ok | 是 | 优先级自动设为 1（检测通过，播放检测：ok） |
| easybangumi | kazumi-baimao | 1.0.1 | 2026-10-20（内容未变） | 完整 | ok（海外：ok） | ok | 是 | 域名已跳转，改用新域名 https://www.bmddm.com（原 https://www.baimaodm.com）；优先级自动设为 1（检测通过，播放检测：ok） |
| easybangumi | kazumi-gpjda | 1.0 | 2026-07-10（内容未变） | 无法转换 | - | - | 否 | 规则使用 POST 搜索，Animeko 的 Web 数据源不支持 |
| easybangumi | kazumi-lmm | 2.2 | 2026-10-14（内容未变） | 无法转换 | - | - | 否 | 手写 JS 逻辑，没有可提取的 Kazumi 规则常量（缺 SEARCH_URL/SEARCH_LIST_XPATH） |
| easybangumi | kazumi-mifun | 1.1.1 | 2026-10-20（内容未变） | 无法转换 | - | - | 否 | 手写 JS 逻辑，没有可提取的 Kazumi 规则常量（缺 SEARCH_URL/SEARCH_LIST_XPATH） |
| easybangumi | kazumi-mxdm | 2.3.1 | 2026-10-20（内容未变） | 完整 | ok（海外：ok） | ok | 是 | 优先级自动设为 1（检测通过，播放检测：ok） |
| easybangumi | kazumi-omofun03 | 1.1 | 2026-07-27（内容未变） | 完整 | unreachable（海外：unreachable） | - | 是 | 优先级自动设为 3（检测没有结论（unreachable））；请求失败：SSLError |
| easybangumi | kazumi-sorani | 1.0 | 2026-07-27（内容未变） | 无法转换 | - | - | 否 | 接口型，没有可提取的 Kazumi 规则常量（缺 SEARCH_URL/SEARCH_LIST_XPATH） |
| easybangumi | kazumi-tvtfun | 1.1 | 2026-07-27（内容未变） | 无法转换 | - | - | 否 | 接口型，没有可提取的 Kazumi 规则常量（缺 SEARCH_URL/SEARCH_LIST_XPATH） |
| easybangumi | kazumi-ylsp | 1.1 | 2026-07-27（内容未变） | 完整 | unreachable（海外：unreachable）（已剔除） | - | 是 | 优先级自动设为 3（检测没有结论（unreachable））；HTTP 523 |
| easybangumi | le | 1.0 | 2025-10-19（内容未变） | 无法转换 | - | - | 否 | 手写 JS 逻辑，没有可提取的 Kazumi 规则常量（缺 SEARCH_URL/SEARCH_LIST_XPATH） |
| easybangumi | omofun | 1.3 | 2025-10-19（内容未变） | 无法转换 | - | - | 否 | 手写 JS 逻辑，没有可提取的 Kazumi 规则常量（缺 SEARCH_URL/SEARCH_LIST_XPATH） |
| easybangumi | xifandm | 1.1 | 2026-07-15（内容未变） | 无法转换 | - | - | 否 | 手写 JS 逻辑，没有可提取的 Kazumi 规则常量（缺 SEARCH_URL/SEARCH_LIST_XPATH） |
| easybangumi | yhw | 1.0 | 2025-10-11（内容未变） | 无法转换 | - | - | 否 | 手写 JS 逻辑，没有可提取的 Kazumi 规则常量（缺 SEARCH_URL/SEARCH_LIST_XPATH） |

</details>

## 国内外出口对比

<details><summary>展开查看</summary>

同一批候选分别用国内出口（代理）和 GitHub 海外服务器直连各测了一遍；表中「自动检测」列括号里是海外直连的结果。国内出口通过的按国内成绩排名；国内没通过、只有海外直连通过的也照样采用，只是排名和分档低一级。

| 国内 / 海外 | 个数 |
|---|---|
| 两边都通过 | 22 |
| 只有国内通过 | 4 |
| 只有海外通过 | 3 |
| 两边都没通过 | 15 |

| 候选 | 国内 | 海外 | 说明 | 入选 |
|---|---|---|---|---|
| anibaka:age | unreachable | blocked | 两边都没通过，但原因不同 | 是 |
| anibaka:agekkkk | unreachable | blocked | 两边都没通过，但原因不同 | 是 |
| anibaka:cyfz | unreachable | blocked | 两边都没通过，但原因不同 | 是 |
| easybangumi:kazumi-9ciyuan | unreachable | blocked | 两边都没通过，但原因不同 | 是 |
| kazumi:TvTFun | unreachable | ok | 海外通过、国内出口没通过：已按海外直连的结果采用（排名低一级）；可能是代理线路问题，也可能站点限制国内访问，值得留意 | 是 |
| anibaka:animoe | ok | blocked | 国内通过、海外被拦（海外服务器常被站点拦，符合预期） | 是 |
| easybangumi:kazumi-ant | ok | unreachable | 国内通过、海外打不开 | 是 |
| kazumi:dalvdm | ok | blocked | 国内通过、海外被拦（海外服务器常被站点拦，符合预期） | 是 |
| anibaka:moonci | unreachable | ok | 海外通过、国内出口没通过：已按海外直连的结果采用（排名低一级）；可能是代理线路问题，也可能站点限制国内访问，值得留意 | 否 |
| kazumi:AGE | unreachable | blocked | 两边都没通过，但原因不同 | 否 |
| kazumi:baimao | unreachable | ok | 海外通过、国内出口没通过：已按海外直连的结果采用（排名低一级）；可能是代理线路问题，也可能站点限制国内访问，值得留意 | 否 |
| anibaka:dalvdm | ok | blocked | 国内通过、海外被拦（海外服务器常被站点拦，符合预期） | 否 |

</details>

## UA 体检

<details><summary>展开查看</summary>

| 检查项 | 结果 | 说明 |
|---|---|---|
| requests 的 UA 与统一 UA 一致 | 通过 | 发出：Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/159.0.0.0 Safari/537.36 |
| 浏览器的 UA 与统一 UA 一致 | 通过 | 发出：Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/159.0.0.0 Safari/537.36 |
| 浏览器的客户端提示（Sec-CH-UA）版本与 UA 一致 | 通过 | UA 写 Chrome/159，Sec-CH-UA 写 "Chromium";v="159", "Google Chrome";v="159", "Not_A Brand";v="24" |
| 浏览器没有暴露 HeadlessChrome 品牌 | 通过 | "Chromium";v="159", "Google Chrome";v="159", "Not_A Brand";v="24" |

</details>

## 站点图标

<details><summary>展开查看</summary>

18 个没变；下面只列有变化或没取到的。

| 源 | 结果 | 说明 |
|---|---|---|
| aniyuan-2kdm | 没取到（保留原地址） | 试了 2 个候选地址都不是可用的图片，保留原来的 iconUrl |
| aniyuan-age | 沿用上次 | 这次没取到，沿用上次存的图标（试了 1 个候选地址都不是可用的图片） |
| aniyuan-akianime | 没取到（保留原地址） | 试了 2 个候选地址都不是可用的图片，保留原来的 iconUrl |
| aniyuan-ani-pekolove | 沿用上次 | 这次没取到，沿用上次存的图标（试了 2 个候选地址都不是可用的图片） |
| aniyuan-cyfz | 没取到（保留原地址） | 试了 2 个候选地址都不是可用的图片，保留原来的 iconUrl |
| aniyuan-ios-mifun | 没取到（保留原地址） | 试了 2 个候选地址都不是可用的图片，保留原来的 iconUrl |
| aniyuan-omofun03 | 没取到（保留原地址） | 试了 2 个候选地址都不是可用的图片，保留原来的 iconUrl |
| aniyuan-tvtfun | 没取到（保留原地址） | 试了 1 个候选地址都不是可用的图片，保留原来的 iconUrl |

</details>
