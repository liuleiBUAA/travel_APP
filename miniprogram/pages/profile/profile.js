const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    isLoggedIn: false,
    userInfo: null,
    userId: '',
    errorMsg: '',
    loading: false,
    // 完善资料弹窗
    showProfileSetup: false,
    tempAvatarUrl: '',
    tempNickname: '',
    // 旅行名片（展示用）
    card: { bio: '', budget_level: '', good_at_photo: '', accommodation_pref: '', driving: '', mbti: '', zodiac: '', tags: [] },
  },

  onLoad() {
    this.checkLogin()
  },

  onShow() {
    this.checkLogin()
  },

  checkLogin() {
    if (app.globalData.userInfo && app.globalData.userInfo.user_id) {
      const u = app.globalData.userInfo
      this.setData({ isLoggedIn: true, userInfo: u, userId: u.user_id || '' })
      this.loadCard()
      this.maybeShowProfileSetup(u)
      return
    }
    const token = wx.getStorageSync('token')
    if (token) {
      if (!this._checkingLogin) {
        this._checkingLogin = true
        api.getMe().then(res => {
          this._checkingLogin = false
          if (res && (res.success || res.user_id)) {
            app.globalData.userInfo = { ...res, token }
            this.setData({ isLoggedIn: true, userInfo: res, userId: res.user_id || '' })
            this._applyCard(res)
            this.maybeShowProfileSetup(res)
          }
        }).catch(() => {
          this._checkingLogin = false
        })
      }
      return
    }
    this.setData({ isLoggedIn: false, userInfo: null, userId: '' })
  },

  // ---- 旅行名片 ----
  async loadCard() {
    try {
      const res = await api.getMe()
      if (res && (res.success || res.user_id)) this._applyCard(res)
    } catch (e) {
      console.error('加载名片失败', e)
    }
  },

  _applyCard(me) {
    this.setData({
      card: {
        bio: me.bio || '',
        budget_level: me.budget_level || '',
        good_at_photo: me.good_at_photo || '',
        accommodation_pref: me.accommodation_pref || '',
        driving: me.driving || '',
        mbti: me.mbti || '',
        zodiac: me.zodiac || '',
        tags: Array.isArray(me.tags) ? me.tags : []
      }
    })
  },

  onEditCard() {
    wx.navigateTo({ url: '/pages/card-edit/card-edit' })
  },

  // 检查是否需要弹出完善资料
  maybeShowProfileSetup(userInfo) {
    if (!userInfo) return
    // 昵称是默认的"旅行者XXXX"格式，且用户还没跳过过
    const nickname = userInfo.nickname || ''
    const skipped = wx.getStorageSync('profile_setup_skipped')
    if (/^旅行者.{2,6}$/.test(nickname) && !skipped) {
      this.setData({ showProfileSetup: true })
    }
  },

  // 选择微信头像
  onChooseAvatar(e) {
    const avatarUrl = e.detail.avatarUrl
    if (avatarUrl) {
      this.setData({ tempAvatarUrl: avatarUrl })
    }
  },

  // 获取微信昵称
  onNicknameChange(e) {
    this.setData({ tempNickname: e.detail.value || '' })
  },

  // 跳过设置
  onSkipSetup() {
    wx.setStorageSync('profile_setup_skipped', true)
    this.setData({ showProfileSetup: false })
  },

  // 确认设置资料
  async onConfirmSetup() {
    const { tempNickname, tempAvatarUrl } = this.data
    if (!tempNickname && !tempAvatarUrl) {
      wx.showToast({ title: '请至少设置昵称或头像', icon: 'none' })
      return
    }

    const token = wx.getStorageSync('token')
    if (!token) return

    try {
      const res = await api.updateProfile({ nickname: tempNickname || undefined, avatar_url: tempAvatarUrl || undefined })
      if (res && (res.user_id || res.nickname)) {
        // 更新全局数据
        const updated = { ...app.globalData.userInfo }
        if (tempNickname) updated.nickname = tempNickname
        if (tempAvatarUrl) updated.avatar_url = tempAvatarUrl
        app.globalData.userInfo = updated
        this.setData({
          showProfileSetup: false,
          userInfo: updated
        })
        wx.showToast({ title: '资料更新成功', icon: 'success' })
      } else {
        wx.showToast({ title: '更新失败，请稍后再试', icon: 'none' })
      }
    } catch (e) {
      console.error('更新资料失败', e)
      wx.showToast({ title: '网络错误', icon: 'none' })
    }
  },

  // 微信一键登录
  onPhoneLogin(e) {
    if (app.wxLogin) {
      app.wxLogin()
    }
  },

  // 手动打开编辑资料弹窗
  onEditProfile() {
    const u = this.data.userInfo || {}
    this.setData({
      showProfileSetup: true,
      tempNickname: u.nickname || '',
      tempAvatarUrl: u.avatar_url || ''
    })
  },

  onLogout() {
    wx.showModal({
      title: '提示',
      content: '确定要退出登录吗？',
      success: (res) => {
        if (res.confirm) {
          this.setData({ isLoggedIn: false, userInfo: null, userId: '' })
          // 退出后回到登录页（登录门槛）
          app.logout()
        }
      }
    })
  },

  goMyTrips() {
    wx.navigateTo({ url: '/pages/my-trips/my-trips' })
  },
  goMyGuides() { wx.showToast({ title: '功能开发中', icon: 'none' }) },
  goMyMatches() {
    wx.navigateTo({ url: '/pages/my-buddies/my-buddies' })
  },
  goSettings() { wx.showToast({ title: '功能开发中', icon: 'none' }) },
})
