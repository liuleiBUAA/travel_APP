const api = require('../../utils/api')

Page({
  data: {
    myTrips: [],
    myTripsLoading: false,
    myTripsEmpty: false,
  },

  onShow() {
    this.loadMyTrips()
  },

  async loadMyTrips() {
    const token = wx.getStorageSync('token')
    if (!token) {
      this.setData({ myTrips: [], myTripsLoading: false, myTripsEmpty: true })
      return
    }
    this.setData({ myTripsLoading: true, myTripsEmpty: false })
    try {
      const res = await api.getMyCompanions()
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
    const trip = e.currentTarget.dataset.trip
    if (!trip) return
    wx.navigateTo({ url: `/pages/trip-detail/trip-detail?id=${trip.companion_id}` })
  },

  onDeleteTrip(e) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    wx.showModal({
      title: '删除行程',
      content: '删除后其他人将无法看到这条找搭子信息，确定删除吗？',
      confirmText: '删除',
      confirmColor: '#ef4444',
      success: async (res) => {
        if (!res.confirm) return
        try {
          const r = await api.deleteCompanion(id)
          if (r && r.success) {
            wx.showToast({ title: '已删除', icon: 'success' })
            this.loadMyTrips()
          } else {
            wx.showToast({ title: (r && r.detail) || '删除失败', icon: 'none' })
          }
        } catch (err) {
          console.error('删除行程失败', err)
          wx.showToast({ title: '网络错误', icon: 'none' })
        }
      }
    })
  },
})
