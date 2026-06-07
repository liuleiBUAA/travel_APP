// 前端配置文件
const CONFIG = {
    // API 基础地址
    // 开发环境: http://localhost:8000/api
    // 生产环境: https://awesometravelpartner.cn/api
    // API_BASE_URL: 'https://awesometravelpartner.cn/api', // 域名被腾讯云边缘拦截
    API_BASE_URL: 'https://111.229.241.225/api', // 临时用源站IP
    
    // 微信小程序 AppID
    WX_APPID: 'wxc76b2ea964e5a3c1',
    
    // 版本号
    VERSION: '1.0.0'
};

// 兼容模块导出和直接引用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CONFIG;
}
