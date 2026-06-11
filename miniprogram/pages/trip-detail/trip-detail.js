const api = require('../../utils/api')

Page({
  data: {
    loading: true,
    companionId: null,
    detail: null,
    route: null,
    seeking: {},
    preferences: {},
    // 留言
    comments: [],
    commentsLoading: false,
    commentInput: '',
    commentSubmitting: false,
    isLoggedIn: false,
    // 交换微信（我与帖主之间）
    exchangeStatus: 'none',
    exchange: null
  },

  onLoad(options) {
    const id = options.id || options.companion_id
    if (!id) {
      wx.showToast({ title: '缺少行程ID', icon: 'none' })
      setTimeout(() => wx.navigateBack(), 1500)
      return
    }
    this.setData({ companionId: id, isLoggedIn: !!wx.getStorageSync('token') })
    this.loadDetail()
    this.loadComments()
  },

  onShow() {
    // 从登录页/名片页回来时刷新登录态和交换状态
    this.setData({ isLoggedIn: !!wx.getStorageSync('token') })
    if (this.data.detail) this.loadExchangeStatus()
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
        this.loadExchangeStatus()
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

  // 查看作者主页
  goAuthorProfile() {
    const author = this.data.detail && this.data.detail.author
    if (!author || !author.user_id) return
    wx.navigateTo({ url: `/pages/user-profile/user-profile?id=${author.user_id}` })
  },

  // 查看留言者主页
  goCommenterProfile(e) {
    const uid = e.currentTarget.dataset.uid
    if (!uid) return
    wx.navigateTo({ url: `/pages/user-profile/user-profile?id=${uid}` })
  },

  // ---- 留言 ----
  async loadComments() {
    this.setData({ commentsLoading: true })
    try {
      const res = await api.getComments(this.data.companionId)
      if (res.success && Array.isArray(res.data)) {
        this.setData({ comments: res.data, commentsLoading: false })
      } else {
        this.setData({ comments: [], commentsLoading: false })
      }
    } catch (e) {
      console.error('加载留言失败', e)
      this.setData({ comments: [], commentsLoading: false })
    }
  },

  onCommentInput(e) {
    this.setData({ commentInput: e.detail.value })
  },

  async onSubmitComment() {
    if (this.data.commentSubmitting) return
    const content = this.data.commentInput.trim()
    if (!content) {
      wx.showToast({ title: '留言不能为空', icon: 'none' })
      return
    }
    if (!wx.getStorageSync('token')) {
      this.goLogin()
      return
    }
    this.setData({ commentSubmitting: true })
    try {
      const res = await api.postComment(this.data.companionId, content)
      if (res && res.success && res.data) {
        this.setData({
          comments: [...this.data.comments, res.data],
          commentInput: ''
        })
        wx.showToast({ title: '留言成功', icon: 'success' })
      } else {
        wx.showToast({ title: (res && res.detail) || '留言失败', icon: 'none' })
      }
    } catch (e) {
      console.error('留言失败', e)
      wx.showToast({ title: '网络错误', icon: 'none' })
    } finally {
      this.setData({ commentSubmitting: false })
    }
  },

  onDeleteComment(e) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    wx.showModal({
      title: '删除留言',
      content: '确定删除这条留言吗？',
      confirmText: '删除',
      confirmColor: '#ef4444',
      success: async (res) => {
        if (!res.confirm) return
        try {
          const r = await api.deleteComment(id)
          if (r && r.success) {
            this.setData({ comments: this.data.comments.filter(c => c.comment_id !== id) })
            wx.showToast({ title: '已删除', icon: 'success' })
          } else {
            wx.showToast({ title: (r && r.detail) || '删除失败', icon: 'none' })
          }
        } catch (err) {
          console.error('删除留言失败', err)
          wx.showToast({ title: '网络错误', icon: 'none' })
        }
      }
    })
  },

  // ---- 交换微信 ----
  async loadExchangeStatus() {
    const d = this.data.detail
    if (!d || d.is_mine || !this.data.isLoggedIn) return
    const ownerId = d.author && d.author.user_id
    if (!ownerId) return
    try {
      const res = await api.getExchangeStatus(this.data.companionId, ownerId)
      if (res && res.success) {
        this.setData({ exchangeStatus: res.status, exchange: res.data })
      }
    } catch (e) {
      console.error('查询交换状态失败', e)
    }
  },

  // 向帖主发起申请
  onRequestExchange() {
    const d = this.data.detail
    const ownerId = d && d.author && d.author.user_id
    if (!ownerId) {
      wx.showToast({ title: '无法获取对方信息', icon: 'none' })
      return
    }
    this._sendExchangeRequest(ownerId, d.user_name)
  },

  // 帖主向留言者发起申请
  onRequestExchangeWith(e) {
    const uid = Number(e.currentTarget.dataset.uid)
    const nickname = e.currentTarget.dataset.nickname || '对方'
    if (!uid) return
    this._sendExchangeRequest(uid, nickname)
  },

  _sendExchangeRequest(toUserId, nickname) {
    wx.showModal({
      title: '申请交换微信',
      content: `向 ${nickname} 发出交换微信申请，对方同意后你们将互相看到微信号`,
      confirmText: '发申请',
      success: async (res) => {
        if (!res.confirm) return
        try {
          const r = await api.createExchange(Number(this.data.companionId), toUserId)
          if (r && r.success) {
            wx.showToast({ title: '申请已发出', icon: 'success' })
            this.loadExchangeStatus()
          } else {
            const msg = (r && r.detail) || '申请失败'
            if (msg.indexOf('微信号') >= 0) {
              wx.showModal({
                title: '先填微信号',
                content: '交换微信前需要先在旅行名片里填写你的微信号',
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
          console.error('发起交换失败', err)
          wx.showToast({ title: '网络错误', icon: 'none' })
        }
      }
    })
  },

  async _handleExchange(action) {
    const ex = this.data.exchange
    if (!ex) return
    try {
      const r = await api.handleExchange(ex.exchange_id, action)
      if (r && r.success) {
        wx.showToast({ title: action === 'accept' ? '已同意，互见微信号' : '已拒绝', icon: 'none' })
        this.loadExchangeStatus()
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
    } catch (e) {
      console.error('处理交换申请失败', e)
      wx.showToast({ title: '网络错误', icon: 'none' })
    }
  },

  onAcceptExchange() {
    this._handleExchange('accept')
  },

  onRejectExchange() {
    wx.showModal({
      title: '拒绝申请',
      content: '拒绝后对方近期无法再次向你申请，确定吗？',
      confirmText: '拒绝',
      confirmColor: '#ef4444',
      success: (res) => {
        if (res.confirm) this._handleExchange('reject')
      }
    })
  },

  // 复制已交换的微信号
  copyWechat() {
    const wechat = this.data.exchange && this.data.exchange.other_wechat_id
    if (!wechat) return
    wx.setClipboardData({
      data: wechat,
      success: () => wx.showToast({ title: '微信号已复制', icon: 'success' })
    })
  },

  // 未登录点击 → 引导去登录
  goLogin() {
    wx.showModal({
      title: '需要登录',
      content: '登录后即可留言、申请交换微信',
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
