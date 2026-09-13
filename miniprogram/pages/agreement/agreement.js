// 用户服务协议 / 隐私政策 展示页
// 通过 ?type=service|privacy 决定展示哪一份
Page({
  data: {
    type: 'privacy',
    title: '隐私政策'
  },

  onLoad(options) {
    const type = (options && options.type) === 'service' ? 'service' : 'privacy'
    const title = type === 'service' ? '用户服务协议' : '隐私政策'
    this.setData({ type, title })
    wx.setNavigationBarTitle({ title })
  }
})
