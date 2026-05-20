# 📅 个人会议截止日期日历

> 一个**只追踪你投稿了哪些会**的自动更新日历,包含公开工具都没有的
> **rebuttal(反驳期)/ notification(录用通知)/ camera-ready(终稿)** 日期。

这份 README 是写给 **Claude Code** 看的。如果你(人类)是第一次打开,先读
最下面的「给人类:5 分钟上手」。如果你是 Claude Code agent,从「给 agent 的
任务说明」开始。

---

## 这个项目是什么

```
config.yml(你投了哪些会)─┐
                          ├─► generate.py ─► deadlines.ics(订阅一次,永久更新)
overrides.yml(手填/agent填的日期)┘   ▲
                                       │
                ccfddl/ccf-deadlines 公开数据集(每天抓最新)
```

- **`config.yml`** — 你投稿的会议清单(名字 + 年份)。平时唯一需要改的文件。
- **`overrides.yml`** — rebuttal / notification / camera-ready 日期。这些**没有任何
  公开数据源**,只能从各会议征稿页抓取。以前要手填,现在交给 agent 每天查。
- **`generate.py`** — 把上面两者和实时数据集合并,生成 `deadlines.ics`。
- **`.github/workflows/update.yml`** — 备用方案:GitHub Action 每天跑一次
  `generate.py`(只抓自动数据,不查 rebuttal 等)。

---

## 为什么用 Claude Code Routine(这是你想要的「每天自动做」)

`generate.py` 只能抓数据集里**已有**的字段(摘要/投稿截止、开会日期、地点)。
但 rebuttal / notification / camera-ready 只以文字形式写在各会议官网,**没有
机器可读的数据源**。普通脚本抓不了——但带判断力的 agent 可以读懂网页文字、
把这些日期抽出来。

**Claude Code Routine** 就是干这个的:在 Anthropic 的云端按计划运行,你的电脑
关机也照跑。把 `ROUTINE_PROMPT.md` 里的内容设成一个每日 Routine,agent 就会
每天:

1. 读 `config.yml` 看你投了哪些会
2. 逐个去会议官网查 rebuttal / notification / camera-ready 日期
3. 更新 `overrides.yml`
4. 跑 `generate.py` 重新生成 `deadlines.ics`
5. 提交回仓库

这样你订阅的日历就**真正全自动**了,连那三类"散文里的日期"也自动补齐。

---

## 给人类:5 分钟上手

### A. 部署到 GitHub
1. 新建一个 GitHub 仓库,把本文件夹所有文件传上去(或 `git push`)。
2. 仓库 **Settings → Actions → General → Workflow permissions** 选
   **Read and write permissions**(让自动任务能提交更新后的 `.ics`)。

### B. 设成每日 Routine(核心,需 Pro 及以上套餐)
1. 在 Claude Code 里连接这个 GitHub 仓库。
2. 新建一个 **Routine**:
   - 频率:**每天**(daily)
   - 仓库:选这个仓库
   - 提示词:复制 `ROUTINE_PROMPT.md` 的全部内容
3. 保存。以后它每天自动运行,电脑关机也没关系。

> 套餐限额:Pro 每天 5 次、Max 15 次,每天查一次足够。

### C. 订阅日历(只做一次)
用生成文件的 **raw** 链接:
```
https://raw.githubusercontent.com/<你的用户名>/<仓库名>/main/deadlines.ics
```
- **Google 日历**:其他日历 → ＋ → 通过网址添加 → 粘贴。
- **Apple 日历**:文件 → 新建日历订阅 → 粘贴。
- **Outlook**:添加日历 → 从 Web 订阅 → 粘贴。

> 是**订阅**网址,不是**导入**文件,否则不会自动更新。

---

## 添加一个会议

编辑 `config.yml`:
```yaml
conferences:
  - name: CVPR
    year: 2026
    label: CVPR 2026
```
`name` 会自动匹配数据集(不区分大小写)。少数会议文件名特殊——例如
**NeurIPS** 存为 `nips.yml`。匹配失败时加一行 hint:
```yaml
  - name: NeurIPS
    year: 2026
    file: conference/AI/nips.yml
```

## 本地手动运行
```bash
pip install -r requirements.txt
python generate.py            # 生成 deadlines.ics
python generate.py --dry-run  # 仅预览,不写文件
```

---

## 诚实的局限
- **提醒**:在每个截止日期前 14/7/3/1 天触发(可在 config.yml 的 reminder_days 调整),
  只加在截止日期事件上,不加在多天的开会事件上。
- **时区**:用固定 UTC 偏移(含 AoE = UTC-12),够单次提醒用,不建模夏令时。
- **数据可能滞后**:投稿季初期某些会只有占位日期,每日刷新会自动跟进修正。
- **数据集由社区维护**:临近截止时,一切以会议官网为准。

数据集:ccfddl/ccf-deadlines (https://github.com/ccfddl/ccf-deadlines) — MIT 许可。
