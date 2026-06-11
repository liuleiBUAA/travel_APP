# 部署操作手册

> 在**有 SSH 密钥的笔记本**上执行（EC2 出不去 22 端口，不能直连服务器）。
> 密钥等敏感值一律不写进本文件——以 `<占位符>` 表示，执行时手动替换。

## 0. 本次部署特别步骤（2026-06-11 交换微信版本，做完可删除本节）

本版本包含：旅行名片/留言独立页、交换微信申请制、收掉帖子明文微信号。
**微信 AppSecret 已重置**，部署时必须同步更新服务器配置，步骤揉在下面第 1-2 节里，按顺序执行即可。

## 1. 服务器上拉代码 + 迁移

```bash
ssh root@111.229.241.225

# -- 以下在服务器上执行 --
# 首次：克隆仓库（公开仓库，无需凭证）；以后：git pull 即可
cd /opt
git clone https://github.com/liuleiBUAA/travel_APP.git travel_APP_repo 2>/dev/null \
  || (cd travel_APP_repo && git fetch origin)
cd /opt/travel_APP_repo
git checkout feature/profile-and-comments
git pull origin feature/profile-and-comments

# 覆盖后端代码（cp 不会动服务器独有的 harness 模块）
cp -r backend/* /opt/travel_companion_miniapp/backend/

# 同步景点图片（行程配图功能，2026-06-11 起）
mkdir -p /opt/travel_companion_miniapp/travel_guide/data/images
cp -r travel_guide/data/images/* /opt/travel_companion_miniapp/travel_guide/data/images/

# 同步玩法/城市攻略（详情页内容，2026-06-11 起）
mkdir -p /opt/travel_companion_miniapp/travel_guide/data/playbooks
cp -r travel_guide/data/playbooks/* /opt/travel_companion_miniapp/travel_guide/data/playbooks/

# 跑迁移（都幂等，重复跑无害）
cd /opt/travel_companion_miniapp/backend
python3 migrate_add_user_profile_comments.py
python3 migrate_add_contact_exchange.py
```

## 2. 更新环境变量（本次必做：Secret 已重置）

```bash
# 仍在服务器上
nano /opt/travel_companion_miniapp/backend/.env
```

确保以下三行存在且为新值：

```
WX_MINI_APPID=wx781c464fc0568970
WX_MINI_SECRET=<微信后台刚重置的新Secret，从mp.weixin.qq.com复制>
TOKEN_SECRET=<新随机值，用下面命令生成>
```

生成 TOKEN_SECRET：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

> 换 TOKEN_SECRET 会让所有用户重新登录一次，预期内。
> ⚠️ 新 Secret 只许出现在服务器的 .env 里，不要写进任何会 commit 的文件。

## 3. 重启后端服务

```bash
pkill -f 'uvicorn main:app'; sleep 1
cd /opt/travel_companion_miniapp/backend
nohup /usr/bin/python3 /usr/local/bin/uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/travel_api.log 2>&1 &
sleep 3 && tail -20 /tmp/travel_api.log   # 确认无报错
```

### 验证

```bash
curl -s "https://awesometravelpartner.cn/api/companions/list?limit=3" | python3 -m json.tool
# 详情接口不应再返回 contact_wechat 字段：
curl -s "https://awesometravelpartner.cn/api/companions/1" | grep -c contact_wechat   # 期望输出 0
# 景点图片可访问（期望 200 + image/jpeg）：
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" "https://awesometravelpartner.cn/api/static/attractions/法国/巴黎/卢浮宫_1.jpg"
# 行程带 images 字段：
curl -s -X POST "https://awesometravelpartner.cn/api/routes/generate" -H "Content-Type: application/json" -d '{"cities":["巴黎"]}' | grep -c '"images"'   # 期望 > 0
# 玩法详情接口（期望返回 success: true）：
curl -s "https://awesometravelpartner.cn/api/attractions/playbook?name=巴黎" | grep -c success   # 期望 1
```

小程序侧：退出登录 → 重新微信登录（验证新 Secret）→ 名片填微信号 → 留言 → 申请交换微信 → 对方在「我的搭子」同意 → 互见微信号。

### 查看日志（排错用）

```bash
ssh root@111.229.241.225 "tail -50 /tmp/travel_api.log"
```

---

## 4. 更新小程序前端

1. 打开**微信开发者工具**
2. 导入项目，选择 `miniprogram/` 目录
3. AppID: `wx781c464fc0568970`
4. 点击"编译"确认功能正常
5. 点击右上角**"上传"**
6. 填写版本号（如 `1.1.0`）和描述
7. 登录 [微信公众平台](https://mp.weixin.qq.com/) → 管理 → 版本管理
8. 找到刚上传的版本 → 点击**"选为体验版"**
9. 扫体验版二维码测试

---

## 服务器信息

| 项目 | 值 |
|------|-----|
| 服务器 IP | `111.229.241.225` |
| SSH | `ssh root@111.229.241.225`（密钥在个人笔记本） |
| 后端运行路径 | `/opt/travel_companion_miniapp/backend/` |
| git 仓库路径 | `/opt/travel_APP_repo/`（部署源，从 GitHub 拉取） |
| API 地址 | `https://awesometravelpartner.cn/api/` |
| 端口 | 8000 |
| 数据库 | SQLite (`travel_companion.db`) |
| 环境变量 | `/opt/travel_companion_miniapp/backend/.env`（敏感值只存这里） |

## 日常部署流程（以后每次）

```
EC2 写代码 → push GitHub → 笔记本 ssh 上服务器 → git pull → cp 覆盖 → (有迁移则跑迁移) → 重启 uvicorn → 验证
```
