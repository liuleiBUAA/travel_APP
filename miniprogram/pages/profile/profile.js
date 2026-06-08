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
    // 我发布的行程
    myTrips: [],
    myTripsLoading: false,
    myTripsEmpty: false,
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
      this.loadMyTrips()  // ✅ 修复: 不传user_id
      this.maybeShowProfileSetup(u)
      return
    }
    const token = wx.getStorageSync('token')
    if (token) {
      if (!this._checkingLogin) {
        this._checkingLogin = true
        api.getMe().then(res => {  // ✅ 修复: 不传token参数
          this._checkingLogin = false
          if (res && (res.success || res.user_id)) {
            app.globalData.userInfo = { ...res, token }
            this.setData({ isLoggedIn: true, userInfo: res, userId: res.user_id || '' })
            this.loadMyTrips()  // ✅ 修复: 不传user_id
            this.maybeShowProfileSetup(res)
          }
        }).catch(() => {
          this._checkingLogin = false
        })
      }
      return
    }
    this.setData({ isLoggedIn: false, userInfo: null, userId: '', myTrips: [] })
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
      // ✅ 修复: 不传token参数,由api.js自动从storage获取
      const res = await api.updateProfile(tempNickname || undefined, undefined, tempAvatarUrl || undefined)
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
          wx.removeStorageSync('token')
          app.globalData.userInfo = null
          this.setData({ isLoggedIn: false, userInfo: null, userId: '', myTrips: [] })
          wx.showToast({ title: '已退出登录', icon: 'none' })
        }
      }
    })
  },

  // ---- 我发布的行程 ----
  async loadMyTrips() {
    // ✅ 修复: 检查token,不需要userId参数
    const token = wx.getStorageSync('token')
    if (!token) {
      this.setData({ myTrips: [], myTripsLoading: false, myTripsEmpty: true })
      return
    }
    this.setData({ myTripsLoading: true, myTripsEmpty: false })
    try {
      const res = await api.getMyCompanions()  // ✅ 修复: 不传userId
      if (res.success && Array.isArray(res.data)) {
        const trips = res.data.map(t => ({
          ...t,
          route: (t.route && Array.isArray(t.route.cities)) ? t.route : { cities: [] }
        }))
        this.setData({
          myTrips: trips,
          myTripsLoading: false,
          myTripsEmpty: trips.length === 0
        })
      } else {
        this.setData({ myTrips: [], myTripsLoading: false, myTripsEmpty: true })
      }
    } catch (err) {
      console.error('加载我的行程失败', err)
      this.setData({ myTrips: [], myTripsLoading: false, myTripsEmpty: true })
    }
  },

  onTripDetail(e) {
    console.log('[onTripDetail] 被触发', e)
    const trip = e.currentTarget.dataset.trip
    console.log('[onTripDetail] trip数据:', JSON.stringify(trip).substring(0, 200))
    if (!trip) {
      console.error('[onTripDetail] trip为空，返回')
      return
    }

    // 跳转到行程详情页面，传递 companion_id
    wx.navigateTo({
      url: `/pages/trip-detail/trip-detail?id=${trip.companion_id}`,
      fail: (err) => {
        console.error('[onTripDetail] 跳转失败', err)
        // 降级方案：如果详情页不存在，用 showModal 展示简要信息
        const cities = (trip.route && Array.isArray(trip.route.cities)) ? trip.route.cities.join(' → ') : '行程详情'
        wx.showModal({
          title: cities,
          content: `出发日期: ${trip.travel_date || '未设置'}\n天数: ${trip.duration_days || 0}天\n交通: ${trip.transport_mode || '不限'}\n住宿: ${trip.accommodation || '不限'}\n消费: ${trip.budget_level || '经济'}\n拍照: ${trip.good_at_photo || '不限'}\n发布于: ${trip.created_at || '未知'}`,
          showCancel: false,
          confirmText: '知道了'
        })
      }
    })
  },

  goMyTrips() { /* 已在页面内展示 */ },
  goMyGuides() { wx.showToast({ title: '功能开发中', icon: 'none' }) },
  goMyMatches() { wx.showToast({ title: '功能开发中', icon: 'none' }) },
  goSettings() { wx.showToast({ title: '功能开发中', icon: 'none' }) },
})
