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

自动同步：每天北京时间 09:17 运行一次；改动 `*.py`、`config.json`、`overrides/`、`baseline/` 或工作流文件时也会运行。也可以在仓库 **Actions → sync-subscription → Run workflow** 手动运行。每次运行的转换报告在任务页的 Summary 里，同时保存为 `dist/report.md`。

### 在自己的仓库里部署

1. 新建公开仓库，上传本目录所有文件。
2. **Settings → Actions → General → Workflow permissions** 选 **Read and write permissions**。
3. 到 **Actions** 页面手动运行一次 `sync-subscription`（若提示 Actions 被禁用，先点启用）。

## 合并规则

同一个站点在多个来源里都有时，只留一个：

1. **分组**：按站点主机名分组（去掉 `www.` / `m.`；JSON 接口源按图标域名）。
2. **取新**：取规则文件**最后修改时间**（git 提交时间）更新的那个，**不比版本号**。时间相同时优先级为 Kazumi > 纯纯看番 > AniBaka。
3. **id 固定**：站点在 AniBaka 里有，id 为 `anibaka-<key>`（与旧订阅一致），否则为 `kazumi-<名字>`。谁胜出都不改 id，Animeko 里已有的启用状态不会丢。
4. **回退**：AniBaka 规则转不了、或搜索地址只能靠推测时，使用 `baseline/anibaka.json` 里同 id 的现成配置（基线日期取该 AniBaka 规则的日期）。基线里也没有的，在报告里列为“已跳过”。
5. **检测冲突**：胜出的来源冒烟测试没过、另一个过了：默认仍取新的，只在报告里提示。

## 转换范围

| 来源 | 能转 | 转不了（报告里会列出） |
|---|---|---|
| Kazumi | XPath（含位置式，用 `:nth-of-type`）、GET 搜索接口（JSONPath） | POST 搜索、接口取章节、并集 XPath 等；`overrides/` 里手写了 sorani、xfdmnext、giriGiriLove、ezdmw |
| AniBaka | `fetch`+`searchList`、`maccmsSuggest`、`fetch`+`jsonSeries`（GET）、`episodes` | POST/JSON 站、磁力站、anime1、`jsonEpisodes` 等 → 回退基线 |
| 纯纯看番 | `kazumi-*.js` 文件头里的 Kazumi 规则常量（还原成规则后按 Kazumi 转换） | 手写逻辑的 JS（age、omofun、xifandm、yhw、Jellyfin、lmm、mifun、sorani、tvtfun 等）、POST 的 |

纯纯看番默认只收 `extensions/`（作者真机验证过）；`dev-extensions/` 约 70 个未验证，默认不收。

## 重要限制

- **只验证“搜得到、有剧集列表”，验证不了能不能播放**，播放要在 Animeko 里实际试。
- 播放一律用 Animeko 的 WebView 嗅探。AniBaka 里靠站内解密/接口取直链的（silisili、lm6、dm84 等）可能拿不到视频，报告里会标“有近似”。
- Kazumi / 纯纯看番的规则没有线路名，转出来的源所有线路合并为一条。
- 冒烟测试在 GitHub 海外服务器上跑，访问不了的国内站标 `unreachable`，不代表配置错误；有验证码的标 `blocked`。检测未通过的**只标记不剔除**：在描述前加 `[自动检测未通过：原因]`。
- `overrides/` 手写配置不会跟着上游更新，上游版本变了报告里会提醒核对。
- 同一规则在不同来源的 git 日期可能只是发布/整理提交，不一定代表规则内容有改动，遇到取新取错的站用 `prefer` 指定。

## 配置（`config.json`）

| 键 | 作用 |
|---|---|
| `exclude` | 不收录的 Kazumi 规则名 |
| `exclude_anibaka` | 不收录的 AniBaka 规则 key |
| `exclude_easybangumi` | 不收录的纯纯看番文件名（不带 `.js`） |
| `easybangumi_channels` | `["release"]`（默认）；加上 `"dev"` 会收 `dev-extensions/` |
| `prefer` | `{"站点主机名": "kazumi" / "easybangumi" / "anibaka"}`，强制取某一边 |
| `prefer_working` | `true`：胜出的检测没过而另一个过了时，自动换用能过的 |
| `prefer_baseline` | 这些 AniBaka key 直接用 `baseline/anibaka.json` 的配置 |
| `site_aliases` | `{"主机名": "规范主机名"}`，手动并站 |
| `default_tier` / `tiers` | 数据源优先级（0 最高，4 最低）；`tiers` 按规则名/key 单独设置 |
| `drop_failed` | `true`：把“搜得到页面但选择器没选中结果”的源剔除（验证码/无法访问的不剔除） |
| `smoke_keyword` | 冒烟测试用的搜索关键词 |

`overrides/<Kazumi规则名>.json`：完整的 Animeko 数据源对象，优先于自动转换。`_kazumiVersion` 记录它基于的 Kazumi 规则版本。

## 本地运行

```bash
pip install -r requirements.txt
git clone https://github.com/Predidit/KazumiRules.git ../KazumiRules
git clone https://github.com/AniBakaBaka/AniBakaRule.git ../AniBakaRule
git clone https://github.com/easybangumiorg/CommunityJsExtensionEasyBangumi.git ../EasyBangumi
python build.py --kazumi ../KazumiRules --anibaka ../AniBakaRule --easybangumi ../EasyBangumi --out dist --smoke
```

要用完整 git 历史（不要 `--depth 1`），否则取不到每个规则文件的最后修改时间。三个来源参数都可以省略。

测试（不联网，`test_xpath2css.py` 可选设置 `KAZUMI_RULES=../KazumiRules`）：

```bash
python tests/test_xpath2css.py   # XPath → CSS 翻译器
python tests/test_anx.py         # AniBaka / 纯纯看番转换 + 同站取新
python tests/test_pipeline.py    # 整条流水线（本地模拟站点）
```

## 文件

| 文件 | 作用 |
|---|---|
| `build.py` | 总控：收集、冒烟测试、合并、输出 |
| `convert.py` / `xpath2css.py` | Kazumi 规则转换 / XPath → CSS 翻译器 |
| `anx2animeko.py` | AniBaka 规则转换 |
| `ebjs.py` | 纯纯看番 JS 源转换 |
| `smoke.py` | 联网冒烟测试 |
| `baseline/anibaka.json` | AniBaka 规则转不了时的回退配置 |
| `overrides/` | 手写的 Kazumi 规则配置 |
| `config.json`、`tests/`、`.github/workflows/sync.yml` | 配置、测试、工作流 |
