# Animeko 订阅自动同步

每天自动把三个来源的番剧源规则转换成 Animeko 能用的数据源订阅，合并成一个文件 `dist/all.json`：

| 来源 | 内容 |
|---|---|
| [KazumiRules](https://github.com/Predidit/KazumiRules) | `index.json` 里列出的规则（即 Kazumi 应用里“规则仓库”那批） |
| [AniBakaRule](https://github.com/AniBakaBaka/AniBakaRule) | 全部规则（`anx-rule/2` 格式） |
| [纯纯看番社区源](https://github.com/easybangumiorg/CommunityJsExtensionEasyBangumi) | `extensions/` 里能提取出规则的 JS 源 |

## 使用

订阅链接（Animeko「设置 → 数据源订阅」里添加，任选其一）：

- `https://cdn.jsdelivr.net/gh/nlhaiuy/aniyuan@main/dist/all.json`（国内一般更容易访问，有约半天缓存）
- `https://raw.githubusercontent.com/nlhaiuy/aniyuan/main/dist/all.json`

仓库必须是公开的，私有仓库的链接无法匿名访问。

自动同步：每天北京时间 09:17 运行一次；改动 `*.py`、`config.json`、`overrides/`、`baseline/`、`manual/` 或工作流文件时也会运行。也可以在仓库 **Actions → sync-subscription → Run workflow** 手动运行。每次运行的转换报告在任务页的 Summary 里，同时保存为 `dist/report.md`。

工作流分两个任务：**build** 只有只读权限、不保留 `GITHUB_TOKEN`，负责跑测试、联网检测和无头浏览器（要打开一堆第三方站点），产物只有 `dist/` 和 `state/` 里的几个 JSON；**publish** 才有写权限，不运行浏览器、不访问第三方站点，只检查产物是合法 JSON、条目数没异常偏少，再提交。

### 在自己的仓库里部署

1. 新建公开仓库，上传本目录所有文件。
2. **Settings → Actions → General → Workflow permissions** 选 **Read and write permissions**。
3. 到 **Actions** 页面手动运行一次 `sync-subscription`（若提示 Actions 被禁用，先点启用）。

## 手动维护的源（`manual/`）

你亲自验证过可用的源放在 `manual/` 里（Animeko 导出的订阅文件，或单个源 JSON 都行），同站点时**永远优先于自动转换**，不会被自动修复、替换，也不会因为检测没过而落选（只在报告里写备注）。没有 `id` 的会自动补，和别的来源同站时 id 沿用 AniBaka 的稳定 id。目前有 `girigirilove.json`。

### 域名会变怎么办

静态的源（`manual/`、`baseline/`、`overrides/`）域名换了不会自己更新，所以程序会**跟随上游**：同一个站（按主域名里的名字，如 `girigirilove`，与 `.com/.xyz` 无关）的 Kazumi / AniBaka / 纯纯看番规则多数已经换到新的主域名时，把静态源里的旧主域名整体换掉（保留 `ani.` / `m3u8.` / `bg.` 这些子域名），**重新联网检测通过才采用**，没通过就保持原样并在报告备注里提示。另外，搜索请求被网站自己跳转到新域名、且之后一切正常时，也会自动换成新域名（`follow_redirects`）。两项都只改输出的订阅，不改 `manual/` 里的原文件。可用 `follow_upstream_domains: false` 关闭。

## 合并规则

同一个站点在多个来源里都有时，只留一个：

0. **手动优先**：`manual/` 里有这个站的源，直接用它，下面几条只用来决定 id。
1. **分组**：按站点主机名分组（去掉 `www.` / `m.`；JSON 接口源按图标域名）。
2. **实测优先**（开启联网检测时）：能播放 > 检测通过 > 没有结论（无法访问 / 验证码 / 跳过） > 明确失败。最新的那个明确失败而旧的通过，就用旧的，并在报告里写明原因。可用 `select_by_smoke: false` 关闭。
3. **取新**：同一档里取规则**最后真正改动的时间**更新的那个，**不比版本号**。时间相同时优先级为 Kazumi > 纯纯看番 > AniBaka > 基线。
4. **id 固定**：id 为 `aniyuan-<站点名>`，站点名取自 AniBaka 的 key（站点在 AniBaka 里有时），否则取 Kazumi 规则名。谁胜出都不改 id，Animeko 里已有的启用状态不会丢。（旧版订阅用的是 `anibaka-<key>` / `kazumi-<名字>`，改成统一的 `aniyuan-` 前缀那一次，Animeko 里这些源的启用状态需要重新开一次。）
5. **基线一起比**：`baseline/anibaka.json` 里你原来的配置不再只是“转不了时的备胎”，而是和自动转换的结果作为**两个候选**一起比较（同一条 AniBaka 规则，域名不同也算同一个站）：检测通过的优先；都没联网检测时，自动转换的搜索地址若是推测的就用基线，否则用自动转换（上游）。你在基线里设置的 `tier` / `channelTiers` 会保留。转不了又没有基线的，在报告里列为“已跳过”。

### “最后改动时间”怎么算

git 提交日期会被“发布 / 整理”提交带偏（例如社区仓库一次提交就刷新了所有文件的日期）。所以程序在 `state/seen.json` 里记录每个规则**文件内容的哈希**和它的日期：

- 第一次见到：用 git 日期。
- 内容哈希没变：沿用记录的日期，不管 git 日期怎么变。
- 内容哈希变了：用 git 日期（若比记录新），否则用本次同步的时间。

`state/seen.json` 由工作流自动提交，不要手动删（删了会退回 git 日期）。

### 检测历史：连续失败才降级

单次检测会受网络影响，所以 `state/health.json` 记录每个候选的历次检测结果。**以前通过过、这次才第一次明确失败（`fail`）**的候选处于宽限期：按上次通过时的成绩排名（不会立刻让位给别的来源）、描述里不加警告、也不会被 `drop_failed` 剔除，只在报告备注里写“暂不降级”；连续失败达到 `fail_threshold`（默认 2）次才真正降级。从没通过过的候选第一次失败就算数。`blocked` / `unreachable` / 没检测既不算失败也不会清零。通过一次就清零。

## 联网检测（`--smoke`、`--playcheck`）

每次同步会真的去请求站点，对**每个候选**依次做：

1. **冒烟测试**：用关键词搜索 → 进详情页 → 检查剧集选择器（`no-channel` 和 `index-grouped` 都支持）。第一个条目的详情页打不开时，会再试后面两个。被 403 / 503 拦住（Cloudflare 一类）时，改用无头浏览器取页面再试一次（`browser_fallback`，需要 `--playcheck`）。
2. **自动修复选择器**：检测失败时，直接看真实页面重选。用“常见模板的容器 × 常见详情页路径”去试，挑命中最多最精确的；再在详情页上挑剧集最多的播放列表。候选库 = 内置 + 从 AniBaka 规则里挖出来的（人工维护过）。修复后必须**重新通过检测**才会采用，描述前会加 `[选择器已自动修复]`。
3. **替换脆弱写法**：位置式选择器（多个 `:nth-of-type`）还能用时，如果更稳的写法也通过、且剧集数不少于原来，就替换。
4. **跟随域名跳转**：搜索被跳转到新域名、且之后一切正常，就把源里的旧域名整体换成新域名。
5. **播放检测**：用无头浏览器（Chromium）打开第一集的播放页，监听页面和 iframe 的请求、`<video>` 元素，用**这个源自己的 `matchVideoUrl`** 去匹配。结果：`ok` 能播且正则认得出；`mismatch` 视频地址出现了但正则认不出（配置要改）；`none` 没抓到（可能要点击/登录，不一定坏）；`blocked` 验证码；`error`。

这些结果直接参与“同站取舍”：能播 > 没检测 > 没抓到 > 认不出 > 没结论 > 明确失败。

## 转换范围

| 来源 | 能转 | 转不了（报告里会列出） |
|---|---|---|
| Kazumi | XPath（含位置式，用 `:nth-of-type`）、GET 搜索接口（JSONPath） | POST 搜索、接口取章节、并集 XPath 等；`overrides/` 里手写了 sorani、xfdmnext、giriGiriLove、ezdmw |
| AniBaka | `fetch`+`searchList`、`maccmsSuggest`、`fetch`+`jsonSeries`（GET）、`episodes` | POST/JSON 站、磁力站、anime1、`jsonEpisodes` 等 → 回退基线 |
| 纯纯看番 | `kazumi-*.js` 文件头里的 Kazumi 规则常量（还原成规则后按 Kazumi 转换） | 手写逻辑的 JS（age、omofun、xifandm、yhw、Jellyfin、lmm、mifun、sorani、tvtfun 等）、POST 的 |

纯纯看番默认只收 `extensions/`（作者真机验证过）；`dev-extensions/` 约 70 个未验证，默认不收。

## 订阅里的 id / 名称 / 描述格式

输出前由 `normalize.py` 统一规整：

- **id**：`aniyuan-<站点名>`，小写字母、数字和连字符；不再带 `anibaka-` / `kazumi-` 这类来源前缀（它和实际采用的来源常常对不上）。站点名沿用原来的 AniBaka key / Kazumi 规则名，所以同一个站的 id 之后不会再变。
- **名称**：全角括号转半角，括号前留一个空格；纯英文/数字的站名（如 `ant`、`LMM`）补上域名，写成 `ant (mayi520.org)`；名称本来就是域名里的名字（`mgnacg` / `mgnacg.com`）则不补。想用别的名字，在 `config.json` 的 `names` 里按 id 指定。
- **描述**：`[自动检测未通过：…] [选择器已自动修复] 站点简介。（来源：AniBaka 规则 age rev 6，自动转换）`。简介取上游规则自带的，没有就写 `站点 域名。`；来源（Kazumi 规则 / AniBaka 规则 / 纯纯看番社区源 / 基线配置 / 手动维护，加规则名、版本和“自动转换 / 手写配置”）由程序统一生成，各转换器不再自己拼。

## 重要限制

- 播放检测用的是无头浏览器，不等于 Animeko 的 WebView：有的站需要点击、登录、特定 UA 才出视频，会显示 `none`，不代表一定不能播；`ok` 也只代表抓到了视频地址，最终仍请在 Animeko 里试播。
- 播放一律用 Animeko 的 WebView 嗅探。AniBaka 里靠站内解密/接口取直链的（silisili、lm6、dm84 等）可能拿不到视频，报告里会标“有近似”。
- Kazumi / 纯纯看番的规则没有线路名，转出来的源所有线路合并为一条。
- 检测在 GitHub 海外服务器上跑，访问不了的国内站标 `unreachable`（没有结论，不会被降级也不会被修复），不代表配置错误；有验证码或被 403 拦住的标 `blocked`。这两类只在报告里记录，**不会**往订阅的描述里加警告（多半是海外服务器的问题）。只有页面能打开、但选择器确实没选中结果的（`fail`），且已连续失败到 `fail_threshold` 次（见上面的检测历史）才**只标记不剔除**：在描述前加 `[自动检测未通过：原因]`。
- `overrides/` 手写配置不会跟着上游更新，上游版本变了报告里会提醒核对。
- 首次运行没有哈希记录，日期仍用 git 日期（社区仓库的日期可能偏新），之后才会按内容变化校正；遇到取新取错的站用 `prefer` 指定。

## 配置（`config.json`）

| 键 | 作用 |
|---|---|
| `exclude` | 不收录的 Kazumi 规则名 |
| `exclude_anibaka` | 不收录的 AniBaka 规则 key |
| `exclude_easybangumi` | 不收录的纯纯看番文件名（不带 `.js`） |
| `easybangumi_channels` | `["release"]`（默认）；加上 `"dev"` 会收 `dev-extensions/` |
| `prefer` | `{"站点主机名": "kazumi" / "easybangumi" / "anibaka"}`，强制取某一边 |
| `select_by_smoke` | 默认 `true`：同站多个来源时先看联网检测结果；`false` 只看时间 |
| `prefer_baseline` | 这些 AniBaka key 直接用 `baseline/anibaka.json` 的配置 |
| `site_aliases` | `{"主机名": "规范主机名"}`，手动并站（已有：girigiri 的接口域名、2kdm.com → mutedm.com） |
| `browser_fallback` | 默认 `true`：requests 被 403/503 拦时改用无头浏览器 |
| `default_tier` / `tiers` | 数据源优先级（0 最高，4 最低）；`tiers` 按规则名/key 单独设置 |
| `repair` / `replace_brittle` / `follow_redirects` / `follow_upstream_domains` | 默认都是 `true`：自动修复失效选择器 / 替换脆弱的位置式写法 / 跟随搜索跳转的新域名 / 静态源跟随上游换主域名 |
| `play_check_max` / `play_wait_ms` | 播放检测的数量上限（默认 80）/ 每个最多等待毫秒数（默认 20000） |
| `drop_failed` | `true`：把“搜得到页面但选择器没选中结果”的源剔除（验证码/无法访问的不剔除） |
| `fail_threshold` | 默认 `2`：连续明确失败几次才降级 / 加警告 / 剔除（以前通过过的候选，没到次数都算宽限期） |
| `names` | `{"id": "显示名称"}`：手动指定某个源的名称，优先于自动规整 |
| `smoke_keyword` | 冒烟测试用的搜索关键词 |

`overrides/<Kazumi规则名>.json`：完整的 Animeko 数据源对象，优先于自动转换。`_kazumiVersion` 记录它基于的 Kazumi 规则版本。

## 本地运行

```bash
pip install -r requirements.txt
git clone https://github.com/Predidit/KazumiRules.git ../KazumiRules
git clone https://github.com/AniBakaBaka/AniBakaRule.git ../AniBakaRule
git clone https://github.com/easybangumiorg/CommunityJsExtensionEasyBangumi.git ../EasyBangumi
playwright install chromium   # 只在需要播放检测时
python build.py --kazumi ../KazumiRules --anibaka ../AniBakaRule --easybangumi ../EasyBangumi --out dist --smoke --playcheck
```

要用完整 git 历史（不要 `--depth 1`），否则取不到每个规则文件的最后修改时间。三个来源参数都可以省略。

测试（不联网，`test_xpath2css.py` 可选设置 `KAZUMI_RULES=../KazumiRules`）：

```bash
python tests/test_xpath2css.py   # XPath → CSS 翻译器
python tests/test_anx.py         # AniBaka / 纯纯看番转换 + 同站取新
python tests/test_health.py      # 检测历史：连续失败才降级
python tests/test_normalize.py   # id / 名称 / 描述规整
python tests/test_pipeline.py    # 整条流水线（本地模拟站点）
python tests/test_live.py        # 自动修复 / 域名跳转 / 播放检测（本地模拟站点 + Chromium）
```

## 文件

| 文件 | 作用 |
|---|---|
| `build.py` | 总控：收集、冒烟测试、合并、输出 |
| `convert.py` / `xpath2css.py` | Kazumi 规则转换 / XPath → CSS 翻译器 |
| `anx2animeko.py` | AniBaka 规则转换 |
| `ebjs.py` | 纯纯看番 JS 源转换 |
| `smoke.py` | 联网冒烟测试 |
| `domains.py` | 静态源跟随上游域名 |
| `repair.py` | 选择器自动修复 |
| `playcheck.py` | 无头浏览器播放检测 |
| `health.py` | 检测历史：连续失败才降级 |
| `normalize.py` | 输出前统一 id / 名称 / 描述格式 |
| `state/seen.json` | 各规则文件内容哈希和最后改动时间（自动维护） |
| `state/health.json` | 各候选历次联网检测结果（自动维护，别手动删，删了会失去宽限期） |
| `manual/` | 亲测可用的源，同站永远优先 |
| `baseline/anibaka.json` | AniBaka 规则转不了时的回退配置 |
| `overrides/` | 手写的 Kazumi 规则配置 |
| `config.json`、`tests/`、`.github/workflows/sync.yml` | 配置、测试、工作流 |
