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

> ⚠️ RHEL 系启用 firewalld 后，重启 Docker 可能报
> `ZONE_CONFLICT: 'docker0' already bound to a zone` 而无法启动，
> 处理方法见 [第 9 节故障速查](#9-部署故障速查实战记录)。
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

#### 构建时 pip / npm 报 DNS 解析失败（国内服务器常见）

现象：`Temporary failure in name resolution`、`No matching distribution found`、
`npm ERR! network`。宿主能拉镜像但构建容器解析不了域名，按两步处理。

**① 给 Docker 配 DNS**（宿主 `/etc/resolv.conf` 指向 `127.0.0.53` 时容器必然失败）

```bash
cat /etc/resolv.conf          # 若首行是 127.0.0.53，需要下面这步
sudo mkdir -p /etc/docker
# ⚠️ 若 daemon.json 已存在，先 cat 查看原内容，把 dns 合并进去，不要整文件覆盖
sudo tee /etc/docker/daemon.json >/dev/null <<'EOF'
{
  "dns": ["223.5.5.5", "119.29.29.29"]
}
EOF
python3 -m json.tool /etc/docker/daemon.json    # 校验 JSON 合法
sudo systemctl restart docker
```

**② 在根 `.env` 启用国内镜像源后重建**

```bash
cat >> /opt/hex-auth/.env <<'EOF'
PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
NPM_REGISTRY=https://registry.npmmirror.com
EOF

cd /opt/hex-auth
sudo docker compose build backend frontend
sudo docker compose up -d
```

**③ BuildKit 无视 `registry-mirrors`（实测高频）**

现象：`docker info` 里 Registry Mirrors 已生效，`docker pull` 也正常，但
`docker compose build` 仍报：

```
failed to resolve source metadata ... registry-1.docker.io: i/o timeout
```

原因：BuildKit（buildx）有自己的镜像解析器，不读取 `daemon.json` 的 mirrors。
处理：先逐个预拉基础镜像，再临时改用传统构建器：

```bash
docker pull python:3.12
docker pull node:20
docker pull nginx:alpine
docker pull mysql:8.0

cd /opt/hex-auth
sudo env COMPOSE_DOCKER_CLI_BUILD=0 docker compose up -d --build
```

> 实测可用的公共镜像源（阿里云个人加速器在部分网络下不生效时）：
> `https://docker.m.daocloud.io`、`https://docker.1ms.run`。
> 这两个源只加速 Docker Hub 镜像，pip/npm 仍需 ② 里的源。

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

> **方案 B（服务器已有宝塔面板）**：跳过本节的 certbot 流程，走宝塔面板：
> 网站 → 添加站点（域名 `auth.aaa.com`，**纯静态**）→ 站点 SSL → Let's Encrypt
> 一键申请并开「强制 HTTPS」（宝塔自动续期，无需 5.1 的 standalone）。
> 然后编辑站点配置文件：
> 1. **删除**默认的 `location ~ .*\.(gif|jpg|jpeg|png|bmp|swf)$` 与
>    `location ~ .*\.(js|css)?$` 两个静态缓存 location——否则 JS/CSS 请求被截去
>    站点根目录，前端全部 404（这是宝塔下最容易踩的坑）
> 2. 加入三个反代 location（`/admin/` 与 `/api/` → `127.0.0.1:8000`，
>    `/` → `127.0.0.1:8080`），**每段都必须带**
>    `proxy_set_header X-Real-IP $remote_addr;`（限流与审计依赖真实 IP）
> 3. **保留** `root` 行与 `location ~ \.well-known`（证书续期文件验证依赖）
> 4. 完整的 location 片段与验收命令见 `deploy/nginx/auth.aaa.com.conf` 与第 6 节
>
> 以下为裸 Nginx 的标准流程。

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

### 修改配置后如何生效

`env_file` 只在**创建容器时**读取一次，`docker compose restart` 不会重新注入环境变量。
按改动内容选择方式：

| 改动 | 生效方式 |
| --- | --- |
| `backend/.env`（JWT、RSA_MASTER_KEY、限流、CORS、DATABASE_URL） | `sudo docker compose up -d --force-recreate backend` |
| 根 `.env` 的 `PIP_INDEX_URL` / `NPM_REGISTRY` | 只影响构建：`sudo docker compose build backend frontend && sudo docker compose up -d` |
| 根 `.env` 的 `MYSQL_*` | 仅首次初始化建库时生效，见下方说明 |
| `docker-compose.yml` 本身 | `sudo docker compose up -d`（compose 会自动检测并重建） |

验证变量是否真的进了容器：

```bash
sudo docker compose exec backend env | grep -E "JWT_|RSA_|DATABASE_URL|RATE_LIMIT"
sudo docker compose config | head -40     # 查看插值后的最终配置
```

两个高危操作：

- **改 `RSA_MASTER_KEY`**：数据库中已加密的产品私钥将全部无法解密（旧密钥才能解开旧密文）。
  确需更换时必须先用旧密钥解密、再用新密钥重新加密全部产品，否则不要动。
- **改 `MYSQL_PASSWORD`**：只改 `.env` 不会修改 MySQL 里已存在的用户密码，后端会直接连不上。
  正确做法是先进数据库改密码，再同步 `.env`：
  ```bash
  sudo docker compose exec mysql mysql -uroot -p -e     "ALTER USER 'hexauth'@'%' IDENTIFIED BY '<新密码>'; FLUSH PRIVILEGES;"
  # 然后更新 backend/.env 的 DATABASE_URL 里对应密码，再 --force-recreate backend
  ```

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

### 用数据库客户端连接（Navicat / DataGrip / DBeaver）

默认 MySQL **不映射任何宿主机端口**（安全设计），从本机直连会报
`10061 connection refused`，这是正常的，不是配置错误。

**推荐做法：SSH 隧道（不需要对公网开放数据库）**

#### 第一步：服务器上把 3306 只映射到回环地址

编辑 `/opt/hex-auth/docker-compose.yml`，在 `mysql:` 服务下增加 `ports`（缩进与 `environment:` 对齐）：

```yaml
  mysql:
    image: mysql:8.0
    container_name: hex-auth-mysql
    restart: always
    ports:
      - "127.0.0.1:3306:3306"      # 只监听本机，公网不可达
    environment:
      ...
```

`docker-compose.yml` 里已经预留了这两行（注释状态），取消注释即可：

```bash
cd /opt/hex-auth
sudo vi docker-compose.yml     # mysql 服务下：去掉 ports / - "127.0.0.1:3306:3306" 的注释
sudo docker compose up -d mysql      # 重建 mysql 容器，数据卷不受影响
ss -lntp | grep 3306                 # 应显示 127.0.0.1:3306
```

#### 第二步：客户端开 SSH 隧道

Navicat 的配置分成两页，**两页的账号密码完全不同，最容易填错**：

| 配置页 | 字段 | 值 |
| --- | --- | --- |
| **SSH 隧道** | 主机 / 端口 | 服务器公网 IP / `22` |
| | **用户名** | **`root`**（服务器 SSH 账号） |
| | 认证方式 / 密码 | 密码（或 Public Key） |
| | **密码** | **服务器 root 密码**（不是数据库密码） |
| **常规** | 主机 / 端口 | `127.0.0.1` / `3306` |
| | 用户名 | `hexauth` |
| | 密码 | 根 `.env` 里的 `MYSQL_PASSWORD` |
| | 数据库 | `hex_auth` |

要点：

- 常规页的主机必须填 `127.0.0.1`，它是从**服务器本地**解析的，走 SSH 隧道出口
- DataGrip / DBeaver 同理：先勾选 SSH tunnel，数据库 host 填 `127.0.0.1`

#### 第三步（可选）：用完恢复严格隔离

删掉 `ports` 段，再执行 `sudo docker compose up -d mysql`。

#### 排错

| 报错 | 原因与处理 |
| --- | --- |
| `10061 connection refused` | MySQL 未映射端口（默认状态），按上面第一步开启 |
| `Access denied for 'password'. Authentication that can continue: publickey,...,password (31)` | 这是 **SSH 层**报错：SSH 页的「用户名」栏被填成了 `password`，应填 `root`，密码放到「密码」栏 |
| `Permission denied (publickey,...)` | 服务器禁止 root 密码登录。检查 `grep -i "^PermitRootLogin" /etc/ssh/sshd_config`，改为 `yes` 后 `systemctl restart sshd`；或改用密钥认证 |
| 报 `Access denied for user 'hexauth'@...` | 已经连上 MySQL，是数据库密码不对：核对根 `.env` 的 `MYSQL_PASSWORD` 与 `DATABASE_URL` 中是否一致 |

先在命令行验证 SSH 本身是否连通（Windows PowerShell）：

```powershell
ssh root@<服务器IP>
```

能登入才说明账号密码没问题，再回去核对客户端两个页面的字段。

**不开放端口的方式（只做临时查询）**

```bash
sudo docker compose exec mysql mysql -uhexauth -p hex_auth
# 或直接跑单条 SQL
sudo docker compose exec -T mysql sh -c 'exec mysql -uhexauth -p"$MYSQL_PASSWORD" hex_auth -e "SHOW TABLES;"'
```

> ⚠️ 不要把 3306 映射成 `0.0.0.0:3306` 或 `"3306:3306"`。一旦暴露公网，MySQL 会持续被
> 暴力破解扫描。必须直连时，也要配合安全组只放行你自己的出口 IP。

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

---

## 9. 部署故障速查（实战记录）

以下是首次部署中真实遇到过的故障，按出现顺序排列。遇到报错先查这张表。

### 9.1 命令/依赖缺失（最小化镜像常见）

| 报错 | 处理 |
| --- | --- |
| `sudo: certbot：找不到命令` | RHEL 系先启用 EPEL：`dnf install -y epel-release && dnf install -y certbot`；装不上就用 5.1 的 acme.sh 备选 |
| `bash: dig: 未找到命令` | 用系统自带的 `getent hosts auth.aaa.com`，或 `dnf install -y bind-utils` |
| `sudo: git：找不到命令` | `dnf install -y git`（最小化镜像默认没有） |
| `no configuration file provided: not found`（docker compose） | 不在项目目录，或部署脚手架还在未合并的分支上：`git checkout main && git pull`，确认 `ls docker-compose.yml` 存在 |

### 9.2 构建期网络问题

| 报错 | 原因与处理 |
| --- | --- |
| `Temporary failure in name resolution`（pip/npm） | 构建容器 DNS 解析失败：`/etc/resolv.conf` 指向 `127.0.0.53` 时，按第 3 节配置 `daemon.json` 的 `dns`，并在根 `.env` 启用 `PIP_INDEX_URL` / `NPM_REGISTRY` 镜像源 |
| `dial tcp ...docker.io... connection refused / i/o timeout` | Docker Hub 被墙/污染：`daemon.json` 配 `registry-mirrors`（实测可用：`https://docker.m.daocloud.io`、`https://docker.1ms.run`，阿里云个人加速器在部分网络下不生效） |
| `docker info` 有 Registry Mirrors，但 build 仍连 `registry-1.docker.io` | **BuildKit 不读取 `registry-mirrors`**。先 `docker pull` 预拉四个基础镜像，再用 `sudo env COMPOSE_DOCKER_CLI_BUILD=0 docker compose up -d --build` 走传统构建器 |
| 构建前端时 `Killed`（退出码 137） | 内存不足，按 1.1 加 swap；或本地构建 `docker save` 上传 |

### 9.3 Docker 守护进程启动失败

报错特征：

```
failed to start daemon: Error initializing network controller:
Failed to program NAT chain: ZONE_CONFLICT: 'docker0' already bound to a zone
```

原因：firewalld 与 Docker 争抢 `docker0` 网卡的 zone 归属。处理：

```bash
systemctl stop firewalld
systemctl disable firewalld            # 云服务器对外防线是安全组，可禁用 firewalld
ip link set docker0 down 2>/dev/null
ip link delete docker0 2>/dev/null     # 删除残留网卡，Docker 启动时会重建
systemctl reset-failed docker
systemctl start docker
systemctl status docker --no-pager | head -3   # 应为 active (running)
```

> 若必须保留 firewalld：`firewall-cmd --permanent --zone=docker --change-interface=docker0 && firewall-cmd --reload` 后再启动 Docker。
> 修改 `daemon.json` 后 Docker 起不来时，先 `python3 -m json.tool /etc/docker/daemon.json` 校验 JSON，再检查是否覆盖掉了原有配置。

### 9.4 数据库客户端连接（Navicat / DataGrip）

完整流程见「日常运维 → 用数据库客户端连接」。高频错误：

| 报错 | 层级 | 处理 |
| --- | --- | --- |
| `10061 connection refused` | TCP | MySQL 默认未映射端口，属正常；按运维章节开放 `127.0.0.1:3306` |
| `Access denied for 'password'. Authentication that can continue: publickey,...,password (31)` | **SSH** | SSH 认证失败：用户名必须是 `root`（不是 hexauth、不是 password），密码是**服务器 root 密码**；`hexauth` 是 MySQL 账号，不是 Linux 用户 |
| `Permission denied (publickey,gssapi-keyex,...)` | SSH | 密码错或 root 被禁止密码登录；不知道密码就在阿里云控制台「重置实例密码」并重启实例 |
| `1045 - Access denied for user 'root'@'172.19.0.1' (using password: NO)` | **MySQL** | SSH 已通（能到达 172.19.0.1 网桥即证明）；常规页没填密码：用户名 `hexauth`、密码取根 `.env` 的 `MYSQL_PASSWORD` |
| `1045 ... (using password: YES)` | MySQL | 密码发了但不对：核对 `MYSQL_PASSWORD`，注意复制别带行尾空格 |

> 两套凭据千万别混：**SSH 页 = 服务器 root + 服务器密码；常规页 = hexauth + MYSQL_PASSWORD**。

### 9.5 配置变更不生效

- 改 `backend/.env` 后 `docker compose restart` **无效**：env_file 只在容器创建时读取，
  必须 `docker compose up -d --force-recreate backend`
- 服务器上 `git pull` 显示「已是最新」但文件是旧的：你停在已合并的功能分支上，
  `git checkout main && git pull`；本地有改动先 `git stash` 或备份

### 9.6 SSH 层防护

多次密码输错后出现 `Connection timed out`：可能是 fail2ban/防爆破临时封禁，
等待几分钟后重试；或用阿里云控制台 VNC 登录执行 `fail2ban-client set sshd unbanip <你的IP>`（如部署了 fail2ban）。
