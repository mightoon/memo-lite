const app = getApp()
const API_BASE = app.globalData.apiBaseUrl

// 封装请求
function request(options) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: API_BASE + options.url,
      method: options.method || 'GET',
      data: options.data || {},
      header: {
        'Content-Type': 'application/json'
      },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else {
          reject(new Error(res.data.error || '请求失败'))
        }
      },
      fail: (err) => {
        reject(new Error('网络错误'))
      }
    })
  })
}

module.exports = {
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
