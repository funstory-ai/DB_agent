-- 用途：连通性与当前库冒烟（只读）
-- 主表：无
-- 已知坑：无

SELECT
    current_database() AS db,
    1 AS ok;
