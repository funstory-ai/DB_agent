# `immdata.imt_campaigninfo`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imt_campaigninfo` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 28559780 |
| 创建时间 | 2026-03-27 16:48:38.075732 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：业务库活动/落地归因信息（设备侧）
- **同步方式**：业务库 → Databend
- **更新频率**：随访问/转化上报
- **业务含义**：设备维度 campaign / UTM / reference
- **建议粒度**：记录行（`deviceid` 可多条）
- **主键 / 唯一键**：`id`
- **常用过滤**：`COALESCE(isdeleted,0)=0`
- **关联建议**：`deviceid`；勿直接当「安装唯一归因」除非已去重规则
- **勿想当然**：空 UTM 很常见；`translated=1` 不代表付费

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `id` | `bigint` | NO |  |  |
| 1 | `deviceid` | `varchar(16382)` | YES |  |  |
| 1 | `reference` | `varchar(16382)` | YES |  |  |
| 1 | `utmcampaign` | `varchar(16382)` | YES |  |  |
| 1 | `utmmedium` | `varchar(16382)` | YES |  |  |
| 1 | `utmsource` | `varchar(16382)` | YES |  |  |
| 1 | `translated` | `tinyint` | YES |  |  |
| 1 | `extenddata` | `varchar(16382)` | YES |  |  |
| 1 | `operator` | `varchar(16382)` | YES |  |  |
| 1 | `updatetime` | `timestamp` | YES |  |  |
| 1 | `createtime` | `timestamp` | YES |  |  |
| 1 | `isdeleted` | `tinyint` | YES |  |  |
| 1 | `dataversion` | `int` | YES |  |  |
| 1 | `appversion` | `varchar(16382)` | YES |  |  |
| 1 | `browser` | `varchar(16382)` | YES |  |  |
| 1 | `browseruseragent` | `varchar(16382)` | YES |  |  |
| 1 | `ext1` | `varchar(16382)` | YES |  |  |
| 1 | `ext2` | `varchar(16382)` | YES |  |  |
| 1 | `ext3` | `varchar(16382)` | YES |  |  |
| 1 | `platform` | `varchar(16382)` | YES |  |  |
| 1 | `interfacelang` | `varchar(16382)` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imt_campaigninfo LIMIT 20;
```
