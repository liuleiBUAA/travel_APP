const api = require('../../utils/api')
const app = getApp()

// 登录成功后的兜底跳转（无上级页面时）
const HOME_URL = '/pages/home/home'

Page({
  data: {
    logging: false,   // 微信登录请求中
    agreed: false,    // 协议勾选（默认不勾选，微信审核要求）
    errorMsg: ''
  },

  onLoad() {
    // 不再做「启动登录墙」：本页只在用户主动登录时才进入。
    // 若已登录，提示并返回上一页。
    const token = wx.getStorageSync('token')
    if (token) {
      this.checkExisting(token)
    }
  },

  async checkExisting(token) {
    try {
      const res = await api.getMe()
      if (res && res.user_id) {
        app.globalData.userInfo = { ...res, token }
        this.goBack()
      }
    } catch (e) {
      wx.removeStorageSync('token')
    }
  },

  // 勾选/取消勾选协议
  onToggleAgree() {
    this.setData({ agreed: !this.data.agreed, errorMsg: '' })
  },

  openService() {
    wx.navigateTo({ url: '/pages/agreement/agreement?type=service' })
  },

  openPrivacy() {
    wx.navigateTo({ url: '/pages/agreement/agreement?type=privacy' })
  },

  // 微信一键登录（未勾选协议时不执行任何登录动作）
  async onWxLogin() {
    if (this.data.logging) return
    if (!this.data.agreed) {
      this.setData({ errorMsg: '请先阅读并勾选同意《用户服务协议》与《隐私政策》' })
      wx.showToast({ title: '请先勾选同意协议', icon: 'none' })
      return
    }
    this.setData({ logging: true, errorMsg: '' })
    try {
      const loginRes = await new Promise((resolve, reject) => {
        wx.login({ success: resolve, fail: reject })
      })
      if (!loginRes.code) {
        throw new Error('未获取到微信登录凭证')
      }
      const res = await api.wxLogin(loginRes.code)
      if (res && res.user_id && res.token) {
        app.globalData.userInfo = res
        wx.setStorageSync('token', res.token)
        wx.showToast({ title: '登录成功', icon: 'success' })
        setTimeout(() => this.goBack(), 600)
      } else {
        this.setData({ logging: false, errorMsg: '登录失败，请重试' })
      }
    } catch (e) {
      console.error('[login] 微信登录失败', e)
      this.setData({ logging: false, errorMsg: '登录失败：' + (e.errMsg || e.message || '网络错误') })
    }
  },

  // 登录后回到用户来的地方；没有上级页面则回首页
  goBack() {
    const pages = getCurrentPages()
    if (pages.length > 1) {
      const prev = pages[pages.length - 2]
      if (prev && typeof prev.onShow === 'function') {
        // 让上一页刷新登录态
        prev.__needRefresh = true
      }
      wx.navigateBack()
    } else {
      wx.reLaunch({ url: HOME_URL })
    }
  },

  // 游客继续浏览
  onSkip() {
    this.goBack()
  }
})
