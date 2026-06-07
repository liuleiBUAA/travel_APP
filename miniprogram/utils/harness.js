/**
 * Harness Hooks - 小程序端自动验证和约束执行
 *
 * 在微信小程序中实现类似后端的 Hook 机制。
 * 微信小程序没有文件系统的 Hooks，但可以在关键操作前后拦截。
 *
 * 使用方法：
 *   const harness = require('../../utils/harness')
 *
 *   // 注册 Hook
 *   harness.on('afterApiCall', (res) => {
 *     if (!res.success) console.warn('API失败:', res)
 *   })
 *
 *   // 用守卫包裹 API 调用
 *   harness.apiGuard(() => api.generateRoute(data), 'generateRoute')
 */

const harness = {
  // Hook 注册表
  _hooks: {},

  // 指标收集
  _metrics: {},

  // 违规记录
  _violations: [],

  // ==================== Hook 注册 ====================

  /**
   * 注册 Hook
   * @param {string} event - 事件名
   * @param {Function} callback - 回调函数
   */
  on(event, callback) {
    if (!this._hooks[event]) {
      this._hooks[event] = []
    }
    this._hooks[event].push(callback)
  },

  /**
   * 触发 Hook
   * @param {string} event - 事件名
   * @param {Object} context - 上下文数据
   */
  trigger(event, context) {
    const hooks = this._hooks[event] || []
    hooks.forEach(cb => {
      try {
        cb(context)
      } catch (e) {
        console.error(`[Harness] Hook 错误 (${event}):`, e)
      }
    })
  },

  // ==================== 内置传感器 ====================

  /**
   * 验证 API 返回格式
   */
  validateApiResponse(res, endpoint) {
    const issues = []

    if (!res || typeof res !== 'object') {
      issues.push(`[${endpoint}] 返回值不是对象`)
      this.recordViolation(`API返回类型错误: ${endpoint}`)
      return issues
    }

    if ('success' in res && res.success === false) {
      this.trigger('onApiError', { endpoint, response: res })
    }

    if (!('success' in res)) {
      issues.push(`[${endpoint}] 缺少 success 字段`)
      this.recordViolation(`API缺少success字段: ${endpoint}`)
    }

    return issues
  },

  /**
   * 验证发布数据完整性
   */
  validatePublishData(data) {
    const issues = []

    if (!data.user_id) issues.push('缺少 user_id')
    if (!data.route_json) issues.push('缺少路线数据')
    if (!data.travel_date) issues.push('缺少出行日期')

    if (data.duration_days && (data.duration_days < 1 || data.duration_days > 90)) {
      issues.push(`天数不合理: ${data.duration_days}`)
      this.recordViolation(`天数异常: ${data.duration_days}`)
    }

    if (data.travel_date) {
      const dateRegex = /^\d{4}-\d{2}-\d{2}$/
      if (!dateRegex.test(data.travel_date)) {
        issues.push(`日期格式错误: ${data.travel_date}`)
      }
    }

    if (issues.length > 0) {
      this.recordViolation(`发布数据验证失败: ${issues.join(', ')}`)
    }

    return issues
  },

  // ==================== API 守卫 ====================

  /**
   * API 调用守卫 - 自动计时、验证返回、记录指标、错误处理
   *
   * @param {Function} apiCall - 返回 Promise 的 API 调用函数
   * @param {string} name - 端点名称
   * @param {Object} options - { silent: boolean }
   * @returns {Promise} API 结果
   */
  async apiGuard(apiCall, name, options = {}) {
    const startTime = Date.now()

    this.trigger('beforeApiCall', { endpoint: name })

    try {
      const res = await apiCall()
      const issues = this.validateApiResponse(res, name)

      if (issues.length > 0) {
        console.warn(`[Harness] ${issues.join(', ')}`)
      }

      const elapsed = Date.now() - startTime
      this.recordMetric(`api.${name}.time`, elapsed)

      if (elapsed > 3000) {
        console.warn(`[Harness] 🐢 慢接口: ${name} (${elapsed}ms)`)
        this.recordViolation(`慢接口: ${name} (${elapsed}ms)`)
      }

      this.trigger('afterApiCall', { endpoint: name, response: res, time: elapsed })
      return res

    } catch (err) {
      const elapsed = Date.now() - startTime
      console.error(`[Harness] 🔴 API 错误 [${name}]:`, err)
      this.trigger('onApiError', { endpoint: name, error: err, time: elapsed })
      this.recordMetric(`api.${name}.error`, 1)

      if (!options.silent) {
        wx.showToast({ title: '网络请求失败', icon: 'none', duration: 2000 })
      }

      throw err
    }
  },

  // ==================== 页面生命周期守卫 ====================

  /**
   * 页面级 Harness 守卫
   * 放在 Page() 中使用，监控 setData 调用
   */
  pageGuard(page, options = {}) {
    const self = this
    const originalSetData = page.setData.bind(page)
    let setDataCount = 0

    page.setData = function(data, callback) {
      setDataCount++
      const dataSize = JSON.stringify(data).length

      if (dataSize > 1024 * 100) {
        console.warn(`[Harness] setData 数据量大: ${(dataSize / 1024).toFixed(1)}KB`)
        self.recordViolation(`大数据setData: ${(dataSize / 1024).toFixed(1)}KB`)
      }

      return originalSetData(data, callback)
    }

    const originalOnUnload = page.onUnload
    page.onUnload = function() {
      if (setDataCount > 20) {
        console.warn(`[Harness] setData 调用次数过多: ${setDataCount} 次`)
      }
      self.recordMetric(`page.setDataCount`, setDataCount)
      if (originalOnUnload) originalOnUnload.call(page)
    }

    return page
  },

  // ==================== 违规记录 ====================

  recordViolation(reason) {
    const violation = { reason, time: new Date().toISOString() }
    this._violations.push(violation)
    console.warn(`[Harness] 违规: ${reason}`)

    const stored = wx.getStorageSync('harness_violations') || []
    stored.push(violation)
    if (stored.length > 50) stored.splice(0, stored.length - 50)
    wx.setStorageSync('harness_violations', stored)
  },

  // ==================== 指标收集 ====================

  recordMetric(name, value) {
    if (!this._metrics[name]) this._metrics[name] = []
    this._metrics[name].push(value)
  },

  getMetrics() {
    const summary = {}
    Object.keys(this._metrics).forEach(name => {
      const values = this._metrics[name]
      if (values && values.length > 0) {
        const numericValues = values.filter(v => typeof v === 'number')
        summary[name] = {
          count: numericValues.length,
          avg: numericValues.length > 0 ? Math.round(numericValues.reduce((a, b) => a + b, 0) / numericValues.length) : 0,
          max: numericValues.length > 0 ? Math.max(...numericValues) : 0,
          last: values[values.length - 1]
        }
      }
    })
    return summary
  },

  getHealthReport() {
    return {
      violations: (this._violations || []).slice(-10),
      violationsCount: (this._violations || []).length,
      metrics: this.getMetrics(),
      hooksRegistered: Object.keys(this._hooks || {}).reduce((acc, key) => {
        acc[key] = (this._hooks[key] || []).length
        return acc
      }, {})
    }
  },

  enableAuthCheck() {
    this.on('beforeApiCall', (context) => {
      const token = wx.getStorageSync('token')
      if (!token) {
        console.warn('[Harness] 未登录状态发起 API 调用:', context.endpoint)
      }
    })
  }
}

module.exports = harness
