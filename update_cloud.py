# -*- coding: utf-8 -*-
"""
一键更新云端看板数据
用法：python update_cloud.py

功能：
1. 从本地 MySQL 导出最新数据到 Parquet 文件
2. git 提交并推送到 GitHub
3. Streamlit Cloud 检测到仓库更新后自动重新构建（约3-5分钟）

前提：本地 MySQL 运行中，git 已配置好远程仓库
"""
import os
import sys
import time
import subprocess
import pandas as pd
from sqlalchemy import create_engine, text

# ====================== 配置 ======================
MYSQL_URL = "mysql+mysqlconnector://root:123456@127.0.0.1:3306/test"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

# 导出的表 + 起始月份（保留2021年起，覆盖默认范围和同比）
year = "年份"
TABLES = ["sku", "brand", "brand_distribution_rate", "industry"]
MIN_YM = 2021

# 各表只导出 app.py 实际使用的列（精简数据量约70%）
KEEP_COLS = {
    "sku": ["year_month", "品类", "品牌", "品牌产品", "产品包装", "品名(含属性)",
            "集团权益", "处方性质",
            "销售额('000 RMB)", "销售量-Pack('00))", "加权铺货率"],
    "brand": ["year_month", "品类", "品牌", "品牌产品",
              "销售额('000 RMB)", "销售量-Pack('00))", "加权铺货率"],
    "brand_distribution_rate": ["year_month", "品牌_NEW", "加权铺货率", "销售额('000 RMB)"],
    "industry": ["year_month", "品类", "品牌",
                 "销售额('000 RMB)", "销售量-Pack('00))"],
}

# ====================== 步骤1：导出数据 ======================
def export_data():
    print("=" * 50)
    print("[1/3] 从 MySQL 导出数据到 Parquet ...")
    print("=" * 50)
    engine = create_engine(MYSQL_URL, pool_recycle=1800, pool_pre_ping=True, echo=False)

    # 创建 data 目录
    os.makedirs(DATA_DIR, exist_ok=True)

    total = 0
    for t in TABLES:
        t0 = time.time()
        cols = KEEP_COLS.get(t)
        if cols:
            col_sql = ", ".join(f"`{c}`" for c in cols)
            sql = f"SELECT {col_sql} FROM `{t}` WHERE `year_month` >= {MIN_YM};"
        else:
            sql = f"SELECT * FROM `{t}` WHERE `year_month` >= {MIN_YM};"
        print(f"  [{t}] 读取 MySQL (year_month>={MIN_YM}, {len(cols) if cols else 'all'}列) ...", end="", flush=True)
        df = pd.read_sql(text(sql), con=engine)
        parquet_path = os.path.join(DATA_DIR, f"{t}.parquet")
        df.to_parquet(parquet_path, index=False, engine="pyarrow", compression="snappy")
        cost = time.time() - t0
        size_mb = os.path.getsize(parquet_path) / 1024 / 1024
        print(f" {len(df)} 行 → {size_mb:.1f}MB ({cost:.1f}s)")
        total += len(df)
    print(f"  合计 {total} 行")
    return total

# ====================== 步骤2：git提交 ======================
def git_commit():
    print("\n" + "=" * 50)
    print("[2/3] git 提交 ...")
    print("=" * 50)
    cmds = [
        ["git", "add", "data/"],
        ["git", "commit", "-m", f"chore: 更新数据快照 {time.strftime('%Y-%m-%d %H:%M')}"],
    ]
    for c in cmds:
        r = subprocess.run(c, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=SCRIPT_DIR)
        if r.stdout and r.stdout.strip():
            print(f"  {r.stdout.strip()}")
        if r.returncode != 0 and r.stdout and "nothing to commit" not in r.stdout and "no changes" not in r.stdout:
            if c[1] == "commit" and "nothing to commit" in ((r.stdout or "") + (r.stderr or "")):
                print("  无数据变更，跳过推送")
                return False
    return True

# ====================== 步骤3：git推送 ======================
def git_push():
    print("\n" + "=" * 50)
    print("[3/3] 推送到 GitHub ...")
    print("=" * 50)
    env = os.environ.copy()
    env["HTTPS_PROXY"] = "http://127.0.0.1:7897"
    env["HTTP_PROXY"] = "http://127.0.0.1:7897"
    for i in range(3):
        r = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=SCRIPT_DIR, env=env)
        if r.returncode == 0:
            print("  ✅ 推送成功！")
            print(f"  {r.stdout.strip()}")
            return True
        print(f"  第{i+1}次推送失败: {r.stderr.strip()[:100]}")
        if i < 2:
            print("  等待5秒重试 ...")
            time.sleep(5)
    print("  ❌ 推送失败，请检查网络后重试：python update_cloud.py")
    print(f"  错误: {r.stderr.strip()}")
    return False

# ====================== 主流程 ======================
def main():
    print("╔══════════════════════════════════════════════╗")
    print("║   云端看板数据一键更新工具                   ║")
    print("╚══════════════════════════════════════════════╝")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"目录: {SCRIPT_DIR}")
    print()

    try:
        export_data()
        if not git_commit():
            print("\n✅ 数据已是最新，无需更新云端")
            return
        if not git_push():
            return

        print("\n" + "=" * 50)
        print("🎉 全部完成！")
        print("=" * 50)
        print("  Streamlit Cloud 将自动检测更新并重新构建")
        print("  约 3-5 分钟后看板刷新即可看到新数据")
        print("  看板地址: https://market-dashboard-m5.streamlit.app")
    except Exception as e:
        print(f"\n❌ 出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
