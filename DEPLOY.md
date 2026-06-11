# 部署操作手册

## 1. 拉取最新代码

```bash
cd /path/to/travel_APP
git pull origin main
```

如果是新机器，先克隆：

```bash
git clone https://github.com/liuleiBUAA/travel_APP.git
cd travel_APP
```

---

## 2. 部署后端到服务器

### 上传代码

```bash
# 上传整个后端目录
scp -r backend/ root@111.229.241.225:/opt/travel_companion_miniapp/backend/
```

或者只上传修改的文件：

```bash
scp backend/main.py root@111.229.241.225:/opt/travel_companion_miniapp/backend/main.py
scp backend/services/auth_service.py root@111.229.241.225:/opt/travel_companion_miniapp/backend/services/auth_service.py
scp backend/services/route_service.py root@111.229.241.225:/opt/travel_companion_miniapp/backend/services/route_service.py
```

### 重启后端服务

```bash
ssh root@111.229.241.225 "pkill -f 'uvicorn main:app' && sleep 1 && cd /opt/travel_companion_miniapp/backend && nohup /usr/bin/python3 /usr/local/bin/uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/travel_api.log 2>&1 &"
```

### 验证服务正常

```bash
curl -s "https://awesometravelpartner.cn/api/companions/list?limit=3" | python3 -m json.tool
```

### 查看日志（排错用）

```bash
ssh root@111.229.241.225 "tail -50 /tmp/travel_api.log"
```

---

## 3. 更新小程序前端

1. 打开**微信开发者工具**
2. 导入项目，选择 `miniprogram/` 目录
3. AppID: `wx781c464fc0568970`
4. 点击"编译"确认功能正常
5. 点击右上角**"上传"**
6. 填写版本号（如 `1.0.3`）和描述
7. 登录 [微信公众平台](https://mp.weixin.qq.com/) → 管理 → 版本管理
8. 找到刚上传的版本 → 点击**"选为体验版"**
9. 扫体验版二维码测试

---

## 4. 推送代码到 GitHub

```bash
cd /path/to/travel_APP
git add .
git commit -m "feat: 描述修改内容"
git push origin main
```

push 失败就开 VPN 重试。

---

## 服务器信息

| 项目 | 值 |
|------|-----|
| 服务器 IP | `111.229.241.225` |
| SSH | `ssh root@111.229.241.225` |
| 后端路径 | `/opt/travel_companion_miniapp/backend/` |
| API 地址 | `https://awesometravelpartner.cn/api/` |
| 端口 | 8000 |
| 数据库 | SQLite (`travel_companion.db`) |

## 环境变量

服务器上 `/opt/travel_companion_miniapp/backend/.env`：

```
WX_MINI_APPID=wx781c464fc0568970
WX_MINI_SECRET=77ba74f777f8afd614f1fc63dd297212
```
