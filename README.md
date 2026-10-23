# hex-auth 授权中心系统

hex-auth 是一个功能完整的授权中心系统，用于管理软件产品的授权、客户端设备和审计日志。

## 技术栈

### 后端
- **框架**: FastAPI 0.104.1
- **ORM**: SQLAlchemy 2.0.23
- **数据库**: MySQL
- **认证**: JWT (JSON Web Tokens)
- **依赖管理**: pip

### 前端
- **框架**: Vue 3.5.13
- **语言**: TypeScript 5.6.2
- **构建工具**: Vite 6.0.5
- **状态管理**: Pinia 2.2.5
- **UI库**: Naive UI 2.39.0
- **HTTP客户端**: Axios 1.7.7

## 项目结构

```
hex-auth/
├── backend/                  # 后端代码
│   ├── app/                  # 应用主目录
│   │   ├── admin/            # 管理员API
│   │   ├── api/              # 客户端API
│   │   ├── core/             # 核心配置
│   │   ├── models/           # 数据模型
│   │   ├── schemas/          # 数据验证
│   │   └── main.py           # 应用入口
│   ├── .env                  # 环境变量配置（不入库，参考 .env.example）
│   ├── .env.example          # 环境变量模板
│   ├── create_admin.py       # 初始管理员创建脚本
│   ├── create_db.py          # 数据库初始化脚本
│   ├── Dockerfile            # 后端Docker构建文件
│   └── requirements.txt      # 依赖列表
├── frontend/                 # 前端代码
│   ├── public/               # 静态资源
│   ├── src/                  # 源代码
│   │   ├── api/              # API请求
│   │   ├── components/       # Vue组件
│   │   ├── layouts/          # 布局组件
│   │   ├── pages/            # 页面组件
│   │   ├── router/           # 路由配置
│   │   └── stores/           # 状态管理
│   ├── Dockerfile            # 前端Docker构建文件
│   └── package.json          # 依赖配置
└── README.md
```

## 功能特性

### 管理员功能
- 仪表盘：显示系统概览和统计数据
- 产品管理：创建、编辑和删除产品
- 授权管理：生成、编辑和吊销授权码
- 客户端管理：查看和管理客户端设备
- 审计日志：记录系统操作日志

### 客户端API
- 授权验证：验证授权码有效性
- 设备激活：激活客户端设备
- 状态检查：检查授权状态

## 快速开始

### 后端运行

1. **安装依赖**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **配置环境变量**

   复制模板创建 `.env` 文件（`.env` 不会提交到仓库）：
   ```bash
   cp .env.example .env
   ```
   按需修改以下内容：
   ```
   # 数据库配置
   DATABASE_URL="mysql+pymysql://root:password@localhost:3306/hex_auth"
   
   # JWT配置（生产环境务必替换为随机密钥：
   # python -c "import secrets; print(secrets.token_hex(32))"）
   JWT_SECRET_KEY="your-random-secret"
   JWT_ALGORITHM="HS256"
   JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
   
   # RSA私钥主密钥（用于加密存储各产品的RSA私钥）
   # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   RSA_MASTER_KEY="your-fernet-key"
   
   # CORS白名单（逗号分隔）
   CORS_ALLOW_ORIGINS="http://localhost:3000"
   ```

   > 说明：每个产品创建时会自动生成独立的 RSA 密钥对，私钥以 `RSA_MASTER_KEY` 加密后存库，公钥明文存库，无需手动配置密钥文件。
   > ⚠️ `RSA_MASTER_KEY` 一旦设定请妥善保存：丢失后数据库中已加密的产品私钥将无法恢复。历史明文私钥无需处理，会在下次激活时自动升级为加密存储。

3. **初始化数据库并创建初始管理员**
   ```bash
   python create_db.py
   python create_admin.py
   ```
   初始管理员为 `admin / admin123`，登录后请立即在「个人中心」修改密码。

4. **启动开发服务器**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

### 前端运行

1. **安装依赖**
   ```bash
   cd frontend
   npm install
   ```

2. **启动开发服务器**
   ```bash
   npm run dev
   ```

3. **构建生产版本**
   ```bash
   npm run build
   ```

### 数据库重建与恢复

- **重建（新库）**：`python create_db.py` 创建数据库，`python create_admin.py` 按当前模型自动建表并初始化管理员
- **备份**：
  ```bash
  mysqldump -u user -p hex_auth > backup_$(date +%F).sql
  ```
- **恢复（已有数据）**：用 SQL 备份文件恢复：
  ```bash
  mysql -u user -p hex_auth < backup.sql
  ```
- **自动备份**：使用 `scripts/backup.sh`（自动从 `backend/.env` 读取连接信息，gzip 压缩并按保留天数清理旧备份）：
  ```bash
  # 手动执行：备份到指定目录，保留14天
  ./scripts/backup.sh /var/backups/hex-auth 14

  # crontab 每天凌晨3点自动备份
  # 0 3 * * * /path/to/hex-auth/scripts/backup.sh /var/backups/hex-auth 14 >> /var/log/hex-auth-backup.log 2>&1
  ```

## 部署

> 推荐直接按 **[DEPLOY.md](DEPLOY.md)** 使用 Docker Compose 部署（含 `auth.aaa.com`
> 的域名、HTTPS、备份与验收清单）。以下为手工部署方案，供参考。

### 部署方式1：前后端Docker部署（连接已有的MySQL和Nginx）

如果您的服务器已经安装了MySQL和Nginx，可以使用此方案，只部署前后端服务。

#### 1. 准备工作
- 确保服务器已安装Docker和Docker Compose
- 确保MySQL已创建数据库 `hex_auth`
- 确保Nginx已配置好反向代理

#### 2. 配置环境变量

使用 `backend/.env.example` 作为模板（`docker run --env-file` 指向 `backend/.env`）：

```bash
# 数据库连接配置（连接到已有的MySQL）
DATABASE_URL="mysql+pymysql://root:password@localhost:3306/hex_auth"

# JWT配置（生产环境务必替换为随机密钥）
JWT_SECRET_KEY="your-random-secret"
JWT_ALGORITHM="HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# RSA私钥主密钥（一旦设定请妥善保存，丢失后已加密私钥无法恢复）
RSA_MASTER_KEY="your-fernet-key"

# CORS白名单（前后端通过Nginx同源代理时无需额外配置）
CORS_ALLOW_ORIGINS="https://your-domain.com"
```

#### 3. 构建并启动前后端容器

```bash
# 构建后端容器
docker build -t hex-auth-backend ./backend

# 构建前端容器
docker build -t hex-auth-frontend ./frontend

# 运行后端容器
docker run -d --name hex-auth-backend -p 8000:8000 --env-file ./backend/.env hex-auth-backend

# 运行前端容器
docker run -d --name hex-auth-frontend -p 8080:80 hex-auth-frontend
```

#### 4. 配置服务器Nginx（HTTPS）

> ⚠️ **安全要求**：后端 8000 端口只允许本机访问（`docker run` 时不要加 `-p 8000:8000`，
> 或用防火墙封禁外网访问），所有流量必须经 Nginx 反代进入。限流与审计依赖
> `X-Real-IP` 请求头，该头由 Nginx 用真实客户端地址覆写；若后端直连公网，
> 攻击者可伪造此头绕过限流。

授权码与令牌属于敏感数据，生产环境必须走 HTTPS。在 `/etc/nginx/conf.d/` 目录下创建 `hex-auth.conf` 文件：

```nginx
# HTTP 跳转 HTTPS
server {
    listen 80;
    server_name your-domain.com;  # 替换为您的域名
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;  # 替换为您的域名

    ssl_certificate     /etc/nginx/ssl/fullchain.pem;   # 替换为证书路径
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    
    # 前端代理
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # 后端API代理
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # 管理员API代理
    location /admin {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

证书可用 Let's Encrypt 免费签发并自动续期：

```bash
# 安装 certbot 后签发证书（以Ubuntu为例）
certbot certonly --nginx -d your-domain.com
# 证书位于 /etc/letsencrypt/live/your-domain.com/，
# 将上面 nginx 配置中的 ssl_certificate 路径指向它，certbot 会自动续期
```

#### 5. 重启Nginx服务

```bash
# 检查Nginx配置语法
nginx -t

# 重启Nginx服务
systemctl restart nginx
```

### 部署方式2：Docker Compose部署（含MySQL容器）

如果您的服务器没有安装MySQL，可以使用此方案，一键部署完整的服务栈，包括MySQL数据库。

#### 1. 创建docker-compose.yml文件

在项目根目录创建 `docker-compose.yml` 文件：

```yaml
version: '3.8'

# 数据库服务
services:
  # MySQL数据库
  mysql:
    image: mysql:8.0
    container_name: hex-auth-mysql
    restart: always
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: hex_auth
    ports:
      - "3306:3306"
    volumes:
      - mysql-data:/var/lib/mysql
    networks:
      - hex-auth-network

  # 后端API服务
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: hex-auth-backend
    restart: always
    depends_on:
      - mysql
    environment:
      # 数据库连接配置（连接到容器内的MySQL）
      DATABASE_URL: "mysql+pymysql://root:root@mysql:3306/hex_auth"
      JWT_SECRET_KEY: "your-random-secret"
      JWT_ALGORITHM: "HS256"
      JWT_ACCESS_TOKEN_EXPIRE_MINUTES: "30"
      RSA_MASTER_KEY: "your-fernet-key"
    ports:
      - "8000:8000"
    networks:
      - hex-auth-network

  # 前端服务
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: hex-auth-frontend
    restart: always
    depends_on:
      - backend
    ports:
      - "80:80"
    networks:
      - hex-auth-network

# 网络配置
networks:
  hex-auth-network:
    driver: bridge

# 数据卷配置
volumes:
  mysql-data:
```

#### 2. 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

#### 3. 访问服务

- 前端地址：`http://your-server-ip`
- 后端API：`http://your-server-ip:8000`

### Dockerfile说明

#### 后端Dockerfile (backend/Dockerfile)

```dockerfile
FROM python:3.12

# 设置工作目录
WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install -r requirements.txt

# 复制应用代码
COPY . .

# 创建密钥目录
RUN mkdir -p /app/keys

# 暴露端口
EXPOSE 8000

# 启动应用
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 前端Dockerfile (frontend/Dockerfile)

```dockerfile
FROM node:20 as build

# 设置工作目录
WORKDIR /app

# 安装依赖
COPY package*.json ./
RUN npm install

# 复制应用代码
COPY . .

# 构建生产版本
RUN npm run build

# 使用Nginx作为前端服务器
FROM nginx:alpine

# 复制构建产物到Nginx静态目录
COPY --from=build /app/dist /usr/share/nginx/html

# 复制Nginx配置文件
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

# 启动Nginx
CMD ["nginx", "-g", "daemon off;"]
```

#### 前端Nginx配置 (frontend/nginx.conf)

```nginx
server {
    listen 80;
    server_name localhost;
    
    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }
    
    # 静态资源缓存配置
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        root /usr/share/nginx/html;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

## API文档

### 管理员API
- **仪表盘**: GET /admin/dashboard
- **产品管理**: GET/POST/PUT/DELETE /admin/product
- **授权管理**: GET/POST/PUT/DELETE /admin/license
- **客户端管理**: GET /admin/client
- **审计日志**: GET /admin/audit

### 客户端API
- **授权验证**: POST /api/v1/license/verify
- **设备激活**: POST /api/v1/license/activate
- **状态检查**: GET /api/v1/license/status

## 开发流程

### 后端开发
1. 创建数据模型 (`app/models/`)
2. 创建数据验证模式 (`app/schemas/`)
3. 创建API路由 (`app/admin/` 或 `app/api/`)
4. 如修改了数据模型：新库由 `create_admin.py` 启动时自动按模型建表；已有数据库需手动执行 `ALTER TABLE` SQL 升级

### 前端开发
1. 创建页面组件 (`src/pages/`)
2. 配置路由 (`src/router/index.ts`)
3. 创建API请求 (`src/api/index.ts`)
4. 开发UI组件和交互逻辑

## 贡献指南

1. Fork 仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 许可证

MIT License

## 联系方式

如有问题或建议，请通过 [GitHub Issues](https://github.com/jiangyi-vento/hex-auth/issues) 反馈。
