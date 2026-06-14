const api = require('../../utils/api')

Page({
  data: {
    loading: true,
    errorMsg: '',
    playbook: null,
    isCity: false
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
        const pb = res.playbook
        // 把后端返回的相对图片路径补成完整 URL
        if (pb.hero) pb.hero = api.imageUrl(pb.hero)
        if (pb.transport_map_url) pb.transport_map_url = api.imageUrl(pb.transport_map_url)
        if (pb.gallery) pb.gallery = pb.gallery.map(p => ({ ...p, url: api.imageUrl(p.url) }))
        if (pb.attractions) {
          pb.attractions = pb.attractions.map(a => ({
            ...a,
            thumb: a.thumb ? api.imageUrl(a.thumb) : ''
          }))
        }
        this.setData({ playbook: pb, isCity: pb.type === 'city', loading: false })
      } else {
        this.setData({ loading: false, errorMsg: '暂无该景点的玩法攻略' })
      }
    } catch (err) {
      this.setData({ loading: false, errorMsg: '暂无该景点的玩法攻略' })
    }
  },

  // 点景点目录里的卡片 → 打开该景点详情页（仅 has_detail 的可点）
  openAttraction(e) {
    const { name, hasdetail } = e.currentTarget.dataset
    if (!hasdetail) {
      wx.showToast({ title: '该景点暂无详情', icon: 'none' })
      return
    }
    wx.navigateTo({ url: `/pages/attraction/attraction?name=${encodeURIComponent(name)}` })
  },

  // 预览图集
  previewGallery(e) {
    const { url, urls } = e.currentTarget.dataset
    wx.previewImage({ current: url, urls: urls || [url] })
  },

  // 预览交通图
  previewMap(e) {
    const url = e.currentTarget.dataset.url
    if (url) wx.previewImage({ current: url, urls: [url] })
  },

  // 酒店链接（复制到剪贴板，小程序不能直接开外链）
  copyHotelLink(e) {
    const link = e.currentTarget.dataset.link
    if (!link) return
    wx.setClipboardData({
      data: link,
      success: () => wx.showToast({ title: '预订链接已复制', icon: 'none' })
    })
  }
})
