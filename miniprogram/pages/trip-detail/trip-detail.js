const api = require('../../utils/api')

Page({
  data: {
    loading: true,
    companionId: null,
    detail: null,
    route: null,
    seeking: {},
    preferences: {}
  },

  onLoad(options) {
    const id = options.id || options.companion_id
    if (!id) {
      wx.showToast({ title: '缺少行程ID', icon: 'none' })
      setTimeout(() => wx.navigateBack(), 1500)
      return
    }
    this.setData({ companionId: id })
    this.loadDetail()
  },

  // 转发给好友
  onShareAppMessage() {
    const d = this.data.detail || {}
    const route = this.data.route || {}
    const cities = Array.isArray(route.cities) ? route.cities.join('·') : ''
    return {
      title: `${d.user_name || '旅行者'}的${cities}之旅，找搭子中`,
      path: `/pages/trip-detail/trip-detail?id=${this.data.companionId}`
    }
  },

  // 分享到朋友圈
  onShareTimeline() {
    const route = this.data.route || {}
    const cities = Array.isArray(route.cities) ? route.cities.join('·') : '旅行'
    return {
      title: `${cities} 找搭子中，一起出发吗？`,
      query: `id=${this.data.companionId}`
    }
  },

  async loadDetail() {
    this.setData({ loading: true })
    try {
      const res = await api.getCompanionDetail(this.data.companionId)
      if (res.success && res.data) {
        const detail = res.data
        const route = detail.route || {}
        const seeking = detail.seeking || {}
        const preferences = detail.preferences || {}

        this.setData({
          loading: false,
          detail,
          route,
          seeking,
          preferences
        })
      } else {
        wx.showToast({ title: '获取详情失败', icon: 'none' })
        setTimeout(() => wx.navigateBack(), 1500)
      }
    } catch (err) {
      console.error('加载行程详情失败', err)
      wx.showToast({ title: '加载失败', icon: 'none' })
      this.setData({ loading: false })
    }
  },

  // 复制联系方式
  copyContact() {
    const contact = this.data.detail && this.data.detail.contact_wechat
    if (!contact) return
    wx.setClipboardData({
      data: contact,
      success: () => wx.showToast({ title: '微信号已复制', icon: 'success' })
    })
  },

  // 未登录点击联系方式 → 引导去登录
  goLogin() {
    wx.showModal({
      title: '需要登录',
      content: '登录后即可查看对方联系方式',
      confirmText: '去登录',
      success: (res) => {
        if (res.confirm) {
          wx.switchTab({ url: '/pages/profile/profile' })
        }
      }
    })
  },

  // 删除自己的行程
  onDelete() {
    wx.showModal({
      title: '删除行程',
      content: '删除后其他人将无法看到这条找搭子信息，确定删除吗？',
      confirmText: '删除',
      confirmColor: '#ef4444',
      success: async (res) => {
        if (!res.confirm) return
        try {
          const r = await api.deleteCompanion(this.data.companionId)
          if (r && r.success) {
            wx.showToast({ title: '已删除', icon: 'success' })
            setTimeout(() => wx.navigateBack(), 1200)
          } else {
            wx.showToast({ title: (r && r.detail) || '删除失败', icon: 'none' })
          }
        } catch (err) {
          console.error('删除失败', err)
          wx.showToast({ title: '网络错误', icon: 'none' })
        }
      }
    })
  }
})
