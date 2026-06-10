const api = require('../../utils/api')
const app = getApp()

// 登录成功后进入的主界面
const HOME_URL = '/pages/index/index'

Page({
  data: {
    checking: true,   // 启动时校验 token，老用户一闪而过
    logging: false,   // 微信登录请求中
    errorMsg: ''
  },

  onLoad() {
    this.tryAutoEnter()
  },

  // 已有有效 token 则直接进主界面，否则停在登录页
  async tryAutoEnter() {
    const token = wx.getStorageSync('token')
    if (!token) {
      this.setData({ checking: false })
      return
    }
    try {
      const res = await api.getMe()
      if (res && res.user_id) {
        app.globalData.userInfo = { ...res, token }
        this.enterHome()
        return
      }
      // token 失效
      wx.removeStorageSync('token')
    } catch (e) {
      wx.removeStorageSync('token')
    }
    this.setData({ checking: false })
  },

  // 微信一键登录
  async onWxLogin() {
    if (this.data.logging) return
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
        this.enterHome()
      } else {
        this.setData({ logging: false, errorMsg: '登录失败，请重试' })
      }
    } catch (e) {
      console.error('[login] 微信登录失败', e)
      this.setData({ logging: false, errorMsg: '登录失败：' + (e.errMsg || e.message || '网络错误') })
    }
  },

  enterHome() {
    wx.reLaunch({ url: HOME_URL })
  }
})
