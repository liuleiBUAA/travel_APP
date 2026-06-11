const api = require('../../utils/api')

Page({
  data: {
    loading: true,
    errorMsg: '',
    playbook: null
  },

  onLoad(options) {
    const name = decodeURIComponent(options.name || '')
    if (!name) {
      this.setData({ loading: false, errorMsg: '缺少景点名称' })
      return
    }
    wx.setNavigationBarTitle({ title: name })
    this.loadPlaybook(name)
  },

  async loadPlaybook(name) {
    try {
      const res = await api.getAttractionPlaybook(name)
      if (res.success && res.playbook) {
        this.setData({ playbook: res.playbook, loading: false })
      } else {
        this.setData({ loading: false, errorMsg: '暂无该景点的玩法攻略' })
      }
    } catch (err) {
      this.setData({ loading: false, errorMsg: '暂无该景点的玩法攻略' })
    }
  }
})
