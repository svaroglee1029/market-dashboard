# -*- coding: utf-8 -*-
"""
一键更新云端看板数据
用法：python update_cloud.py

功能：
1. 从本地 MySQL 导出最新数据到 SQLite
2. 压缩为 dashboard_data.db.gz
3. git 提交并推送到 GitHub
4. Streamlit Cloud 检测到仓库更新后自动重新构建（约3-5分钟）

前提：本地 MySQL 运行中，git 已配置好远程仓库
"""
import os
import sys
import time
import gzip
import shutil
import sqlite3
import subprocess
import pandas as pd
from sqlalchemy import create_engine, text

# ====================== 配置 ======================
MYSQL_URL = "mysql+mysqlconnector://root:123456@127.0.0.1:3306/test"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "dashboard_data.db")
DB_GZ_PATH = os.path.join(SCRIPT_DIR, "dashboard_data.db.gz")

# 导出的表 + 起始月份（保留2024年起，覆盖默认范围和同比）
TABLES = ["sku", "brand", "brand_distribution_rate", "industry"]
MIN_YM = 202301

# ====================== 步骤1：导出数据 ======================
def export_data():
    print("=" * 50)
    print("[1/4] 从 MySQL 导出数据到 SQLite ...")
    print("=" * 50)
    engine = create_engine(MYSQL_URL, pool_recycle=1800, pool_pre_ping=True, echo=False)

    # 删除旧 db，全新导出
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"  已删除旧文件: {os.path.basename(DB_PATH)}")

    conn = sqlite3.connect(DB_PATH)
    total = 0
    for t in TABLES:
        t0 = time.time()
        print(f"  [{t}] 读取 MySQL (year_month>={MIN_YM}) ...", end="", flush=True)
        df = pd.read_sql(text(f"SELECT * FROM `{t}` WHERE `year_month` >= {MIN_YM};"), con=engine)
        df.to_sql(t, conn, if_exists="replace", index=False)
        conn.commit()
        # 建索引
        try:
            conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{t}_ym ON `{t}`(year_month)")
            conn.commit()
        except Exception:
            pass
        cost = time.time() - t0
        print(f" {len(df)} 行 ({cost:.1f}s)")
        total += len(df)
    conn.close()

    # VACUUM 压缩
    print("  VACUUM 压缩中 ...", end="", flush=True)
    vc = sqlite3.connect(DB_PATH)
    vc.execute("VACUUM")
    vc.close()
    db_mb = os.path.getsize(DB_PATH) / 1024 / 1024
    print(f" 完成 ({db_mb:.1f}MB)")
    print(f"  合计 {total} 行")
    return total

# ====================== 步骤2：gzip压缩 ======================
def gzip_db():
    print("\n" + "=" * 50)
    print("[2/4] 压缩为 gzip ...")
    print("=" * 50)
    with open(DB_PATH, "rb") as f_in, gzip.open(DB_GZ_PATH, "wb", compresslevel=9) as f_out:
        shutil.copyfileobj(f_in, f_out)
    gz_mb = os.path.getsize(DB_GZ_PATH) / 1024 / 1024
    print(f"  {os.path.basename(DB_GZ_PATH)} = {gz_mb:.1f}MB")
    if gz_mb > 100:
        print(f"  ⚠️ 警告：文件超过 GitHub 100MB 限制 ({gz_mb:.1f}MB)！")
        print(f"  建议：增大 MIN_YM 或减少导出的表")
        return False
    return True

# ====================== 步骤3：git提交 ======================
def git_commit():
    print("\n" + "=" * 50)
    print("[3/4] git 提交 ...")
    print("=" * 50)
    cmds = [
        ["git", "add", "dashboard_data.db.gz"],
        ["git", "commit", "-m", f"chore: 更新数据快照 {time.strftime('%Y-%m-%d %H:%M')}"],
    ]
    for c in cmds:
        r = subprocess.run(c, capture_output=True, text=True, cwd=SCRIPT_DIR)
        if r.stdout.strip():
            print(f"  {r.stdout.strip()}")
        if r.returncode != 0 and "nothing to commit" not in r.stdout and "no changes" not in r.stdout:
            # commit 无变更不算错
            if c[1] == "commit" and "nothing to commit" in (r.stdout + r.stderr):
                print("  无数据变更，跳过推送")
                return False
    return True

# ====================== 步骤4：git推送 ======================
def git_push():
    print("\n" + "=" * 50)
    print("[4/4] 推送到 GitHub ...")
    print("=" * 50)
    # 走系统代理（国内直连github常被阻断）
    env = os.environ.copy()
    env["HTTPS_PROXY"] = "http://127.0.0.1:7897"
    env["HTTP_PROXY"] = "http://127.0.0.1:7897"
    # GitHub 网络偶发不稳定，重试3次
    for i in range(3):
        r = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True, cwd=SCRIPT_DIR, env=env)
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
        if not gzip_db():
            return
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
