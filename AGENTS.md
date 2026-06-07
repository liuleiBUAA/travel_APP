# AGENTS.md - 找搭子小程序项目指南

> 给 AI Agent / 新开发者 / Claude Code 的项目入口文档

## 项目概览

**找搭子**（Travel Companion）—— 旅行路线生成 + 搭子匹配的全栈应用，支持网页版和微信小程序。

- **后端**：Python / FastAPI / SQLAlchemy / SQLite
- **小程序前端**：微信原生框架（WXML / WXSS / JS）
- **网页前端**：原生 HTML / CSS / JavaScript
- **路线引擎**：自研（travel_guide 模块，基于图搜索的多跳交通中转）

## 目录结构

```
travel_companion_miniapp/
├── backend/                # FastAPI 后端（端口 8000）
│   ├── main.py             # API 路由入口
│   ├── models.py           # SQLAlchemy 数据模型
│   ├── database.py         # SQLite 配置
│   └── services/
│       ├── auth_service.py     # 微信登录 + token
│       ├── route_service.py    # 路线生成（对接 travel_guide）
│       └── match_service.py    # 匹配算法
├── miniprogram/            # 微信小程序
│   ├── app.js/json/wxss    # 全局配置
│   ├── utils/api.js        # API 封装（BASE_URL 指向后端）
│   └── pages/
│       ├── index/          # 发布行程
│       ├── guide/          # 智能推荐 + 攻略
│       └── match/          # 匹配结果
├── frontend/               # 网页版（端口 9090）
│   └── index.html          # 单页应用
├── travel_guide/           # 路线引擎（独立 Python 模块）
│   ├── config/             # 配置
│   ├── data/               # 四大洲目的地+交通数据（JSON/CSV/MD）
│   └── src/                # 核心算法
│       ├── core/           # 路线规划 + 智能推荐
│       ├── data_query/     # 航班/地面交通查询
│       └── tools/          # 批量生成 + 验证工具
├── nginx/                  # Nginx 反向代理配置
├── docker-compose.yml      # Docker 部署
└── deploy.sh               # 部署脚本
```

## 技术约束（MUST FOLLOW）

### 后端规则
1. **API 路径**：所有接口以 `/api/` 开头
2. **返回格式**：统一 `{ "success": true/false, ... }`
3. **数据库**：SQLite，文件在 `backend/` 目录下
4. **依赖注入**：通过 `get_db()` 获取 session，用完必须 `db.close()`
5. **不要修改** `travel_guide/data/` 下的 JSON/CSV 数据文件
6. **不要修改** `miniprogram/project.config.json` 中的 AppID

### 小程序规则
1. **页面路由**：新增页面必须在 `app.json` 的 `pages` 数组中注册
2. **API 调用**：统一通过 `utils/api.js`，不要直接 `wx.request`
3. **登录状态**：通过 `app.globalData.userInfo` 获取，`wx.getStorageSync('token')` 获取 token
4. **setData 优化**：避免频繁调用 setData，合并更新
5. **包大小**：主包 2MB 以下，图片走 CDN

### 数据库模型
- **User**：id, openid, union_id, nickname, avatar_url, login_type, created_at
- **Companion**：id, user_id, user_name, route_json, travel_date, duration_days, seeking, transport_mode, accommodation, budget_level, good_at_photo, preferences, created_at

## 常用命令

```bash
# 启动后端
cd backend && pip install -r requirements.txt && python main.py

# 启动网页版前端
cd frontend && python -m http.server 9090

# 验证路线数据
cd travel_guide && python -m tools.verify_routes

# 批量生成路线
cd travel_guide && python -m tools.batch_generate
```

## API 端点速查

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/auth/wx-login | 微信登录 |
| POST | /api/auth/register | 网页注册 |
| POST | /api/auth/login | 网页登录 |
| GET  | /api/auth/me | 获取当前用户 |
| POST | /api/routes/generate | 生成路线（recommend/destination/manual） |
| POST | /api/companions/publish | 发布找搭子 |
| POST | /api/companions/match | 智能匹配 |
| GET  | /api/companions/list | 所有发布列表 |
| GET  | /api/companions/search | 关键词搜索 |
| GET  | /api/destinations/countries | 区域下的国家 |
| GET  | /api/destinations/cities | 国家下的城市 |
| GET  | /api/destinations/search | 城市搜索 |

## 部署环境变量

- `WX_MINI_APPID`：微信小程序 AppID
- `WX_MINI_SECRET`：微信小程序 AppSecret
- `TOKEN_SECRET`：JWT 签名密钥

## 生产环境

- 域名：`https://awesometravelpartner.cn`
- 部署：Docker + Nginx
- 小程序 `BASE_URL`：已指向生产域名
