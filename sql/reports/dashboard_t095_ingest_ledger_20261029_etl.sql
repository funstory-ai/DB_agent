-- T095  新账本（计费 v2.4 / 路由 v1.1）入湖 ETL 草案
-- 大类：dashboard（涉及写仓建表 + 中间层 + 每日调度）
-- 目标：把对象存储里的 parquet 账本接进 immdata，供 UCloud 账单逐单对账
--
-- 执行者：写仓同学。本仓只读账号不代跑（onboarding 规定）。
-- 使用方式：§1 PoC 必做；§2 及之后的列序/类型须以 §1.3 的 infer_schema
--           实测结果校准一次，再正式建表。未跑 PoC 直接执行 §2 有风险。
--
-- 数据源（Oracle Cloud Object Storage，S3 兼容）：
--   bucket    billing-ledger
--   endpoint  https://ax9rsosmvaht.compat.objectstorage.ap-seoul-1.oraclecloud.com
--   region    ap-seoul-1
--   生产前缀  imt-prod/billing-ledger/{temp|hourly|daily}/{yyyy}/{mm}/{dd}/
--             imt-prod/routing-ledger/raw/{yyyy}/{mm}/{dd}/{hh}/
--   测试前缀  imt-test/…
--
-- 已实测（2026-10-29）：
--   · 生产 imt-prod/routing-ledger/raw 于 2026-10-29 开始写 v1.1 文件
--   · imt-prod/billing-ledger 在 10-29 出现 v2.1 与 v2.4 并存（10-28 及之前全为 v2.1）


-- ============================================================================
-- §0  前置核查（只读，本仓账号可跑）
-- ============================================================================

-- 0.1 现有 stage（已确认：仅 3 个，无任何指向 billing-ledger 的 stage）
SHOW STAGES;

-- 0.2 确认目标表尚未存在
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'immdata'
  AND table_name IN ('imt_billing_ledger', 'imt_routing_ledger');


-- ============================================================================
-- §1  PoC（写仓同学执行）—— 先证明"能读"，再谈建表
-- ============================================================================
-- 三个目的：
--   a) 验证"阿里云北京实例 → OCI 首尔"跨境连通且带宽可接受（本项目最大未知数）
--   b) 用 infer_schema 拿到 parquet 真实列名与类型，作为 §2 DDL 的唯一校准依据
--   c) 测出单个/单日文件的 COPY 耗时，据此判断每日全量是否可行
--
-- 背景风险：本仓分析机（本机）访问同一 OCI 端点时极慢，单个 get_object 多次
-- 卡顿超过 10 分钟，抽样扫描 40 个文件未完成。虽然分析机在办公网、不代表
-- Databend 实例的网络条件，但仍应先用 §1 实测，确认耗时可接受再上 TASK。

-- 1.1 建外部 stage（AK/SK 为占位，须替换为向开发申请的生产只读凭据）
--     ENABLE_VIRTUAL_HOST_STYLE = FALSE 是关键：OCI 只支持 path-style 寻址，
--     若按默认 virtual-host 风格请求，会出现签名不匹配 / 403。
CREATE STAGE IF NOT EXISTS billing_ledger_stage
  URL = 's3://billing-ledger/imt-prod/'
  CONNECTION = (
    ENDPOINT_URL              = 'https://ax9rsosmvaht.compat.objectstorage.ap-seoul-1.oraclecloud.com',
    ACCESS_KEY_ID             = '<向开发要：生产只读 AK>',
    SECRET_ACCESS_KEY         = '<向开发要：生产只读 SK>',
    REGION                    = 'ap-seoul-1',
    ENABLE_VIRTUAL_HOST_STYLE = FALSE
  );

-- 1.2 连通性自检：列一天的对象。几十秒内有结果 = 认证与网络均 OK
LIST @billing_ledger_stage/routing-ledger/raw/2026/10/29/;

-- 1.3 取真实 schema —— 这两条的输出就是 §2 DDL 的校准依据
SELECT * FROM infer_schema(location => '@billing_ledger_stage/routing-ledger/raw/2026/10/29/00/');
SELECT * FROM infer_schema(location => '@billing_ledger_stage/billing-ledger/daily/2026/10/29/');

-- 1.4 单文件读通 + 计时
SELECT count(*) FROM @billing_ledger_stage/routing-ledger/raw/2026/10/29/00/;


-- ============================================================================
-- §2  正式建表
-- ============================================================================
-- 列清单依据《账本变更说明》（后端出具，2026-10-19）：
--   计费账本 v2.4 = 27 列，前 19 列与 immdata.token_used_aw 完全一致（可复用现有口径）
--   路由账本 v1.1 = 35 列（v1.0 为 34 列，缺最后 RawUsageJson）
-- 正式执行前请用 §1.3 的 infer_schema 结果核一遍列序与类型。

-- 2.1 路由账本：一行 = 一次实际发给上游的 HTTP 请求
CREATE TABLE IF NOT EXISTS immdata.imt_routing_ledger (
  -- 关联与身份
  trace_id                     varchar,   -- 请求级 id，与计费账本同名字段同源
  auto_operation_id            varchar,   -- 可空，自动翻译一次操作的 id
  route_invocation_id          varchar,
  node_execution_id            varchar,
  route_attempt_id             varchar,   -- 本表行主键，计费账本指向它
  attempt_index                int,       -- 同一 trace 内的发送序号，从 1 起
  transport_attempt_index      int,
  route_system                 varchar,   -- llm_router / qwen_direct / babelfast / runpod_gemma / deepl
  user_id                      bigint,
  tenant_id                    varchar,
  -- 请求了什么、发给了谁
  requested_resource_id        varchar,
  actual_upstream_resource_id  varchar,   -- 实际发给上游的模型 id
  provider_name                varchar,   -- 筛 'UCloud' 用此列
  route_name                   varchar,
  category_name                varchar,
  product_line                 varchar,
  is_stream                    boolean,
  -- 时间与结果
  started_at                   timestamp, -- UTC，分区的"时"按此字段
  completed_at                 timestamp,
  duration_ms                  bigint,
  outcome                      varchar,   -- success/upstream_error/transport_error/parse_error/cancelled/disposed
  http_status_code             int,       -- 可空
  error_kind                   varchar,
  -- 上游报告的原始用量（非计费用量，勿与计费混用）
  raw_input_usage              bigint,
  raw_cached_input_usage       bigint,
  raw_output_usage             bigint,
  raw_character_usage          bigint,    -- 仅 DeepL
  usage_state                  varchar,   -- complete / partial / unavailable / parse_failed
  -- 上游请求 id —— UCloud 对账的 join 键在这一组
  upstream_request_id          varchar,   -- 首选上游 id（UCloud OpenAI 协议取 x-request-id）
  upstream_request_id_source   varchar,
  upstream_request_ids         varchar,   -- JSON：按来源记录的所有捕获到的 id
  upstream_response_id         varchar,
  request_id_state             varchar,   -- captured / conflict / absent / no_response / pending_contract
  route_reason                 varchar,
  -- v1.1 新增（第 35 列）：上游 usage 原文 JSON
  raw_usage_json               varchar,   -- v1.0 文件加载后此列为 NULL
  -- 元信息
  _src_file                    varchar    -- 来源对象路径，便于回溯与排重
);

-- 2.2 计费账本 v2.4（27 列）
CREATE TABLE IF NOT EXISTS immdata.imt_billing_ledger (
  -- ↓ 前 19 列与 token_used_aw 同名同义
  userid                       bigint,
  tenantid                     bigint,
  providername                 varchar,
  productline                  varchar,
  categoryname                 varchar,
  resourcename                 varchar,
  actualresourceid             varchar,
  inputusage                   bigint,
  cachedinputusage             bigint,
  outputusage                  bigint,
  delta                        bigint,
  usageunit                    varchar,
  timestamp                    timestamp,
  recordtype                   varchar,
  businessid                   varchar,
  actionid                     varchar,
  countername                  varchar,
  counterperiod                varchar,
  clientip                     varchar,
  -- ↓ v2.4 追加 8 列（第 20–27 列）
  requestedresourceid          varchar,
  requestedcredit              bigint,
  chargedcredit                bigint,
  giveawaycredit               bigint,
  creditpoolallocations        varchar,
  grantedcredit                bigint,
  trace_id                     varchar,   -- 关联键：计费 ↔ 路由
  route_attempt_id             varchar,   -- 关联键：计费 → 路由（多对一）
  _src_file                    varchar
);


-- ============================================================================
-- §3  增量加载
-- ============================================================================
-- ★★★ 三个必守的坑 ★★★
--
-- 坑 1（阻塞级，需开发先修）：聚合层丢失关联键。
--   实测 2026-10-22 同一批数据：temp 原始文件 trace_id / route_attempt_id = 2/2 有值；
--   同天 hourly 聚合 60 行，两个关联键却全为 0。
--   即 hourly/daily 聚合把关联键剥掉了 —— 修复前 billing 的聚合层接进来也
--   join 不到路由账本，属于"接入了也用不了"的阻塞项。
--
-- 坑 2（缺列容忍）：同一天内可能 v2.1(19 列) 与 v2.4(27 列) 并存，
--   路由账本也可能 v1.0(34 列) 与 v1.1(35 列) 并存。用列数较少的文件加载
--   列数较多的表时，必须显式容忍缺列，否则加载报错。
--   处理方式见下方 FILE_FORMAT 的 MISSING_FIELD_AS。
--
-- 坑 3（文件去重 vs 覆盖重跑）：Databend 按已加载文件清单自动跳重，
--   但《账本变更说明》明确"聚合重跑会用同名对象覆盖"。文件被覆盖重写后，
--   同名对象不会被重新加载，数据修正不会生效。
--   对策：约定 T+1 整天加载一次；若已知某天被重跑，需显式 FORCE 重载。

-- 3.1 路由账本
--     PATTERN 用正则把 v1.0 / v1.1 一起纳入，不要写死 -v1.1.parquet
--     （写死会静默漏掉新版本，与变更说明"版本号当可变段"同一道理）
COPY INTO immdata.imt_routing_ledger
FROM (
  SELECT *, metadata$filename
  FROM @billing_ledger_stage/routing-ledger/raw/2026/10/29/
)
PATTERN = '.*-v1\\.[0-9]+\\.parquet'
FILE_FORMAT = (TYPE = PARQUET, MISSING_FIELD_AS = NULL);

-- 3.2 计费账本（daily 层，一天一个对象，跨境拉取最省）
COPY INTO immdata.imt_billing_ledger
FROM (
  SELECT *, metadata$filename
  FROM @billing_ledger_stage/billing-ledger/daily/2026/10/29/
)
PATTERN = 'billing-ledger-v[0-9]+\\.[0-9]+\\.parquet'
FILE_FORMAT = (TYPE = PARQUET, MISSING_FIELD_AS = NULL);


-- ============================================================================
-- §4  每日调度（PoC 跑通、确认单日耗时可接受后再建）
-- ============================================================================
-- 说明：实测 token_used_aw 的同步截止点为 UTC 上一天 23:59:59，账本也可能迟到，
-- 因此建议 T+1 凌晨执行，并配套"当日行数为 0"的告警。
--
-- CREATE TASK IF NOT EXISTS t_ingest_routing_ledger_daily
--   SCHEDULE = 'USING CRON 0 3 * * * Asia/Shanghai'
--   AS COPY INTO immdata.imt_routing_ledger
--      FROM (SELECT *, metadata$filename FROM @billing_ledger_stage/routing-ledger/raw/<昨日分区>/)
--      PATTERN = '.*-v1\\.[0-9]+\\.parquet'
--      FILE_FORMAT = (TYPE = PARQUET, MISSING_FIELD_AS = NULL);
--
-- ALTER TASK t_ingest_routing_ledger_daily RESUME;


-- ============================================================================
-- §5  验收
-- ============================================================================

-- 5.1 行数与来源版本分布（看有没有某一版被漏吃）
SELECT substr(_src_file, 1, 90) AS src, count(*) AS n
FROM immdata.imt_routing_ledger
GROUP BY 1 ORDER BY 2 DESC LIMIT 20;

-- 5.2 关联键完整性（坑 1 的验收：has_trace / has_attempt 不应为 0）
SELECT count(*) AS rows_all,
       count(trace_id) AS has_trace,
       count(route_attempt_id) AS has_attempt
FROM immdata.imt_billing_ledger
WHERE _src_file LIKE '%daily%';

-- 5.3 对账可用性：UCloud 各模型的 request_id 捕获状态（真正能 join 的是 captured）
SELECT r.actual_upstream_resource_id,
       r.request_id_state,
       count(*) AS n
FROM immdata.imt_routing_ledger r
WHERE r.provider_name = 'UCloud'
GROUP BY 1, 2
ORDER BY 3 DESC;

-- 5.4 逐单 join 样板：计费 → 路由 → 上游 request id
--     注意 outcome 必须过滤 success：失败/重发路由行若捕获了 request id，
--     UCloud 账单里并没有对应的计费项，不滤会造成"我方多、对方少"的假不一致。
SELECT b.recordtype, b.actualresourceid,
       b.inputusage, b.outputusage,
       r.provider_name, r.upstream_request_id, r.request_id_state,
       r.raw_input_usage, r.raw_output_usage, r.started_at
FROM immdata.imt_billing_ledger b
JOIN immdata.imt_routing_ledger r
  ON b.route_attempt_id = r.route_attempt_id
WHERE r.provider_name = 'UCloud'
  AND r.outcome = 'success'
LIMIT 100;


-- ============================================================================
-- 附：接入前必须向开发要 / 确认的 4 件事（缺一不可）
-- ============================================================================
-- A. 生产只读 AK/SK（专用子账号）。
--    不要直接沿用 deploy/Test/appsettings.json 里那对：那是测试凭据，
--    实测却能读取 imt-prod 前缀，本身即属越权，不适合也不能用于生产 ETL。
-- B. 修复 hourly/daily 聚合丢失 trace_id / route_attempt_id 的问题（见坑 1，阻塞级）。
-- C. 给路由账本补一层 daily 聚合。当前只有 raw（一天数百个小文件），
--    跨境异地逐个拉取不可行；《账本变更说明》里也明确邀请提这个需求。
-- D. 确认 UCloud 流量是否还会回来。
--    实测：2026-10-20 起 UCloud 在 immdata.token_used_aw 中骤降
--    （gpt-6-luna 由 10-19 的 90,184 行/天，降至 10-20 之后每天个位数至百余行）。
--    若不再有量，方案即使建成也缺少可对的对象。
