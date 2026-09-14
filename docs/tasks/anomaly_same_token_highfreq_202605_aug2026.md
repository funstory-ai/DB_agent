# 异常：同 token 高频用户 2026-05～08

- **需求编号**: T016
- **规范大类**: `anomaly`
- **状态**: ✅ 已完成
- **日期**: 2026-08-25

- **主表**: `immdata.token_used_aw`（`recordtype='capture'`）
- **Pro 月上限假设**: 2000 万 token（`categoryname='pro-token'`，input+output）
