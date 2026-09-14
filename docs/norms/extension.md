# 插件代码查阅（埋点 / 墙 / 实验）

查数时若 **事件名、trigger、软硬墙、实验分组、上线时间** 在库表里对不上或说不清，到 **沉浸式翻译插件仓库** 核对，不要猜。

## 仓库

- 本地路径：`F:\extension`（本机插件工程，**不是** `databend_sql`）
- **每次查阅前必须 `git pull`**（在该目录），再搜索代码，避免用过期埋点。
- 本仓只读查数账号；**不要改插件代码**，只读。

## 何时必须查

- 付费墙 / 注册墙 / 限额弹窗的 `event_name` + `trigger`
- `ab_tag` / 实验组与产品策略的对应
- 配置开关何时取消软墙、阈值变更（可对 git log / 注释日期）
- 用户说「以前叫软硬墙」但 behaviour 里事件已消失

## 怎么查（建议）

1. `cd F:\extension` → `git pull`
2. 搜：`user_need_pro`、`freeUsageLimitModal`、`unregisteredUsageLimitModal`、`usage_limit_soft`、`usage_limit_hard`、`ab_tag`
3. 把 **确认的事件+trigger** 写进当次 `docs/tasks/`，需要跨任务复用再补表文档「勿想当然」

## 红线

- 未 pull 就当现网口径
- 把插件里的内部函数名当成 `user_behaviour.event_name`
- 把查阅笔记只留在聊天、不进任务文档
