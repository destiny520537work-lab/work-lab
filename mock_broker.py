"""
模拟券商接口服务器
真实券商（如华泰、中信）的REST API格式基本类似这个结构
运行：python mock_broker.py
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, validator
import uuid
import random
import uvicorn

app = FastAPI(title="Mock Broker API", version="1.0")

# 内存存储（模拟券商已接收的信号）
received_signals: dict = {}

# ── 数据模型 ──────────────────────────────────────────────
class TradeSignal(BaseModel):
    signal_id: str          # 唯一ID，用于幂等性校验
    stock_code: str         # 股票代码，如 000001.SZ
    direction: str          # BUY / SELL
    action: str             # OPEN（开仓）/ CLOSE（平仓）
    volume: int             # 数量（股）
    price: float            # 0 = 市价单
    trade_date: str
    trade_time: str

    @validator("direction")
    def check_direction(cls, v):
        if v not in ["BUY", "SELL"]:
            raise ValueError("direction must be BUY or SELL")
        return v

    @validator("volume")
    def check_volume(cls, v):
        if v <= 0:
            raise ValueError("volume must be positive")
        if v % 100 != 0:
            raise ValueError("A股最小交易单位是100股（1手）")
        return v


# ── 接口一：上传交易信号 ──────────────────────────────────
@app.post("/api/v1/signals/upload")
async def upload_signal(signal: TradeSignal):
    """
    券商接收交易信号的核心接口
    返回：accepted / duplicate / rejected
    """
    # 1. 幂等性检查（同一个signal_id不重复执行）
    if signal.signal_id in received_signals:
        return {
            "status": "duplicate",
            "signal_id": signal.signal_id,
            "message": "该信号已处理，忽略重复提交"
        }

    # 2. 模拟10%概率的券商临时不可用（真实世界常见！）
    if random.random() < 0.1:
        raise HTTPException(
            status_code=503,
            detail="Broker temporarily unavailable - please retry"
        )

    # 3. 存储并返回订单号
    received_signals[signal.signal_id] = signal.dict()
    order_id = f"ORD_{uuid.uuid4().hex[:8].upper()}"

    return {
        "status": "accepted",
        "signal_id": signal.signal_id,
        "order_id": order_id,
        "message": f"信号已接收，订单号：{order_id}"
    }


# ── 接口二：查询账户当日状态 ──────────────────────────────
@app.get("/api/v1/account/status")
async def account_status():
    """查询账户持仓和当日盈亏"""
    return {
        "account_id": "DEMO_001",
        "total_assets": 1_000_000.00,
        "available_cash": 500_000.00,
        "today_pnl": 3200.50,
        "positions": [
            {
                "stock_code": "000001.SZ",
                "name": "平安银行",
                "quantity": 1000,
                "avg_price": 15.50,
                "current_price": 15.80,
                "unrealized_pnl": 300.00
            },
            {
                "stock_code": "600519.SH",
                "name": "贵州茅台",
                "quantity": 200,
                "avg_price": 1780.00,
                "current_price": 1800.00,
                "unrealized_pnl": 4000.00
            }
        ]
    }


# ── 接口三：查看已接收的所有信号 ────────────────────────
@app.get("/api/v1/signals/received")
async def get_received_signals():
    return {
        "count": len(received_signals),
        "signals": received_signals
    }


if __name__ == "__main__":
    print("✅ 模拟券商服务器启动中...")
    print("📄 API文档：http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
