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
          // 出发日期取「月-日」短格式（travel_date 形如 2026-08-15）
          let dateShort = ''
          if (c.travel_date && c.travel_date.length >= 10) {
            dateShort = c.travel_date.slice(5)  // "08-15"
          }
          // 还差几人：seeking.people_max - 已组队人数（真实字段，缺省不显示）
          let needText = ''
          const seeking = c.seeking || {}
          const wantMax = seeking.people_max
          const cur = (c.user_male_count || 0) + (c.user_female_count || 0)
          if (typeof wantMax === 'number' && wantMax > cur) {
            needText = '还差 ' + (wantMax - cur) + ' 人'
          }
          return {
            ...c,
            citiesText: cities.slice(0, 3).join(' → ') + (cities.length > 3 ? '…' : ''),
            dateShort,
            needText
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
