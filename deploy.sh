#!/bin/bash
# 找搭子小程序一键部署脚本

set -e

echo "🚀 开始部署找搭子小程序..."
echo ""

# 检查是否在正确目录
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ 错误：请在项目根目录运行此脚本"
    exit 1
fi

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "⚠️  未找到 .env 文件，从模板创建..."
    cp .env.example .env
    echo "⚠️  请编辑 .env 文件，填入你的 WX_MINI_SECRET"
    exit 1
fi

# 安装 Docker（如果未安装）
if ! command -v docker &> /dev/null; then
    echo "📦 安装 Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# 安装 docker-compose（如果未安装）
if ! command -v docker-compose &> /dev/null; then
    echo "📦 安装 docker-compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

echo "🔨 构建并启动服务..."
docker-compose down 2>/dev/null || true
docker-compose up --build -d

echo ""
echo "✅ 部署完成！"
echo ""
echo "📋 服务状态："
docker-compose ps
echo ""
echo "🌐 访问地址："
echo "   - 网页版: http://$(curl -s ifconfig.me)"
echo "   - API文档: http://$(curl -s ifconfig.me)/docs"
echo ""
echo "📖 下一步："
echo "   1. 配置域名解析到本服务器IP"
echo "   2. 运行 ./init-ssl.sh 申请 HTTPS 证书"
echo "   3. 在微信小程序后台配置服务器域名"
