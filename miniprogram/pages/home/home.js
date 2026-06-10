const app = getApp()

Page({
  data: {
    nickname: ''
  },

  onShow() {
    const u = app.globalData.userInfo
    this.setData({ nickname: (u && (u.nickname || u.nickName)) || '' })
  },

  // 做攻略（非 tab 页，navigateTo）
  goGuide() {
    wx.navigateTo({ url: '/pages/guide/guide' })
  },

  // 找搭子 / 发布路线（tab 页，switchTab）
  goPublish() {
    wx.switchTab({ url: '/pages/index/index' })
  },

  // 浏览搭子（非 tab 页，navigateTo）
  goMatch() {
    wx.navigateTo({ url: '/pages/match/match' })
  },

  // 我的（tab 页，switchTab）
  goProfile() {
    wx.switchTab({ url: '/pages/profile/profile' })
  }
})
