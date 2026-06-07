# 找搭子 - 智能旅行匹配平台

旅行路线生成 + 搭子匹配的全栈应用，支持网页版和微信小程序。

---

## 核心功能

### 1. 智能路线引擎（travel_guide）

基于图搜索的自研路线规划引擎，支持三种生成模式：

| 模式 | 适用场景 | 输入 | 输出 | 依赖攻略库 |
|------|----------|------|------|------------|
| **recommend** 智能推荐 | 不知道去哪，让 AI 推荐 | 月份 + 天数 + 偏好标签 | 完整 day-by-day 行程 | ✅ 需要 |
| **destination** 选择城市 | 知道去哪，需要详细攻略 | 城市列表 | 完整 day-by-day 行程 | ✅ 需要 |
| **manual** 手动输入 | 已有行程，只找搭子 | 城市 + 天数 | 仅城市列表（无详细攻略） | ❌ 不需要 |

---

### 2. 路线生成原理

#### 2.1 recommend 模式（智能推荐）

**流程：**
```
用户输入（月份/天数/区域/标签）
    ↓
目的地评分系统（recommend_smart.py）
    ├─ 季节匹配度：+0.3（最佳季节）/ +0.1（全年）/ -0.2（淡季）
    ├─ 标签匹配度：用户标签 ∩ 目的地标签
    ├─ 天数适配度：目的地推荐天数 vs 用户总天数
    └─ 基础分：目的地热度权重
    ↓
排序 + 组合筛选（总天数约束）
    ↓
TravelEngine.plan() 生成详细行程
```

**评分公式：**
```python
总分 = 基础分 + 季节分 + 标签匹配分 + 天数适配分
```

**示例：**
- 输入：`month=7, days=10, region="Europe", tags=["海滩", "历史"]`
- 输出：希腊圣托里尼（海滩+历史，7-9月最佳）+ 雅典（历史，全年）

---

#### 2.2 destination 模式（指定城市）

**流程：**
```
用户输入城市列表：["巴黎", "阿姆斯特丹", "布鲁塞尔"]
    ↓
TravelEngine.plan()
    ├─ 1. 顺序优化（TSP 近似算法，避免回头路）
    ├─ 2. 交通时间计算（火车/自驾/飞机）
    ├─ 3. 依附城市处理（环线目的地自动衔接）
    └─ 4. 逐日行程构建
    ↓
输出：CSV + Markdown + JSON
```

**顺序优化算法（TSP 近似）：**
```python
def optimize_order_no_backtrack(cities, start=None, end=None):
    """
    贪心算法：每次选择距离当前城市最近的未访问城市
    - 支持指定起点/终点
    - 避免回头路（最小化总距离）
    """
    current = start or cities[0]
    remaining = set(cities) - {current}
    path = [current]

    while remaining:
        nearest = min(remaining, key=lambda c: distance(current, c))
        path.append(nearest)
        current = nearest
        remaining.remove(nearest)

    if end and end != path[-1]:
        path.remove(end)
        path.append(end)

    return path
```

**交通时间计算：**
- **火车**：直接查询 `transport_routes.json` 中的预设时间
- **自驾**：`距离(km) / 80 km/h`
- **飞机**：`飞行时间 + 1小时安检`
- **多跳中转**：自动计算 A→B→C 的最优路径（BFS 搜索）

**依附城市系统：**
```json
// city_dependencies.json
{
  "依附关系": {
    "奥地利湖区": "萨尔茨堡",
    "五渔村": "佛罗伦萨"
  }
}
```
- 环线目的地（如奥地利湖区）无法直接计算到其他城市的交通
- 通过"依附城市"（萨尔茨堡）自动衔接前后交通

---

#### 2.3 manual 模式（手动输入）

**特点：**
- 不调用 TravelEngine，直接存储用户输入的城市和天数
- 用于已有详细行程的用户，只需要找搭子
- 不生成 day-by-day 攻略

---

### 3. 新增参数（2026-04-06 更新）

#### 3.1 transport_preference（交通偏好）

**取值：**
- `auto`（默认）：自动选择最优交通方式
- `train`：优先火车（适合欧洲铁路通票用户）
- `flight`：优先飞机（适合长距离快速移动）

**实现原理：**
```python
# TravelEngine 实例属性（从 config.json 加载）
self.transport_preference = "auto"

# 临时覆盖（API 调用时）
_orig = self.engine.transport_preference
self.engine.transport_preference = request.transport_preference
try:
    plan_result = self.engine.plan(...)
finally:
    self.engine.transport_preference = _orig  # 恢复原值
```

**影响范围：**
- 交通方式选择逻辑（`_edge_min_time` 方法）
- 路线优化时的权重计算

---

#### 3.2 options_display_mode（显示模式）

**取值：**
- `compact`（默认）：精简模式，只显示核心信息
- `detailed`：详细模式，显示所有备选方案和交通细节

**实现原理：**
- 同 `transport_preference`，通过临时覆盖实例属性实现
- 控制输出 CSV/Markdown 的详细程度

---

#### 3.3 start_node / end_node（起终点指定）

**功能：**
- `start_node`：强制指定起点城市（覆盖顺序优化结果）
- `end_node`：强制指定终点城市（覆盖顺序优化结果）

**使用场景：**
- 用户从特定城市出发（如居住地）
- 需要在特定城市结束行程（如返程航班）

**实现：**
```python
def plan(self, name, raw_nodes, start_node=None, end_node=None, ...):
    # 1. 顺序优化时考虑起终点约束
    nodes = self._optimize_node_order(raw_nodes, start_node, end_node, force_order)
    # 2. 构建行程时自动添加到达日/离开日
    ...
```

---

### 4. 搭子匹配算法

#### 4.1 综合评分公式

```python
总分 = 路线相似度 × 40% + 时间匹配度 × 20% + 偏好匹配度 × 40%
```

#### 4.2 路线相似度（Jaccard + 顺序）

```python
def calculate_route_similarity(route_a, route_b):
    cities_a = set(route_a["cities"])
    cities_b = set(route_b["cities"])

    # 1. Jaccard 相似度（70%）
    overlap = cities_a & cities_b
    union = cities_a | cities_b
    jaccard_score = len(overlap) / len(union)

    # 2. 顺序相似度（20%）
    order_score = calculate_order_similarity(route_a, route_b, overlap)

    # 3. 天数相似度（10%）
    days_diff = abs(route_a["total_days"] - route_b["total_days"])
    days_score = max(0, 1 - days_diff / max(route_a["total_days"], route_b["total_days"]))

    return jaccard_score * 0.7 + order_score * 0.2 + days_score * 0.1
```

**关键优化：**
- 如果城市完全不重合（`overlap == 0`），直接返回 0（硬性过滤）

---

#### 4.3 硬性筛选条件

以下条件不满足时，直接过滤（不参与评分）：

| 条件 | 说明 |
|------|------|
| **性别要求** | 男/女/不限（不限可匹配所有） |
| **交通方式** | 混合可匹配所有，其他需一致 |
| **住宿安排** | 必须一致（酒店/民宿/青旅） |
| **消费水平** | 必须有交集（经济/中档/豪华） |
| **人数范围** | 必须有交集（如 2-4人 vs 3-5人 → 可匹配） |

---

### 5. 数据覆盖

| 区域 | 国家数 | 城市数 | 目的地数 | 交通路线数 |
|------|--------|--------|----------|------------|
| 欧洲 | 30+ | 200+ | 150+ | 500+ |
| 亚洲 | 15+ | 100+ | 80+ | 200+ |
| 北美 | 2 | 50+ | 40+ | 100+ |
| 大洋洲 | 2 | 30+ | 25+ | 50+ |

**数据文件结构：**
```
travel_guide/data/
├── Europe/
│   ├── city_coordinates.json       # 城市坐标（经纬度）
│   ├── city_mapping.json           # 城市别名映射
│   ├── city_dependencies.json      # 依附关系
│   ├── transport_routes.json       # 交通时间数据库
│   └── Europe_destinations.json    # 目的地攻略库
├── Asia/
├── North_America/
└── Oceania/
```

---

## 技术架构

### 后端（FastAPI + SQLAlchemy）

```
backend/
├── main.py                    # FastAPI 入口 + 路由定义
├── models.py                  # SQLAlchemy 数据模型
├── database.py                # 数据库连接
├── services/
│   ├── route_service.py       # 路线生成服务（调用 TravelEngine）
│   ├── match_service.py       # 匹配算法服务
│   ├── auth_service.py        # 用户认证服务
│   └── companion_service.py   # 搭子发布/搜索服务
└── harness/                   # Harness 守卫系统
    ├── __init__.py            # HarnessHooks 类
    └── lessons-learned.md     # 经验教训库
```

**Harness 守卫系统：**
- `@harness.api_guard` 装饰器：自动计时 + 返回格式验证 + 异常捕获
- 权限边界（PermissionBoundary）：循环检测、操作约束
- 自定义 Hook：`after_api_call`（敏感字段检测）、`on_error`（错误记录）
- 健康检查端点：`/api/harness/health`、`/api/harness/metrics`

---

### 前端（原生 HTML/JS + 微信小程序）

**网页版（frontend/index.html）：**
- 纯原生实现，无框架依赖
- 三种模式切换：智能推荐 / 选择城市 / 手动输入
- 实时路线生成 + 搭子匹配

**微信小程序（miniprogram/）：**
- 原生 WXML/WXSS/JS
- 微信登录（wx.login() → code 换 token）
- 与网页版共用后端 API

---

### 路线引擎（travel_guide）

```
travel_guide/
├── src/
│   ├── core/
│   │   ├── route_planner.py       # TravelEngine 核心引擎
│   │   ├── recommend_smart.py     # 智能推荐系统
│   │   ├── route_validator.py     # 路线数据验证
│   │   └── utils.py               # 工具函数
│   └── tools/
│       ├── batch_generate.py      # 批量生成路线
│       └── verify_routes.py       # 验证路线数据
├── data/                          # 各区域数据文件
└── config.json                    # 全局配置
```

**config.json 配置项：**
```json
{
  "same_day_max_hours": 4.0,           // 同日最大交通时间（小时）
  "force_gateway_departure": true,     // 强制从门户城市出发
  "transport_preference": "auto",      // 交通偏好（auto/train/flight）
  "options_display_mode": "compact",   // 显示模式（compact/detailed）
  "check_low_freq_flights": false      // 是否联网查询低频航班
}
```

---

## API 接口

### 路线生成

**POST** `/api/routes/generate`

**请求体：**
```json
{
  "mode": "recommend",                    // recommend / destination / manual
  "month": 7,                             // 月份（recommend 模式）
  "days": 10,                             // 总天数
  "region": "Europe",                     // 区域
  "tags": ["海滩", "历史"],               // 标签（recommend 模式）
  "cities": ["巴黎", "阿姆斯特丹"],       // 城市列表（destination/manual 模式）
  "start_city": "巴黎",                   // 起点城市（recommend 模式）
  "start_node": "巴黎",                   // 起点城市（destination 模式）
  "end_node": "布鲁塞尔",                 // 终点城市（destination 模式）
  "force_order": false,                   // 是否强制按输入顺序
  "transport_preference": "auto",         // 交通偏好（auto/train/flight）
  "options_display_mode": "compact"       // 显示模式（compact/detailed）
}
```

**响应：**
```json
{
  "success": true,
  "route": {
    "cities": ["巴黎", "阿姆斯特丹", "布鲁塞尔"],
    "total_days": 10,
    "itinerary": [
      {
        "day": 0,
        "type": "arrival",
        "city": "巴黎",
        "description": "抵达巴黎"
      },
      {
        "day": 1,
        "type": "stay",
        "city": "巴黎",
        "attractions": ["埃菲尔铁塔", "卢浮宫"],
        "description": "游览巴黎市区"
      },
      ...
    ],
    "csv_path": "/path/to/route.csv",
    "md_path": "/path/to/route.md"
  }
}
```

---

### 搭子匹配

**POST** `/api/companions/match`

**请求体：**
```json
{
  "route_id": 123,
  "min_score": 0.6
}
```

**响应：**
```json
{
  "success": true,
  "matches": [
    {
      "companion_id": 456,
      "user": {
        "nickname": "旅行者A",
        "gender": "female"
      },
      "route": {
        "cities": ["巴黎", "阿姆斯特丹"],
        "total_days": 8
      },
      "score": 0.85,
      "breakdown": {
        "route_similarity": 0.9,
        "time_match": 0.8,
        "preference_match": 0.85
      }
    }
  ]
}
```

---

## 部署

### Docker 部署（推荐）

```bash
# 1. 构建镜像
docker-compose build

# 2. 启动服务
docker-compose up -d

# 3. 查看日志
docker-compose logs -f backend
```

**服务端口：**
- 后端 API：`http://localhost:8000`
- 网页前端：`http://localhost:80`
- Nginx：`http://localhost:443`（HTTPS）

---

### 本地开发

**后端：**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**前端：**
```bash
cd frontend
python -m http.server 8080
```

**小程序：**
1. 安装微信开发者工具
2. 导入 `miniprogram/` 目录
3. 修改 `miniprogram/config.js` 中的 API 地址

---

## 命令行工具

```bash
cd travel_guide

# 直接规划路线
python -m src.core.cli 巴黎 阿姆斯特丹 布鲁塞尔

# 批量生成推荐路线
python -m src.tools.batch_generate

# 验证路线数据
python -m src.tools.verify_routes
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.10+ / FastAPI / SQLAlchemy / SQLite |
| 网页前端 | 原生 HTML / CSS / JavaScript（无框架） |
| 小程序 | 微信原生框架（WXML / WXSS / JS） |
| 路线引擎 | 自研（图搜索 + TSP 近似 + 多跳中转 + 依附城市系统） |
| 部署 | Docker + Nginx + docker-compose |

---

## 开发日志

- **2026-04-03**：初始版本，三种路线生成模式
- **2026-04-06**：新增 `transport_preference`、`options_display_mode`、`start_node`/`end_node` 参数，四层全部同步（route_service → main.py → frontend → miniprogram）

---

## 许可证

MIT License
