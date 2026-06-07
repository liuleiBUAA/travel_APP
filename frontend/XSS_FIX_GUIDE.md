# 网页版 XSS 修复指南

## 问题

`frontend/index.html` 大量使用 `innerHTML` 直接拼接用户可控的数据（`user_name`, `city`, `keyword` 等），导致存储型 XSS 漏洞。

**受影响位置：**
- Line 1065-1068: `toggleCity()` 中的 city.name 拼接到 onclick
- Line 1113: `updateSelectedCities()` 中的 city 拼接到 onclick
- Line 1151: 自动完成列表拼接 city 到 onclick
- Line 1222: 路线结果拼接 cities
- Line 1604: 匹配结果拼接 user_name
- Line 1607: 匹配结果拼接 cities
- Line 1639-1642: 搜索结果拼接 user_name 和 cities

## 修复方案

### 方法 1：添加转义函数（推荐）

在 `<script>` 开头添加：

```javascript
// HTML 转义函数，防止 XSS
function escapeHtml(unsafe) {
    if (unsafe == null) return '';
    return String(unsafe)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
```

然后替换所有插值：

```javascript
// ❌ 错误（XSS 风险）
`<div>${user_name}</div>`

// ✅ 正确
`<div>${escapeHtml(user_name)}</div>`
```

### 方法 2：改用 DOM API（更安全）

```javascript
// ❌ innerHTML 拼接
resultDiv.innerHTML = `<div class="match-user">${match.user_name}</div>`;

// ✅ DOM API
const div = document.createElement('div');
div.className = 'match-user';
div.textContent = match.user_name;  // 自动转义
resultDiv.appendChild(div);
```

### 方法 3：事件委托替代 onclick 内联

```javascript
// ❌ 字符串拼接到 onclick（双重注入风险）
`<div onclick="toggleCity('${city}')">...</div>`

// ✅ 事件委托
`<div class="city-item" data-city="${escapeHtml(city)}">...</div>`

// 在外层统一绑定
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('city-item')) {
        const city = e.target.dataset.city;
        toggleCity(city);
    }
});
```

## 快速修复清单

建议按优先级修复：

### P0（立即修复）
- [ ] Line 1604: `match.user_name` → `escapeHtml(match.user_name)`
- [ ] Line 1607: `match.route.cities` → `match.route.cities.map(c => escapeHtml(c))`
- [ ] Line 1639: `c.user_name` → `escapeHtml(c.user_name)`
- [ ] Line 1642: `c.route.cities` → `c.route.cities.map(city => escapeHtml(city))`

### P1（本周修复）
- [ ] Line 1065-1068: `city.name` → 改用 `data-city` + 事件委托
- [ ] Line 1113: `toggleCity('${city}')` → 改用 `data-city` + 事件委托
- [ ] Line 1151: 自动完成列表改用事件委托

### P2（择机修复）
- [ ] Line 1222: `data.route.cities` → 转义
- [ ] 所有错误消息中的 `error.message` → 转义

## 测试方法

插入恶意数据测试：

```javascript
// 测试昵称 XSS
昵称输入：<img src=x onerror=alert('XSS')>
期望：显示为文本，不执行脚本

// 测试城市名 XSS
城市名：Paris<script>alert('XSS')</script>
期望：显示为 Paris&lt;script&gt;...，不执行脚本
```

## 注意事项

⚠️ **小程序端不受影响**：小程序使用 `{{ }}` 数据绑定，自动转义，无 XSS 风险。

⚠️ **本修复仅针对 `frontend/index.html`**：如果不使用网页版，可跳过此修复。

## 完整修复后的示例

```javascript
// 添加转义函数
function escapeHtml(unsafe) {
    if (unsafe == null) return '';
    return String(unsafe)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// 修复匹配结果显示
listDiv.innerHTML = matches.map(match => `
    <div class="match-card">
        <div class="match-score">${Math.round(match.match_score * 100)}% 匹配</div>
        <div class="match-user">👤 ${escapeHtml(match.user_name)}</div>
        <div class="match-date">📅 ${escapeHtml(match.travel_date)} · ${match.duration_days}天</div>
        <div class="match-cities">
            ${match.route.cities.map(city =>
                `<span class="city-badge">${escapeHtml(city)}</span>`
            ).join('')}
        </div>
    </div>
`).join('');
```

**修复完成标志：** 所有用户可控数据（昵称、城市名、关键词）在插入 HTML 前都经过 `escapeHtml()` 处理。
