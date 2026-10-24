# hex-auth 授权中心 API 文档

## 1. 简介

hex-auth 是一个统一的在线授权中心，为多形态程序提供在线激活、心跳校验、授权吊销与后台管理能力。本文档介绍外部程序如何通过 API 请求 hex-auth 服务进行鉴权。

## 2. 快速开始

### 2.1 API 基础信息

| 项目 | 说明 |
| --- | --- |
| API 版本 | v1 |
| 基础 URL | 生产：`https://your-domain/api/v1`；本地开发：`http://localhost:8000/api/v1` |
| 通信协议 | HTTP/HTTPS（生产环境必须 HTTPS） |
| 请求方法 | POST |
| 数据格式 | JSON |
| 业务失败 | 业务失败（success=false）仍是 HTTP 200；仅限流(429)与参数校验失败(422)返回非 200，见 4.1 |

### 2.2 核心概念

- **授权码 (License Key)**: 唯一的授权标识符，由管理员在后台生成
- **客户端指纹 (Client Fingerprint)**: 客户端设备的唯一标识，建议使用硬件信息生成
- **客户端类型 (Client Type)**: 客户端程序的类型，可选值：`gui`, `cli`, `service`, `plugin`
- **授权令牌 (License Token)**: 由服务器生成的加密令牌，包含授权信息和有效期

## 3. API 详细说明

### 3.1 激活 API

**端点**: `/license/activate`

**功能**: 激活授权，生成授权令牌

**请求格式**:

```json
{
  "license_key": "XXXX-XXXX-XXXX-XXXX",
  "client_fp": "HASH1234567890",
  "client_type": "gui"
}
```

**参数说明**:

| 参数名 | 类型 | 必需 | 说明 |
| --- | --- | --- | --- |
| license_key | string | 是 | 授权码，长度 10-50 |
| client_fp | string | 是 | 客户端指纹，建议使用硬件信息哈希生成，长度 10-100 |
| client_type | string | 是 | 客户端类型，可选值：`gui`, `cli`, `service`, `plugin`（长度 3-20） |

**响应格式**:

```json
{
  "success": true,
  "message": "Activation successful",
  "heartbeat_interval": 3600,
  "token": {
    "token": {
      "iss": "hex-auth",
      "product": "XRAY_GUI",
      "license_key": "XXXX-XXXX-XXXX-XXXX",
      "client_fp": "HASH1234567890",
      "iat": 1730000000,
      "exp": 1760000000
    },
    "signature": "base64-encoded-signature"
  }
}
```

**响应说明**:

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| success | boolean | 激活是否成功 |
| message | string | 响应消息 |
| heartbeat_interval | int | 产品配置的心跳间隔（秒），客户端按此间隔发送心跳 |
| token | object | 授权令牌，包含 token 数据和 signature 签名 |
| token.token | object | 令牌数据，包含授权信息和有效期 |
| token.signature | string | 令牌签名，用于验证令牌完整性 |

**失败响应示例**:

```json
{
  "success": false,
  "message": "Invalid license key"
}
```

**行为说明**:

- 设备被管理员禁用后，无法通过重新激活自我解禁（返回 `Client has been disabled`），需联系管理员
- 处于异常状态（长时间未心跳）的设备重新激活会自动恢复正常
- 异常（离线）设备**仍占用设备名额**：更换设备需管理员在后台「客户端管理」删除旧设备释放名额
- 同一指纹重复激活不会占用新的设备名额

### 3.2 心跳 API

**端点**: `/license/heartbeat`

**功能**: 维持客户端与服务器的连接，更新客户端最后心跳时间与来源IP

**请求格式**:

```json
{
  "token": {
    "token": {
      "iss": "hex-auth",
      "product": "XRAY_GUI",
      "license_key": "XXXX-XXXX-XXXX-XXXX",
      "client_fp": "HASH1234567890",
      "iat": 1730000000,
      "exp": 1760000000
    },
    "signature": "base64-encoded-signature"
  }
}
```

**参数说明**:

| 参数名 | 类型 | 必需 | 说明 |
| --- | --- | --- | --- |
| token | object | 是 | 授权令牌，包含 token 数据和 signature 签名 |

**响应格式**:

```json
{
  "success": true,
  "message": "Heartbeat successful"
}
```

**失败响应示例**:

```json
{
  "success": false,
  "message": "Invalid token signature"
}
```

### 3.3 状态 API

**端点**: `/license/status`

**功能**: 检查授权状态，获取授权有效期

**请求格式**:

```json
{
  "token": {
    "token": {
      "iss": "hex-auth",
      "product": "XRAY_GUI",
      "license_key": "XXXX-XXXX-XXXX-XXXX",
      "client_fp": "HASH1234567890",
      "iat": 1730000000,
      "exp": 1760000000
    },
    "signature": "base64-encoded-signature"
  }
}
```

**参数说明**:

| 参数名 | 类型 | 必需 | 说明 |
| --- | --- | --- | --- |
| token | object | 是 | 授权令牌，包含 token 数据和 signature 签名 |

**响应格式**:

```json
{
  "success": true,
  "message": "License is valid",
  "status": "valid",
  "expire_at": 1760000000
}
```

**响应说明**:

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| success | boolean | 状态检查是否成功 |
| message | string | 响应消息 |
| status | string | 授权状态：`valid`, `revoked`, `expired`, `disabled` |
| expire_at | integer | 授权过期时间戳 |

**失败响应示例**:

```json
{
  "success": false,
  "message": "License has expired",
  "status": "expired"
}
```

### 3.4 令牌离线验签

客户端可在本地验证令牌完整性，无需请求服务器。算法：对 `token` 部分
按 **key 排序序列化为紧凑 JSON**，使用产品 **RSA 公钥**做 **SHA256 + PKCS#1 v1.5**
签名验证（公钥可向管理员索取，或在管理后台产品详情中复制）。

Python 验签示例：

```python
import base64, json, time
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

def verify_license_token(token: dict, public_key_pem: str) -> bool:
    try:
        payload = json.dumps(token["token"], sort_keys=True).encode("utf-8")
        key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        key.verify(
            base64.b64decode(token["signature"]),
            payload,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return token["token"]["exp"] > int(time.time())
    except Exception:
        return False
```

> 验签通过仅代表令牌未被篡改；吊销、禁用等实时状态仍以 `heartbeat` / `status` 接口为准。

## 4. 错误码说明

| 错误消息 | 说明 |
| --- | --- |
| Invalid license key | 无效的授权码 |
| License has been revoked | 授权已被吊销 |
| License has expired | 授权已过期 |
| Product not found | 产品不存在 |
| Product has been disabled | 产品已被禁用 |
| Maximum number of devices reached | 已达到最大设备数限制 |
| Invalid client type | 客户端类型不合法（仅激活接口） |
| License not found | 授权不存在（心跳/状态接口，如授权已被删除） |
| Invalid token format | 无效的令牌格式 |
| Invalid token signature | 无效的令牌签名 |
| Client not found | 客户端不存在 |
| Client has been disabled | 客户端已被禁用 |
| License is invalid | 授权无效 |

### 4.1 非 200 响应（与业务失败格式不同）

| HTTP 状态码 | 触发场景 | 响应格式 |
| --- | --- | --- |
| 429 | 同一 IP 触发限流：激活 10 次/分钟，心跳与状态 300 次/分钟 | `{"detail": "Too many requests, please retry later"}` |
| 422 | 请求参数不满足校验（缺失字段、长度超限、类型错误） | `{"detail": [{"loc": [...], "msg": "..."}]}` |

客户端实现时应区分三种情况：HTTP 非 200（限流/参数错误）、HTTP 200 且 `success=false`（业务失败）、HTTP 200 且 `success=true`。收到 429 时应退避重试而非立即重发。

## 5. 示例代码

### 5.1 Python 示例

```python
import requests
import json

# 基础配置
BASE_URL = "http://your-server:8000/api/v1"

# 激活授权
def activate_license(license_key, client_fp, client_type):
    url = f"{BASE_URL}/license/activate"
    data = {
        "license_key": license_key,
        "client_fp": client_fp,
        "client_type": client_type
    }
    
    response = requests.post(url, json=data)
    return response.json()

# 发送心跳
def send_heartbeat(token):
    url = f"{BASE_URL}/license/heartbeat"
    data = {
        "token": token
    }
    
    response = requests.post(url, json=data)
    return response.json()

# 检查状态
def check_status(token):
    url = f"{BASE_URL}/license/status"
    data = {
        "token": token
    }
    
    response = requests.post(url, json=data)
    return response.json()

# 使用示例
if __name__ == "__main__":
    # 1. 激活授权
    license_key = "XXXX-XXXX-XXXX-XXXX"
    client_fp = "HASH1234567890"
    client_type = "gui"
    
    activation_result = activate_license(license_key, client_fp, client_type)
    print("激活结果:", json.dumps(activation_result, indent=2))
    
    if activation_result["success"]:
        token = activation_result["token"]
        
        # 2. 发送心跳
        heartbeat_result = send_heartbeat(token)
        print("心跳结果:", json.dumps(heartbeat_result, indent=2))
        
        # 3. 检查状态
        status_result = check_status(token)
        print("状态检查结果:", json.dumps(status_result, indent=2))
```

### 5.2 JavaScript 示例

```javascript
// 基础配置
const BASE_URL = "http://your-server:8000/api/v1";

// 激活授权
async function activateLicense(licenseKey, clientFp, clientType) {
  const url = `${BASE_URL}/license/activate`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      license_key: licenseKey,
      client_fp: clientFp,
      client_type: clientType
    })
  });
  return response.json();
}

// 发送心跳
async function sendHeartbeat(token) {
  const url = `${BASE_URL}/license/heartbeat`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ token })
  });
  return response.json();
}

// 检查状态
async function checkStatus(token) {
  const url = `${BASE_URL}/license/status`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ token })
  });
  return response.json();
}

// 使用示例
async function main() {
  // 1. 激活授权
  const licenseKey = "XXXX-XXXX-XXXX-XXXX";
  const clientFp = "HASH1234567890";
  const clientType = "gui";
  
  const activationResult = await activateLicense(licenseKey, clientFp, clientType);
  console.log("激活结果:", activationResult);
  
  if (activationResult.success) {
    const token = activationResult.token;
    
    // 2. 发送心跳
    const heartbeatResult = await sendHeartbeat(token);
    console.log("心跳结果:", heartbeatResult);
    
    // 3. 检查状态
    const statusResult = await checkStatus(token);
    console.log("状态检查结果:", statusResult);
  }
}

main();
```

## 6. 最佳实践

### 6.1 客户端实现建议

1. **安全存储授权令牌**:
   - 将授权令牌存储在安全位置，如加密的配置文件或系统密钥存储
   - 避免明文存储授权令牌

2. **合理设置心跳间隔**:
   - 使用激活响应返回的 `heartbeat_interval` 作为心跳间隔，不要自行硬编码
   - 避免过于频繁的心跳请求：同 IP 心跳限流为 300 次/分钟

3. **处理授权异常**:
   - 实现完善的错误处理机制，处理各种授权失败情况
   - 给用户友好的错误提示，引导用户解决授权问题

4. **定期检查授权状态**:
   - 在程序启动时和定期检查授权状态
   - 及时提醒用户授权即将过期

### 6.2 服务器部署建议

1. **使用 HTTPS**:
   - 生产环境必须使用 HTTPS 协议，保护 API 通信安全

2. **配置防火墙**:
   - 限制 API 访问 IP，防止恶意请求

3. **监控 API 调用**:
   - 监控 API 调用频率和错误率，及时发现异常情况

4. **定期备份数据库**:
   - 定期备份授权数据，防止数据丢失

## 7. 常见问题

### 7.1 授权激活失败怎么办？

- 检查授权码是否正确
- 检查授权是否已被吊销或过期
- 检查产品是否已被禁用
- 检查设备数量是否已达到限制

### 7.2 心跳失败怎么办？

- 检查授权令牌是否有效
- 检查客户端是否已被禁用
- 检查网络连接是否正常

### 7.3 如何生成客户端指纹？

客户端指纹建议使用硬件信息生成，如：
- CPU ID + 硬盘 ID + 主板 ID
- MAC 地址 + 硬盘序列号
- 使用加密算法对硬件信息进行哈希处理

### 7.4 授权令牌的有效期是多久？

授权令牌的有效期与授权的过期时间一致，在激活时由服务器生成。

## 8. 联系我们

如果您在使用 hex-auth API 过程中遇到问题，请联系管理员或技术支持。

---

**文档版本**: 1.1
**更新日期**: 2026-10-24
**适用版本**: hex-auth v1.x
