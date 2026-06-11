const api = require('../../utils/api')

Page({
  data: {
    loading: false,
    received: [],
    sent: [],
    accepted: [],
    empty: false,
  },

  onShow() {
    this.loadExchanges()
  },

  async loadExchanges() {
    if (!wx.getStorageSync('token')) {
      this.setData({ received: [], sent: [], accepted: [], empty: true })
      return
    }
    this.setData({ loading: true })
    try {
      const res = await api.getMyExchanges()
      if (res && res.success) {
        const received = res.received || []
        const sent = res.sent || []
        const accepted = res.accepted || []
        this.setData({
          loading: false,
          received, sent, accepted,
          empty: received.length === 0 && sent.length === 0 && accepted.length === 0
        })
      } else {
        this.setData({ loading: false, empty: true })
      }
    } catch (e) {
      console.error('加载交换列表失败', e)
      this.setData({ loading: false, empty: true })
    }
  },

  async _handle(e, action) {
    const id = Number(e.currentTarget.dataset.id)
    if (!id) return
    try {
      const r = await api.handleExchange(id, action)
      if (r && r.success) {
        wx.showToast({ title: action === 'accept' ? '已同意，互见微信号' : '已拒绝', icon: 'none' })
        this.loadExchanges()
      } else {
        const msg = (r && r.detail) || '操作失败'
        if (msg.indexOf('微信号') >= 0) {
          wx.showModal({
            title: '先填微信号',
            content: '同意交换前需要先在旅行名片里填写你的微信号',
            confirmText: '去填写',
            success: (m) => {
              if (m.confirm) wx.navigateTo({ url: '/pages/card-edit/card-edit' })
            }
          })
        } else {
          wx.showToast({ title: msg, icon: 'none' })
        }
      }
    } catch (err) {
      console.error('处理失败', err)
      wx.showToast({ title: '网络错误', icon: 'none' })
    }
  },

  onAccept(e) {
    this._handle(e, 'accept')
  },

  onReject(e) {
    wx.showModal({
      title: '拒绝申请',
      content: '拒绝后对方近期无法再次向你申请，确定吗？',
      confirmText: '拒绝',
      confirmColor: '#ef4444',
      success: (res) => {
        if (res.confirm) this._handle(e, 'reject')
      }
    })
  },

  onCopyWechat(e) {
    const wechat = e.currentTarget.dataset.wechat
    if (!wechat) return
    wx.setClipboardData({
      data: wechat,
      success: () => wx.showToast({ title: '微信号已复制', icon: 'success' })
    })
  },

  goTrip(e) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    wx.navigateTo({ url: `/pages/trip-detail/trip-detail?id=${id}` })
  },

  goUserProfile(e) {
    const uid = e.currentTarget.dataset.uid
    if (!uid) return
    wx.navigateTo({ url: `/pages/user-profile/user-profile?id=${uid}` })
  },
})
