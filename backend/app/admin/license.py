from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
from datetime import date
from app.core.database import get_db
from app.models.admin_user import AdminUser
from app.models.license import License, LicenseStatus
from app.models.product import Product
from app.schemas.license import LicenseCreate, LicenseUpdate, LicenseResponse
from app.admin.auth import get_current_admin
from app.utils.audit_utils import create_audit_log

router = APIRouter()

# 创建授权
@router.post("/", response_model=LicenseResponse, status_code=status.HTTP_201_CREATED)
def create_license(
    license_data: LicenseCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    # 检查产品是否存在
    product = db.query(Product).filter(Product.product_code == license_data.product_code).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # 检查授权码是否已存在
    existing_license = db.query(License).filter(License.license_key == license_data.license_key).first()
    if existing_license:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="License key already exists"
        )
    
    # 创建授权
    db_license = License(
        license_key=license_data.license_key,
        product_code=license_data.product_code,
        max_devices=license_data.max_devices,
        expire_at=license_data.expire_at,
        remark=license_data.remark
    )
    
    db.add(db_license)
    db.commit()
    db.refresh(db_license)
    
    # 记录审计日志
    create_audit_log(
        db=db,
        admin_username=current_admin.username,
        action="创建",
        target_type="授权",
        target_id=db_license.id,
        target_instance=db_license
    )
    
    return db_license

# 查询授权列表
@router.get("/", response_model=List[LicenseResponse])
def get_licenses(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: LicenseStatus = None,
    product_code: str = None,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    query = db.query(License)
    
    # 按状态过滤
    if status:
        query = query.filter(License.status == status)
    
    # 按产品代码过滤
    if product_code:
        query = query.filter(License.product_code == product_code)
    
    licenses = query.offset(skip).limit(limit).all()
    return licenses

# 查询单个授权
@router.get("/{license_id}", response_model=LicenseResponse)
def get_license(
    license_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    license = db.query(License).filter(License.id == license_id).first()
    if not license:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="License not found"
        )
    return license

# 更新授权
@router.put("/{license_id}", response_model=LicenseResponse)
def update_license(
    license_id: int,
    license_update: LicenseUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    license = db.query(License).filter(License.id == license_id).first()
    if not license:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="License not found"
        )
    
    # 更新授权信息
    update_data = license_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(license, key, value)
    
    # 如果更新了过期时间，检查是否需要更新状态
    if "expire_at" in update_data:
        if license.expire_at < date.today():
            license.status = LicenseStatus.EXPIRED
        elif license.status == LicenseStatus.EXPIRED:
            # 已过期授权续期到未来日期时恢复正常，否则激活成功但心跳永远被拒
            license.status = LicenseStatus.ACTIVATED
    
    db.commit()
    db.refresh(license)
    
    # 记录审计日志
    create_audit_log(
        db=db,
        admin_username=current_admin.username,
        action="更新",
        target_type="授权",
        target_id=license.id,
        target_instance=license,
        detail={"updated_fields": list(update_data.keys())}
    )
    
    return license

# 吊销授权
@router.post("/{license_id}/revoke", response_model=LicenseResponse)
def revoke_license(
    license_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    license = db.query(License).filter(License.id == license_id).first()
    if not license:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="License not found"
        )
    
    # 吊销授权
    license.status = LicenseStatus.REVOKED
    
    db.commit()
    db.refresh(license)
    
    # 记录审计日志
    create_audit_log(
        db=db,
        admin_username=current_admin.username,
        action="吊销",
        target_type="授权",
        target_id=license.id,
        target_instance=license
    )
    
    return license

# 删除授权
@router.delete("/{license_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_license(
    license_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    license = db.query(License).filter(License.id == license_id).first()
    if not license:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="License not found"
        )
    
    # 删除关联的客户端记录
    from app.models.client import Client
    db.query(Client).filter(Client.license_id == license_id).delete()
    
    # 记录审计日志
    create_audit_log(
        db=db,
        admin_username=current_admin.username,
        action="删除",
        target_type="授权",
        target_id=license.id,
        target_instance=license
    )
    
    # 删除授权
    db.delete(license)
    db.commit()
    
    return None