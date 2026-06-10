Page({
  // 发布路线（非 tab 页，navigateTo）
  goPublish() {
    wx.navigateTo({ url: '/pages/index/index' })
  },

  // 搜搭子（非 tab 页，navigateTo）
  goSearch() {
    wx.navigateTo({ url: '/pages/match/match' })
  }
})
