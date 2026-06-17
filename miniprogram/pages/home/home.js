const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    nickname: '',
    recent: []
  },

  onShow() {
    const u = app.globalData.userInfo
    this.setData({ nickname: (u && (u.nickname || u.nickName)) || '' })
    this.loadRecent()
  },

  // 最新找搭子动态（横滑卡片）
  async loadRecent() {
    try {
      const res = await api.listCompanions(6)
      if (res.success && Array.isArray(res.data)) {
        const recent = res.data.map(c => {
          const cities = (c.route && Array.isArray(c.route.cities)) ? c.route.cities : []
          return {
            ...c,
            citiesText: cities.slice(0, 3).join(' → ') + (cities.length > 3 ? '…' : '')
          }
        })
        this.setData({ recent })
      }
    } catch (err) {
      console.error('加载最新发布失败', err)
    }
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id
    if (id) {
      wx.navigateTo({ url: `/pages/trip-detail/trip-detail?id=${id}` })
    }
  },

  // 做攻略（非 tab 页，navigateTo）
  goGuide() {
    wx.navigateTo({ url: '/pages/guide/guide' })
  },

  // 语音助手
  goVoice() {
    wx.navigateTo({ url: '/pages/voice-assistant/voice-assistant' })
  },

  // 找搭子（tab 页，switchTab 到找搭子选择页）
  goPublish() {
    wx.switchTab({ url: '/pages/companion/companion' })
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
