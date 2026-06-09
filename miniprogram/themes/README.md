# 主题切换说明

整个小程序的配色由一组 CSS 变量统一控制，变量定义在 `miniprogram/app.wxss` 顶部
`/* THEME START */ ... /* THEME END */` 之间。各页面 wxss 只引用变量、不写死颜色，
所以**换主题不用动任何页面文件**。

## 三套主题

| 文件 | 主题 | 调性 |
|------|------|------|
| `theme-A-clean.wxss`  | 清爽留白现代风 | 靛蓝主色 + 中性灰，白底大留白（Airbnb 感） |
| `theme-B-purple.wxss` | 紫色收敛版（默认） | 沿用原 #667eea 紫，去掉打架的粉/绿 |
| `theme-C-travel.wxss` | 明快旅行风 | 珊瑚橙 + 天空蓝，年轻活泼 |

当前 `app.wxss` 内置的是 **主题 B**。

## 怎么切换

1. 打开想试的主题文件，例如 `theme-A-clean.wxss`
2. 复制它 `THEME START` ~ `THEME END` 之间的整段内容
3. 打开 `app.wxss`，把顶部 `THEME START` ~ `THEME END` 之间的内容整段替换掉
4. 微信开发者工具里点「编译」，整个 App 立即换肤

> 只替换变量区，不要动 `THEME END` 之后的通用样式（按钮、卡片、输入框等结构）。

## 加自己的主题

复制任意一个主题文件，改里面的颜色值即可。变量含义见文件内注释。
