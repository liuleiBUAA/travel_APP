// 语音对话式助手：录音 → 微信同声传译转文字 → 后端意图路由 → 渲染对话+结果卡
const api = require('../../utils/api.js')

// 微信同声传译插件
const plugin = requirePlugin('WechatSI')
const manager = plugin.getRecordRecognitionManager()

Page({
  data: {
    messages: [],        // 对话气泡：{role:'user'|'assistant', text, type, data}
    recording: false,    // 是否正在录音
    loading: false,      // 是否在等后端
    inputText: '',       // 文本输入兜底
    scrollToView: ''     // 滚动锚点
  },

  onLoad() {
    this.initRecord()
    // 开场白
    this.pushMsg('assistant', '你好呀！说一句话就行，比如「找7月去日本的搭子」「发布去瑞士10天的行程」「圣托里尼有什么好玩的」～', 'text')
  },

  // 初始化语音识别回调
  initRecord() {
    manager.onRecognize = (res) => {
      // 识别中间结果（可不展示）
    }
    manager.onStop = (res) => {
      this.setData({ recording: false })
      const text = (res.result || '').trim()
      if (!text) {
        wx.showToast({ title: '没听清，再说一次', icon: 'none' })
        return
      }
      this.handleUserText(text)
    }
    manager.onError = (res) => {
      this.setData({ recording: false })
      wx.showToast({ title: '识别失败：' + (res.msg || ''), icon: 'none' })
    }
  },

  // 按住说话
  startRecord() {
    this.setData({ recording: true })
    manager.start({ duration: 30000, lang: 'zh_CN' })
  },
  // 松手结束
  stopRecord() {
    if (this.data.recording) manager.stop()
  },

  // 文本输入兜底
  onInput(e) {
    this.setData({ inputText: e.detail.value })
  },
  sendText() {
    const text = (this.data.inputText || '').trim()
    if (!text) return
    this.setData({ inputText: '' })
    this.handleUserText(text)
  },

  // 往对话里加一条气泡
  pushMsg(role, text, type, data) {
    const messages = this.data.messages.concat([{ role, text, type: type || 'text', data: data || null }])
    this.setData({ messages, scrollToView: 'msg-' + (messages.length - 1) })
  },

  // 处理用户一句话：加气泡 → 调后端 → 按 action 渲染
  handleUserText(text) {
    this.pushMsg('user', text, 'text')
    // 组装传给后端的对话历史（只要 role+content，过滤掉结果卡气泡）
    const history = this.data.messages
      .filter(m => m.type === 'text')
      .map(m => ({ role: m.role, content: m.text }))

    this.setData({ loading: true })
    api.voiceAssistant(history).then(res => {
      this.setData({ loading: false })
      if (!res || res.success !== true) {
        this.pushMsg('assistant', '出了点小问题，再试一次吧～', 'text')
        return
      }
      // 助手回话
      if (res.reply) this.pushMsg('assistant', res.reply, 'text')
      // 按 action 渲染结果
      this.renderAction(res)
    }).catch(() => {
      this.setData({ loading: false })
      this.pushMsg('assistant', '网络好像不太好，再试一次吧～', 'text')
    })
  },

  renderAction(res) {
    const action = res.action
    if (action === 'show_companions') {
      const list = (res.data && res.data.list) || []
      if (list.length) this.pushMsg('assistant', '', 'companions', list)
    } else if (action === 'show_guides') {
      const results = (res.data && res.data.results) || []
      if (results.length) this.pushMsg('assistant', '', 'guides', results)
    } else if (action === 'confirm_publish') {
      // 二次确认卡：用户必须点【确认发布】才真正 publish
      this.pushMsg('assistant', '', 'confirm', res.data || {})
    }
    // ask / none / retry：仅回话气泡，无额外卡片
  },

  // ── 结果卡交互 ──
  // 点搭子卡 → 跳详情
  onTapCompanion(e) {
    const id = e.currentTarget.dataset.id
    if (id) wx.navigateTo({ url: `/pages/trip-detail/trip-detail?id=${id}` })
  },
  // 点攻略卡 → 跳景点页
  onTapGuide(e) {
    const name = e.currentTarget.dataset.name
    if (name) wx.navigateTo({ url: `/pages/attraction/attraction?name=${encodeURIComponent(name)}` })
  },

  // 【确认发布】：先生成路线，再 publish
  onConfirmPublish(e) {
    const card = e.currentTarget.dataset.card || {}
    const cities = card.cities || []
    const month = card.travel_month
    const days = card.duration_days || 7
    if (!cities.length || !month) {
      wx.showToast({ title: '信息不全，无法发布', icon: 'none' })
      return
    }
    wx.showLoading({ title: '正在发布...' })
    // 1) 生成路线（destination 模式：按城市生成）
    api.generateRoute({ mode: 'destination', cities }).then(r => {
      const route = (r && r.route) || { cities }
      // 2) 拼出发日期：当年(或明年)该月1号
      const now = new Date()
      let year = now.getFullYear()
      if (month < now.getMonth() + 1) year += 1  // 月份已过则明年
      const travelDate = `${year}-${String(month).padStart(2, '0')}-01`
      // 3) 发布
      return api.publishCompanion({
        route_json: route,
        travel_date: travelDate,
        duration_days: days,
        seeking: { description: card.seeking || '不限', gender: '不限', people_min: 1, people_max: 4 }
      })
    }).then(pr => {
      wx.hideLoading()
      if (pr && pr.success) {
        this.pushMsg('assistant', '发布成功啦！其他人就能搜到你的行程了～', 'text')
      } else {
        this.pushMsg('assistant', '发布失败：' + ((pr && pr.message) || '请稍后重试'), 'text')
      }
    }).catch(() => {
      wx.hideLoading()
      this.pushMsg('assistant', '发布失败，请稍后重试～', 'text')
    })
  },

  // 取消发布
  onCancelPublish() {
    this.pushMsg('assistant', '好的，已取消发布。还需要我帮你做点什么吗？', 'text')
  }
})
