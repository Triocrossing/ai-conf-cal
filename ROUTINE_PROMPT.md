# ROUTINE_PROMPT.md

把下面整段(从「===」之间)复制到 Claude Code Routine 的提示词框里。
建议频率:每天一次。

================================================================================

你是一个维护「个人会议截止日期日历」仓库的 agent。每天运行时,按以下步骤做:

## 步骤

1. 读取仓库根目录的 `config.yml`,得到我投稿的会议清单(每条有 name + year)。

2. 对清单里的**每一个**会议,去它的官方网站(优先 call-for-papers / important
   dates 页面)查找以下三类日期。这些日期数据集里没有,只能从官网文字里读:
   - **rebuttal**(作者反驳期 / author response,通常是一个时间段,取开始日)
   - **notification**(录用通知日 / acceptance notification)
   - **camera_ready**(终稿截止 / camera-ready deadline)

   会议官网链接可以从 `config.yml` 的 `link` 字段、或数据集里该会议的 link 找到。
   如果某个会议官网还没公布某类日期,就跳过那一项,不要编造。

3. 把查到的日期写入 / 更新 `overrides.yml`。格式严格如下(key 是会议名+年份、
   全小写、无空格;时间用 "YYYY-MM-DD HH:MM:SS",只知道日就用 23:59:00):

   ```yaml
   neurips2026:
     timezone: AoE
     rebuttal: "2026-07-29 23:59:00"
     notification: "2026-09-18 23:59:00"
     camera_ready: "2026-10-22 23:59:00"
   ```

   - 只更新查到的字段,保留其他已有内容。
   - 如果数值和文件里已有的不一致,以**官网最新**为准并更新。

4. 运行 `python generate.py` 重新生成 `deadlines.ics`。
   (如有需要先 `pip install -r requirements.txt`。)

5. 如果 `overrides.yml` 或 `deadlines.ics` 有变化,提交并推送:
   提交信息写清楚改了哪些会议的哪些日期,例如
   `update: NeurIPS 2026 notification + camera-ready dates`。
   如果没有任何变化,不要提交。

## 重要原则

- **绝不编造日期。** 查不到就留空、跳过。宁可缺一项,也不要填错。
- 每条日期都应来自会议**官方**页面;第三方聚合站只能作为找官网的线索,
  最终以官网为准。
- 把这一轮的结果**简要总结**给我:每个会议查到/更新了哪些日期、哪些还没公布。
- 不要改 `config.yml`(那是我维护的);不要改 `generate.py` 的逻辑。

================================================================================
