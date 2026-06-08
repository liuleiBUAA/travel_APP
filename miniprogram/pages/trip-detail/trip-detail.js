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
  }
})
