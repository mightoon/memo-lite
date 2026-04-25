const API_BASE = 'https://mightoon.site/memo-lite/api'

// 获取当前用户的 openid
function getOpenid() {
  return wx.getStorageSync('openid')
}

// 封装请求
function request(options) {
  return new Promise((resolve, reject) => {
    const openid = getOpenid()
    const headers = {
      'Content-Type': 'application/json'
    }
    // 如果有 openid，添加到请求头
    if (openid) {
      headers['X-User-Openid'] = openid
    }

    wx.request({
      url: API_BASE + options.url,
      method: options.method || 'GET',
      data: options.data || {},
      header: headers,
      timeout: 10000,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else {
          reject(new Error(res.data.error || '请求失败'))
        }
      },
      fail: (err) => {
        reject(new Error(err.errMsg || '网络错误'))
      }
    })
  })
}

module.exports = {
  // 用户登录
  login: (code, userInfo) => {
    return request({
      url: '/login',
      method: 'POST',
      data: { code, userInfo }
    })
  },

  // 添加笔记
  addNote: (content) => {
    return request({
      url: '/notes',
      method: 'POST',
      data: { content }
    })
  },

  // 获取笔记列表
  getNotes: (params = {}) => {
    let url = '/notes'
    const queryParams = []
    if (params.start_date) queryParams.push(`start_date=${params.start_date}`)
    if (params.end_date) queryParams.push(`end_date=${params.end_date}`)
    if (params.status && params.status !== '全部') queryParams.push(`status=${encodeURIComponent(params.status)}`)
    if (queryParams.length > 0) url += '?' + queryParams.join('&')
    
    return request({ url })
  },

  // 更新笔记状态
  updateNoteStatus: (noteId, status) => {
    return request({
      url: `/notes/${noteId}/status`,
      method: 'PUT',
      data: { status }
    })
  },

  // 批量更新状态
  batchUpdateStatus: (ids, status) => {
    return request({
      url: '/notes/batch/status',
      method: 'PUT',
      data: { ids, status }
    })
  },

  // 批量删除
  batchDelete: (ids) => {
    return request({
      url: '/notes/batch',
      method: 'DELETE',
      data: { ids }
    })
  }
}
