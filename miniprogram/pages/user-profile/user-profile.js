const api = require('../../utils/api')

Page({
  data: {
    loading: true,
    profile: null,
    notFound: false
  },

  onLoad(options) {
    const id = options.id || options.user_id
    if (!id) {
      wx.showToast({ title: '缺少用户ID', icon: 'none' })
      setTimeout(() => wx.navigateBack(), 1500)
      return
    }
    this.loadProfile(id)
  },

  async loadProfile(userId) {
    this.setData({ loading: true })
    try {
      const res = await api.getUserProfile(userId)
      if (res.success && res.data) {
        this.setData({ loading: false, profile: res.data })
      } else {
        this.setData({ loading: false, notFound: true })
      }
    } catch (e) {
      console.error('加载用户主页失败', e)
      this.setData({ loading: false, notFound: true })
    }
  }
})
