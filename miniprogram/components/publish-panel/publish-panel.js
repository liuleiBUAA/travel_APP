const api = require('../../utils/api')
const app = getApp()

Component({
  options: {
    // 让全局 app.wxss 的 .card/.form-input 等样式作用到组件内部
    styleIsolation: 'apply-shared'
  },

  data: {
    inputMode: 'smart',  // 'smart' | 'manual' | 'custom'
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
    // 自定义模式
    customTitle: '',          // 标题（必填）
    customText: '',           // 一句话
    customImages: [],         // 已上传图片 URL 数组（相对路径，用于发布）
    customImagesDisplay: [],  // 完整 URL 数组（用于页面展示）
    customUploading: false,   // 上传中标志
    // 表单
    userName: '',
    travelDate: '',
    todayStr: '',
    peopleMin: '1',
    peopleMax: '2',
    genderOptions: ['不限', '男', '女', '情侣'],
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

  lifetimes: {
    attached() {
      // 默认出发日期 = 30天后，日期选择下限 = 今天
      const fmt = (dt) => `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`
      const now = new Date()
      const defaultDate = new Date(now.getTime() + 30 * 24 * 3600 * 1000)
      this.setData({ todayStr: fmt(now), travelDate: fmt(defaultDate) })

      const g = app.globalData
      if (g.selectedCities.length > 0) {
        this.setData({ selectedCities: g.selectedCities, currentRegion: g.currentRegion })
      }
      this.loadCountries(this.data.currentRegion)
      // 同页 tab 切换时只触发 attached、不触发 pageLifetimes.show，
      // 故在此也执行一次 show 逻辑。置标志位，避免独立页里 attached+show 重复请求
      this._justAttached = true
      this.refreshOnShow()
    }
  },

  pageLifetimes: {
    show() {
      // attached 刚跑过则跳过本次，防止重复请求
      if (this._justAttached) {
        this._justAttached = false
        return
      }
      this.refreshOnShow()
    },

    hide() {
      // 同步到全局
      app.globalData.selectedCities = this.data.selectedCities
    }
  },

  methods: {
    // show 时的刷新逻辑（attached 与 pageLifetimes.show 共用）
    refreshOnShow() {
      // 同步用户信息，自动填充昵称
      if (app.globalData.userInfo) {
        this.setData({
          userInfo: app.globalData.userInfo,
          userName: app.globalData.userInfo.nickname || app.globalData.userInfo.nickName || ''
        })
        this.prefillFromCard()
      } else {
        this.setData({ userInfo: null, userName: '' })
      }

      // 从「做攻略」带路线过来：填充已选城市并切到智能选城模式
      if (app.globalData.routeFromGuide) {
        app.globalData.routeFromGuide = false
        const cities = Array.isArray(app.globalData.selectedCities) ? app.globalData.selectedCities : []
        if (cities.length > 0) {
          this.setData({ selectedCities: cities, inputMode: 'smart' })
          wx.showToast({ title: '已带入攻略路线，填日期即可发布', icon: 'none', duration: 2200 })
        }
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
      } else if (mode === 'custom') {
        // 自定义模式复用智能选城的地区/国家/城市选择器
        if (this.data.countries.length === 0) {
          this.loadCountries(this.data.currentRegion)
        }
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

    // ---- 自定义模式 ----
    onCustomTitleInput(e) {
      this.setData({ customTitle: e.detail.value })
    },

    onCustomTextInput(e) {
      this.setData({ customText: e.detail.value })
    },

    chooseCustomImages() {
      const remaining = 9 - this.data.customImages.length
      if (remaining <= 0) {
        wx.showToast({ title: '最多上传9张', icon: 'none' })
        return
      }
      wx.chooseMedia({
        count: remaining,
        mediaType: ['image'],
        sourceType: ['album', 'camera'],
        success: (res) => {
          const files = res.tempFiles || []
          this.uploadCustomImages(files.map(f => f.tempFilePath))
        }
      })
    },

    async uploadCustomImages(paths) {
      if (!paths || paths.length === 0) return
      if (!app.globalData.userInfo) {
        wx.showToast({ title: '请先登录再上传', icon: 'none' })
        return
      }
      this.setData({ customUploading: true })
      wx.showLoading({ title: '上传中...' })
      const uploaded = []
      try {
        for (const p of paths) {
          const res = await api.uploadImage(p)
          if (res && res.url) uploaded.push(res.url)
        }
        this.setData({
          customImages: this.data.customImages.concat(uploaded),
          customImagesDisplay: this.data.customImagesDisplay.concat(uploaded.map(u => api.imageUrl(u)))
        })
      } catch (err) {
        wx.showToast({ title: '图片上传失败', icon: 'none' })
        console.error('上传失败', err)
      } finally {
        wx.hideLoading()
        this.setData({ customUploading: false })
      }
    },

    removeCustomImage(e) {
      const idx = e.currentTarget.dataset.index
      const list = this.data.customImages.slice()
      const disp = this.data.customImagesDisplay.slice()
      list.splice(idx, 1)
      disp.splice(idx, 1)
      this.setData({ customImages: list, customImagesDisplay: disp })
    },

    previewCustomImage(e) {
      const idx = e.currentTarget.dataset.index
      const urls = this.data.customImagesDisplay
      wx.previewImage({ current: urls[idx], urls: urls })
    },

    // ---- 用户资料 ----
    showEditNickname() {
      const ui = this.data.userInfo || {}
      this.setData({ editingNickname: true, newNickname: ui.nickname || '' })
    },

    cancelEditNickname() {
      this.setData({ editingNickname: false })
    },

    // 用旅行名片预填发布表单默认值（仅首次，用户改过不覆盖）
    async prefillFromCard() {
      if (this._cardPrefilled) return
      this._cardPrefilled = true
      try {
        const me = await api.getMe()
        if (!me || !(me.success || me.user_id)) return
        const d = this.data
        const patch = {}
        if (me.budget_level && d.budgetOptions.includes(me.budget_level)) {
          patch.budgetSelected = [me.budget_level]
        }
        if (me.good_at_photo) {
          const i = d.photoOptions.indexOf(me.good_at_photo)
          if (i >= 0) patch.photoIndex = i
        }
        if (me.accommodation_pref) {
          const i = d.accommodationOptions.indexOf(me.accommodation_pref)
          if (i >= 0) patch.accommodationIndex = i
        }
        if (Object.keys(patch).length > 0) this.setData(patch)
      } catch (e) {
        console.error('名片预填失败', e)
      }
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
        const res = await api.updateProfile({ nickname })
        if (res.success) {
          app.globalData.userInfo.nickname = res.nickname
          this.setData({ userInfo: app.globalData.userInfo, userName: res.nickname, editingNickname: false })
          wx.showToast({ title: '已更新' })
        }
      } catch (e) {
        wx.showToast({ title: '更新失败', icon: 'none' })
      }
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
          this.setData({ searchResults: Array.isArray(res.suggestions) ? res.suggestions : [] })
        } catch (err) {
          console.error('搜索失败', err)
        }
      }, 300)
    },

    selectSearchSuggestion(e) {
      const item = this.data.searchResults[e.currentTarget.dataset.index]
      if (!item) return
      if (item.type === 'country') {
        // 选国家：切到对应区域并展开该国城市卡片
        this.setData({
          cityInput: '',
          searchResults: [],
          currentRegion: item.region || this.data.currentRegion,
          currentCountry: item.name
        })
        app.globalData.currentRegion = this.data.currentRegion
        if (item.region) this.loadCountries(item.region)
        this.loadCities(item.region || this.data.currentRegion, item.name)
      } else if (this.data.selectedCities.indexOf(item.name) === -1) {
        const list = this.data.selectedCities.concat(item.name)
        this.setData({ selectedCities: list, cityInput: '', searchResults: [] })
        app.globalData.selectedCities = list
      } else {
        this.setData({ cityInput: '', searchResults: [] })
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
        if (d.inputMode === 'custom') {
          // 自定义模式：不生成路线，直接组装 custom route_json
          const customTitle = (d.customTitle || '').trim()
          if (!customTitle) {
            wx.hideLoading()
            wx.showToast({ title: '请填写标题', icon: 'none' })
            return
          }
          if (!d.currentCountry) {
            wx.hideLoading()
            wx.showToast({ title: '请先选择国家', icon: 'none' })
            return
          }
          if (d.selectedCities.length < 1) {
            wx.hideLoading()
            wx.showToast({ title: '请至少选择一个城市', icon: 'none' })
            return
          }
          const customText = (d.customText || '').trim()
          if (d.customUploading) {
            wx.hideLoading()
            wx.showToast({ title: '图片上传中，请稍候', icon: 'none' })
            return
          }
          route = {
            route_type: 'custom',
            custom_title: customTitle,
            cities: d.selectedCities,
            city_count: d.selectedCities.length,
            custom_text: customText,
            custom_images: d.customImages,
            region: d.currentRegion,
            country: d.currentCountry,
            description: customTitle
          }

        } else if (d.inputMode === 'manual') {
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
          if (d.selectedCities.length < 1) {
            wx.hideLoading()
            wx.showToast({ title: '请至少选择一个城市', icon: 'none' })
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
          duration_days: d.inputMode === 'custom' ? (route.total_days || null) : (route.total_days || 10),
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
                  wx.navigateTo({ url: '/pages/match/match' })
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
  }
})
