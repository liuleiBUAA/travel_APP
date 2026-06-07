const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    searchKeyword: '',
    searchLoading: false,
    searchDone: false,
    searchResults: [],
    selectedCities: [],
    matchDate: '2026-05-15',
    flexOptions: [
      { value: 3, label: '±3天' },
      { value: 5, label: '±5天' },
      { value: 7, label: '±7天' },
      { value: 14, label: '±14天' }
    ],
    flexIndex: 2,
    peopleMin: '',
    peopleMax: '',
    genderOptions: ['不限', '男', '女'],
    genderIndex: 0,
    transportOptions: ['不限', '公共交通为主', '自驾为主', '混合'],
    transportIndex: 0,
    accommodationOptions: ['不限', '可拼房', '各住各的'],
    accommodationIndex: 0,
    budgetOptions: ['穷游', '经济', '舒适', '轻奢'],
    budgetSelected: [],
    photoOptions: ['不限', '一般', '擅长', '大师'],
    photoIndex: 0,
    userMaleCount: '',
    userFemaleCount: '',
    loading: false,
    matchCount: -1,
    matches: [],
    companions: []
  },

  onShow() {
    const sc = app.globalData && Array.isArray(app.globalData.selectedCities)
      ? app.globalData.selectedCities
      : []
    this.setData({ selectedCities: sc })
    this.loadCompanions()
  },

  onSearchInput(e) {
    this.setData({ searchKeyword: e.detail.value })
  },

  async doSearch() {
    const keyword = this.data.searchKeyword.trim()
    if (!keyword) {
      wx.showToast({ title: '请输入关键词', icon: 'none' })
      return
    }
    this.setData({ searchLoading: true, searchDone: false, searchResults: [] })
    try {
      const res = await api.searchCompanions(keyword)
      const searchResults = (Array.isArray(res.data) ? res.data : []).map(item => ({
        ...item,
        route: (item.route && Array.isArray(item.route.cities)) ? item.route : { cities: [] }
      }))
      this.setData({
        searchLoading: false,
        searchDone: true,
        searchResults
      })
    } catch (err) {
      this.setData({ searchLoading: false, searchDone: true })
      wx.showToast({ title: '搜索失败', icon: 'none' })
    }
  },

  onDateChange(e) {
    this.setData({ matchDate: e.detail.value })
  },

  onFlexChange(e) {
    this.setData({ flexIndex: parseInt(e.detail.value) })
  },

  onPickerChange(e) {
    const field = e.currentTarget.dataset.field
    this.setData({ [field]: parseInt(e.detail.value) })
  },

  onMatchInput(e) {
    const field = e.currentTarget.dataset.field
    this.setData({ [field]: e.detail.value })
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

  async loadCompanions() {
    try {
      const res = await api.listCompanions(20)
      if (res.success && Array.isArray(res.data)) {
        const companions = res.data.map(c => ({
          ...c,
          route: (c.route && Array.isArray(c.route.cities)) ? c.route : { cities: [] }
        }))
        this.setData({ companions })
      } else {
        this.setData({ companions: [] })
      }
    } catch (err) {
      console.error('加载列表失败', err)
    }
  },

  async startMatch() {
    if (this.data.selectedCities.length < 2) {
      wx.showToast({ title: '请至少选择2个城市', icon: 'none' })
      return
    }

    this.setData({ loading: true, matchCount: -1, matches: [] })

    try {
      // 确保有路线
      let route = app.globalData.generatedRoute
      if (!route) {
        const routeRes = await api.generateRoute({
          mode: 'destination',
          cities: this.data.selectedCities
        })
        route = routeRes.route || null
        app.globalData.generatedRoute = route
      }

      const matchParams = {
        route_json: route,
        travel_date: this.data.matchDate,
        time_flexibility_days: this.data.flexOptions[this.data.flexIndex].value
      }

      // 可选字段：只有填写了才传
      if (this.data.peopleMin) matchParams.people_min = parseInt(this.data.peopleMin)
      if (this.data.peopleMax) matchParams.people_max = parseInt(this.data.peopleMax)

      const gender = this.data.genderOptions[this.data.genderIndex]
      if (gender && gender !== '不限') matchParams.gender = gender

      const transport = this.data.transportOptions[this.data.transportIndex]
      if (transport && transport !== '不限') matchParams.transport_mode = transport

      const accommodation = this.data.accommodationOptions[this.data.accommodationIndex]
      if (accommodation && accommodation !== '不限') matchParams.accommodation = accommodation

      const photo = this.data.photoOptions[this.data.photoIndex]
      if (photo && photo !== '不限') matchParams.good_at_photo = photo

      if (this.data.budgetSelected.length > 0) {
        matchParams.budget_level = this.data.budgetSelected.join(',')
      }

      if (this.data.userMaleCount) matchParams.user_male_count = parseInt(this.data.userMaleCount)
      if (this.data.userFemaleCount) matchParams.user_female_count = parseInt(this.data.userFemaleCount)

      const res = await api.matchCompanions(matchParams)

      // 格式化分数为百分比
      const matches = (Array.isArray(res.matches) ? res.matches : []).map(m => ({
        ...m,
        route: (m.route && Array.isArray(m.route.cities)) ? m.route : { cities: [] },
        seeking: m.seeking || {},
        match_score_pct: Math.round((m.match_score || 0) * 100),
        similarity_score_pct: Math.round((m.similarity_score || 0) * 100),
        time_score_pct: Math.round((m.time_score || 0) * 100),
        preference_score_pct: Math.round((m.preference_score || 0) * 100)
      }))

      this.setData({
        loading: false,
        matchCount: res.count || 0,
        matches: matches
      })
    } catch (err) {
      this.setData({ loading: false })
      wx.showToast({ title: '匹配失败', icon: 'none' })
      console.error('匹配失败', err)
    }
  }
})
