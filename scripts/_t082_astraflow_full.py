"""T082 AstraFlow 全量请求日志 vs 我方 token_used_aw(UCloud 专线) 对账。

AstraFlow 文件: 597,903 行 (8 个 UTC 日 sheet)，逐请求级别，带 request_id。
时间列为 UTC，对账需换算成北京日与 token_used_aw 的 date_add(hour,8,timestamp) 口径一致。
"""
import sys, time
sys.path.insert(0, "scripts")
import polars as pl
import db

AF = r"C:\Users\86933\Downloads\AstraFlow_model_logs_20261030_084956_to_20261106_084956_exported_20261106_085002.xlsx"
NEED = ["model_name", "apikey_name", "start_time_readable", "prompt_tokens",
        "completion_tokens", "total_tokens", "cache_hit_tokens",
        "cache_creation_tokens", "is_success", "http_status_code",
        "region", "top_organization_id", "organization_id"]
SHEETS = [f"UTC_2026-10-{d}" for d in ("30", "31")] + \
         [f"UTC_2026-11-0{d}" for d in ("1", "2", "3", "4", "5", "6")]


def load_astraflow():
    t = time.time()
    parts = []
    for s in SHEETS:
        d = pl.read_excel(AF, engine="calamine", sheet_name=s, columns=NEED)
        d = d.with_columns(pl.lit(s).alias("__sheet"))
        parts.append(d)
    df = pl.concat(parts, how="vertical_relaxed")
    # 数值列强制转 int
    for c in ["prompt_tokens", "completion_tokens", "total_tokens",
              "cache_hit_tokens", "cache_creation_tokens"]:
        df = df.with_columns(pl.col(c).cast(pl.Int64, strict=False).fill_null(0))
    # UTC -> 北京日
    df = df.with_columns(
        pl.col("start_time_readable").str.to_datetime("%Y-%m-%d %H:%M:%S")
        .dt.replace_time_zone("UTC").dt.convert_time_zone("Asia/Shanghai")
        .dt.date().alias("bj_date"))
    print(f"[load] {df.height} rows in {time.time()-t:.1f}s")
    return df


def af_agg(df):
    g = df.group_by(["bj_date", "model_name"]).agg(
        pl.len().alias("req"),
        pl.col("prompt_tokens").sum().alias("inp"),
        pl.col("completion_tokens").sum().alias("out"),
        pl.col("cache_hit_tokens").sum().alias("cache_hit"),
        pl.col("cache_creation_tokens").sum().alias("cache_creat"),
        (pl.col("is_success").str.to_lowercase() == "true").sum().alias("ok"),
    )
    return g.sort(["bj_date", "model_name"])


def db_agg():
    sql = """
    SELECT to_char(date_add(hour,8,timestamp),'YYYY-MM-DD') bj,
           actualresourceid,
           count(*) n,
           SUM(inputusage) inp, SUM(outputusage) outp
    FROM immdata.token_used_aw
    WHERE providername='UCloud' AND recordtype='capture'
      AND timestamp >= '2026-11-01 16:00:00' AND timestamp < '2026-11-06 16:00:00'
    GROUP BY bj, actualresourceid ORDER BY bj, inp DESC"""
    c, rows = db.query(sql)
    from collections import defaultdict
    d = defaultdict(dict)
    for bj, mid, n, inp, outp in rows:
        d[bj][mid] = (int(n or 0), float(inp or 0), float(outp or 0))
    return d


def main():
    df = load_astraflow()
    af = af_agg(df)
    # 全局按模型
    afm = df.group_by("model_name").agg(
        pl.len().alias("req"),
        pl.col("prompt_tokens").sum().alias("inp"),
        pl.col("completion_tokens").sum().alias("out"),
        pl.col("cache_hit_tokens").sum().alias("cache_hit"),
    ).sort("req", descending=True)
    print("\n=== AstraFlow 全量按模型 (input=prompt, output=completion) ===")
    print(afm)

    # 我方 DB
    dbd = db_agg()
    print("\n=== 我方 token_used_aw UCloud 专线 按北京日×模型 ===")
    models = sorted({m for b in dbd for m in dbd[b]})
    print(f"{'北京日':12s}" + "".join(f"{m:>16s}" for m in models))
    for bj in sorted(dbd):
        line = f"{bj:12s}"
        for m in models:
            n, i, o = dbd[bj].get(m, (0, 0, 0))
            line += f"{i/1e6:>8.1f}M(n={n})".rjust(16)
        print(line)

    # 逐日×模型 对比 (input)
    print("\n=== 逐北京日 × 模型 input 对比 (亿 token, AstraFlow vs 我方) ===")
    print(f"{'北京日':11s} {'模型':14s} {'AF_in':>11s} {'DB_in':>11s} {'差%':>7s} | {'AF_out':>11s} {'DB_out':>11s} {'差%':>7s} | AF_req DB_n")
    # 构建 AF dict
    afd = {}
    for r in af.sort("bj_date", "model_name").iter_rows(named=True):
        afd[(str(r["bj_date"]), r["model_name"])] = r
    cmp_daily = []
    all_keys = set(afd) | {(bj, m) for bj in dbd for m in dbd[bj]}
    for key in sorted(all_keys):
        bj, m = key
        a = afd.get(key)
        d = dbd.get(bj, {}).get(m)
        ai = a["inp"] if a else 0
        ao = a["out"] if a else 0
        areq = a["req"] if a else 0
        di = d[1] if d else 0
        do = d[2] if d else 0
        dn = d[0] if d else 0
        if ai == 0 and di == 0:
            continue
        ind = (di - ai) / ai * 100 if ai else None
        outd = (do - ao) / ao * 100 if ao else None
        cmp_daily.append([bj, m, ai, di, round(ind, 1) if ind is not None else None,
                          ao, do, round(outd, 1) if outd is not None else None, areq, dn])

    # 窗口总计 按模型
    win_models = sorted({m for bj, m in all_keys})
    cmp_total = []
    for m in win_models:
        ai = sum(afd[(bj, mm)]["inp"] for (bj, mm) in afd if mm == m)
        ao = sum(afd[(bj, mm)]["out"] for (bj, mm) in afd if mm == m)
        areq = sum(afd[(bj, mm)]["req"] for (bj, mm) in afd if mm == m)
        di = sum(dbd[bj][m][1] for bj in dbd if m in dbd[bj])
        do = sum(dbd[bj][m][2] for bj in dbd if m in dbd[bj])
        dn = sum(dbd[bj][m][0] for bj in dbd if m in dbd[bj])
        if ai == 0 and di == 0:
            continue
        ind = (di - ai) / ai * 100 if ai else None
        outd = (do - ao) / ao * 100 if ao else None
        cmp_total.append([m, ai, di, round(ind, 1) if ind is not None else None,
                          ao, do, round(outd, 1) if outd is not None else None, areq, dn])

    # 平均每请求 token (luna 专项)
    print("\n=== gpt-6-luna 平均每请求 token ===")
    for label, rows_src in [("AstraFlow", afd), ("我方DB", None)]:
        pass
    af_luna = afd.get(("2026-11-03", "gpt-6-luna"))  # representative stable day not needed; use totals
    # use window totals for luna
    def _tot(prefix):
        ti = sum(afd[(bj, "gpt-6-luna")]["inp"] for (bj, mm) in afd if mm == "gpt-6-luna") if prefix == "af" else \
             sum(dbd[bj]["gpt-6-luna"][1] for bj in dbd if "gpt-6-luna" in dbd[bj])
        to = sum(afd[(bj, "gpt-6-luna")]["out"] for (bj, mm) in afd if mm == "gpt-6-luna") if prefix == "af" else \
             sum(dbd[bj]["gpt-6-luna"][2] for bj in dbd if "gpt-6-luna" in dbd[bj])
        tn = sum(afd[(bj, "gpt-6-luna")]["req"] for (bj, mm) in afd if mm == "gpt-6-luna") if prefix == "af" else \
             sum(dbd[bj]["gpt-6-luna"][0] for bj in dbd if "gpt-6-luna" in dbd[bj])
        return ti, to, tn
    ti_af, to_af, tn_af = _tot("af")
    ti_db, to_db, tn_db = _tot("db")
    print(f"  输入/请求:  AF={ti_af/tn_af:.0f}  DB={ti_db/tn_db:.0f}")
    print(f"  输出/请求:  AF={to_af/tn_af:.0f}  DB={to_db/tn_db:.0f}")
    print(f"  (我方输出/请求 仅为网关的 {to_db/tn_db/(to_af/tn_af)*100:.0f}%)")

    # 导出 xlsx
    import pandas as pd
    out = "output/astraflow_vs_db_20261030_20261106.xlsx"
    dbrows = [(bj, m, dbd[bj][m][0], dbd[bj][m][1], dbd[bj][m][2])
              for bj in dbd for m in dbd[bj]]
    note = pd.DataFrame({
        "结论": [
            "数据源: AstraFlow = UCloud 推理网关逐请求日志(org 66837208, apikey=aw-测试, 597,903 行); 我方 = immdata.token_used_aw(UCloud 专线).",
            "时间口径: AstraFlow start_time(UTC)+8h = 北京日, 与 token_used_aw date_add(hour,8,timestamp) 一致.",
            "INPUT 对得上: gpt-6-luna 在 11-03~11-06 稳定日, 我方 inputusage 与网关 prompt_tokens 差 ≤4%(窗口+6.3%).",
            "OUTPUT 系统性偏低: gpt-6-luna 我方 outputusage 比网关 completion_tokens 低 12~29%(窗口 -22.9%).",
            "请求数基本对上: gpt-6-luna 窗口 AF 595,750 vs DB 636,611(+7%); 稳定日逐日差 ≤4%.",
            "平均每请求: 输入 AF=460/DB=458 一致; 输出 AF=179/DB=129 → 我方少记约 28% 的 completion token.",
            "假设(P043): 我方 output 记录偏低, 疑似 imt-api 对 completion_tokens 少记/漏记(非缺失请求). 需查 imt-api 落库逻辑证实.",
            "kimi/qwen: 量极小(各<0.02亿), 我方捕捉到网关约一半, 绝对量可忽略; qwen 网关 out>>in 属异常样本.",
            "request_id: 我方账本只存 imt-api 自生成的 businessid/traceid/routeattemptid, 不存 UCloud 网关 UUID, 无法逐条 1:1 关联, 只能聚合级对账.",
            "10-31/11-01 及 11-07 的 -100% 行因我方查询窗口(北京 11-02~11-06)未覆盖, 非真实缺口.",
        ]
    })
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        afm.to_pandas().to_excel(w, sheet_name="AstraFlow_全量按模型", index=False)
        af.to_pandas().to_excel(w, sheet_name="AstraFlow_逐日x模型", index=False)
        pd.DataFrame(dbrows, columns=["bj", "model", "n", "inp", "outp"]).to_excel(
            w, sheet_name="DB_UCloud_逐日x模型", index=False)
        pd.DataFrame(cmp_daily, columns=["bj", "model", "AF_in", "DB_in", "in差%",
                                        "AF_out", "DB_out", "out差%", "AF_req", "DB_n"]).to_excel(
            w, sheet_name="对比_逐日x模型", index=False)
        pd.DataFrame(cmp_total, columns=["model", "AF_in", "DB_in", "in差%",
                                         "AF_out", "DB_out", "out差%", "AF_req", "DB_n"]).to_excel(
            w, sheet_name="对比_窗口总计", index=False)
        note.to_excel(w, sheet_name="说明", index=False)
    print("\n[export]", out)


if __name__ == "__main__":
    main()
