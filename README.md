# Kazumi + AniBaka → Animeko 订阅自动同步

每天自动读取 [KazumiRules](https://github.com/Predidit/KazumiRules) 的 `index.json`（也就是 Kazumi 应用里“规则仓库”列出的那批规则），
和 [AniBakaRule](https://github.com/AniBakaBaka/AniBakaRule) 的全部规则，合并、转换成 Animeko 能用的数据源订阅，放到 `dist/all.json`。Kazumi 的规则更新后，订阅会自动跟着更新。

## 一次性设置

1. 在 GitHub 新建一个仓库（公开、私有都行，但公开仓库才能用下面的订阅链接），把本目录的所有文件上传进去。
2. 仓库 **Settings → Actions → General → Workflow permissions**，选 **Read and write permissions**。
3. 到 **Actions** 页面，选 `sync-subscription`，点 **Run workflow** 手动跑一次。
4. 跑完后 `dist/all.json` 就是你的订阅。在 Animeko「设置 → 数据源订阅」里添加下面任一链接（把 `用户名/仓库名` 换成你的）：
   - `https://cdn.jsdelivr.net/gh/用户名/仓库名@main/dist/all.json`（国内一般更容易访问，缓存约半天）
   - `https://raw.githubusercontent.com/用户名/仓库名/main/dist/all.json`

之后每天北京时间 09:17 自动同步；每次运行的转换报告在 Actions 任务页的 Summary 里，也保存在 `dist/report.md`。

## 同站点取新

- 按站点主机名（去掉 `www.`/`m.`）分组；同一个站在多个来源里都有时，取**规则文件最后修改时间更新**的那个（用 git 提交时间，并列取 Kazumi）。
- 订阅里的 `id` 固定：站点在 AniBaka 里有就用 `anibaka-<key>`（和你原来的订阅一致），否则 `kazumi-<名字>`。谁赢了不影响 id，Animeko 里的启用状态不会丢。
- AniBaka 规则转不了（POST/JSON 站、磁力站、anime1、用 jsonEpisodes 取章节的等）时，回退到 `baseline/anibaka.json` 里同 id 的现成配置；搜索地址只能靠推测的（MacCMS suggest）也优先用 baseline 里手调过的。baseline 里也没有的会在报告里列为“已跳过”。
- “更新的那个”自动检测没过、旧的却过了：默认仍取新的，并在报告里提示；想自动换用旧的就把 `prefer_working` 设为 `true`，或用 `prefer` 指定。

## 它做了什么

| 步骤 | 说明 |
|---|---|
| 转换 | 把 Kazumi 的 XPath 翻译成 CSS 选择器（位置式的 `//div[2]/div[1]` 用 `:nth-of-type` 翻译），搜索接口类规则转成 JSONPath。 |
| 手写覆盖 | 规则用到 POST、接口取章节、并集 XPath 等，无法自动转换的（目前：sorani、xfdmnext、giriGiriLove、ezdmw），使用 `overrides/规则名.json` 里手写的配置。 |
| 联网冒烟测试 | 用关键词真的去搜一次，再进详情页检查剧集选择器是否有结果。结果为 `ok / fail / blocked / unreachable`。 |
| 输出 | `dist/all.json`。检测未通过的**只标记不剔除**：在源的描述前加 `[自动检测未通过：原因]`。 |

## 重要限制

- **只能验证到“搜得到、有剧集列表”，验证不了能不能播放**，播放要在 Animeko 里实际试。
- 没有线路名：Kazumi 规则里没有线路名选择器，转出来的源所有线路合并为一条。
- GitHub 的服务器在海外，部分国内站点可能访问不了，会标成 `unreachable`，这不代表配置错误。
- 有验证码或反爬检查的站（标成 `blocked`）在 Animeko 里不一定能用，请自己测试。
- 手写覆盖不会自动跟着 Kazumi 规则更新；规则版本变了，报告里会提醒你核对。

## 调整

- `config.json`
  - `exclude_anibaka`：不收录的 AniBaka 规则 key（默认为空）。
  - `prefer`：`{"站点主机名": "kazumi" 或 "anibaka"}` 强制取某一边。`prefer_baseline`：这些 AniBaka key 直接用 baseline 的配置。`site_aliases`：手动并站。
  - `default_tier` / `tiers`：数据源优先级（0 最高，4 最低），可以按规则名单独设置。
  - `exclude`：不收录的规则名（默认不排除任何规则；aafun 和 moonci 是同一个站，会按“同站取新”自动合并）。
  - `drop_failed`：设为 `true` 时，把“搜得到页面但选择器没选中结果”的源直接剔除（验证码/无法访问的不会被剔除）。
- `overrides/`：放一个 `规则名.json`（完整的 Animeko 数据源对象，`id` 建议用 `kazumi-小写规则名`），就会优先使用它。里面的 `_kazumiVersion` 记录它基于 Kazumi 规则的哪个版本。

## 本地运行

```bash
pip install -r requirements.txt
git clone https://github.com/Predidit/KazumiRules.git ../KazumiRules
git clone https://github.com/AniBakaBaka/AniBakaRule.git ../AniBakaRule
python build.py --kazumi ../KazumiRules --anibaka ../AniBakaRule --out dist --smoke
python tests/test_xpath2css.py   # 翻译器自测（可选：KAZUMI_RULES=../KazumiRules）
python tests/test_anx.py         # AniBaka 转换 + 同站取新自测
python tests/test_pipeline.py    # 流水线自测（本地模拟站点）
```

## 文件

- `anx2animeko.py`：AniBaka 规则转换　`baseline/anibaka.json`：转不了时的回退配置
- `xpath2css.py`：XPath → CSS 翻译器　`convert.py`：规则转换　`smoke.py`：冒烟测试　`build.py`：总控
- `config.json`、`overrides/`、`tests/`、`.github/workflows/sync.yml`

## AniBaka 转换的限制

- 播放一律改成 Animeko 的 WebView 嗅探；AniBaka 里靠站内解密/接口取直链的（silisili、lm6、dm84 等）可能拿不到视频，报告里会标“有近似”。
- 能转：fetch+searchList、maccmsSuggest、fetch+jsonSeries（GET）、episodes。其余见报告。
