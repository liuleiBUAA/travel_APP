# 安全部署配置说明

## 必须配置的环境变量

### 1. TOKEN_SECRET（必须修改）

**当前问题：** 使用源码硬编码的默认值 `travel-companion-dev-secret-change-me`，任何人读源码就能伪造 token。

**修复方法：**

在服务器上设置环境变量（以 systemd 为例）：

```bash
# 编辑 systemd service 文件
sudo vim /etc/systemd/system/travel-companion.service

# 添加环境变量（使用下面生成的强随机密钥）
[Service]
Environment="TOKEN_SECRET=bcA1oShGbDvM5_F6BA8uDRJeTgcH7ufg92aosFqori4"
Environment="WX_MINI_APPID=你的小程序APPID"
Environment="WX_MINI_SECRET=你的小程序SECRET"

# 重新加载并重启服务
sudo systemctl daemon-reload
sudo systemctl restart travel-companion
```

**重要提示：** 更改 TOKEN_SECRET 后，所有现有 token 会失效，用户需要重新登录。

---

## 2. 微信小程序配置

```bash
# 在微信公众平台获取
WX_MINI_APPID=wxXXXXXXXXXXXXXXXX
WX_MINI_SECRET=你的小程序密钥
```

---

## 3. CORS 白名单

已修复为白名单模式，当前允许的域名：
- `https://ht.awesometravelpartner.cn`
- `https://awesometravelpartner.cn`
- `http://localhost:8080` (开发用)
- `http://localhost:3000` (开发用)

如需添加新域名，修改 `backend/main.py` 中的 `ALLOWED_ORIGINS` 列表。

---

## 安全修复清单

✅ **已修复：**
- [x] 统一鉴权中间件：所有需要身份的接口从 token 解析 user_id
- [x] publish 接口：不再信任请求体的 user_id
- [x] my 接口：从 token 获取 user_id
- [x] membership 接口：从 token 获取 user_id
- [x] CORS 白名单：移除 `allow_origins=["*"]`
- [x] TOKEN_SECRET 配置说明：提供强随机密钥

⚠️ **仍需注意：**
- [ ] 支付接口是 stub，直接返回成功（生产环境必须接入真实微信支付）
- [ ] 网页版 XSS（如果使用 frontend/index.html）
- [ ] 密码哈希较弱（如果使用网页版注册）

---

## 部署检查清单

部署到服务器前，确认：

1. [ ] 已设置强随机 TOKEN_SECRET
2. [ ] 已配置正确的 WX_MINI_APPID 和 WX_MINI_SECRET
3. [ ] CORS 白名单只包含你的域名
4. [ ] 小程序前端修改了 API 调用（见下文）

---

## 前端适配修改

由于后端接口改为强制鉴权，前端需要确保所有请求都带 Authorization header。

**已修改的接口（需要登录）：**
- `POST /api/companions/publish`
- `GET /api/companions/my`
- `GET /api/membership/status`
- `POST /api/membership/buy`

前端 `api.js` 已正确配置 Authorization header，无需修改。

---

## 生成新的强随机密钥

如需生成新密钥：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

每次生成都不同，选一个记录到环境变量中。
