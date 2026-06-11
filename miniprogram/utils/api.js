// API配置
// 开发环境: http://localhost:8000/api
// 生产环境: https://awesometravelpartner.cn/api
const BASE_URL = 'https://awesometravelpartner.cn/api'

function getToken() {
  return wx.getStorageSync('token') || ''
}

function request(url, method, data) {
  return new Promise((resolve, reject) => {
    const token = getToken()
    console.log('[API请求]', method || 'GET', url, 'token:', token ? token.substring(0, 20) + '...' : '无', data ? JSON.stringify(data).substring(0, 100) : '')
    wx.request({
      url: BASE_URL + url,
      method: method || 'GET',
      data: data,
      header: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': token } : {})
      },
      success(res) {
        console.log('[API响应]', url, '状态:', res.statusCode, JSON.stringify(res.data).substring(0, 300))
        resolve(res.data)
      },
      fail(err) {
        console.error('[API失败]', url, err.errMsg || JSON.stringify(err))
        reject(err)
      }
    })
  })
}

module.exports = {
  // 认证
  wxLogin(code, nickname, avatarUrl) {
    return request('/auth/wx-login', 'POST', { code, nickname, avatar_url: avatarUrl })
  },
  getMe() {
    // ✅ 修复: 使用header传token,不用query参数
    return request('/auth/me')
  },
  updateProfile(data) {
    // ✅ 修复: token从storage自动获取,不用参数传递
    // data 可含: nickname/gender/avatar_url + 名片字段 bio/budget_level/good_at_photo/accommodation_pref/driving/tags
    return request('/auth/update-profile', 'POST', data)
  },
  getUserProfile(userId) {
    return request(`/users/${userId}/profile`)
  },
  // 目的地
  getCountries(region) {
    return request(`/destinations/countries?region=${encodeURIComponent(region)}`)
  },
  getCities(region, country, limit) {
    return request(`/destinations/cities?region=${encodeURIComponent(region)}&country=${encodeURIComponent(country)}&limit=${limit || 16}`)
  },
  searchDestinations(q) {
    return request(`/destinations/search?q=${encodeURIComponent(q)}`)
  },
  // 路线
  generateRoute(data) {
    return request('/routes/generate', 'POST', data)
  },
  // 搭子
  publishCompanion(data) {
    return request('/companions/publish', 'POST', data)
  },
  matchCompanions(data) {
    return request('/companions/match', 'POST', data)
  },
  listCompanions(limit) {
    return request(`/companions/list?limit=${limit || 20}`)
  },
  getMyCompanions(limit) {
    // ✅ 修复: 不传user_id,后端从token中解析
    return request(`/companions/my?limit=${limit || 20}`)
  },
  searchCompanions(keyword, limit) {
    return request(`/companions/search?keyword=${encodeURIComponent(keyword)}&limit=${limit || 20}`)
  },
  getCompanionDetail(id) {
    return request(`/companions/${id}`)
  },
  deleteCompanion(id) {
    return request(`/companions/${id}`, 'DELETE')
  },
  // 留言
  getComments(companionId) {
    return request(`/companions/${companionId}/comments`)
  },
  postComment(companionId, content) {
    return request(`/companions/${companionId}/comments`, 'POST', { content })
  },
  deleteComment(commentId) {
    return request(`/comments/${commentId}`, 'DELETE')
  }
}
