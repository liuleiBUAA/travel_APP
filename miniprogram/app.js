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
    this.autoLogin()
    this.wxLogin = this.wxLogin.bind(this)
  },

  async autoLogin() {
    try {
      const token = wx.getStorageSync('token')
      if (token) {
        try {
          const res = await api.getMe(token)
          console.log('[autoLogin] getMe响应:', JSON.stringify(res))
          if (res && typeof res === 'object' && (res.success !== false)) {
            // getMe 返回 user_id 即可认为有效
            if (res.user_id) {
              this.globalData.userInfo = { ...res, token }
              console.log('[autoLogin] token有效，用户:', this.globalData.userInfo)
              // 刷新所有已加载页面的 onShow
              const pages = getCurrentPages()
              pages.forEach(page => {
                if (page && typeof page.onShow === 'function') {
                  page.onShow()
                }
              })
              return
            }
          }
          console.warn('[autoLogin] getMe返回格式异常，清除token:', res)
          wx.removeStorageSync('token')
        } catch (e) {
          console.error('[autoLogin] getMe失败，清除token重新微信登录', e)
          wx.removeStorageSync('token')
        }
      }
      // 无token或已失效，走微信登录
      console.log('[autoLogin] 触发微信登录')
      await this.wxLogin()
    } catch (e) {
      console.error('[autoLogin] 自动登录异常', e)
    }
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
