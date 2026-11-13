# 网页事件、campaign 与流量来源上下文补全

- **需求编号**: T114
- **规范大类**: query（上下文文档维护，未执行查数）
- **状态**: ✅ 已完成
- **日期**: 2026-11-10
- **定稿 SQL**: 无 / 本次交付为上下文文档与阅读入口

## 初始需求

核对 DB_agent 是否包含 imm_data_dashboard 中网页相关事件的上下文；补足 Agent 查询网站浏览量、campaign 与流量来源时需要的字段含义、主体口径和选表信息。

## 口径

| 项 | 定义 |
|----|------|
| 时间窗 | 2026-11-10 本地文档快照；本任务为上下文维护，不设业务取数窗口、不查库 |
| 核对对象 | 网页事件、身份、campaign / UTM / referrer 的历史定义与 Agent 阅读入口 |
| 验证范围 | 来源文档、字段目录、相对链接、自动同步结构段和差异格式，不代表现网数据质量验证 |

### 范围与证据

- 只读核对两个本地仓库的现有文档与 SQL，不连接数据库，不修改 imm_data_dashboard。
- 网站访问与来源的历史定义来自 imm_data_dashboard 的 `base_info/table.md`、`webdata/webapp.md`、`webdata/网站首页ab测试数据.md`、`webdata/official_homepage_onboarding_not_upgrade_devices.md`、`webdata/onboarding_pageview_funnel.md`。
- 本仓映证 T012（WebApp document DAU）与 T063（官网指纹→新装断链）。
- 新文档区分历史定义、任务观察与待核验信息；不将本地 SQL 当作现网表结构或任务运行状态的证明。

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| 网页事件与字段映射 | [`web_events.md`](../norms/web_events.md)第 2、3、8 节；保留两个下载事件名与 arg8 含义差异 | ✅ |
| 网站 PV / UV、匿名访客与身份缺口 | 上述文档第 1、4 节；区分指纹、身份类型、设备、登录 ID 及不可关联访客 | ✅ |
| campaign / source / medium / referrer 及归因模型 | 上述文档第 3、5 节；区分访问携带、首次触达与订单快照 | ✅ |
| 网页明细与 WebApp 派生表选型 | 上述文档第 6、7 节；表目录、行为表及三张相关表文档接入 | ✅ |
| Agent 能发现并读取上下文 | AGENTS、Cursor alwaysApply 规则、query 与全局规范索引、表目录、README | ✅ |

## 抽样复核（文档维护）

- 逐项对照前述历史来源；明确下载事件名、扩展字段、身份覆盖和新访客来源表的边界，未把差异合并成已确认的现网定义。
- 已核新增文档字段名与 `user_behaviour` 表目录中的 18 个字段一致。
- 新增相对链接存在性检查通过；4 份改动表文档的 `AUTO:SCHEMA` 段与 HEAD 一致；`git diff --check` 通过。
- 修正 query / AGENTS / Cursor 中插件版本规则的适用范围，避免误用于网站匿名流量。

本次不交付业务数字，不进行数据库抽样或现网表/埋点验证。
