#!/bin/bash

echo "🚀 启动找搭子小程序..."
echo ""

# 检查是否在正确的目录
if [ ! -d "backend" ]; then
    echo "❌ 错误：请在 travel_companion_miniapp 目录下运行此脚本"
    exit 1
fi

# 检查Python依赖
echo "📦 检查依赖..."
cd backend
if ! python -c "import fastapi" 2>/dev/null; then
    echo "⚠️  缺少依赖，正在安装..."
    pip install -r requirements.txt
fi

echo ""
echo "✅ 依赖检查完成"
echo ""
echo "🌐 启动后端服务..."
echo "   - API地址: http://localhost:8000"
echo "   - API文档: http://localhost:8000/docs"
echo ""
echo "🎨 前端访问方式："
echo "   1. 直接打开: frontend/index.html"
echo "   2. HTTP服务: cd frontend && python -m http.server 8080"
echo ""
echo "按 Ctrl+C 停止服务"
echo "================================"
echo ""

python main.py
