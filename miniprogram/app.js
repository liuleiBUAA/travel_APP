const api = require('./utils/api')

App({
  globalData: {
    selectedCities: [],
    currentRegion: '欧洲',
    currentCountry: '',
    generatedRoute: null,
    userInfo: null,  // { user_id, nickname, avatar_url, token }
  },

  onLaunch() {
    // 不设登录门槛：启动直接进首页，游客可浏览攻略/搭子列表。
    // 仅在发布行程、留言、申请交换微信等写操作时，才引导用户到 pages/login 授权登录。
    this.wxLogin = this.wxLogin.bind(this)
  },

  // 退出登录后回首页（不强制登录）
  logout() {
    wx.removeStorageSync('token')
    this.globalData.userInfo = null
    wx.reLaunch({ url: '/pages/home/home' })
  },

  async wxLogin() {
    try {
      const loginRes = await new Promise((resolve, reject) => {
        wx.login({ success: resolve, fail: reject })
      })
      if (!loginRes.code) {
        console.error('[wxLogin] wx.login无code')
        return
      }
      const res = await api.wxLogin(loginRes.code)
      console.log('[wxLogin] 后端响应:', JSON.stringify(res))
      if (res && typeof res === 'object' && (res.success !== false) && res.user_id) {
        this.globalData.userInfo = res
        wx.setStorageSync('token', res.token)
        console.log('[wxLogin] 登录成功:', res)
        // 登录成功后，刷新当前页面
        const pages = getCurrentPages()
        if (pages.length > 0) {
          pages[pages.length - 1].onShow()
        }
      } else {
        console.error('[wxLogin] 后端返回异常:', res)
      }
    } catch (e) {
      console.error('[wxLogin] 微信登录失败', e)
    }
  }
})
