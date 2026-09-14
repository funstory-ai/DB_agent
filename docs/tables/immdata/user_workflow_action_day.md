# `immdata.user_workflow_action_day`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.user_workflow_action_day` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 574892 |
| 创建时间 | 2026-05-28 09:29:38.163915 |
| 表注释 | 用户每日工作流嵌入指标：导出动作 / 高级设置使用 |

## 来源与用途（手工维护）

- **数据来源**：工作流相关埋点日汇总（批量翻译 / 高级功能等，见表注释）
- **同步方式**：ETL
- **业务含义**：用户每日工作流嵌套/高级能力使用
- **建议粒度**：用户 × 日
- **常用过滤**：`dt`
- **关联建议**：用户 id
- **勿想当然**：覆盖人群可能偏小，勿当全体活跃定义

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `dt` | `date` | NO |  | 日期（北京时间） |
| 1 | `userid` | `bigint` | NO |  | 注册用户ID |
| 1 | `export_cnt` | `int` | NO | 0 | 导出次数（click_download_subtitle + open_download_subtitle_page） |
| 1 | `copy_cnt` | `int` | NO | 0 | 复制次数（暂无事件，预留字段） |
| 1 | `advanced_feature_cnt` | `int` | NO | 0 | 高级功能使用次数（7类事件合计） |
| 1 | `has_advanced_feature` | `tinyint` | NO | 0 | 当天是否使用过高级功能（1=是，0=否） |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.user_workflow_action_day LIMIT 20;
```
