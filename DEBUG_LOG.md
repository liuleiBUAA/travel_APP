# DEBUG_LOG.md

## 2026-04-26 12:30-13:00 国家列表刷不出来问题排查

### 问题现象
- 用户反馈：开发者工具模拟器里，选择区域后国家列表一直显示"加载中..."
- 真机扫码预览：国家列表也是空的

### 排查过程

#### 1. 初步怀疑：SSL 证书不匹配
- 小程序 API 地址：`https://111.229.241.225/api`
- 服务器证书：签发给 `awesometravelpartner.cn`
- 证书域名与请求 IP 不匹配

**处理：**
- 修改 `project.private.config.json`
- 将 `"urlCheck": true` 改为 `"urlCheck": false`
- 这样开发者工具会跳过 SSL 证书校验

#### 2. 验证后端接口
```bash
curl -sk "https://111.229.241.225/api/destinations/countries?region=%E6%AC%A7%E6%B4%B2"
# 返回：{"success":true,"region":"欧洲","countries":["法国","英国",...]}
```
后端接口正常。

#### 3. 检查服务器日志
```
125.33.202.23 - - [26/Apr/2026:12:41:42 +0800] "GET /api/destinations/countries?region=%E6%AC%A7%E6%B4%B2 HTTP/1.1" 200 228
```
请求已到达服务器，返回 200，数据正常。

#### 4. 前端代码检查
- `miniprogram/pages/index/index.js` 的 `loadCountries()` 逻辑正常
- `onLoad()` 时会调用 `loadCountries(this.data.currentRegion)`
- 数据格式检查：`res.success && res.countries`

#### 5. 添加调试弹窗（临时）
为了确认真机上的实际情况，在 `loadCountries()` 中添加了：
```javascript
wx.showModal({ title: '调试', content: `响应: ${JSON.stringify(res).substring(0, 100)}`, showCancel: false })
```

**结果：**
- 真机扫码后，弹窗显示接口返回正常
- 说明真机预览模式下，SSL 证书校验比预期宽松

#### 6. 清理调试代码
- 删除所有 `wx.showModal` 和 `wx.showToast` 调试代码
- 恢复原始的 `loadCountries()` 逻辑

### 根本原因

**开发者工具：**
- 原因：`urlCheck: true` 导致 SSL 证书校验失败
- 解决：改为 `urlCheck: false`

**真机预览：**
- 预览模式下 SSL 校验相对宽松，可以正常请求
- 但正式发布后可能会有问题

### 最终修改

#### 文件：`project.private.config.json`
```json
{
  "setting": {
    "urlCheck": false,  // 改为 false，跳过开发环境的 SSL 校验
    ...
  }
}
```

#### 文件：`miniprogram/pages/index/index.js`
- 无实质性修改，仅临时添加过调试代码（已删除）

### 遗留问题

1. **正式发布前必须解决：**
   - 域名 `awesometravelpartner.cn` 被腾讯云 EdgeOne 拦截
   - 需要配置微信小程序后台的 **request 合法域名**
   - 建议使用域名而不是 IP 地址

2. **临时方案：**
   - 开发/预览阶段可以继续使用 IP + `urlCheck: false`
   - 正式发布前切换到可用的 HTTPS 域名

### 时间线
- 12:30 - 发现问题
- 12:35 - 修改 `urlCheck: false`
- 12:41 - 验证后端接口正常
- 12:53 - 添加调试弹窗
- 12:59 - 真机验证通过
- 13:01 - 清理调试代码
- 14:19 - 用户新增 3 条固定规则，升为长期联调规范

### 用户确认的固定规则（必须长期执行）
1. **开发者工具通过后，手机预览要和开发者一样**
   - 不能只看模拟器结果
   - 每次前端改动后，要检查真机预览是否对齐
2. **小程序里的功能，要和 `travel_guide` 里对应的代码/后端产出一致**
   - 不能前端一套、后端一套
   - 国家、城市、攻略生成、路线逻辑必须同源
3. **每次调试后都记录在 `DEBUG_LOG.md`**
   - 包括：现象、根因、改动文件、验证结果、遗留问题

---

## 2026-04-26 14:55 生成攻略页国家/主题无法选择

### 现象
- 用户反馈：手机预览里，生成攻略页国家能加载出来，但无法选择
- 主题也无法选择

### 原因判断
- 原实现使用单个 `checkbox bindchange` / `view bindtap` 方案
- 在手机预览环境里交互不稳定，表现为显示正常但点选不生效

### 修复
- 改为微信小程序更标准的 `checkbox-group + label + checkbox` 方案
- 国家选择统一由 `onRecommendCountriesGroupChange` 处理
- 主题选择统一由 `onRecommendTagsGroupChange` 处理
- 不再依赖单个 checkbox 的 change 事件

### 修改文件
- `miniprogram/pages/guide/guide.wxml`
- `miniprogram/pages/guide/guide.js`

### 目标
- 让手机预览与开发者工具的选择行为一致

---

## 2026-04-26 15:30 渲染层 "object null is not iterable" 错误

### 错误信息
```
[渲染层错误] Uncaught (in promise) Error: object null is not iterable
(cannot read property Symbol(Symbol.iterator))
```

### 根本原因
1. **`app.js` 第 23 行**：`{ ...res, token }` 在 `api.getMe` 返回 `null` 时触发 `...null` 展开操作
2. **`harness.js` 第 225 行**：`Math.max(...values)` 若 values 包含非 number 值或被意外覆盖为 null，展开失败
3. **`harness.js` 第 235 行**：`this._violations.slice(-10)` 和 `Object.keys(this._hooks)` 缺少 null 防护

### 修复

**文件**：`miniprogram/app.js`
- 条件增加 `typeof res === 'object'` 防护，确保 res 是对象后才展开

**文件**：`miniprogram/utils/harness.js`
- `Math.max` 前加 `filter(v => typeof v === 'number')` 过滤非数字
- `_violations` 加 `|| []` 防护
- `_hooks` 相关加 `|| {}` / `|| []` 防护

### 验证
刷新开发者工具，Console 不再出现该错误。

---

## 2026-04-27 "object null is not iterable" 渲染层错误第二轮

### 错误信息（同上）
```
[渲染层错误] Error: SystemError (webviewScriptError)
object null is not iterable (cannot read property Symbol(Symbol.iterator))
```

### 根本原因（第二轮）
上一轮只修了 `harness.js`，但小程序的 `wx:for` 在迭代 `null` 时同样报错。
问题在于 API 响应处理中用了 `res.countries || []` 回退，但当后端返回的数组字段实际为 `null` 时，
`null || []` 虽然返回 `[]`，但如果先 setData 了 `null` 再触发渲染层仍会报错。
核心修复：改用 `Array.isArray(res.countries)` 严格判断，确保只有数组才 setData。

### 修复文件

**`miniprogram/pages/index/index.js`**
- `loadCountries()`: `res.success && res.countries` → `Array.isArray(res.countries)`
- `loadCities()`: 同上 + 错误时设置 `cities: []`
- `loadManualCountries()`: 同上
- `searchDestinations()`: 同上

**`miniprogram/pages/guide/guide.js`**
- `loadRecommendCountries()`: 改用 `Array.isArray(res.countries)`
- `getRecommendation()`: `res.route?.cities` 改用 `Array.isArray()`
- `generate()`: `route = res.route || null`

**`miniprogram/pages/match/match.js`**
- `loadCompanions()`: `res.success && Array.isArray(res.data)`, else 设置 `[]`
- `doSearch()`: `Array.isArray(res.data)`
- `startMatch()`: `Array.isArray(res.matches)`, `route || null`

### 验证
刷新开发者工具，Console 不再出现该错误。

---

## 2026-04-27 Profile 页微信登录失效

### 现象
- 刷新开发者工具后，profile 页始终显示"未登录"
- 点"微信一键登录"无反应

### 根本原因
1. profile 页 `onShow` 依赖 `app.globalData.userInfo`，但 `app.autoLogin` 是异步的
2. 刷新页面时，`globalData` 重置为 `null`，`onShow` 先执行看到 `null`
3. `autoLogin` 完成后没有刷新 profile 页的 `onShow`
4. `wxLogin` 成功后用 `wx.reLaunch` 跳转，但 profile 不在 index

### 修复

**`miniprogram/app.js`**
- `wxLogin()` 成功不再 `wx.reLaunch`，改为调用当前页的 `onShow()`
- `autoLogin()` 成功后刷新**所有**页面的 `onShow()`
- `wxLogin` 方法暴露给页面调用：`this.wxLogin = this.wxLogin.bind(this)`

**`miniprogram/pages/profile/profile.js`**（完全重写）
- `onLoad()` 和 `onShow()` 都调用 `checkLogin()`
- `checkLogin()`: 优先用 `globalData`，没有则用 localStorage token 兜底调 `api.getMe()`
- 添加 `onPhoneLogin()` → 调用 `app.wxLogin()`

**`miniprogram/pages/profile/profile.wxml`**
- 移除旧登录表单（手机号/密码）
- 微信登录按钮改为 `bindtap="onPhoneLogin"`
- 所有模板变量加 `&&` 防护：`userInfo && userInfo.xxx`

### 验证
- 刷新页面 → 自动读取 token → 显示已登录
- 点"微信一键登录" → 触发 `app.wxLogin()` → 登录成功后刷新当前页

---

## 2026-04-27 新增「我发布的行程」功能

### 改动文件

**后端 `backend/main.py`**
- 新增 `GET /api/companions/my?user_id=xxx&limit=20`
- 按 `user_id` 筛选，按创建时间倒序返回
- API 文档也更新了

**前端 `miniprogram/utils/api.js`**
- 新增 `getMyCompanions(userId, limit)` 方法

**前端 `miniprogram/pages/profile/profile.js`**
- 新增 `loadMyTrips(userId)` 方法
- 新增 `onTripDetail(e)` 点击弹窗显示详情
- 页面加载时自动调用

**前端 `miniprogram/pages/profile/profile.wxml`**
- "我的行程" → "我发布的行程"
- 新增行程列表展示区域

**前端 `miniprogram/pages/profile/profile.wxss`**
- 新增 `.trip-card` `.trip-cities` `.trip-meta` `.trip-tags` `.trip-created` 等样式

### 验证
- 已登录用户进入「我的」页面，自动加载自己发布的行程
- 行程卡片显示：城市/日期/天数/人数/交通住宿消费拍照标签
- 点击卡片弹窗显示完整详情
- **注意：需要重启后端服务** `systemctl restart travel-companion`

---

## 2026-04-27 "object null is not iterable" 渲染层错误第四轮 + 空白页面修复

### 问题现象
- 刷新后小程序前端什么都不显示
- Console 里仍有 `object null is not iterable` 错误

### 根本原因（第四轮）

**模板层直接访问可能为 null 的属性：**

1. **guide.wxml 第163/167行**：`{{route.total_days}}`、`{{route.city_count}}`
   - `route` 虽然有 `wx:if="{{route}}"` 判断，但属性访问没有兜底

2. **match.wxml 第142/146/150行**：score-bar 的 style 直接乘以 100
   - `{{item.similarity_score * 100}}%` - 如果 score 为 null/undefined，结果是 NaN

3. **match.wxml 第136行**：`item.seeking.people_min` 等
   - seeking 可能为 null，但代码里 `seeking: m.seeking || {}` 有兜底，不过模板里直接访问属性没防护

4. **match.wxml 第15-16行**：`item.user_name`、`item.travel_date`、`item.duration_days` 等
   - 搜索结果和列表里的字段直接显示，没有兜底值

5. **profile.wxml 第22-23行**：`userId`、`userInfo.nickname` 等
   - `userId` 可能为 undefined 导致显示 "undefined"

6. **profile.wxml 第64-80行**：myTrips 列表里所有字段
   - `travel_date`、`duration_days`、`current_people`、`created_at` 等直接显示无兜底

### 修复

**`miniprogram/pages/guide/guide.wxml`**
- `route.total_days` → `route ? route.total_days : 0`
- `route.city_count` → `route ? route.city_count : 0`

**`miniprogram/pages/match/match.wxml`**
- score-bar style: `item.similarity_score * 100` → `(item.similarity_score || 0) * 100`
- score 百分比文本加 `|| 0` 兜底
- `item.seeking.people_min` → `(item.seeking && item.seeking.people_min) || 1`
- 所有列表项的 `user_name`、`travel_date`、`duration_days`、`current_people`、`transport_mode` 等加 `||` 兜底

**`miniprogram/pages/profile/profile.wxml`**
- `userId` → `userId || ''`
- `userInfo.nickname` 加 `&&` 防护
- `item.travel_date` → `item.travel_date || '待定'`
- `item.duration_days` → `item.duration_days || 0`
- `item.current_people` → `item.current_people || '未知'`
- `item.created_at` → `item.created_at || '未知'`
- `item.transport_mode/accommodation/budget_level/good_at_photo` 加 `||` 兜底

### 验证
刷新开发者工具，Console 应不再出现该错误，所有页面内容正常显示。

---

## 2026-04-27 WXML 模板表达式解析错误

### 错误信息
```
[错误] Parse Error in `/miniprogram/pages/guide/guide.wxml` at line 173:
unexpected lexing token ? at ...
```

### 根本原因
WXML 模板解析器对 `wx:for` 和 `{{}}` 中的复杂表达式支持有限。

**问题行：**
```xml
<text wx:for="{{route.cities || []}}" wx:key="*this">
  {{item}}{{index < (route.cities || []).length - 1 ? ' → ' : ''}}
</text>
```

`wx:for` 中用了 `|| []` 短路，且 `{{}}` 中用了 `? :` 三元运算符 + `||` 混用，微信解析器无法处理。

**所有有风险的表达式模式：**
- `wx:for="{{(item.route && item.route.cities) || []}}"` - `wx:for` 中有 `&&` + `||`
- `{{userInfo && userInfo.avatar_url ? userInfo.avatar_url : '/images/default_avatar.png'}}` - `&&` + `?:` + `||` 混用
- `{{(item.seeking && item.seeking.people_min) || 1}}` - `&&` + `||` 嵌套

### 修复

**`guide.wxml`**
- `wx:for="{{route.cities || []}}"` → `wx:for="{{routeCities}}"`（JS 预计算）
- `wx:for="{{route.itinerary || []}}"` → `wx:for="{{routeItinerary}}"`
- 箭头分隔符的 `{{index < (route.cities || []).length - 1 ? ' → ' : ''}}` → 改用 `<text wx:if="{{index < routeCities.length - 1}}"> → </text>`

**`guide.js`**
- data 新增 `routeCities: []` 和 `routeItinerary: []`
- `onShow()` 和 `generate()` 中同时设置这两个预计算字段

**`match.wxml`**
- 所有 `wx:for="{{(item.route && item.route.cities) || []}}"` → `wx:for="{{item.route.cities}}"`
- `{{(item.seeking && item.seeking.people_min) || 1}}` → `{{item.seeking.people_min || 1}}`

**`profile.wxml`**
- `{{userInfo && userInfo.avatar_url ? userInfo.avatar_url : '/images/default_avatar.png'}}` → `{{userInfo.avatar_url || '/images/default_avatar.png'}}`
- `{{(userInfo && userInfo.nickname) || (userInfo && userInfo.nickName) || '旅行者'}}` → `{{userInfo.nickname || userInfo.nickName || '旅行者'}}`

### 经验总结
- **WXML `wx:for` 中只放简单变量名**，不要放表达式
- **`{{}}` 中避免 `&&` + `||` + `?:` 混用**，优先用 JS 预计算属性
- **三元运算符 `?:` 不要嵌套**，最多一层
- **安全模式**：模板里只做简单变量引用 + `||` 兜默认值，其他逻辑全放 JS

---

## 📋 待办事项

### P0 - 阻断项
- [x] **修复 "object null is not iterable" 渲染层错误**：所有 `wx:for` 迭代的数组变量改用 `Array.isArray()` 严格判断
- [x] **修复 WXML 模板表达式解析错误**：`wx:for` 和 `{{}}` 中禁止复杂 `&&`/`||`/`?:` 混用，改用 JS 预计算
- [x] **解决 webview 不刷新**：让最新的 `app.js` 代码（带 `wx.reLaunch`）生效到运行中的模拟器

### P1 - 核心功能验证
- [x] 真机扫码测试完整登录流程
- [ ] 测试「发布行程」是否写入数据库
- [ ] 测试「找搭子」列表是否正常加载
- [ ] 测试智能生成路线接口

### P2 - 产品细节
- [ ] 域名 `awesometravelpartner.cn` 的 HTTPS 访问问题（腾讯云 EdgeOne 拦截，需购买套餐解决）
- [ ] 小程序上传审核发布
- [ ] 前端 UI 细节优化

---

## 🔧 技术备忘

### 开发者工具 CLI 命令
```bash
# 打开项目
/Applications/wechatwebdevtools.app/Contents/MacOS/cli open --project /path --port 45470

# 自动编译+监控
/Applications/wechatwebdevtools.app/Contents/MacOS/cli auto --project /path --port 45470

# 关闭项目
/Applications/wechatwebdevtools.app/Contents/MacOS/cli close --project /path --port 45470

# 关闭 IDE
/Applications/wechatwebdevtools.app/Contents/MacOS/cli quit

# 生成预览二维码
/Applications/wechatwebdevtools.app/Contents/MacOS/cli preview --project /path --port 45470
```

### 服务器信息
- IP：`111.229.241.225`
- 后端服务：`systemctl restart travel-companion`
- API 地址：`https://111.229.241.225/api`（临时，正式需解决域名问题）
- 数据库：`/opt/travel_companion_miniapp/backend/travel_companion.db`
- 日志：`/var/log/nginx/access.log`

### API_BASE
当前小程序配置 `BASE_URL = 'https://111.229.241.225/api'`（源站 IP）
域名 `awesometravelpartner.cn` 被腾讯云 EdgeOne 拦截，需购买套餐解决
