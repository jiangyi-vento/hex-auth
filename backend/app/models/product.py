from sqlalchemy import Column, Integer, String, Text, DateTime, Enum
from sqlalchemy.sql import func
import enum
from app.core.database import Base

class ProductStatus(str, enum.Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True, comment="主键ID")
    product_code = Column(String(50), unique=True, index=True, nullable=False, comment="产品唯一标识")
    name = Column(String(100), nullable=False, comment="产品名称")
    public_key = Column(String(1000), nullable=False, comment="RSA公钥")
    # 私钥以 enc: 前缀+Fernet 密文存储，长度约为明文的1.4倍，必须用 TEXT（VARCHAR(2000) 会溢出）
    private_key = Column(Text, nullable=False, comment="RSA私钥（Fernet加密）")
    heartbeat_interval = Column(Integer, default=3600, comment="心跳间隔（秒）")
    status = Column(Enum(ProductStatus), default=ProductStatus.ENABLED, comment="产品状态")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")