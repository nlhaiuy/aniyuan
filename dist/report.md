# 订阅转换报告

写入订阅 **31** 个数据源（候选 72 个，同站点合并后）。

检测出口：国内出口（代理 socks5h://127.0.0.1:7890），并用 GitHub 海外服务器直连做了一遍对照，见「国内外出口对比」。

## 本次变化

**移除（2）**

- GirigiriLove（aniyuan-girigirilove，m3u8.girigirilove.com）
- 青空次元 (Sorani)（aniyuan-sorani，api.sorani.cc）

**档位变化（8）**

- Animoe动漫：3 → 1
- 次元番：3 → 1
- 嘀嗒影视 (Dida HD)：1 → 4
- MiFun：3 → 1
- 西瓜卡通：3 → 2
- 9ciyuan (jcydm1.com)：1 → 4
- ant (mayi520.org)：2 → 1
- xfdmneo (dm1.xfdm.pro)：4 → 1

**换域名（1）**

- 西瓜卡通：cn1.xgcartoon.com → www.xgcartoon.com

## 同站点取舍

| 站点 | 最终 id | 采用 | 理由 | 候选（最后修改） |
|---|---|---|---|---|
| 5dm.dev | aniyuan-5dm | anibaka:5dm | 只有这一个来源 | anibaka:5dm(2026-10-07) |
| 7sefun.top | aniyuan-7sefun | easybangumi:kazumi-7sefun | 最新的 anibaka:7sefun 自动检测没有结论，改用检测结果更好的（ok） | easybangumi:kazumi-7sefun(2026-10-20)<br>kazumi:7sefun(2026-08-10)<br>anibaka:7sefun(2026-11-01) |
| agedm.io | aniyuan-age | anibaka:age | 更新（2026-11-01） | anibaka:age(2026-11-01)<br>kazumi:AGE(2026-10-28) |
| akianime.com | aniyuan-akianime | anibaka:akianime | 只有这一个来源；同名站点 akianime.cc 因域名不一致被分成了两组，已合并为一个（保留检测结果更好的 anibaka:akianime） | anibaka:akianime(2026-11-15)<br>kazumi:akianime(2026-08-17) |
| ani.pekolove.net | aniyuan-ani-pekolove | anibaka:ani_pekolove | 只有这一个来源 | anibaka:ani_pekolove(2026-11-15) |
| anime7.top | aniyuan-anime7 | anibaka:anime7 | 更新（2026-11-15） | anibaka:anime7(2026-11-15)<br>easybangumi:kazumi-anime7(2026-10-20) |
| animoe.org | aniyuan-animoe | anibaka:animoe | 只有这一个来源 | anibaka:animoe(2026-11-01) |
| baimaodm.com | aniyuan-baimao | easybangumi:kazumi-baimao | 更新（2026-10-20） | easybangumi:kazumi-baimao(2026-10-20)<br>kazumi:baimao(2026-01-28) |
| cn.agekkkk.com | aniyuan-agekkkk | anibaka:agekkkk | 只有这一个来源 | anibaka:agekkkk(2026-11-01) |
| cyfz.top | aniyuan-cyfz | anibaka:cyfz | 只有这一个来源 | anibaka:cyfz(2026-11-16) |
| dcc3.com | aniyuan-mxdm | easybangumi:kazumi-mxdm | 更新（2026-10-20） | easybangumi:kazumi-mxdm(2026-10-20)<br>kazumi:MXdm(2026-10-01) |
| didahd.xyz | aniyuan-didahd | anibaka:didahd | 只有这一个来源 | anibaka:didahd(2026-11-01) |
| dm1.xfdm.pro | aniyuan-xfdmneo | kazumi:xfdmneo | 只有这一个来源 | kazumi:xfdmneo(2026-03-08) |
| dmbus.cc | aniyuan-dm84 | anibaka:dm84 | 更新（2026-11-01） | anibaka:dm84(2026-11-01)<br>kazumi:DM84(2026-02-02) |
| ezdmw.org | aniyuan-ezdmw | anibaka:ezdmw | 只有这一个来源 | anibaka:ezdmw(2026-11-01) |
| gugu3.com | aniyuan-gugu | anibaka:gugu | 只有这一个来源 | anibaka:gugu(2026-09-30) |
| ios.mifun.org | aniyuan-ios-mifun | anibaka:ios_mifun | 只有这一个来源 | anibaka:ios_mifun(2026-11-15) |
| jcydm1.com | aniyuan-9ciyuan | easybangumi:kazumi-9ciyuan | 只有这一个来源 | easybangumi:kazumi-9ciyuan(2026-10-20) |
| lm6.net | aniyuan-lm6 | anibaka:lm6 | 只有这一个来源 | anibaka:lm6(2026-11-16) |
| lmm22.com | aniyuan-lmm | kazumi:LMM | 只有这一个来源 | kazumi:LMM(2026-11-13) |
| mayi520.org | aniyuan-ant | easybangumi:kazumi-ant | 只有这一个来源 | easybangumi:kazumi-ant(2026-10-20) |
| mgnacg.com | aniyuan-mgnacg | anibaka:mgnacg | 更新（2026-11-01） | anibaka:mgnacg(2026-11-01)<br>kazumi:mgnacg(2026-10-15) |
| moonci.com | aniyuan-moonci | anibaka:moonci | 更新（2026-11-15） | anibaka:moonci(2026-11-15)<br>kazumi:moonci(2026-10-19)<br>kazumi:aafun(2026-08-21) |
| mutedm.com | aniyuan-2kdm | kazumi:mutefun | 最新的 anibaka:2kdm 自动检测未通过，改用检测结果更好的（unreachable） | kazumi:mutefun(2026-10-31)<br>anibaka:2kdm(2026-11-01) |
| next.xifanacg.com | aniyuan-xfdmnext | kazumi:xfdmnext | 只有这一个来源 | kazumi:xfdmnext(2026-10-01) |
| omofun03.top | aniyuan-omofun03 | easybangumi:kazumi-omofun03 | 只有这一个来源 | easybangumi:kazumi-omofun03(2026-07-27) |
| sbdl.cc | aniyuan-dalvdm | kazumi:dalvdm | 更新（2026-10-15） | kazumi:dalvdm(2026-10-15)<br>anibaka:dalvdm(2026-10-07) |
| silisilifun.com | aniyuan-silisili | anibaka:silisili | 只有这一个来源 | anibaka:silisili(2026-11-01) |
| tvtfun.net | aniyuan-tvtfun | kazumi:TvTFun | 只有这一个来源 | kazumi:TvTFun(2026-10-28) |
| xgcartoon.com | aniyuan-xigua | anibaka:xigua | 只有这一个来源 | anibaka:xigua(2026-11-15) |
| ylys.cc | aniyuan-ylsp | easybangumi:kazumi-ylsp | 只有这一个来源 | easybangumi:kazumi-ylsp(2026-07-27) |

## 全部候选

| 来源 | 规则 | 版本 | 修改日期（依据） | 转换 | 自动检测 | 播放 | 采用 | 备注 |
|---|---|---|---|---|---|---|---|---|
| kazumi | 7sefun | 1.3 | 2026-08-10（内容未变） | 有近似 | ok（海外：ok） | ok | 否 | 末尾 text() 已改为取元素全部文本 |
| kazumi | aafun | 1.2 | 2026-08-21（内容未变） | 完整 | ok（海外：ok） | ok | 否 |  |
| kazumi | AGE | 1.6 | 2026-10-28（内容未变） | 完整 | unreachable（海外：blocked） | - | 否 | 请求失败：SSLError |
| kazumi | akianime | 1.4 | 2026-08-17（内容未变） | 完整 | ok（海外：ok） | ok | 否 | 已自动修复选择器：搜索选择器改为 .vod-detail a[href]（命中 2/31）；剧集选择器改为 .anthology-list-box a（84 集） |
| kazumi | baimao | 1.0 | 2026-01-28（内容未变） | 完整 | unreachable（海外：ok） | - | 否 | 国内出口检测打不开（连续 1 次），0 天前通过过，暂按上次的成绩排名；请求失败：SSLError |
| kazumi | dalvdm | 1.2 | 2026-10-15（内容未变） | 完整 | ok（海外：blocked） | none | 是 | 优先级自动设为 2（检测通过，播放检测：none）；等了 20 秒没有出现视频地址 |
| kazumi | DM84 | 1.4 | 2026-02-02（内容未变） | 完整 | ok（海外：ok） | none | 否 | 等了 20 秒没有出现视频地址 |
| kazumi | ezdmw | 1.2 | 2026-08-16（内容未变） | 无法转换 | - | - | 否 | 章节 XPath 无法转换：并集 / |
| kazumi | giriGiriLove | 2.7 | 2026-11-13（内容未变） | 无法转换 | - | - | 否 | 章节接口格式是 delimited（分隔字符串等），Animeko 的 json-api 没有对应的解析方式 |
| kazumi | LMM | 2.4 | 2026-11-13（内容未变） | 完整 | ok（海外：ok） | ok | 是 | 优先级自动设为 1（检测通过，播放检测：ok） |
| kazumi | mgnacg | 1.2 | 2026-10-15（内容未变） | 完整 | ok（海外：ok） | none | 否 | 等了 20 秒没有出现视频地址 |
| kazumi | moonci | 1.1 | 2026-10-19（内容未变） | 完整 | ok（海外：ok） | ok | 否 |  |
| kazumi | mutefun | 1.6 | 2026-10-31（内容未变） | 完整 | unreachable（海外：blocked） | - | 是 | 优先级自动设为 3（检测没有结论（unreachable））；请求失败：SSLError |
| kazumi | MXdm | 2.4 | 2026-10-01（内容未变） | 完整 | ok（海外：ok） | ok | 否 |  |
| kazumi | sorani | 1.0 | 2026-07-13（内容未变） | 无法转换 | -（海外：ok） | - | 否 | 从播放页学习 play 失败：播放页没有发出带视频地址的 JSON 接口请求（共抓到 0 个 XHR/fetch；视频地址可能在页面 HTML / iframe 里，或需要登录 / 点击）；json-api 数据源必须有 play（取视频地址的请求）：Kazumi 规则里没有，官方订阅里没有同一接口的源，也没能从播放页学出来，需要手写 play |
| kazumi | TvTFun | 1.3 | 2026-10-28（内容未变） | 完整 | unreachable（海外：ok） | - | 是 | 国内出口检测打不开（连续 2 次），1 天前通过过，暂按上次的成绩排名；优先级自动设为 2（国内出口检测打不开，沿用 1.3 天前通过时的成绩，播放检测：none）；请求失败：SSLError |
| kazumi | xfdmneo | 1.1 | 2026-03-08（内容未变） | 完整 | unreachable（海外：ok） | - | 是 | 国内出口检测打不开（连续 1 次），3 天前通过过，暂按上次的成绩排名；优先级自动设为 1（国内出口检测打不开，沿用 2.7 天前通过时的成绩，播放检测：ok）；请求失败：SSLError |
| kazumi | xfdmnext | 1.1 | 2026-10-01（内容未变） | 有近似 | ok（海外：ok） | ok | 是 | 播放接口（play）借鉴自官方订阅里同一接口的源「稀饭动漫 Next」；搜索请求体改用官方写法；详情请求体改用官方写法；剧集序号 / 类型字段借鉴官方；优先级自动设为 1（检测通过，播放检测：ok） |
| anibaka | 7sefun | rev 9 | 2026-11-01（内容未变） | 完整 | ok（海外：ok） | none | 否 | 等了 20 秒没有出现视频地址 |
| anibaka | cyfz | rev 9 | 2026-11-16（内容未变） | 完整 | unreachable（海外：ok） | - | 是 | 国内出口检测打不开（连续 8 次），3 天前通过过，暂按上次的成绩排名；优先级自动设为 1（国内出口检测打不开，沿用 2.7 天前通过时的成绩，播放检测：ok）；请求失败：SSLError |
| anibaka | 5dm | rev 1 | 2026-10-07（内容未变） | 完整 | blocked（海外：blocked） | - | 是 | 优先级自动设为 3（检测没有结论（blocked））；HTTP 403 |
| anibaka | ani_pekolove | rev 10 | 2026-11-15（内容未变） | 有近似 | blocked（海外：blocked） | - | 是 | searchList 没有 detailPattern，条目里的所有链接都会被当作结果（已启用 preferShorterName）；XPath 里按文字过滤的条件（contains(text(), ..)）转不了，已去掉，可能多选到非剧集链接；AniBaka 规则没有线路名，所有线路合并为一条；AniBaka 播放步骤不是嗅探（fetch/query/regex/replace/select/setMediaHeaders/setVar），已改成 WebView 嗅探，请在 Animeko 里试播确认；优先级自动设为 3（检测没有结论（blocked））；搜索页出现验证码/环境检查（验证码 / 环境检查，Animeko 会弹验证浏览器让用户通过） |
| anibaka | lm6 | rev 6 | 2026-11-16（内容未变） | 有近似 | unreachable（海外：ok） | - | 是 | AniBaka 播放步骤用了 crypto 取直链；Animeko 只能靠 WebView 嗅探，可能拿不到视频；国内出口检测打不开（连续 1 次），0 天前通过过，暂按上次的成绩排名；优先级自动设为 1（国内出口检测打不开，沿用 0.4 天前通过时的成绩，播放检测：ok）；请求失败：SSLError |
| anibaka | aniwatch | rev 5 | 2026-11-01（内容未变） | 无法转换 | - | - | 否 | 章节步骤无法转换（需要 episodes 操作，实际是：fetch, jsonEpisodes, regex）；baseline 里也没有这个源，已跳过 |
| anibaka | akianime | rev 8 | 2026-11-15（内容未变） | 有近似 | ok（海外：unreachable） | ok | 是 | searchList 没有 detailPattern，条目里的所有链接都会被当作结果（已启用 preferShorterName）；优先级自动设为 1（检测通过，播放检测：ok） |
| anibaka | animoe | rev 5 | 2026-11-01（内容未变） | 有近似 | ok（海外：blocked） | ok | 是 | AniBaka 播放步骤不是嗅探（playerAaaa/regex），已改成 WebView 嗅探，请在 Animeko 里试播确认；优先级自动设为 1（检测通过，播放检测：ok） |
| anibaka | tvtfun | rev 13 | 2026-11-01（内容未变） | 无法转换 | - | - | 否 | 章节步骤无法转换（需要 episodes 操作，实际是：fetch, jsonEpisodes, regex）；baseline 里也没有这个源，已跳过 |
| anibaka | ios_mifun | rev 9 | 2026-11-15（内容未变） | 完整 | ok（海外：ok） | ok | 是 | 优先级自动设为 1（检测通过，播放检测：ok） |
| anibaka | agekkkk | rev 3 | 2026-11-01（内容未变） | 有近似 | blocked（海外：blocked） | - | 是 | 搜索用到 maccmsVerify（MacCMS 图片验证码），Animeko 有自动 solver，通常能自动通过，通不过时会弹验证浏览器；searchList 没有 detailPattern，条目里的所有链接都会被当作结果（已启用 preferShorterName）；优先级自动设为 3（检测没有结论（blocked））；搜索页出现验证码/环境检查（网站防火墙的点击/滑块验证，Animeko 会弹验证浏览器让用户通过） |
| anibaka | didahd | rev 7 | 2026-11-01（内容未变） | 有近似 | fail（海外：fail） | - | 是 | AniBaka 播放步骤用了 maccmsVerify 取直链；Animeko 只能靠 WebView 嗅探，可能拿不到视频；详情页 HTTP 404（https://www.didahd.xyz/detail/1185.html）（自动修复也失败：没有详情页内容可用来修复剧集选择器） |
| anibaka | anime7 | rev 6 | 2026-11-15（内容未变） | 有近似 | ok（海外：ok） | ok | 是 | searchList 没有 detailPattern，条目里的所有链接都会被当作结果（已启用 preferShorterName）；优先级自动设为 1（检测通过，播放检测：ok） |
| anibaka | hanimeone | rev 7 | 2026-11-01（内容未变） | 无法转换 | - | - | 否 | 章节步骤无法转换（需要 episodes 操作，实际是：jsonEpisodes, template）；baseline 里也没有这个源，已跳过 |
| anibaka | girigirilove | rev 5 | 2026-11-01（内容未变） | 无法转换 | - | - | 否 | 章节步骤无法转换（需要 episodes 操作，实际是：fetch, maccmsApiEpisodes, regex, template）；baseline 里也没有这个源，已跳过 |
| anibaka | girigirilove_beta | rev 2 | 2026-11-01（内容未变） | 无法转换 | - | - | 否 | 章节步骤无法转换（需要 episodes 操作，实际是：fetch, maccmsApiEpisodes, regex, template）；baseline 里也没有这个源，已跳过 |
| anibaka | xifanacg | rev 5 | 2026-09-30（内容未变） | 无法转换 | - | - | 否 | 搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等）；baseline 里也没有这个源，已跳过 |
| anibaka | age | rev 7 | 2026-11-01（内容未变） | 有近似 | unreachable（海外：blocked） | - | 是 | searchList 没有 detailPattern，条目里的所有链接都会被当作结果（已启用 preferShorterName）；优先级自动设为 3（检测没有结论（unreachable））；请求失败：SSLError |
| anibaka | xigua | rev 9 | 2026-11-15（内容未变） | 有近似 | unreachable（海外：ok） | - | 是 | searchList 没有 detailPattern，条目里的所有链接都会被当作结果（已启用 preferShorterName）；AniBaka 播放步骤不是嗅探（json/regex/template），已改成 WebView 嗅探，请在 Animeko 里试播确认；国内出口检测打不开（连续 1 次），0 天前通过过，暂按上次的成绩排名；优先级自动设为 2（国内出口检测打不开，沿用 0.4 天前通过时的成绩，播放检测：none）；请求失败：SSLError |
| anibaka | 2kdm | rev 6 | 2026-11-01（内容未变） | 完整 | fail（海外：fail） | - | 否 | HTTP 404 |
| anibaka | gugu | rev 4 | 2026-09-30（内容未变） | 完整 | fail（海外：fail） | - | 是 | HTTP 404 |
| anibaka | anime1 | rev 3 | 2026-11-01（内容未变） | 无法转换 | - | - | 否 | 搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等）；baseline 里也没有这个源，已跳过 |
| anibaka | dmhy | rev 5 | 2026-11-01（内容未变） | 无法转换 | - | - | 否 | 搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等）；baseline 里也没有这个源，已跳过 |
| anibaka | mikan | rev 6 | 2026-11-01（内容未变） | 无法转换 | - | - | 否 | 搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等）；baseline 里也没有这个源，已跳过 |
| anibaka | dm84 | rev 3 | 2026-11-01（内容未变） | 有近似 | ok（海外：ok） | none | 是 | searchList 没有 detailPattern，条目里的所有链接都会被当作结果（已启用 preferShorterName）；AniBaka 播放步骤不是嗅探（fetch/json/regex/replace/select/setVar/template），已改成 WebView 嗅探，请在 Animeko 里试播确认；优先级自动设为 2（检测通过，播放检测：none）；等了 20 秒没有出现视频地址 |
| anibaka | fsdm02 | rev 3 | 2026-09-30（内容未变） | 无法转换 | - | - | 否 | 搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等）；baseline 里也没有这个源，已跳过 |
| anibaka | mgnacg | rev 2 | 2026-11-01（内容未变） | 有近似 | ok（海外：ok） | none | 是 | AniBaka 播放步骤用了 playerDecrypt 取直链；Animeko 只能靠 WebView 嗅探，可能拿不到视频；优先级自动设为 2（检测通过，播放检测：none）；等了 20 秒没有出现视频地址 |
| anibaka | moonci | rev 5 | 2026-11-15（内容未变） | 有近似 | ok（海外：ok） | ok | 是 | searchList 没有 detailPattern，条目里的所有链接都会被当作结果（已启用 preferShorterName）；AniBaka 播放步骤用了 crypto 取直链；Animeko 只能靠 WebView 嗅探，可能拿不到视频；优先级自动设为 1（检测通过，播放检测：ok） |
| anibaka | silisili | rev 2 | 2026-11-01（内容未变） | 有近似 | fail（海外：fail） | - | 是 | searchList 没有 detailPattern，条目里的所有链接都会被当作结果（已启用 preferShorterName）；AniBaka 播放步骤用了 crypto 取直链；Animeko 只能靠 WebView 嗅探，可能拿不到视频；搜索页能打开，但选择器没有选中任何结果（自动修复也失败：在真实搜索页上没找到合适的结果链接选择器） |
| anibaka | ezdmw | rev 5 | 2026-11-01（内容未变） | 有近似 | ok（海外：ok） | none | 是 | searchList 没有 detailPattern，条目里的所有链接都会被当作结果（已启用 preferShorterName）；AniBaka 规则没有线路名，所有线路合并为一条；AniBaka 播放步骤不是嗅探（fetch/query/regex/select/setMediaHeaders/videoUrl），已改成 WebView 嗅探，请在 Animeko 里试播确认；优先级自动设为 2（检测通过，播放检测：none）；等了 20 秒没有出现视频地址 |
| anibaka | dalvdm | rev 9 | 2026-10-07（内容未变） | 有近似 | ok（海外：blocked） | none | 否 | 搜索用 MacCMS 的 suggest 接口（https://www.sbdl.cc/index.php/ajax/suggest?mid=1&wd={keyword}&limit=30，路径是按 MacCMS 默认值推的，AniBaka 里没写）；AniBaka 播放步骤用了 crypto 取直链；Animeko 只能靠 WebView 嗅探，可能拿不到视频；等了 20 秒没有出现视频地址 |
| anibaka | sorani | rev 1 | 2026-10-07（内容未变） | 无法转换 | - | - | 否 | 搜索步骤无法转换（POST/JSON 接口、磁力站、需要嗅探搜索页等）；baseline 里也没有这个源，已跳过 |
| easybangumi | Jellyfin_v1.8_lib7 | 1.7 | 2025-10-12（内容未变） | 无法转换 | - | - | 否 | 手写 JS 逻辑，没有可提取的 Kazumi 规则常量（缺 SEARCH_URL/SEARCH_LIST_XPATH） |
| easybangumi | age | 1.0 | 2026-07-15（内容未变） | 无法转换 | - | - | 否 | 手写 JS 逻辑，没有可提取的 Kazumi 规则常量（缺 SEARCH_URL/SEARCH_LIST_XPATH） |
| easybangumi | girigirilove-beta | 1.0 | 2026-10-14（内容未变） | 无法转换 | - | - | 否 | 手写 JS 逻辑，没有可提取的 Kazumi 规则常量（缺 SEARCH_URL/SEARCH_LIST_XPATH） |
| easybangumi | girigirilove-v2 | 1.6 | 2026-10-25（内容未变） | 无法转换 | - | - | 否 | 手写 JS 逻辑，没有可提取的 Kazumi 规则常量（缺 SEARCH_URL/SEARCH_LIST_XPATH） |
| easybangumi | girigirilove | 1.5 | 2026-07-15（内容未变） | 无法转换 | - | - | 否 | 手写 JS 逻辑，没有可提取的 Kazumi 规则常量（缺 SEARCH_URL/SEARCH_LIST_XPATH） |
| easybangumi | kazumi-7sefun | 1.2.1 | 2026-10-20（内容未变） | 有近似 | ok（海外：ok） | ok | 是 | 末尾 text() 已改为取元素全部文本；优先级自动设为 1（检测通过，播放检测：ok） |
| easybangumi | kazumi-9ciyuan | 1.3.1 | 2026-10-20（内容未变） | 完整 | fail（海外：blocked） | - | 是 | 搜索页能打开，但选择器没有选中任何结果（自动修复也失败：修复后的选择器仍未通过：搜索页能打开，但选择器没有选中任何结果） |
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
| easybangumi | kazumi-ylsp | 1.1 | 2026-07-27（内容未变） | 完整 | unreachable（海外：unreachable） | - | 是 | 优先级自动设为 3（检测没有结论（unreachable））；HTTP 523 |
| easybangumi | le | 1.0 | 2025-10-19（内容未变） | 无法转换 | - | - | 否 | 手写 JS 逻辑，没有可提取的 Kazumi 规则常量（缺 SEARCH_URL/SEARCH_LIST_XPATH） |
| easybangumi | omofun | 1.3 | 2025-10-19（内容未变） | 无法转换 | - | - | 否 | 手写 JS 逻辑，没有可提取的 Kazumi 规则常量（缺 SEARCH_URL/SEARCH_LIST_XPATH） |
| easybangumi | xifandm | 1.1 | 2026-07-15（内容未变） | 无法转换 | - | - | 否 | 手写 JS 逻辑，没有可提取的 Kazumi 规则常量（缺 SEARCH_URL/SEARCH_LIST_XPATH） |
| easybangumi | yhw | 1.0 | 2025-10-11（内容未变） | 无法转换 | - | - | 否 | 手写 JS 逻辑，没有可提取的 Kazumi 规则常量（缺 SEARCH_URL/SEARCH_LIST_XPATH） |

## 国内外出口对比

同一批候选分别用国内出口（代理，决定排名）和 GitHub 海外服务器直连（只做对照）各测了一遍；表中「自动检测」列括号里是海外直连的结果。

| 国内 / 海外 | 个数 |
|---|---|
| 两边都通过 | 20 |
| 只有国内通过 | 5 |
| 只有海外通过 | 6 |
| 两边都没通过 | 13 |

| 候选 | 国内 | 海外 | 说明 | 入选 |
|---|---|---|---|---|
| anibaka:age | unreachable | blocked | 两边都没通过，但原因不同 | 是 |
| anibaka:cyfz | unreachable | ok | 海外通过、国内出口没通过：可能是代理线路问题，也可能站点限制国内访问，值得留意 | 是 |
| anibaka:lm6 | unreachable | ok | 海外通过、国内出口没通过：可能是代理线路问题，也可能站点限制国内访问，值得留意 | 是 |
| anibaka:xigua | unreachable | ok | 海外通过、国内出口没通过：可能是代理线路问题，也可能站点限制国内访问，值得留意 | 是 |
| easybangumi:kazumi-9ciyuan | fail | blocked | 两边都没通过，但原因不同 | 是 |
| kazumi:TvTFun | unreachable | ok | 海外通过、国内出口没通过：可能是代理线路问题，也可能站点限制国内访问，值得留意 | 是 |
| kazumi:mutefun | unreachable | blocked | 两边都没通过，但原因不同 | 是 |
| kazumi:xfdmneo | unreachable | ok | 海外通过、国内出口没通过：可能是代理线路问题，也可能站点限制国内访问，值得留意 | 是 |
| anibaka:akianime | ok | unreachable | 国内通过、海外打不开 | 是 |
| anibaka:animoe | ok | blocked | 国内通过、海外被拦（海外服务器常被站点拦，符合预期） | 是 |
| easybangumi:kazumi-ant | ok | unreachable | 国内通过、海外打不开 | 是 |
| kazumi:dalvdm | ok | blocked | 国内通过、海外被拦（海外服务器常被站点拦，符合预期） | 是 |
| kazumi:AGE | unreachable | blocked | 两边都没通过，但原因不同 | 否 |
| kazumi:baimao | unreachable | ok | 海外通过、国内出口没通过：可能是代理线路问题，也可能站点限制国内访问，值得留意 | 否 |
| anibaka:dalvdm | ok | blocked | 国内通过、海外被拦（海外服务器常被站点拦，符合预期） | 否 |

## 国内出口盲区

最终入选的源里，有 12 个这次在国内出口检测不出结论（被拦 / 打不开），不等于站点坏了：

| 候选 | 状态 | 排名依据 |
|---|---|---|
| kazumi:mutefun | unreachable | 从没检测通过过，没有可沿用的成绩 |
| kazumi:TvTFun | unreachable | 沿用 1.3 天前通过时的成绩 |
| kazumi:xfdmneo | unreachable | 沿用 2.7 天前通过时的成绩 |
| anibaka:cyfz | unreachable | 沿用 2.7 天前通过时的成绩 |
| anibaka:5dm | blocked | 从没检测通过过，没有可沿用的成绩 |
| anibaka:ani_pekolove | blocked | 从没检测通过过，没有可沿用的成绩 |
| anibaka:lm6 | unreachable | 沿用 0.4 天前通过时的成绩 |
| anibaka:agekkkk | blocked | 从没检测通过过，没有可沿用的成绩 |
| anibaka:age | unreachable | 从没检测通过过，没有可沿用的成绩 |
| anibaka:xigua | unreachable | 沿用 0.4 天前通过时的成绩 |
| easybangumi:kazumi-omofun03 | unreachable | 从没检测通过过，没有可沿用的成绩 |
| easybangumi:kazumi-ylsp | unreachable | 从没检测通过过，没有可沿用的成绩 |

## UA 体检

| 检查项 | 结果 | 说明 |
|---|---|---|
| requests 的 UA 与统一 UA 一致 | 通过 | 发出：Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/159.0.0.0 Safari/537.36 |
| 浏览器的 UA 与统一 UA 一致 | 通过 | 发出：Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/159.0.0.0 Safari/537.36 |
| 浏览器的客户端提示（Sec-CH-UA）版本与 UA 一致 | 通过 | UA 写 Chrome/159，Sec-CH-UA 写 "Chromium";v="159", "Google Chrome";v="159", "Not_A Brand";v="24" |
| 浏览器没有暴露 HeadlessChrome 品牌 | 通过 | "Chromium";v="159", "Google Chrome";v="159", "Not_A Brand";v="24" |

## 站点图标

| 源 | 结果 | 说明 |
|---|---|---|
| aniyuan-2kdm | 没取到（保留原地址） | 试了 2 个候选地址都不是可用的图片，保留原来的 iconUrl |
| aniyuan-age | 沿用上次 | 这次没取到，沿用上次存的图标（试了 1 个候选地址都不是可用的图片） |
| aniyuan-akianime | 没取到（保留原地址） | 试了 2 个候选地址都不是可用的图片，保留原来的 iconUrl |
| aniyuan-anime7 | 沿用上次 | 这次没取到，沿用上次存的图标（试了 3 个候选地址都不是可用的图片） |
| aniyuan-ant | 沿用上次 | 这次没取到，沿用上次存的图标（试了 1 个候选地址都不是可用的图片） |
| aniyuan-baimao | 沿用上次 | 这次没取到，沿用上次存的图标（试了 2 个候选地址都不是可用的图片） |
| aniyuan-cyfz | 没取到（保留原地址） | 试了 2 个候选地址都不是可用的图片，保留原来的 iconUrl |
| aniyuan-gugu | 没取到（保留原地址） | 试了 2 个候选地址都不是可用的图片，保留原来的 iconUrl |
| aniyuan-ios-mifun | 没取到（保留原地址） | 试了 2 个候选地址都不是可用的图片，保留原来的 iconUrl |
| aniyuan-omofun03 | 没取到（保留原地址） | 试了 2 个候选地址都不是可用的图片，保留原来的 iconUrl |
| aniyuan-tvtfun | 没取到（保留原地址） | 试了 1 个候选地址都不是可用的图片，保留原来的 iconUrl |
| aniyuan-xigua | 沿用上次 | 这次没取到，沿用上次存的图标（试了 2 个候选地址都不是可用的图片） |
| aniyuan-ylsp | 沿用上次 | 这次没取到，沿用上次存的图标（试了 1 个候选地址都不是可用的图片） |
| aniyuan-5dm | 没变 | https://www.5dm.dev/wp-content/themes/5dm-next/assets/brand/mascot-touch-180.png（180×180） |
| aniyuan-7sefun | 没变 | https://www.7sefun.top/pc/img/favicon.ico（32×32） |
| aniyuan-9ciyuan | 没变 | https://www.jcydm1.com/upload/mxprocms/20241012-1/5ba127dcfd607d60e83d5f984f821ef0.png（150×150） |
| aniyuan-agekkkk | 没变 | https://cn.agekkkk.com/template/the4/statics/img/favicon.ico（64×64） |
| aniyuan-ani-pekolove | 没变 | https://ani.pekolove.net/wp-content/uploads/cropped-acglogo2-2-32x32.png（32×32） |
| aniyuan-animoe | 没变 | https://github.elemecdn.com/mstatic616/images/logo/favicon.png（512×512） |
| aniyuan-dalvdm | 没变 | https://www.sbdl.cc/template/mizhiady/statics/images/favicon.png（300×300） |
| aniyuan-didahd | 没变 | https://www.didahd.xyz/template/mytheme/statics/img/newfavicon.png（175×175） |
| aniyuan-dm84 | 没变 | https://dmbus.cc/favicon.ico（32×32） |
| aniyuan-ezdmw | 没变 | https://www.ezdmw.org/favicon.ico（32×32） |
| aniyuan-lm6 | 没变 | https://m.lm6.net/template/jable/statics/icon/apple-touch-icon.png（180×180） |
| aniyuan-lmm | 没变 | https://www.lmm22.com/template/jable/statics/icon/apple-touch-icon.png（180×180） |
| aniyuan-mgnacg | 没变 | https://r2img.nanoacg.com/favicon.png（32×32） |
| aniyuan-moonci | 没变 | https://www.moonci.com/template/conch/asset/img/ios_fav.png（128×128） |
| aniyuan-mxdm | 没变 | https://www.dcc3.com/favicon.ico（48×48） |
| aniyuan-silisili | 没变 | https://www.silisilifun.com/tgy/img/logo.png（229×112） |
| aniyuan-xfdmneo | 没变 | https://xifan.moe/favicon.ico（32×32） |
| aniyuan-xfdmnext | 没变 | https://next.xifanacg.com/favicon.ico?favicon.0dlvkfxcpy8s1.ico（256×256） |
