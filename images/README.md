# 图标资源说明

本项目需要以下图标文件，请从 iconfont 或设计资源中获取：

## 需要的图标

1. **keyboard.png** - 键盘图标（灰色，48x48）
2. **mic.png** - 麦克风图标（绿色，48x48）
3. **recording.png** - 录音中图标（红色，48x48）

## 获取方式

### 方式1：使用微信小程序官方图标库

无需图片，可以直接使用微信内置图标。修改代码将 `<image>` 替换为：

```html
<!-- 键盘模式 -->
<text wx:if="{{inputMode === 'keyboard'}}" class="iconfont icon-keyboard">⌨️</text>

<!-- 语音模式 -->
<text wx:elif="{{inputMode === 'voice' && !isRecording}}" class="iconfont icon-mic">🎤</text>

<!-- 录音中 -->
<text wx:if="{{isRecording}}" class="iconfont icon-recording">🔴</text>
```

### 方式2：从 Iconfont 下载

访问 [阿里巴巴矢量图标库](https://www.iconfont.cn/) 搜索下载：
- keyboard / 键盘
- microphone / 麦克风
- recording / 录音

下载 PNG 格式，尺寸 48x48 像素，放入此目录即可。

### 方式3：使用 Emoji 作为临时方案

也可以直接在代码中使用 Emoji，无需图片文件。
