const api = require('../../utils/api.js')

Page({
  data: {
    isLogging: false
  },

  onLoad() {
    const openid = wx.getStorageSync('openid')
    if (openid) {
      wx.redirectTo({ url: '/pages/index/index' })
    }
  },

  // 处理登录
  handleLogin() {
    if (this.data.isLogging) return
    this.setData({ isLogging: true })
    wx.showLoading({ title: '登录中...', mask: true })

    // 开发者工具/模拟器直接跳过 getUserProfile
    try {
      if (wx.getSystemInfoSync().platform === 'devtools') {
        return this.doLogin({})
      }
    } catch (e) {
      // ignore
    }

    let handled = false
    const safeDoLogin = (info) => {
      if (handled) return
      handled = true
      this.doLogin(info)
    }

    // 3 秒兜底：某些环境下 getUserProfile 既不 success 也不 fail
    setTimeout(() => safeDoLogin({}), 3000)

    try {
      wx.getUserProfile({
        desc: '用于完善用户资料',
        success: (res) => safeDoLogin(res.userInfo || {}),
        fail: () => safeDoLogin({})
      })
    } catch (e) {
      safeDoLogin({})
    }
  },

  async doLogin(userInfo) {
    try {
      const loginRes = await this.wxLogin()
      const code = loginRes.code
      const loginResult = await api.login(code, userInfo)

      wx.setStorageSync('openid', loginResult.openid)
      wx.setStorageSync('userInfo', {
        nickname: loginResult.nickname,
        avatar: loginResult.avatar,
        role: loginResult.role || null
      })

      wx.hideLoading()
      wx.redirectTo({ url: '/pages/index/index' })
    } catch (err) {
      wx.hideLoading()
      wx.showToast({ title: err.message || '登录失败', icon: 'none' })
    } finally {
      this.setData({ isLogging: false })
    }
  },

  // wx.login 加 10 秒超时保护，防止虚拟账户下无限挂起
  wxLogin() {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('登录超时，请检查网络')), 10000)
      wx.login({
        success: (res) => { clearTimeout(timer); resolve(res) },
        fail: (err) => { clearTimeout(timer); reject(err) }
      })
    })
  },

  // 显示隐私协议
  showPrivacy() {
    wx.showModal({
      title: '隐私协议',
      content: '本小程序仅收集您的微信昵称和头像用于展示，不会将您的个人信息用于其他用途。您的笔记数据将安全存储在服务器上。',
      showCancel: false
    })
  },

  // 显示用户协议
  showTerms() {
    wx.showModal({
      title: '用户协议',
      content: '欢迎使用快速笔记小程序！本小程序提供笔记记录和管理服务，请合理使用，不要发布违法违规内容。',
      showCancel: false
    })
  }
})
