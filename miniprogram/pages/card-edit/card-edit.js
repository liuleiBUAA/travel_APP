const api = require('../../utils/api')

Page({
  data: {
    loading: true,
    saving: false,
    editBio: '',
    editWechat: '',
    budgetOptions: ['穷游', '经济', '舒适', '轻奢'],
    photoOptions: ['一般', '擅长', '大师'],
    accommodationOptions: ['不限', '可拼房', '各住各的'],
    drivingOptions: ['不会开车', '会开但尽量不开', '愿意当司机'],
    mbtiOptions: ['INTJ', 'INTP', 'ENTJ', 'ENTP', 'INFJ', 'INFP', 'ENFJ', 'ENFP', 'ISTJ', 'ISFJ', 'ESTJ', 'ESFJ', 'ISTP', 'ISFP', 'ESTP', 'ESFP'],
    zodiacOptions: ['白羊座', '金牛座', '双子座', '巨蟹座', '狮子座', '处女座', '天秤座', '天蝎座', '射手座', '摩羯座', '水瓶座', '双鱼座'],
    budgetIndex: -1,
    photoIndex: -1,
    accommodationIndex: -1,
    drivingIndex: -1,
    mbtiIndex: -1,
    zodiacIndex: -1,
    tagOptions: ['早起党', '夜猫子', '美食控', '博物馆爱好者', '徒步', '购物', '摄影', '自驾老手', '持国际驾照', '小众路线'],
    editTags: [],
  },

  onLoad() {
    this.loadCard()
  },

  async loadCard() {
    try {
      const me = await api.getMe()
      if (me && (me.success || me.user_id)) {
        const tags = Array.isArray(me.tags) ? me.tags : []
        this.setData({
          loading: false,
          editBio: me.bio || '',
          editWechat: me.wechat_id || '',
          budgetIndex: this.data.budgetOptions.indexOf(me.budget_level || ''),
          photoIndex: this.data.photoOptions.indexOf(me.good_at_photo || ''),
          accommodationIndex: this.data.accommodationOptions.indexOf(me.accommodation_pref || ''),
          drivingIndex: this.data.drivingOptions.indexOf(me.driving || ''),
          mbtiIndex: this.data.mbtiOptions.indexOf(me.mbti || ''),
          zodiacIndex: this.data.zodiacOptions.indexOf(me.zodiac || ''),
          editTags: [...tags]
        })
      } else {
        this.setData({ loading: false })
      }
    } catch (e) {
      console.error('加载名片失败', e)
      this.setData({ loading: false })
      wx.showToast({ title: '加载失败', icon: 'none' })
    }
  },

  onBioInput(e) {
    this.setData({ editBio: e.detail.value })
  },

  onWechatInput(e) {
    this.setData({ editWechat: e.detail.value })
  },

  onBudgetChange(e) { this.setData({ budgetIndex: Number(e.detail.value) }) },
  onPhotoChange(e) { this.setData({ photoIndex: Number(e.detail.value) }) },
  onAccommodationChange(e) { this.setData({ accommodationIndex: Number(e.detail.value) }) },
  onDrivingChange(e) { this.setData({ drivingIndex: Number(e.detail.value) }) },
  onMbtiChange(e) { this.setData({ mbtiIndex: Number(e.detail.value) }) },
  onZodiacChange(e) { this.setData({ zodiacIndex: Number(e.detail.value) }) },

  onToggleTag(e) {
    const tag = e.currentTarget.dataset.tag
    const tags = [...this.data.editTags]
    const i = tags.indexOf(tag)
    if (i >= 0) {
      tags.splice(i, 1)
    } else {
      if (tags.length >= 10) { wx.showToast({ title: '最多10个标签', icon: 'none' }); return }
      tags.push(tag)
    }
    this.setData({ editTags: tags })
  },

  async onSave() {
    if (this.data.saving) return
    const d = this.data
    this.setData({ saving: true })
    try {
      const res = await api.updateProfile({
        bio: d.editBio.trim(),
        wechat_id: d.editWechat.trim(),
        budget_level: d.budgetIndex >= 0 ? d.budgetOptions[d.budgetIndex] : '',
        good_at_photo: d.photoIndex >= 0 ? d.photoOptions[d.photoIndex] : '',
        accommodation_pref: d.accommodationIndex >= 0 ? d.accommodationOptions[d.accommodationIndex] : '',
        driving: d.drivingIndex >= 0 ? d.drivingOptions[d.drivingIndex] : '',
        mbti: d.mbtiIndex >= 0 ? d.mbtiOptions[d.mbtiIndex] : '',
        zodiac: d.zodiacIndex >= 0 ? d.zodiacOptions[d.zodiacIndex] : '',
        tags: d.editTags.join(',')
      })
      if (res && res.success) {
        wx.showToast({ title: '名片已保存', icon: 'success' })
        setTimeout(() => wx.navigateBack(), 600)
      } else {
        wx.showToast({ title: (res && res.detail) || '保存失败', icon: 'none' })
      }
    } catch (e) {
      console.error('保存名片失败', e)
      wx.showToast({ title: '网络错误', icon: 'none' })
    } finally {
      this.setData({ saving: false })
    }
  },
})
