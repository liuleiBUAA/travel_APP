# 找搭子 - 智能旅行匹配小程序

旅行路线生成 + 搭子匹配的微信小程序，基于 FastAPI 后端。

---

## 快速开始（换机器操作指南）

### 1. 克隆代码

```bash
git clone https://github.com/liuleiBUAA/travel_APP.git
cd travel_APP
```

### 2. 微信开发者工具打开项目

1. 打开微信开发者工具
2. 导入项目，选择 `miniprogram/` 目录
3. AppID 填入：`wx781c464fc0568970`（已在 project.config.json 配置）
4. 点击"编译"即可预览

### 3. 上传小程序体验版

1. 在微信开发者工具里点击右上角 **"上传"**
2. 填写版本号（如 `1.0.2`）和版本描述
3. 登录 [微信公众平台](https://mp.weixin.qq.com/) → 管理 → 版本管理
4. 找到刚上传的版本 → 点击"选为体验版"
5. 在体验版页面获取体验版二维码，扫码即可测试

### 4. 推送代码到 GitHub

```bash
cd /path/to/travel_APP
git add .
git commit -m "feat: 描述你的修改"
git push origin main
```

如果 push 失败（网络问题），开 VPN 后重试。

---

## 项目配置信息

### 微信小程序

| 配置项 | 值 |
|--------|-----|
| AppID | `wx781c464fc0568970` |
| 域名 | `awesometravelpartner.cn` |
| 请求域名(request) | `https://awesometravelpartner.cn` |

### 后端服务器

| 配置项 | 值 |
|--------|-----|
| 服务器 IP | `111.229.241.225` |
| SSH 登录 | `ssh root@111.229.241.225` |
| 后端路径 | `/opt/travel_companion_miniapp/backend/` |
| API 地址 | `https://awesometravelpartner.cn/api/` |
| 进程管理 | uvicorn (手动 nohup) |
| 端口 | 8000 |
| Nginx | 反向代理 443→8000 |
| SSL 证书 | Let's Encrypt (自动续期) |
| 数据库 | SQLite (`travel_companion.db`) |

### 后端环境变量（服务器 /opt/travel_companion_miniapp/backend/.env）

```env
WX_MINI_APPID=wx781c464fc0568970
WX_MINI_SECRET=<从微信公众平台获取，不要提交到git>
```

### GitHub 仓库

| 配置项 | 值 |
|--------|-----|
| 仓库地址 | `https://github.com/liuleiBUAA/travel_APP.git` |
| 默认分支 | `main` |

---

## 后端部署操作

### 部署代码到服务器

```bash
# 上传单个文件
scp backend/main.py root@111.229.241.225:/opt/travel_companion_miniapp/backend/main.py

# 上传整个后端目录
scp -r backend/ root@111.229.241.225:/opt/travel_companion_miniapp/backend/
```

### 重启后端服务

```bash
ssh root@111.229.241.225 "pkill -f 'uvicorn main:app' && sleep 1 && cd /opt/travel_companion_miniapp/backend && nohup /usr/bin/python3 /usr/local/bin/uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/travel_api.log 2>&1 &"
```

### 查看后端日志

```bash
ssh root@111.229.241.225 "tail -50 /tmp/travel_api.log"
```

### 测试 API 是否正常

```bash
curl -s "https://awesometravelpartner.cn/api/companions/list?limit=3" | python3 -m json.tool
```

---

## 项目结构

```
travel_APP/
├── miniprogram/                 # 微信小程序前端
│   ├── app.js                   # 全局逻辑（自动登录）
│   ├── app.json                 # 页面注册、tabBar
│   ├── app.wxss                 # 全局样式
│   ├── utils/
│   │   └── api.js               # API 请求封装
│   ├── pages/
│   │   ├── index/               # 发布行程页
│   │   ├── guide/               # 路线攻略页
│   │   ├── match/               # 找搭子页
│   │   ├── profile/             # 我的页面
│   │   └── trip-detail/         # 行程详情页
│   └── images/tabbar/           # tabBar 图标
├── backend/                     # FastAPI 后端
│   ├── main.py                  # 主入口（所有 API 路由）
│   ├── models.py                # 数据库模型
│   ├── database.py              # 数据库连接
│   ├── requirements.txt         # Python 依赖
│   ├── services/
│   │   ├── auth_service.py      # 认证服务
│   │   ├── route_service.py     # 路线生成
│   │   └── match_service.py     # 匹配算法
│   └── .env                     # 环境变量（不提交到git）
├── travel_guide/                # 路线数据和算法
├── project.config.json          # 小程序项目配置
└── README.md                    # 本文件
```

---

## API 接口列表

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | /api/auth/wx-login | 微信登录 | 否 |
| GET | /api/auth/me | 获取当前用户 | 是 |
| POST | /api/auth/update-profile | 更新资料 | 是 |
| GET | /api/destinations/countries | 获取国家列表 | 否 |
| GET | /api/destinations/cities | 获取城市列表 | 否 |
| GET | /api/destinations/search | 搜索目的地 | 否 |
| POST | /api/routes/generate | 生成路线 | 否 |
| POST | /api/companions/publish | 发布行程 | 是 |
| POST | /api/companions/match | 匹配搭子 | 否 |
| GET | /api/companions/list | 获取发布列表 | 否 |
| GET | /api/companions/search | 搜索搭子 | 否 |
| GET | /api/companions/my | 获取我的行程 | 是 |
| GET | /api/companions/{id} | 行程详情 | 否 |

认证方式：HTTP Header `Authorization: <token>`

---

## 常见问题

### 真机扫码后功能异常

1. 确保域名已在微信公众平台配置：设置 → 开发设置 → 服务器域名 → request合法域名添加 `https://awesometravelpartner.cn`
2. 确保 SSL 证书有效：`curl -I https://awesometravelpartner.cn`
3. 开发者工具的 `urlCheck: false` 只对开发者工具有效，真机会严格校验

### 发布行程后看不到

确保已登录（token 有效）。退出登录重新进入会自动重新登录获取新 token。

### push 到 GitHub 失败

网络问题，开 VPN 后重试 `git push origin main`。

### 后端服务挂了

```bash
ssh root@111.229.241.225 "ps aux | grep uvicorn | grep -v grep"
# 如果没有进程在运行：
ssh root@111.229.241.225 "cd /opt/travel_companion_miniapp/backend && nohup /usr/bin/python3 /usr/local/bin/uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/travel_api.log 2>&1 &"
```
