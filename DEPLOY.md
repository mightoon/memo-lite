# 快速笔记 - 微信小程序部署指南

## 项目结构

```
cb_mp_memo-lite/
├── main.py                    # Flask 后端（保持不变，已添加 CORS）
├── requirements.txt           # Python 依赖
├── notes.txt                  # 数据存储文件
├── static/                    # Web 静态资源
├── templates/                 # Web 模板
└── weixin-miniprogram/        # 微信小程序前端代码
    ├── app.js
    ├── app.json
    ├── app.wxss
    ├── pages/
    │   └── index/
    │       ├── index.js       # 页面逻辑
    │       ├── index.wxml     # 页面结构
    │       ├── index.wxss     # 页面样式
    │       └── index.json
    ├── utils/
    │   └── api.js             # API 封装
    └── project.config.json    # 项目配置
```

## 后端部署（Lighthouse 服务器）

### 1. 更新后端代码

将 `main.py` 和 `requirements.txt` 更新到服务器。

**关键变更：**
- 添加了 `flask-cors` 支持，允许小程序跨域访问
- API 端点保持不变

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 重启服务

根据你的部署方式重启 Flask 服务。

如果使用 gunicorn：
```bash
gunicorn -w 2 -b 0.0.0.0:5000 main:app
```

如果使用 Docker：
```bash
docker build -t memo-lite .
docker run -d -p 5000:5000 --name memo-lite memo-lite
```

### 4. 验证 API

```bash
curl https://mightoon.site/memo-lite/api/notes
```

## 小程序前端部署

### 1. 注册小程序账号

访问 [微信公众平台](https://mp.weixin.qq.com/) 注册小程序账号。

### 2. 配置服务器域名

登录小程序后台 → 开发 → 开发管理 → 服务器域名：

**request 合法域名：**
```
https://mightoon.site
```

**注意事项：**
- 域名必须支持 HTTPS
- 域名必须完成 ICP 备案

### 3. 下载微信开发者工具

访问 [微信开发者工具下载页](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html) 下载安装。

### 4. 导入项目

1. 打开微信开发者工具
2. 点击「导入项目」
3. 选择 `weixin-miniprogram` 目录
4. AppID 选择你的小程序 ID（或选择测试号）
5. 点击「导入」

### 5. 配置 API 地址

修改 `weixin-miniprogram/app.js`：

```javascript
App({
  globalData: {
    // 如果是测试环境，可以使用局域网 IP
    // apiBaseUrl: 'http://192.168.1.xxx:5000/api'
    
    // 生产环境
    apiBaseUrl: 'https://mightoon.site/memo-lite/api'
  }
})
```

### 6. 本地调试

1. 点击「编译」按钮
2. 使用模拟器预览效果
3. 真机调试：点击「真机调试」→「扫描二维码」

### 7. 上传代码

1. 点击右上角「上传」按钮
2. 填写版本号和项目备注
3. 点击「上传」

### 8. 提交审核

1. 登录 [微信公众平台](https://mp.weixin.qq.com/)
2. 进入「版本管理」
3. 找到「开发版本」，点击「提交审核」
4. 填写小程序信息和类目
5. 等待审核通过

### 9. 发布上线

审核通过后，在「版本管理」中点击「发布」即可上线。

## 功能对照

| 功能 | Web 版 | 小程序版 | 说明 |
|------|--------|----------|------|
| 文字记录 | ✅ | ✅ | 完全一致 |
| 语音输入 | ✅ Web Speech API | ⚠️ 需接入第三方服务 | 小程序录音 + 语音识别 API |
| 笔记列表 | ✅ | ✅ | 完全一致 |
| 时间筛选 | ✅ | ✅ | 完全一致 |
| 状态筛选 | ✅ | ✅ | 完全一致 |
| 批量操作 | ✅ | ✅ | 完全一致 |

## 语音功能说明

微信小程序的语音输入需要额外接入语音识别服务，推荐方案：

1. **百度语音识别** - 免费额度充足
2. **讯飞语音识别** - 识别准确率高
3. **腾讯云语音识别** - 与微信生态整合好

接入后修改 `pages/index/index.js` 中的 `recognizeVoice` 方法即可。

## 注意事项

1. **HTTPS**：小程序要求服务器必须使用 HTTPS
2. **备案**：域名必须完成 ICP 备案
3. **CORS**：后端已配置，确保 `flask-cors` 正确安装
4. **数据共享**：Web 版和小程序版共用同一个 `notes.txt` 数据文件

## 常见问题

**Q: 提示 "不在以下 request 合法域名列表"？**
A: 在小程序后台配置服务器域名，或开启「不校验合法域名」调试模式。

**Q: 语音输入没有反应？**
A: 当前版本语音输入需要接入第三方语音识别服务，请按上述说明接入。

**Q: 数据同步问题？**
A: Web 版和小程序版使用同一个后端，数据是实时同步的。
