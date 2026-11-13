# `immdata.routing_ledger`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.routing_ledger` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 126229234（2026-11-09 实测） |
| 创建时间 | 2026-10-30 03:24:25.009753（**新建表**） |
| 时间字段 | `startedat`（TIMESTAMP），实测覆盖 **2026-10-29 03:47:47 ~ 2026-11-08 15:59:59**，持续增长 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：imt-api 路由层逐次调用台账（routing ledger），记录每一次**路由尝试**及上游返回的原始用量，持续写入。
- **业务含义**：一条 = 一次 `routeattempt`（含重试；`attemptindex` / `transportattemptindex` 区分第几次尝试），**不等于一次业务请求**。带 `raw*usage` = 上游原始 token 数、`rawusagejson` = 原始 usage 报文。
- **核心价值**：**UCloud 网关逐请求日志与 `token_used_aw` 账本之间唯一的桥接表**（详见下方「标准 JOIN 链路」与 pitfalls **P049**）。
- **建议粒度**：按 `routeattemptid` 逐条；聚合前必须确认是否已按 `upstreamrequestid` 去重。
- **常用过滤**：**必须**带 `startedat` 粗时间窗（1.26 亿行，无过滤聚合会被 kill）；UCloud 相关务必加 `providername='UCloud'`。`providername` 是**上游通道**（BabelFast / Sophnet / OneRouter / Google / DeepL-LB / OpenAI / DashScope / DeepSeek / UCloud / Volcengine / OpenRouter / RunpodGemma …），UCloud 只是其中一路，占比很小（2026-11-02 UTC 为 119,177 / 约 1,346 万）。
- **关联建议**：见「标准 JOIN 链路」。与 `token_used_aw` 用 `routeattemptid`，与网关日志用 `upstreamrequestid`。
- **勿想当然**：
  1. **表名是 `routing` 不是 `route`**：`SHOW TABLES LIKE '%route%'` **搜不到它**，必须列 `immdata` 全表名。
  2. **`businessid` 不能连网关**：`token_used_aw.businessid` 是 imt-api 自生成 UUID，与 UCloud 网关 `request_id` 实测 119,176 条**交集 0**（两套独立命名空间）。此表没有 `businessid` 列。
  3. **时间覆盖很短**：仅 10-29 起，**不含 8 月及更早**，历史月份无法用它做逐请求桥接。
  4. `rawcachedinputusage` 全为 0（imt-api 多 Controller 硬编码 `CachedInputUsage = 0`）；缓存 token 已折进 `rawinputusage`，token 量能对上但**没有单独的 cache 便宜价维度**。
  5. `upstreamrequestid` 并非 100% 有值，须看 `requestidstate`；ID 来源看 `upstreamrequestidsource`（`header:x-request-id` / `header:X-Infron-Request-Id` / `header:x-ds-trace-id` / `header:apim-request-id`，多数为 NULL）。`upstreamrequestids` 是 JSON，含多个来源 ID，可用于补匹配。
  6. `outcome` / `httpstatuscode` / `errorkind` / `routereason` 是**路由执行结果**（成功/取消/上游错误/传输错误/解析失败），**不是模型生成的 `finish_reason`**。本表**没有** `finish_reason` 列；`finish_reason` 只存在于供应商 AstraFlow 网关日志里。

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `traceid` | `varchar(16382)` | YES |  |  |
| 1 | `autooperationid` | `varchar(16382)` | YES |  |  |
| 1 | `routeinvocationid` | `varchar(16382)` | YES |  |  |
| 1 | `nodeexecutionid` | `varchar(16382)` | YES |  |  |
| 1 | `routeattemptid` | `varchar(16382)` | YES |  | 连 `token_used_aw.routeattemptid` |
| 1 | `attemptindex` | `bigint` | YES |  |  |
| 1 | `transportattemptindex` | `bigint` | YES |  |  |
| 1 | `routesystem` | `varchar(16382)` | YES |  |  |
| 1 | `userid` | `bigint` | YES |  |  |
| 1 | `tenantid` | `double` | YES |  |  |
| 1 | `requestedresourceid` | `varchar(16382)` | YES |  |  |
| 1 | `actualupstreamresourceid` | `varchar(16382)` | YES |  | 实际模型名 |
| 1 | `providername` | `varchar(16382)` | YES |  | 上游通道 |
| 1 | `routename` | `varchar(16382)` | YES |  |  |
| 1 | `categoryname` | `varchar(16382)` | YES |  |  |
| 1 | `productline` | `varchar(16382)` | YES |  | 翻译服务类型 |
| 1 | `isstream` | `tinyint` | YES |  |  |
| 1 | `startedat` | `timestamp` | YES |  | **唯一时间字段，必须带窗** |
| 1 | `completedat` | `timestamp` | YES |  |  |
| 1 | `durationms` | `bigint` | YES |  |  |
| 1 | `outcome` | `varchar(16382)` | YES |  | success / cancelled / upstream_error / transport_error / parse_error |
| 1 | `httpstatuscode` | `double` | YES |  |  |
| 1 | `errorkind` | `varchar(16382)` | YES |  |  |
| 1 | `rawinputusage` | `double` | YES |  | 上游原始 input（**已含 cache**） |
| 1 | `rawcachedinputusage` | `double` | YES |  | 全 0 |
| 1 | `rawoutputusage` | `double` | YES |  | 上游原始 output |
| 1 | `rawcharacterusage` | `double` | YES |  |  |
| 1 | `usagestate` | `varchar(16382)` | YES |  | complete / unavailable / parse_failed / partial |
| 1 | `upstreamrequestid` | `varchar(16382)` | YES |  | **网关 UUID，连 AstraFlow `request_id`** |
| 1 | `upstreamrequestidsource` | `varchar(16382)` | YES |  | ID 取自哪个 response header |
| 1 | `upstreamrequestids` | `varchar(16382)` | YES |  | JSON，多来源 ID，可补匹配 |
| 1 | `upstreamresponseid` | `varchar(16382)` | YES |  |  |
| 1 | `requestidstate` | `varchar(16382)` | YES |  | captured / pending_contract / absent / no_response |
| 1 | `routereason` | `varchar(16382)` | YES |  |  |
| 1 | `rawusagejson` | `varchar(16382)` | YES |  | 原始 usage 报文 |

<!-- AUTO:SCHEMA:END -->

## 关键枚举（2026-11-02 UTC 实测）

| 字段 | 取值 |
|------|------|
| `outcome` | success 13,276,023 / cancelled 91,102 / upstream_error 81,385 / transport_error 15,125 / parse_error 891 |
| `usagestate` | complete 13,275,159 / unavailable 188,431 / parse_failed 929 / partial 7 |
| `requestidstate` | pending_contract 7,544,818 / **captured 4,190,884** / absent 1,622,693 / no_response 106,131 |
| `upstreamrequestidsource` | NULL 9,273,642 / `header:x-request-id` 3,884,992 / `header:X-Infron-Request-Id` 164,386 / `header:x-ds-trace-id` 136,652 / `header:apim-request-id` 4,854 |
| `errorkind` | NULL / cancelled / http_status / transport / parse_failed |
| `providername`（UCloud 一路） | 11-02 共 119,177 行；`upstreamrequestid` 空 108 行、`routeattemptid`/`traceid` 空 0 行、`rawusagejson` 空 120 行、`rawoutputusage=0` 0 行 |

## 标准 JOIN 链路（唯一正确路径）

```
AstraFlow 网关日志 .request_id  (UCloud 生成的 UUID)
        =  immdata.routing_ledger.upstreamrequestid
        →  immdata.routing_ledger.routeattemptid
        =  immdata.token_used_aw.routeattemptid
        →  inputusage / outputusage（我方入账）
```

- 实测命中：11-02 当天 `token_used_aw.routeattemptid` ∩ `routing_ledger.routeattemptid` = **118,406 / 118,406 = 100%**；网关 `request_id` ∩ `upstreamrequestid` = **119,069 / 119,176 = 99.91%**。
- **全窗结论（T082，2026-11-09 定案）**：590,861 条三方齐全请求，**input / output 逐条 100.00% 完全相等**（网关 = RL.raw = TU 入账），我方账本无少记。
- ❌ 已作废结论（别再复用）：「供应商多计 luna 输出」「我方 output 少记 22.9% / 每请求只记 72%，要查 imt-api 落库」。

## 已知坑

- **聚合对比会造出假差异**：网关日志含 `finish_reason='length'` 打满 max_tokens 上限（128000 / 65536）的虚高幽灵行（HTTP 200 / is_success=true，但我方系统里根本不存在）。2026-11 全窗 **261 条（0.044% 请求）解释 94.5% 的双方 output 差异**；铁证是我方 UCloud 专线 / RL / TU 全窗 output 最大仅 23,086、≥10 万的行 = 0。**汇总对比前必须先逐条 JOIN 或剔除大值**。详见 pitfalls **P049**。
- **5,733 条「连上 RL 但没进账本」**：`openai/gpt-5-mini` 探测类、RL 原始用量为 0，completion 合计仅 0.0054 亿，可忽略。
- **8 月不能套用**：本表不含 8 月；8 月账单异常（`gpt-5.6-luna` output 账单 92.39 亿 vs 库内 30.66 亿，3.01 倍）是**全月连续的约 3 倍**、不是离散幽灵行，机制未证实，需供应商补 8 月逐请求日志。

## 样例核对（可选）

```sql
-- 单日 UCloud 一路：查看桥接键与原始用量
SELECT upstreamrequestid, routeattemptid, traceid,
       actualupstreamresourceid, rawinputusage, rawoutputusage,
       outcome, usagestate, requestidstate, startedat
FROM immdata.routing_ledger
WHERE providername = 'UCloud'
  AND startedat >= '2026-11-02 00:00:00' AND startedat < '2026-11-03 00:00:00'
LIMIT 20;

-- 逐条 1:1 对账骨架（网关 request_id 集合在 Python/polars 侧准备）
-- 网关.request_id = RL.upstreamrequestid → RL.routeattemptid = TU.routeattemptid
```

## 维护

- 本文件于 **2026-11-09 手工补录**（T082 首次使用该表）。`AUTO:SCHEMA` 段取自当日 `information_schema.columns`，格式与 `sync_table_catalog.py` 一致。
- ⚠️ **暂勿直接跑 `python scripts/sync_table_catalog.py`**：当前只读账号下 `information_schema.tables` 只返回 **80** 张表，而 `INDEX.md` 收录 **111** 张，直接刷新会把历史索引缩水。需先确认账号权限/视图完整性再刷新。
- 相关：pitfalls **P049**、[`OVERVIEW.md`](../OVERVIEW.md)、[`token_used_aw.md`](token_used_aw.md)、T082 交付 `output/route_join_recon_20261102_20261106.xlsx`。
