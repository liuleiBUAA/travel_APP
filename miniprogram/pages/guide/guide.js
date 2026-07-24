const api = require('../../utils/api')
const app = getApp()

// 城市分组配置（纯展示层）：仅目的地数量多的国家分组，其余国家平铺。
// key = 国家名（与后端 destinations 目录一致）；顺序即渲染顺序。
const CITY_GROUPS = {
  '美国东部中部': [
    { icon: '🏙️', title: '东北都会', cities: ['纽约', '波士顿', '华盛顿', '费城', '尼亚加拉瀑布'] },
    { icon: '⛰️', title: '阿巴拉契亚山区', cities: ['阿卡迪亚国家公园', '大雾山国家公园', '仙纳度国家公园', '美东“蓝岭公路与双园”大环线'] },
    { icon: '🌴', title: '佛州 & 南方', cities: ['奥兰多', '迈阿密', '坦帕', '亚特兰大', '大沼泽地国家公园', '新奥尔良', '休斯顿'] },
    { icon: '🌾', title: '中西部 & 落基山', cities: ['芝加哥', '密歇根湖“巨型沙丘与五彩悬崖”大环线', '丹佛', '洛基山国家公园'] },
    { icon: '🔄', title: '跨城大环线', cities: ['🔄 波士顿+阿卡迪亚环线'] },
  ],
  '美国西部': [
    { icon: '🌉', title: '加州海岸都会', cities: ['旧金山', '洛杉矶', '圣地亚哥', '1号公路', '红杉国家公园'] },
    { icon: '🎰', title: '内华达 & 峡谷沙漠', cities: ['拉斯维加斯', '死亡谷国家公园', '🔄 羚羊谷+大峡谷2日环线'] },
    { icon: '🌲', title: '山地国家公园', cities: ['优胜美地国家公园', '冰川国家公园', '🔄 黄石大提顿环线'] },
    { icon: '🌧️', title: '西北太平洋', cities: ['西雅图', '波特兰', '火山口湖国家公园', '华盛顿州“海山冰川”大环线'] },
    { icon: '🔄', title: '跨州大环线', cities: ['🔄 精华版美西环线'] },
  ],
}

// 把扁平城市列表按 CITY_GROUPS 切成分组；未命中的城市兜底进「更多」组，保证一城不落。
function buildCityGroups(country, cities) {
  const defs = CITY_GROUPS[country]
  if (!defs) return []
  const byName = {}
  cities.forEach(c => { byName[c.name] = c })
  const used = {}
  const groups = []
  defs.forEach(def => {
    const list = []
    def.cities.forEach(name => {
      if (byName[name]) { list.push(byName[name]); used[name] = true }
    })
    if (list.length) groups.push({ icon: def.icon, title: def.title, cities: list })
  })
  const leftover = cities.filter(c => !used[c.name])
  if (leftover.length) groups.push({ icon: '📍', title: '更多', cities: leftover })
  return groups
}

Page({
  data: {
    guideMode: 'recommend',   // 'recommend' 帮我推荐 | 'pick' 知道去哪
    // 攻略搜索
    guideSearchInput: '',
    guideSearchResults: [],
    guideSearched: false,
    selectedCities: [],
    // 「知道去哪」模式：自己选城
    pickSearchInput: '',
    pickSuggestions: [],
    pickCountries: [],
    pickCurrentCountry: '',
    pickCities: [],
    pickGroups: [],   // 城市分组（有则按分区渲染，无则扁平）
    showRouteOptions: false,  // 路线高级选项折叠
    // 推荐
    monthOptions: [
      { value: 1, label: '1月 - 冬季' }, { value: 2, label: '2月 - 冬季' },
      { value: 3, label: '3月 - 春季' }, { value: 4, label: '4月 - 春季' },
      { value: 5, label: '5月 - 春季' }, { value: 6, label: '6月 - 夏季' },
      { value: 7, label: '7月 - 夏季' }, { value: 8, label: '8月 - 夏季' },
      { value: 9, label: '9月 - 秋季' }, { value: 10, label: '10月 - 秋季' },
      { value: 11, label: '11月 - 秋季' }, { value: 12, label: '12月 - 冬季' }
    ],
    monthIndex: 4,
    recommendDays: '',
    regionOptions: [
      { value: 'Europe', label: '欧洲', cn: '欧洲' },
      { value: 'Asia', label: '亚洲', cn: '亚洲' },
      { value: 'North_America', label: '北美', cn: '北美' },
      { value: 'Oceania', label: '大洋洲', cn: '大洋洲' }
    ],
    recommendRegion: 'Europe',
    recommendCountries: [],
    recommendSelectedCountries: [],
    tagOptions: [
      { value: '自然风光', label: '🏞️ 自然风光' },
      { value: '人文历史', label: '🏛️ 人文历史' },
      { value: '海岛海滨', label: '🏖️ 海岛海滨' },
      { value: '现代都市', label: '🏙️ 现代都市' },
      { value: '户外探险', label: '⛰️ 户外探险' },
      { value: '小镇村落', label: '🏘️ 小镇村落' },
      { value: '亲子家庭', label: '👨‍👩‍👧‍👦 亲子家庭' }
    ],
    recommendSelectedTags: [],
    recommendStartCity: '',
    recommendPreferences: '',
    recommendResult: [],
    // 路线选项
    forceGateway: true,
    forceOrder: false,
    maxHoursOptions: [
      { value: 3, label: '3小时' },
      { value: 4, label: '4小时（推荐）' },
      { value: 5, label: '5小时' },
      { value: 6, label: '6小时' }
    ],
    maxHoursIndex: 1,
    transportOptions: [
      { value: 'auto', label: '自动' },
      { value: 'train', label: '优先火车' },
      { value: 'flight', label: '优先飞机' }
    ],
    transportIndex: 0,
    displayModeOptions: [
      { value: 'compact', label: '精简' },
      { value: 'detailed', label: '详细' }
    ],
    displayModeIndex: 0,
    destStartNode: '',
    destEndNode: '',
    route: null,
    routeCities: [],
    routeItinerary: [],
    loading: false,
    loadingText: '',
    errorMsg: ''
  },

  // 点图放大预览，同一天的图可左右滑
  previewDayImage(e) {
    const { images, url } = e.currentTarget.dataset
    wx.previewImage({ current: url, urls: (images || []).map(p => p.url) })
  },

  openPlaybook(e) {
    const name = e.currentTarget.dataset.name
    wx.navigateTo({ url: `/pages/attraction/attraction?name=${encodeURIComponent(name)}` })
  },

  // 攻略搜索：输入地名 → 命中卡片
  onGuideSearchInput(e) {
    const v = e.detail.value
    this.setData({ guideSearchInput: v })
    clearTimeout(this._searchTimer)
    if (!v || !v.trim()) {
      this.setData({ guideSearchResults: [], guideSearched: false })
      return
    }
    // 防抖 300ms
    this._searchTimer = setTimeout(() => this.doGuideSearch(v.trim()), 300)
  },

  doGuideSearch(q) {
    api.searchAttractions(q).then(res => {
      const results = ((res && res.results) || []).map(r => ({
        ...r,
        thumb: r.thumb ? api.imageUrl(r.thumb) : ''
      }))
      this.setData({ guideSearchResults: results, guideSearched: true })
    }).catch(() => {
      this.setData({ guideSearchResults: [], guideSearched: true })
    })
  },

  clearGuideSearch() {
    clearTimeout(this._searchTimer)
    this.setData({ guideSearchInput: '', guideSearchResults: [], guideSearched: false })
  },

  // 点搜索结果卡片 → 跳详情页
  openSearchResult(e) {
    const name = e.currentTarget.dataset.name
    wx.navigateTo({ url: `/pages/attraction/attraction?name=${encodeURIComponent(name)}` })
  },

  // 行程里 images 的相对路径转完整 URL
  resolveItineraryImages(itinerary) {
    return (itinerary || []).map(d => {
      if (Array.isArray(d.images) && d.images.length) {
        d.images = d.images.map(p => ({ ...p, url: api.imageUrl(p.url) }))
      }
      return d
    })
  },

  onLoad() {
    this.loadRecommendCountries('欧洲')
  },

  onShow() {
    const sc = app.globalData && Array.isArray(app.globalData.selectedCities)
      ? app.globalData.selectedCities
      : []
    this.setData({ selectedCities: sc })
    if (app.globalData && app.globalData.generatedRoute) {
      const r = app.globalData.generatedRoute
      this.setData({
        route: r,
        routeCities: Array.isArray(r.cities) ? r.cities : [],
        routeItinerary: this.resolveItineraryImages(Array.isArray(r.itinerary) ? r.itinerary : [])
      })
    }
    // onShow 也调用一次，确保切换 tab 后也能加载
    if (this.data.recommendCountries.length === 0) {
      this.loadRecommendCountries('欧洲')
    }
  },

  // ---- 推荐相关 ----
  onMonthChange(e) {
    this.setData({ monthIndex: parseInt(e.detail.value) })
  },

  onInput(e) {
    const field = e.currentTarget.dataset.field
    this.setData({ [field]: e.detail.value })
  },

  selectRecommendRegion(e) {
    const region = e.currentTarget.dataset.region
    const opt = this.data.regionOptions.find(r => r.value === region)
    this.setData({ recommendRegion: region, recommendSelectedCountries: [], recommendCountries: [] })
    this.loadRecommendCountries(opt.cn)
  },

  async loadRecommendCountries(regionCN) {
    console.log('[guide] 开始加载国家:', regionCN)
    console.log('[guide] 当前 recommendCountries:', this.data.recommendCountries)
    try {
      const res = await api.getCountries(regionCN)
      console.log('[guide] 响应:', JSON.stringify(res))
      console.log('[guide] res.success:', res.success, 'res.countries:', res.countries)
      if (res && res.success && Array.isArray(res.countries)) {
        console.log('[guide] 准备设置国家，数量:', res.countries.length)
        this.setData({ recommendCountries: res.countries }, () => {
          console.log('[guide] setData 完成，当前 recommendCountries:', this.data.recommendCountries)
        })
      } else {
        console.error('[guide] 响应格式异常:', res)
        this.setData({ recommendCountries: [] })
      }
    } catch (e) {
      console.error('[guide] 加载国家失败:', e)
      console.error('[guide] 错误详情:', JSON.stringify(e))
      this.setData({ recommendCountries: [] })
    }
  },

  toggleManualRecommendCountry(e) {
    const country = e.currentTarget.dataset.country
    const checked = e.detail.value.length > 0
    let selected = [...this.data.recommendSelectedCountries]
    const idx = selected.indexOf(country)
    if (checked && idx === -1) {
      selected.push(country)
    } else if (!checked && idx > -1) {
      selected.splice(idx, 1)
    }
    this.setData({ recommendSelectedCountries: selected })
  },

  toggleManualRecommendTag(e) {
    const tag = e.currentTarget.dataset.tag
    const checked = e.detail.value.length > 0
    let selected = [...this.data.recommendSelectedTags]
    const idx = selected.indexOf(tag)
    if (checked && idx === -1) {
      selected.push(tag)
    } else if (!checked && idx > -1) {
      selected.splice(idx, 1)
    }
    this.setData({ recommendSelectedTags: selected })
  },

  async getRecommendation() {
    const d = this.data
    const daysInput = d.recommendDays.trim ? d.recommendDays.trim() : String(d.recommendDays).trim()
    const days = daysInput ? parseInt(daysInput) : 10  // 不填默认10天
    if (daysInput && (days < 3 || days > 30)) {
      wx.showToast({ title: '天数需在3-30之间', icon: 'none' })
      return
    }

    this.setData({ loading: true, loadingText: '正在推荐...', recommendResult: [], errorMsg: '' })

    try {
      const body = {
        mode: 'recommend',
        travel_month: d.monthOptions[d.monthIndex].value,
        duration_days: days,
        region: d.recommendRegion,
        force_gateway_departure: d.forceGateway,
        force_order: d.forceOrder,
        same_day_max_hours: d.maxHoursOptions[d.maxHoursIndex].value,
        transport_preference: d.transportOptions[d.transportIndex].value,
        options_display_mode: d.displayModeOptions[d.displayModeIndex].value
      }
      if (d.recommendSelectedCountries.length > 0) {
        body.countries = d.recommendSelectedCountries
      }
      if (d.recommendSelectedTags.length > 0) {
        body.tags = d.recommendSelectedTags
      }
      const startCity = (d.recommendStartCity || '').trim()
      if (startCity) {
        body.start_city = startCity
      }
      const prefsText = (d.recommendPreferences || '').trim()
      if (prefsText) {
        body.destinations = prefsText.split(',').map(c => c.trim()).filter(c => c)
      }

      const res = await api.generateRoute(body)
      const cities = (res.route && Array.isArray(res.route.cities)) ? res.route.cities : []
      this.setData({ loading: false, recommendResult: cities })

      if (cities.length === 0) {
        this.setData({ errorMsg: '未找到合适的推荐路线' })
      }
    } catch (err) {
      this.setData({ loading: false, errorMsg: '推荐失败' })
    }
  },

  applyRecommendation() {
    const cities = this.data.recommendResult
    if (cities.length === 0) return
    const merged = this.data.selectedCities.slice()
    cities.forEach(c => {
      if (merged.indexOf(c) === -1) merged.push(c)
    })
    this.setData({ selectedCities: merged })
    app.globalData.selectedCities = merged
    wx.showToast({ title: `已添加${cities.length}个城市`, icon: 'success' })
  },

  // ---- 模式切换 ----
  switchGuideMode(e) {
    const mode = e.currentTarget.dataset.mode
    this.setData({ guideMode: mode })
    if (mode === 'pick' && this.data.pickCountries.length === 0) {
      this.loadPickCountries(this.data.regionOptions.find(r => r.value === this.data.recommendRegion).cn)
    }
  },

  toggleRouteOptions() {
    this.setData({ showRouteOptions: !this.data.showRouteOptions })
  },

  // ---- 「知道去哪」模式：搜索联想（国家+城市）----
  onPickSearchInput(e) {
    const val = e.detail.value.trim()
    this.setData({ pickSearchInput: val })
    if (!val) {
      this.setData({ pickSuggestions: [] })
      return
    }
    clearTimeout(this._pickSearchTimer)
    this._pickSearchTimer = setTimeout(async () => {
      try {
        const res = await api.searchDestinations(val)
        this.setData({ pickSuggestions: Array.isArray(res.suggestions) ? res.suggestions : [] })
      } catch (err) {
        console.error('搜索失败', err)
      }
    }, 300)
  },

  selectPickSuggestion(e) {
    const item = this.data.pickSuggestions[e.currentTarget.dataset.index]
    if (!item) return
    if (item.type === 'country') {
      // 选国家：切到对应区域并展开该国城市卡片
      const opt = this.data.regionOptions.find(r => r.cn === item.region)
      this.setData({
        pickSearchInput: '',
        pickSuggestions: [],
        recommendRegion: opt ? opt.value : this.data.recommendRegion,
        pickCurrentCountry: item.name
      })
      if (opt) this.loadPickCountries(opt.cn)
      this.loadPickCities(item.name)
    } else {
      // 选城市：直接加入已选
      let list = this.data.selectedCities.slice()
      if (list.indexOf(item.name) === -1) list.push(item.name)
      this.setData({ pickSearchInput: '', pickSuggestions: [], selectedCities: list })
      app.globalData.selectedCities = list
    }
  },

  // ---- 「知道去哪」模式：自己选城（区域→国家→城市）----
  selectPickRegion(e) {
    const region = e.currentTarget.dataset.region
    const opt = this.data.regionOptions.find(r => r.value === region)
    this.setData({ recommendRegion: region, pickCurrentCountry: '', pickCities: [], pickGroups: [], pickCountries: [] })
    this.loadPickCountries(opt.cn)
  },

  async loadPickCountries(regionCN) {
    try {
      const res = await api.getCountries(regionCN)
      this.setData({ pickCountries: (res && res.success && Array.isArray(res.countries)) ? res.countries : [] })
    } catch (e) {
      this.setData({ pickCountries: [] })
    }
  },

  selectPickCountry(e) {
    const country = e.currentTarget.dataset.country
    this.setData({ pickCurrentCountry: country })
    this.loadPickCities(country)
  },

  async loadPickCities(country) {
    const regionCN = this.data.regionOptions.find(r => r.value === this.data.recommendRegion).cn
    try {
      const res = await api.getCities(regionCN, country, 40)
      const cities = (res && res.success && Array.isArray(res.cities)) ? res.cities : []
      this.setData({ pickCities: cities, pickGroups: buildCityGroups(country, cities) })
    } catch (e) {
      this.setData({ pickCities: [], pickGroups: [] })
    }
  },

  togglePickCity(e) {
    const name = e.currentTarget.dataset.name
    let list = this.data.selectedCities.slice()
    const idx = list.indexOf(name)
    if (idx > -1) list.splice(idx, 1)
    else list.push(name)
    this.setData({ selectedCities: list })
    app.globalData.selectedCities = list
  },

  removeSelectedCity(e) {
    const name = e.currentTarget.dataset.name
    const list = this.data.selectedCities.filter(c => c !== name)
    this.setData({ selectedCities: list })
    app.globalData.selectedCities = list
  },

  clearSelectedCities() {
    this.setData({ selectedCities: [] })
    app.globalData.selectedCities = []
    app.globalData.generatedRoute = null
  },

  // ---- 路线生成 ----
  onSwitchChange(e) {
    const field = e.currentTarget.dataset.field
    this.setData({ [field]: e.detail.value })
  },

  onMaxHoursChange(e) {
    this.setData({ maxHoursIndex: parseInt(e.detail.value) })
  },

  onTransportChange(e) {
    this.setData({ transportIndex: parseInt(e.detail.value) })
  },

  onDisplayModeChange(e) {
    this.setData({ displayModeIndex: parseInt(e.detail.value) })
  },

  async generate() {
    if (this.data.selectedCities.length < 2) {
      wx.showToast({ title: '请至少选择2个城市', icon: 'none' })
      return
    }

    this.setData({ loading: true, loadingText: '正在生成攻略...', route: null, errorMsg: '' })

    try {
      const res = await api.generateRoute({
        mode: 'destination',
        cities: this.data.selectedCities,
        region: this.data.recommendRegion,
        force_gateway_departure: this.data.forceGateway,
        force_order: this.data.forceOrder,
        same_day_max_hours: this.data.maxHoursOptions[this.data.maxHoursIndex].value,
        transport_preference: this.data.transportOptions[this.data.transportIndex].value,
        options_display_mode: this.data.displayModeOptions[this.data.displayModeIndex].value,
        start_node: this.data.destStartNode.trim() || null,
        end_node: this.data.destEndNode.trim() || null
      })

      const route = res.route || null
      const routeCities = (route && Array.isArray(route.cities)) ? route.cities : []
      const routeItinerary = this.resolveItineraryImages((route && Array.isArray(route.itinerary)) ? route.itinerary : [])
      app.globalData.generatedRoute = route
      this.setData({ route, routeCities, routeItinerary, loading: false })
    } catch (err) {
      this.setData({ loading: false, errorMsg: '生成失败' })
    }
  },

  // ---- 打通：带着已生成的路线去发布找搭子 ----
  goFindCompanion() {
    const route = this.data.route
    if (!route) {
      wx.showToast({ title: '请先生成攻略', icon: 'none' })
      return
    }
    // 标记来自攻略，发布页 onShow 据此填充城市，避免被覆盖
    app.globalData.generatedRoute = route
    app.globalData.selectedCities = Array.isArray(route.cities) ? route.cities.slice() : []
    app.globalData.routeFromGuide = true
    wx.navigateTo({ url: '/pages/index/index' })
  }
})
