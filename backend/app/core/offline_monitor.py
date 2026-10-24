"""
心跳离线检测：定期扫描 NORMAL 状态的客户端，超过 N 倍心跳间隔未上报的标记为 ABNORMAL。

- 后台协程随应用启动/停止（main.py lifespan），扫描在线程池中执行以避免阻塞事件循环
- 仅做 NORMAL → ABNORMAL 的单向标记，不触碰管理员封禁的 DISABLED 客户端
- ABNORMAL 客户端重新激活即恢复 NORMAL（激活接口已有该逻辑）
"""
import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.client import Client, ClientStatus
from app.models.product import Product

logger = logging.getLogger("hex-auth.offline")

# 产品未配置心跳间隔时的兜底值（与模型默认一致）
_DEFAULT_INTERVAL = 3600


def mark_offline_clients(db: Session) -> int:
    """扫描并标记离线客户端，返回本次标记数量。session 由调用方提供（便于测试）。"""
    # 与 last_heartbeat 的写入口径一致（容器 TZ=Asia/Shanghai，见 compose）
    now = datetime.now()
    thresholds = {
        code: timedelta(seconds=(interval or _DEFAULT_INTERVAL) * settings.CLIENT_OFFLINE_MULTIPLIER)
        for code, interval in db.query(Product.product_code, Product.heartbeat_interval).all()
    }

    marked = 0
    clients = db.query(Client).filter(
        Client.status == ClientStatus.NORMAL,
        Client.last_heartbeat.isnot(None),
    ).all()
    for client in clients:
        threshold = thresholds.get(client.product_code)
        if threshold and (now - client.last_heartbeat) > threshold:
            client.status = ClientStatus.ABNORMAL
            marked += 1

    if marked:
        db.commit()
    return marked


async def offline_monitor_loop():
    """常驻后台任务：按配置周期执行离线扫描。"""
    while True:
        try:
            db = SessionLocal()
            try:
                count = await asyncio.to_thread(mark_offline_clients, db)
                if count:
                    logger.info("已标记 %d 个客户端离线", count)
            finally:
                db.close()
        except Exception:
            logger.exception("离线检测任务执行失败")
        await asyncio.sleep(settings.CLIENT_OFFLINE_CHECK_SECONDS)
