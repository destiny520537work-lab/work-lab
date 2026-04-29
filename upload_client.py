"""
交易信号上传客户端
模拟量化系统每天开盘前自动读取信号文件并上传到券商

运行：python upload_client.py
"""

import csv
import requests
import time
import logging
import json
from datetime import datetime
from pathlib import Path

# ── 日志配置：同时输出到终端 + 写入文件 ───────────────────
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
log_filename = LOG_DIR / f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),                      # 终端输出
        logging.FileHandler(log_filename, encoding="utf-8")  # 文件输出
    ]
)
logger = logging.getLogger(__name__)

# ── 结果记录（写入JSON汇总文件）────────────────────────────
RESULT_FILE = LOG_DIR / f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
upload_results = []   # 收集每条信号的处理结果

# ── 配置 ──────────────────────────────────────────────────
BROKER_URL = "http://localhost:8000"
SIGNAL_FILE = "signals.csv"
MAX_RETRIES = 3
BACKOFF_BASE = 2   # 指数退避基数（秒）


# ── 核心函数：带指数退避的上传 ───────────────────────────
def upload_signal(signal_data: dict) -> dict:
    """
    上传单条信号，失败时自动重试（指数退避）
    指数退避：第1次失败等2s，第2次等4s，第3次等8s
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"  上传 {signal_data['signal_id']} ... (第{attempt}次尝试)")

            response = requests.post(
                f"{BROKER_URL}/api/v1/signals/upload",
                json=signal_data,
                timeout=5
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            if status == 503 and attempt < MAX_RETRIES:
                wait = BACKOFF_BASE ** attempt
                logger.warning(f"  ⚠️  券商暂时不可用，{wait}秒后重试...")
                time.sleep(wait)
            else:
                logger.error(f"  ❌ HTTP错误 {status}: {e.response.text}")
                raise

        except requests.exceptions.Timeout:
            logger.error(f"  ❌ 请求超时（第{attempt}次）")
            if attempt == MAX_RETRIES:
                raise

        except requests.exceptions.ConnectionError:
            logger.error("  ❌ 无法连接到券商服务器，请确认服务已启动")
            raise

    raise Exception(f"信号上传失败，已重试{MAX_RETRIES}次")


# ── 读取CSV并批量上传 ──────────────────────────────────────
def process_signal_file(filepath: str):
    logger.info(f"📂 读取信号文件: {filepath}")
    logger.info("=" * 50)

    success, duplicate, failed = 0, 0, 0

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            signal_data = {
                "signal_id":  row["signal_id"],
                "stock_code": row["stock_code"],
                "direction":  row["direction"],
                "action":     row["action"],
                "volume":     int(row["volume"]),
                "price":      float(row["price"]),
                "trade_date": row["date"],
                "trade_time": row["time"]
            }

            try:
                result = upload_signal(signal_data)
                status = result.get("status")

                if status == "accepted":
                    logger.info(f"  ✅ 成功 | 订单号: {result['order_id']}")
                    success += 1
                    upload_results.append({
                        "signal_id": row["signal_id"],
                        "status": "accepted",
                        "order_id": result["order_id"],
                        "timestamp": datetime.now().isoformat()
                    })
                elif status == "duplicate":
                    logger.warning(f"  ♻️  重复信号，已忽略: {row['signal_id']}")
                    duplicate += 1
                    upload_results.append({
                        "signal_id": row["signal_id"],
                        "status": "duplicate",
                        "timestamp": datetime.now().isoformat()
                    })

            except Exception as e:
                logger.error(f"  ❌ 失败: {e}")
                failed += 1
                upload_results.append({
                    "signal_id": row["signal_id"],
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })

    # ── 打印汇总 ──────────────────────────────────────────
    logger.info("=" * 50)
    logger.info(f"📊 上传完成: ✅成功 {success}  ♻️重复 {duplicate}  ❌失败 {failed}")

    # ── 写入JSON结果文件 ───────────────────────────────────
    summary = {
        "run_time": datetime.now().isoformat(),
        "signal_file": filepath,
        "summary": {"success": success, "duplicate": duplicate, "failed": failed},
        "details": upload_results
    }
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    logger.info(f"📁 结果已保存: {RESULT_FILE}")
    logger.info(f"📁 日志已保存: {log_filename}")


# ── 查询账户状态 ───────────────────────────────────────────
def check_account_status():
    logger.info("\n📈 查询账户当日状态...")
    response = requests.get(f"{BROKER_URL}/api/v1/account/status", timeout=5)
    data = response.json()

    print(f"\n账户ID: {data['account_id']}")
    print(f"总资产: ¥{data['total_assets']:,.2f}")
    print(f"可用现金: ¥{data['available_cash']:,.2f}")
    print(f"今日盈亏: ¥{data['today_pnl']:+,.2f}")
    print("\n持仓:")
    for pos in data["positions"]:
        print(f"  {pos['stock_code']} {pos['name']}: "
              f"{pos['quantity']}股 | "
              f"均价¥{pos['avg_price']} | "
              f"现价¥{pos['current_price']} | "
              f"浮盈¥{pos['unrealized_pnl']:+,.2f}")


# ── 主程序 ────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n🚀 交易信号上传程序启动 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
    print("=" * 50)

    # 1. 上传信号
    process_signal_file(SIGNAL_FILE)

    # 2. 查询账户状态
    check_account_status()
