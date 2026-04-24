const api = require('../../utils/api.js')

Page({
  data: {
    // Tab 相关
    currentTab: 'record',
    
    // 记录相关
    noteContent: '',
    inputMode: 'keyboard', // keyboard, voice
    isRecording: false,
    voiceHint: '',
    message: '',
    messageType: '',
    
    // 语音相关
    recorderManager: null,
    recordStartTime: 0,
    
    // 回顾相关
    timeFilters: [
      { label: '当天', value: 'today' },
      { label: '近3天', value: '3days' },
      { label: '近7天', value: 'week' },
      { label: '全部', value: 'all' }
    ],
    statusFilters: ['全部', '待处理', '已处理'],
    currentTimeFilter: '',
    currentStatusFilter: '全部',
    hasTimeFilterSelected: false,
    notes: [],
    selectedNotes: []
  },

  onLoad() {
    // 初始化录音管理器
    this.initRecorder()
  },

  // ==================== Tab 切换 ====================
  switchTab(e) {
    const tab = e.currentTarget.dataset.tab
    this.setData({ 
      currentTab: tab,
      selectedNotes: []
    })
    if (tab === 'review' && this.data.hasTimeFilterSelected) {
      this.loadNotes()
    }
  },

  // ==================== 记录功能 ====================
  onNoteInput(e) {
    this.setData({ noteContent: e.detail.value })
  },

  // 切换输入模式
  toggleInputMode() {
    if (this.data.isRecording) return
    
    const newMode = this.data.inputMode === 'keyboard' ? 'voice' : 'keyboard'
    this.setData({ 
      inputMode: newMode,
      voiceHint: newMode === 'voice' ? '长按开始语音输入' : ''
    })
  },

  // 初始化录音管理器
  initRecorder() {
    const recorderManager = wx.getRecorderManager()
    
    recorderManager.onStart(() => {
      console.log('录音开始')
      this.setData({ 
        isRecording: true,
        voiceHint: '正在聆听，松开结束'
      })
    })
    
    recorderManager.onStop((res) => {
      console.log('录音结束', res)
      this.setData({ 
        isRecording: false,
        voiceHint: this.data.inputMode === 'voice' ? '长按开始语音输入' : ''
      })
      
      // 进行语音识别
      if (res.tempFilePath) {
        this.recognizeVoice(res.tempFilePath)
      }
    })
    
    recorderManager.onError((err) => {
      console.error('录音错误', err)
      this.setData({ 
        isRecording: false,
        voiceHint: ''
      })
      this.showMessage('录音失败，请重试', 'error')
    })
    
    this.setData({ recorderManager })
  },

  // 开始语音输入
  startVoiceInput() {
    if (this.data.inputMode !== 'voice' || this.data.isRecording) return
    
    // 检查录音权限
    wx.authorize({
      scope: 'scope.record',
      success: () => {
        this.data.recorderManager.start({
          duration: 60000,
          sampleRate: 16000,
          numberOfChannels: 1,
          encodeBitRate: 48000,
          format: 'mp3'
        })
        this.setData({ recordStartTime: Date.now() })
      },
      fail: () => {
        wx.showModal({
          title: '需要录音权限',
          content: '请在设置中开启录音权限',
          success: (res) => {
            if (res.confirm) {
              wx.openSetting()
            }
          }
        })
      }
    })
  },

  // 停止语音输入
  stopVoiceInput() {
    if (this.data.isRecording) {
      // 检查录音时长，最少1秒
      const duration = Date.now() - this.data.recordStartTime
      if (duration < 1000) {
        setTimeout(() => {
          this.data.recorderManager.stop()
        }, 1000 - duration)
      } else {
        this.data.recorderManager.stop()
      }
    }
  },

  // 语音识别
  recognizeVoice(filePath) {
    wx.showLoading({ title: '识别中...' })
    
    wx.uploadFile({
      url: 'https://api.weixin.qq.com/cgi-bin/media/voice/recognize',
      filePath: filePath,
      name: 'file',
      formData: {
        'type': 'voice',
        'language': 'zh_CN'
      },
      success: (res) => {
        wx.hideLoading()
        try {
          const data = JSON.parse(res.data)
          if (data.result) {
            const currentContent = this.data.noteContent
            const separator = currentContent ? ' ' : ''
            this.setData({
              noteContent: currentContent + separator + data.result
            })
            this.showMessage('语音输入成功', 'success')
          } else {
            // 模拟语音识别（实际开发需要接入语音识别服务）
            this.simulateVoiceRecognition()
          }
        } catch (e) {
          // 模拟语音识别
          this.simulateVoiceRecognition()
        }
      },
      fail: () => {
        wx.hideLoading()
        this.simulateVoiceRecognition()
      }
    })
  },

  // 模拟语音识别（演示用，实际开发接入语音识别 API）
  simulateVoiceRecognition() {
    // 由于没有接入正式的语音识别服务，这里使用小程序自带的语音输入
    wx.showModal({
      title: '提示',
      content: '小程序语音输入需要接入第三方语音识别服务（如百度语音、讯飞语音等）。\n\n当前演示版本，请直接输入文字。',
      showCancel: false
    })
  },

  // 提交笔记
  async submitNote() {
    const content = this.data.noteContent.trim()
    if (!content) {
      this.showMessage('请输入内容', 'error')
      return
    }

    try {
      await api.addNote(content)
      this.showMessage('记录成功！', 'success')
      this.setData({ noteContent: '' })
    } catch (err) {
      this.showMessage(err.message || '记录失败', 'error')
    }
  },

  // 显示消息
  showMessage(text, type) {
    this.setData({ message: text, messageType: type })
    setTimeout(() => {
      this.setData({ message: '', messageType: '' })
    }, 3000)
  },

  // ==================== 回顾功能 ====================
  setTimeFilter(e) {
    const value = e.currentTarget.dataset.value
    this.setData({ 
      currentTimeFilter: value,
      hasTimeFilterSelected: true,
      selectedNotes: []
    })
    this.loadNotes()
  },

  setStatusFilter(e) {
    const value = e.currentTarget.dataset.value
    this.setData({ 
      currentStatusFilter: value,
      selectedNotes: []
    })
    if (this.data.hasTimeFilterSelected) {
      this.loadNotes()
    }
  },

  getDateRange() {
    const today = new Date()
    const formatDate = (d) => {
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    }
    const todayStr = formatDate(today)
    
    switch(this.data.currentTimeFilter) {
      case 'today':
        return { start_date: todayStr, end_date: todayStr }
      case '3days':
        const threeDaysAgo = new Date(today)
        threeDaysAgo.setDate(today.getDate() - 2)
        return { start_date: formatDate(threeDaysAgo), end_date: todayStr }
      case 'week':
        const weekAgo = new Date(today)
        weekAgo.setDate(today.getDate() - 6)
        return { start_date: formatDate(weekAgo), end_date: todayStr }
      case 'all':
      default:
        return {}
    }
  },

  async loadNotes() {
    wx.showLoading({ title: '加载中...' })
    try {
      const params = {
        ...this.getDateRange(),
        status: this.data.currentStatusFilter
      }
      const res = await api.getNotes(params)
      this.setData({ notes: res.notes || [] })
    } catch (err) {
      wx.showToast({ title: '加载失败', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  },

  // 切换选择
  toggleSelect(e) {
    const id = e.currentTarget.dataset.id
    const selected = [...this.data.selectedNotes]
    const index = selected.indexOf(id)
    if (index > -1) {
      selected.splice(index, 1)
    } else {
      selected.push(id)
    }
    this.setData({ selectedNotes: selected })
  },

  // 取消批量选择
  cancelBatch() {
    this.setData({ selectedNotes: [] })
  },

  // 切换单条笔记状态
  async toggleNoteStatus(e) {
    const { id, status } = e.currentTarget.dataset
    try {
      await api.updateNoteStatus(id, status)
      this.loadNotes()
    } catch (err) {
      wx.showToast({ title: '更新失败', icon: 'none' })
    }
  },

  // 批量标记为已处理
  async batchSetProcessed() {
    await this.batchUpdateStatus('已处理')
  },

  // 批量标记为待处理
  async batchSetPending() {
    await this.batchUpdateStatus('待处理')
  },

  async batchUpdateStatus(status) {
    if (this.data.selectedNotes.length === 0) return
    
    try {
      await api.batchUpdateStatus(this.data.selectedNotes, status)
      this.setData({ selectedNotes: [] })
      this.loadNotes()
      wx.showToast({ title: '更新成功', icon: 'success' })
    } catch (err) {
      wx.showToast({ title: '更新失败', icon: 'none' })
    }
  },

  // 批量删除
  async batchDelete() {
    if (this.data.selectedNotes.length === 0) return
    
    wx.showModal({
      title: '确认删除',
      content: `确定要删除选中的 ${this.data.selectedNotes.length} 条笔记吗？`,
      confirmColor: '#dc3545',
      success: async (res) => {
        if (res.confirm) {
          try {
            await api.batchDelete(this.data.selectedNotes)
            this.setData({ selectedNotes: [] })
            this.loadNotes()
            wx.showToast({ title: '删除成功', icon: 'success' })
          } catch (err) {
            wx.showToast({ title: '删除失败', icon: 'none' })
          }
        }
      }
    })
  }
})
