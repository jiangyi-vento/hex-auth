# 部署指南：auth.aaa.com

面向轻量级云服务器（1 核 2G 起）的一站式部署说明。架构：

```
浏览器/客户端
      │  443 (HTTPS)
      ▼
宿主机 Nginx ──► /            → 127.0.0.1:8080  前端容器（静态站点）
      │      ──► /admin, /api → 127.0.0.1:8000  后端容器（FastAPI）
      │
      └── MySQL 仅在容器网络内可达（不暴露端口）
```

---

## 0. 前置准备

| 项目 | 要求 |
| --- | --- |
| 服务器 | 1 核 2G 起，磁盘 20G+；1G 内存必须先加 swap（见 1.1） |
| 域名 | A 记录 `auth.aaa.com` 指向服务器公网 IP |
| 备案 | 服务器在中国大陆时，域名需完成 ICP 备案 |
| 端口 | 只对外开放 22 / 80 / 443 |

验证解析生效：

```bash
# 无需安装任何工具（glibc 自带）
getent hosts auth.aaa.com

# 或
ping -c 1 auth.aaa.com
```

> 想用 `dig` 的话先装 bind-utils：`sudo dnf install -y bind-utils`（CentOS 7 用 `yum`）。
> 只要返回的是你的服务器公网 IP 即可；解析未生效时 `getent` 无输出，需回域名控制台检查 A 记录。

---

## 1. 服务器初始化

以 Ubuntu 22.04 / Debian 12 为例。

### 1.1 内存不足 2G 时先加 swap

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h    # 确认 Swap 已生效
```

> 前端镜像构建（Vite + vue-tsc）峰值需要 500M 左右内存，1G 机器不加 swap 容易 OOM。

### 1.2 安装 Docker 与 Nginx

先确认发行版：`cat /etc/os-release`。

**Ubuntu / Debian：**

```bash
curl -fsSL https://get.docker.com | sh
sudo systemctl enable --now docker
docker compose version

sudo apt update
sudo apt install -y nginx certbot git
sudo systemctl enable --now nginx
```

**CentOS / Rocky / Alma / 阿里云 Linux 3（RHEL 系）：**

```bash
# Docker（get.docker.com 同时支持 RHEL 系）
curl -fsSL https://get.docker.com | sh
sudo systemctl enable --now docker
docker compose version

# Git 与 Nginx（最小化镜像默认都没有；CentOS 7 用 yum，8+ 用 dnf）
sudo dnf install -y git nginx || sudo yum install -y git nginx
sudo systemctl enable --now nginx

# Certbot 位于 EPEL 源，必须先启用 EPEL
sudo dnf install -y epel-release || sudo yum install -y epel-release
sudo dnf install -y certbot || sudo yum install -y certbot
certbot --version
```

> 若 EPEL 源不可用（精简镜像、CentOS 7 已 EOL 等），改用 **acme.sh**（纯脚本、零依赖、自带续期），
> 签发方式见 5.1 的备选方案。

> 阿里云/腾讯云服务器还需要在**控制台安全组**放行 80、443（以及 22），
> 否则证书 HTTP 验证会失败，表现为 `Timeout during connect`。
### 1.3 防火墙与安全组

**Ubuntu / Debian（ufw）：**

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

**CentOS / RHEL 系（firewalld）：**

```bash
sudo systemctl enable --now firewalld
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
sudo firewall-cmd --list-services
```

**云厂商安全组**：阿里云/腾讯云/华为云需在控制台的安全组入方向规则中放行
`22`、`80`、`443`。这一层独立于服务器内的 firewalld/ufw，只开其中一个不够。
---

## 2. 获取代码与配置密钥

```bash
sudo mkdir -p /opt && cd /opt
sudo git clone https://github.com/jiangyi-vento/hex-auth.git
cd hex-auth
```

> 国内服务器拉取 GitHub 可能超时。兜底：在本地打包后上传
> ```bash
> # 开发机（项目根目录）
> git archive --format=tar.gz --prefix=hex-auth/ -o hex-auth.tar.gz HEAD
> scp hex-auth.tar.gz root@<服务器IP>:/opt/
> # 服务器
> cd /opt && tar xzf hex-auth.tar.gz
> ```
> 之后更新版本可用 `scp` 增量覆盖，或给服务器配好代理再 `git pull`。

### 2.1 生成两个密钥

```bash
# JWT 签名密钥
python3 -c "import secrets; print(secrets.token_hex(32))"

# RSA 私钥主密钥（加密存储各产品私钥用）
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> 若系统 python 没装 cryptography，可在容器内生成：
> `docker run --rm python:3.12 sh -c "pip install -q cryptography && python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"`

### 2.2 写入配置

根目录 `.env`（供 docker compose 插值）：

```bash
cp .env.example .env
vi .env
# MYSQL_ROOT_PASSWORD=<强密码>
# MYSQL_PASSWORD=<强密码>
```

`backend/.env`：

```bash
cp backend/.env.example backend/.env
vi backend/.env
```

内容要点：

```ini
# 此行会被 compose 覆盖为容器网络地址，此处仅保证格式正确
DATABASE_URL=mysql+pymysql://hexauth:<上一步的 MYSQL_PASSWORD>@mysql:3306/hex_auth?charset=utf8mb4

JWT_SECRET_KEY=<2.1 生成的 64 位十六进制>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

RSA_MASTER_KEY=<2.1 生成的 Fernet 密钥>

CORS_ALLOW_ORIGINS=https://auth.aaa.com
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_RELOAD=False
```

```bash
chmod 600 .env backend/.env
```

> 数据库密码请使用**字母数字**组合；若必须包含 `@ : / ?` 等字符，需要在 `DATABASE_URL`
> 中做 URL 编码（如 `@` → `%40`），否则连接串会被截断。

> ⚠️ **`RSA_MASTER_KEY` 必须另行备份**（密码管理器 / 离线便签）。
> 它丢失后，数据库中已加密的产品私钥无法恢复，只能重建产品并重新发码。

---

## 3. 启动容器

```bash
sudo docker compose up -d --build
sudo docker compose ps          # mysql 应为 healthy，其余为 running
sudo docker compose logs -f backend   # 看到 Uvicorn running 即成功（Ctrl+C 退出日志）
```

内存吃紧时的替代方案（本地构建后传到服务器）：

```bash
# 开发机上
docker build -t hex-auth-backend ./backend
docker build -t hex-auth-frontend ./frontend
docker save hex-auth-backend hex-auth-frontend | gzip > hex-auth-images.tar.gz
scp hex-auth-images.tar.gz user@server:/tmp/

# 服务器上（把 compose 中 build: 改成 image:，或直接 load 后 compose up）
gunzip -c /tmp/hex-auth-images.tar.gz | docker load
```

---

## 4. 初始化数据库与管理员

MySQL 容器首次启动已自动创建 `hex_auth` 库，接着建表并创建初始管理员：

```bash
sudo docker compose exec backend python create_admin.py
# 输出：初始管理员用户已创建: username=admin, password=admin123
```

立即登录 `https://auth.aaa.com` 后到「个人中心」修改密码（修改后所有旧令牌失效，会被强制重新登录）。

---

## 5. 配置 Nginx 与 HTTPS

### 5.1 先签证书（此时 80 端口空闲）

```bash
# 停用默认站点，避免占用 80
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# 使用 standalone 方式签发（certbot 会临时监听 80）
sudo certbot certonly --standalone -d auth.aaa.com
# 证书生成在 /etc/letsencrypt/live/auth.aaa.com/
```
**备选：acme.sh（无 root 包管理器依赖）**

```bash
curl https://get.acme.sh | sh -s email=you@example.com
~/.acme.sh/acme.sh --issue --standalone -d auth.aaa.com

# 安装到与 Nginx 配置相同的路径（续期后自动 reload）
sudo mkdir -p /etc/letsencrypt/live/auth.aaa.com
sudo ~/.acme.sh/acme.sh --install-cert -d auth.aaa.com   --key-file       /etc/letsencrypt/live/auth.aaa.com/privkey.pem   --fullchain-file /etc/letsencrypt/live/auth.aaa.com/fullchain.pem   --reloadcmd      "systemctl reload nginx"
```

### 5.2 启用站点配置

```bash
sudo cp /opt/hex-auth/deploy/nginx/auth.aaa.com.conf /etc/nginx/conf.d/
sudo nginx -t
sudo systemctl reload nginx
```

> 该配置已包含 80→443 跳转、TLS 1.2/1.3、`X-Real-IP` 透传与安全响应头。
> 若你的 Nginx < 1.25.1，把 `http2 on;` 改为 `listen 443 ssl http2;`。

### 5.3 确认自动续期

```bash
# certbot 方式
sudo systemctl list-timers | grep certbot    # 应有 certbot.timer
sudo certbot renew --dry-run

# acme.sh 方式（自带 crontab 任务，无需额外配置）
crontab -l | grep acme
```

---

## 6. 验收清单

逐条执行，全部通过即部署成功：

```bash
# 1) HTTPS 可访问且 80 会跳转
curl -I http://auth.aaa.com        # 301 -> https://auth.aaa.com
curl -I https://auth.aaa.com       # 200

# 2) 管理端 API 通（未带令牌应返回 401，而不是 502/超时）
curl -i https://auth.aaa.com/admin/auth/me

# 3) 客户端公开接口通（返回 JSON 业务响应）
curl -s -X POST https://auth.aaa.com/api/v1/license/status \
  -H 'Content-Type: application/json' -d '{"token":{"token":{},"signature":"x"}}'

# 4) 后端端口未对公网暴露（应连接失败/超时）
curl -m 3 http://<服务器公网IP>:8000/ || echo "已隔离"

# 5) 容器状态
sudo docker compose ps
```

浏览器端：登录 → 仪表盘 → 新建产品 → 新建授权 → 客户端管理，确认无报错。

---

## 7. 日常运维

### 更新版本

```bash
cd /opt/hex-auth
sudo git pull
sudo docker compose up -d --build
```

> 若本次更新包含模型变更，执行对应的 SQL（`backend/sql/*.sql`），没有则跳过。

### 数据库备份

使用仓库自带的 `deploy/backup-docker.sh`（容器内 mysqldump，宿主机无需装 MySQL 客户端）：

```bash
sudo chmod +x /opt/hex-auth/deploy/backup-docker.sh
sudo mkdir -p /var/backups/hex-auth

# 手动备份（保留 14 天）
/opt/hex-auth/deploy/backup-docker.sh /var/backups/hex-auth 14

# 每天 3:17 自动备份
echo '17 3 * * * /opt/hex-auth/deploy/backup-docker.sh /var/backups/hex-auth 14 >> /var/log/hex-auth-backup.log 2>&1' | sudo crontab -
```

恢复（容器环境变量里已有密码，无需在宿主机明文写密码）：

```bash
gunzip -c /var/backups/hex-auth/hex_auth_2026-10-23_031700.sql.gz |   sudo docker compose exec -T mysql sh -c 'exec mysql -uhexauth -p"$MYSQL_PASSWORD" hex_auth'
```

> 非 Docker（原生）部署请用 `scripts/backup.sh`，它从 `backend/.env` 读取连接信息。

### 日志与资源

```bash
sudo docker compose logs -f --tail=100 backend
sudo docker stats --no-stream
journalctl -u nginx -n 50 --no-pager
```

---

## 8. 注意事项

1. **后端必须单 worker**：登录/接口限流器与离线检测是进程内实现，多 worker 会让限流按进程数放大。compose 中已固定 `--workers 1`。
2. **不要暴露 8000**：限流与审计依赖 Nginx 覆写的 `X-Real-IP`，后端直连公网时该头可被伪造。
3. **主密钥要备份**：`RSA_MASTER_KEY` 丢失 = 所有产品私钥失效。
4. **首次登录立即改密**：初始账号是 `admin / admin123`。
5. **定期检查磁盘**：镜像与备份会累积，`docker system df` 查看；定期 `docker image prune`。
6. 单机部署下 MySQL 数据在 `mysql-data` 卷中，**重装/迁移前先备份**；迁移时用 `docker run --rm -v hex-auth_mysql-data:/data ...` 或直接 SQL 导出。
