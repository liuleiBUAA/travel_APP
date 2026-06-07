#!/bin/bash
# SSL 证书申请脚本

set -e

echo "🔒 申请 SSL 证书..."
echo ""

# 检查域名
read -p "请输入域名 (默认: awesometravelpartner.cn): " DOMAIN
DOMAIN=${DOMAIN:-awesometravelpartner.cn}

read -p "请输入邮箱 (用于证书到期提醒): " EMAIL

if [ -z "$EMAIL" ]; then
    echo "❌ 邮箱不能为空"
    exit 1
fi

# 安装 certbot
if ! command -v certbot &> /dev/null; then
    echo "📦 安装 certbot..."
    apt-get update
    apt-get install -y certbot
fi

# 申请证书
echo "📜 正在为 $DOMAIN 申请证书..."
certbot certonly --standalone \
    --agree-tos \
    --no-eff-email \
    --email "$EMAIL" \
    -d "$DOMAIN" \
    -d "www.$DOMAIN"

# 创建证书目录
mkdir -p certbot/conf certbot/www

# 复制证书到项目目录
cp -r /etc/letsencrypt/live/$DOMAIN certbot/conf/ 2>/dev/null || true

echo ""
echo "✅ 证书申请成功！"
echo ""
echo "📋 证书位置: /etc/letsencrypt/live/$DOMAIN/"
echo ""
echo "⚠️  请手动修改 nginx/conf.d/default.conf，启用 HTTPS 配置"
echo "   然后运行: docker-compose restart nginx"
