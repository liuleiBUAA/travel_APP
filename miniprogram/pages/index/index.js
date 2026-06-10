const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    inputMode: 'smart',  // 'smart' or 'manual'
    regions: ['欧洲', '亚洲', '北美', '大洋洲'],
    regionIcons: { '欧洲': '🇪🇺', '亚洲': '🌏', '北美': '🇺🇸', '大洋洲': '🦘' },
    currentRegion: '欧洲',
    countries: [],
    currentCountry: '',
    cities: [],
    selectedCities: [],
    cityInput: '',
    searchResults: [],
    // 手动输入模式
    manualRegionOptions: ['欧洲', '北美', '亚洲', '大洋洲'],
    manualRegionIndex: 0,
    manualCountries: [],
    manualSelectedCountries: [],
    manualCities: '',
    manualDays: '',
    manualPreviewText: '',
    // 表单
    userName: '',
    travelDate: '2026-05-15',
    peopleMin: '1',
    peopleMax: '2',
    genderOptions: ['不限', '男', '女'],
    genderIndex: 0,
    transportOptions: ['不限', '公共交通为主', '自驾为主', '混合'],
    transportIndex: 0,
    accommodationOptions: ['不限', '可拼房', '各住各的'],
    accommodationIndex: 0,
    budgetOptions: ['穷游', '经济', '舒适', '轻奢'],
    budgetSelected: ['经济'],
    photoOptions: ['不限', '一般', '擅长', '大师'],
    photoIndex: 0,
    userMaleCount: '0',
    userFemaleCount: '1',
    publishMsg: '',
    publishOk: false,
    showMorePrefs: false,  // 更多偏好折叠（默认收起，可选项）
    // 用户
    userInfo: null,
    editingNickname: false,
    newNickname: ''
  },

  onLoad() {
    const g = app.globalData
    if (g.selectedCities.length > 0) {
      this.setData({ selectedCities: g.selectedCities, currentRegion: g.currentRegion })
    }
    this.loadCountries(this.data.currentRegion)
  },

  onShow() {
    // 同步用户信息，自动填充昵称
    if (app.globalData.userInfo) {
      this.setData({
        userInfo: app.globalData.userInfo,
        userName: app.globalData.userInfo.nickname || app.globalData.userInfo.nickName || ''
      })
    } else {
      this.setData({ userInfo: null, userName: '' })
    }
    app.globalData.selectedCities = this.data.selectedCities
  },

  // ---- 输入模式切换 ----
  switchInputMode(e) {
    const mode = e.currentTarget.dataset.mode
    this.setData({ inputMode: mode })
    if (mode === 'manual') {
      this.loadManualCountries()
      this.updateManualPreview()
    }
  },

  async onManualRegionChange(e) {
    this.setData({ manualRegionIndex: e.detail.value })
    await this.loadManualCountries()
    this.updateManualPreview()
  },

  async loadManualCountries() {
    const regionName = this.data.manualRegionOptions[this.data.manualRegionIndex]
    try {
      const res = await api.getCountries(regionName)
      this.setData({
        manualCountries: Array.isArray(res.countries) ? res.countries : [],
        manualSelectedCountries: []
      })
    } catch (err) {
      console.error('加载国家失败:', err)
    }
  },

  toggleManualCountry(e) {
    const country = e.currentTarget.dataset.country
    const checked = e.detail.value.length > 0
    let selected = [...this.data.manualSelectedCountries]
    const idx = selected.indexOf(country)
    if (checked && idx === -1) {
      selected.push(country)
    } else if (!checked && idx > -1) {
      selected.splice(idx, 1)
    }
    this.setData({ manualSelectedCountries: selected })
    this.updateManualPreview()
  },

  onManualCitiesInput(e) {
    this.setData({ manualCities: e.detail.value })
    this.updateManualPreview()
  },

  onManualDaysInput(e) {
    this.setData({ manualDays: e.detail.value })
    this.updateManualPreview()
  },

  updateManualPreview() {
    const { manualCities, manualDays, manualRegionIndex, manualRegionOptions } = this.data
    if (!manualCities.trim()) {
      this.setData({ manualPreviewText: '' })
      return
    }

    const cities = manualCities.split(',').map(c => c.trim()).filter(c => c)
    const daysMap = {}

    if (manualDays.trim()) {
      const daysPairs = manualDays.split(',')
      daysPairs.forEach(pair => {
        const parts = pair.split(':').map(s => s.trim())
        if (parts.length === 2) {
          const [city, days] = parts
          daysMap[city] = parseInt(days) || 2
        }
      })
    }

    cities.forEach(city => {
      if (!daysMap[city]) daysMap[city] = 2
    })

    const totalDays = Object.values(daysMap).reduce((a, b) => a + b, 0)
    const region = manualRegionOptions[manualRegionIndex]

    this.setData({
      manualPreviewText: `${region} - ${cities.join(' → ')} 共${totalDays}天`
    })
  },

  // ---- 用户资料 ----
  showEditNickname() {
    const ui = this.data.userInfo || {}
    this.setData({ editingNickname: true, newNickname: ui.nickname || '' })
  },

  cancelEditNickname() {
    this.setData({ editingNickname: false })
  },

  onNicknameInput(e) {
    this.setData({ newNickname: e.detail.value })
  },

  async saveNickname() {
    const nickname = this.data.newNickname.trim()
    if (!nickname) { wx.showToast({ title: '昵称不能为空', icon: 'none' }); return }
    const token = wx.getStorageSync('token')
    if (!token) { wx.showToast({ title: '请先登录', icon: 'none' }); return }
    try {
      const res = await api.updateProfile(token, nickname)
      if (res.success) {
        app.globalData.userInfo.nickname = res.nickname
        this.setData({ userInfo: app.globalData.userInfo, userName: res.nickname, editingNickname: false })
        wx.showToast({ title: '已更新' })
      }
    } catch (e) {
      wx.showToast({ title: '更新失败', icon: 'none' })
    }
  },

  onHide() {
    // 同步到全局
    app.globalData.selectedCities = this.data.selectedCities
  },

  // ---- 区域/国家/城市 ----
  async selectRegion(e) {
    const region = e.currentTarget.dataset.region
    this.setData({ currentRegion: region, currentCountry: '', cities: [], countries: [] })
    app.globalData.currentRegion = region
    await this.loadCountries(region)
  },

  async loadCountries(region) {
    console.log('[loadCountries] 开始加载区域:', region)
    try {
      const res = await api.getCountries(region)
      console.log('[loadCountries] 响应:', JSON.stringify(res))
      if (res && res.success && Array.isArray(res.countries)) {
        this.setData({ countries: res.countries })
        console.log('[loadCountries] 设置国家数:', res.countries.length)
      } else {
        console.error('[loadCountries] 响应格式异常:', res)
        this.setData({ countries: [] })
      }
    } catch (err) {
      console.error('[loadCountries] 失败:', err)
      this.setData({ countries: [] })
    }
  },

  selectCountry(e) {
    const country = e.currentTarget.dataset.country
    this.setData({ currentCountry: country })
    this.loadCities(this.data.currentRegion, country)
  },

  async loadCities(region, country) {
    try {
      const res = await api.getCities(region, country, 16)
      if (res.success && Array.isArray(res.cities)) {
        this.setData({ cities: res.cities })
      } else {
        this.setData({ cities: [] })
      }
    } catch (err) {
      console.error('加载城市失败', err)
      this.setData({ cities: [] })
    }
  },

  toggleCity(e) {
    const name = e.currentTarget.dataset.name
    let list = this.data.selectedCities.slice()
    const idx = list.indexOf(name)
    if (idx > -1) {
      list.splice(idx, 1)
    } else {
      list.push(name)
    }
    this.setData({ selectedCities: list })
    app.globalData.selectedCities = list
  },

  clearAllCities() {
    this.setData({ selectedCities: [] })
    app.globalData.selectedCities = []
    app.globalData.generatedRoute = null
  },

  removeCity(e) {
    const name = e.currentTarget.dataset.name
    let list = this.data.selectedCities.filter(c => c !== name)
    this.setData({ selectedCities: list })
    app.globalData.selectedCities = list
  },

  // ---- 手动输入 ----
  onCityInput(e) {
    const val = e.detail.value.trim()
    this.setData({ cityInput: val })
    if (!val) {
      this.setData({ searchResults: [] })
      return
    }
    // 延迟搜索
    clearTimeout(this._searchTimer)
    this._searchTimer = setTimeout(async () => {
      try {
        const res = await api.searchDestinations(val)
        this.setData({ searchResults: Array.isArray(res.results) ? res.results : [] })
      } catch (err) {
        console.error('搜索失败', err)
      }
    }, 300)
  },

  selectSearchCity(e) {
    const name = e.currentTarget.dataset.name
    if (this.data.selectedCities.indexOf(name) === -1) {
      const list = this.data.selectedCities.concat(name)
      this.setData({ selectedCities: list, cityInput: '', searchResults: [] })
      app.globalData.selectedCities = list
    }
  },

  addManualCity() {
    const name = this.data.cityInput.trim()
    if (name && this.data.selectedCities.indexOf(name) === -1) {
      const list = this.data.selectedCities.concat(name)
      this.setData({ selectedCities: list, cityInput: '', searchResults: [] })
      app.globalData.selectedCities = list
    }
  },

  // ---- 更多偏好折叠 ----
  toggleMorePrefs() {
    this.setData({ showMorePrefs: !this.data.showMorePrefs })
  },

  // ---- 表单 ----
  onInput(e) {
    const field = e.currentTarget.dataset.field
    this.setData({ [field]: e.detail.value })
  },

  onDateChange(e) {
    this.setData({ travelDate: e.detail.value })
  },

  onPickerChange(e) {
    const field = e.currentTarget.dataset.field
    this.setData({ [field]: parseInt(e.detail.value) })
  },

  toggleBudget(e) {
    const val = e.currentTarget.dataset.value
    const checked = e.detail.value.length > 0
    let list = this.data.budgetSelected.slice()
    const idx = list.indexOf(val)
    if (checked && idx === -1) {
      list.push(val)
    } else if (!checked && idx > -1) {
      list.splice(idx, 1)
    }
    this.setData({ budgetSelected: list })
  },

  // ---- 发布 ----
  async publish() {
    const d = this.data

    // 必须先登录
    if (!app.globalData.userInfo) {
      wx.showModal({
        title: '请先登录',
        content: '登录后才能发布行程，是否去登录？',
        confirmText: '去登录',
        success: (res) => {
          if (res.confirm) {
            wx.switchTab({ url: '/pages/profile/profile' })
          }
        }
      })
      return
    }

    const userName = app.globalData.userInfo.nickname || app.globalData.userInfo.nickName || '匿名用户'

    let route = null
    wx.showLoading({ title: '发布中...' })

    try {
      if (d.inputMode === 'manual') {
        // 手动输入模式
        if (!d.manualCities.trim()) {
          wx.hideLoading()
          wx.showToast({ title: '请输入城市名称', icon: 'none' })
          return
        }

        const cities = d.manualCities.split(',').map(c => c.trim()).filter(c => c)
        if (cities.length < 1) {
          wx.hideLoading()
          wx.showToast({ title: '请至少输入1个城市', icon: 'none' })
          return
        }

        const daysMap = {}
        if (d.manualDays.trim()) {
          const daysPairs = d.manualDays.split(',')
          daysPairs.forEach(pair => {
            const parts = pair.split(':').map(s => s.trim())
            if (parts.length === 2) {
              const [city, days] = parts
              daysMap[city] = parseInt(days) || 2
            }
          })
        }
        cities.forEach(city => {
          if (!daysMap[city]) daysMap[city] = 2
        })

        if (d.manualSelectedCountries.length === 0) {
          wx.hideLoading()
          wx.showToast({ title: '请至少选择一个国家', icon: 'none' })
          return
        }

        const regionMap = { '欧洲': 'Europe', '北美': 'North_America', '亚洲': 'Asia', '大洋洲': 'Oceania' }
        const region = regionMap[d.manualRegionOptions[d.manualRegionIndex]]

        const routeRes = await api.generateRoute({
          mode: 'manual',
          region: region,
          countries: d.manualSelectedCountries,
          manual_route: {
            cities: cities,
            days: daysMap
          }
        })
        route = routeRes.route

      } else {
        // 智能选城模式
        if (d.selectedCities.length < 2) {
          wx.hideLoading()
          wx.showToast({ title: '请至少选择2个城市', icon: 'none' })
          return
        }

        const routeRes = await api.generateRoute({
          mode: 'destination',
          cities: d.selectedCities
        })
        route = routeRes.route
      }

      app.globalData.generatedRoute = route

      // 发布 - ✅ 修复: 不传 user_id 和 user_name，后端从 token 自动获取
      const pubRes = await api.publishCompanion({
        route_json: route,
        travel_date: d.travelDate,
        duration_days: route.total_days || 10,
        flexibility_days: 3,
        seeking: {
          people_min: parseInt(d.peopleMin),
          people_max: parseInt(d.peopleMax),
          gender: d.genderOptions[d.genderIndex]
        },
        transport_mode: d.transportOptions[d.transportIndex],
        accommodation: d.accommodationOptions[d.accommodationIndex],
        budget_level: d.budgetSelected.join(','),
        good_at_photo: d.photoOptions[d.photoIndex],
        user_male_count: parseInt(d.userMaleCount),
        user_female_count: parseInt(d.userFemaleCount)
      })

      wx.hideLoading()
      this.setData({ publishMsg: '发布成功！ID: ' + pubRes.companion_id, publishOk: true })

      // 自动搜索匹配的搭子
      try {
        const matchParams = {
          route_json: route,
          travel_date: d.travelDate,
          time_flexibility_days: 3,
          people_min: parseInt(d.peopleMin),
          people_max: parseInt(d.peopleMax),
          gender: d.genderOptions[d.genderIndex],
          transport_mode: d.transportOptions[d.transportIndex],
          accommodation: d.accommodationOptions[d.accommodationIndex],
          budget_level: d.budgetSelected.join(','),
          good_at_photo: d.photoOptions[d.photoIndex],
          user_male_count: parseInt(d.userMaleCount),
          user_female_count: parseInt(d.userFemaleCount)
        }

        const matchRes = await api.matchCompanions(matchParams)

        if (matchRes.count > 0) {
          wx.showModal({
            title: '发布成功',
            content: `找到 ${matchRes.count} 个匹配的搭子，是否查看？`,
            confirmText: '查看',
            cancelText: '稍后',
            success: (res) => {
              if (res.confirm) {
                wx.switchTab({ url: '/pages/match/match' })
              }
            }
          })
        } else {
          wx.showToast({ title: '发布成功，暂无匹配的搭子', icon: 'none', duration: 2000 })
        }
      } catch (matchErr) {
        console.error('自动匹配失败:', matchErr)
        // 即使匹配失败，也保持发布成功的状态
        wx.showToast({ title: '发布成功', icon: 'success' })
      }

    } catch (err) {
      wx.hideLoading()
      this.setData({ publishMsg: '发布失败: ' + (err.errMsg || '网络错误'), publishOk: false })
    }
  }
})
