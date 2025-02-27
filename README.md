# 虚拟直播助手 (Virtual Live Assistant)

这是一个自动化的虚拟直播助手系统，能够从Coze平台获取故事内容，将文本转换为语音，并通过虚拟声卡或本地播放器播放。适用于虚拟主播、自动化内容创作等场景。

## 功能特点

- **自动故事生成**：通过Coze平台API获取生成的故事内容
- **文本转语音**：使用阿里云语音合成服务将文本转换为自然流畅的语音
- **自动播放**：支持通过虚拟声卡或本地播放器播放生成的语音
- **本地存储**：将生成的故事保存在story文件夹中，直接使用故事标题作为文件名
- **文件管理**：自动整理和清理旧文件，保持磁盘空间整洁

## 系统要求

- Python 3.8+
- 阿里云账号（用于语音合成服务）
- Coze平台账号（用于故事生成）
- 虚拟声卡（可选，如果需要将音频输出到其他应用）

## 安装步骤

1. 克隆仓库到本地：

```bash
git clone <repository-url>
cd virtualLive
```

2. 安装依赖包：

```bash
pip install -r requirements.txt
```

3. 配置环境变量：

创建一个`.env`文件，包含以下内容：

```
ALIYUN_AK_ID=你的阿里云AccessKey ID
ALIYUN_AK_SECRET=你的阿里云AccessKey Secret
COZE_TOKEN=你的Coze平台API Token
```

## 配置说明

### 主要配置项

在`main.py`文件中，你可以修改以下配置：

- `USE_PYGAME`：设置为`True`使用pygame播放，设置为`False`使用虚拟声卡
- `VIRTUAL_OUTPUT_DEVICE_ID`：虚拟声卡输出设备ID，可通过`list_devices()`函数查看可用设备

在`getStoryFromCoze.py`文件中，你可以修改：

- `workflow_id`：Coze平台工作流ID

### 虚拟声卡配置

如果你选择使用虚拟声卡输出，需要：

1. 安装虚拟声卡软件（如VB-Cable、Soundflower等）
2. 运行程序并查看设备列表：`python -c "import sounddevice as sd; print(sd.query_devices())"`
3. 找到虚拟声卡的设备ID，并在`main.py`中更新`VIRTUAL_OUTPUT_DEVICE_ID`

## 使用方法

### 基本使用

直接运行主程序：

```bash
python main.py
```

程序将执行以下步骤：
1. 列出所有音频设备
2. 清理story文件夹中的旧文件（默认保留最新的10个故事）
3. 清理旧版本的日期文件夹（兼容旧版本）
4. 从Coze获取新故事并保存到story文件夹中
5. 获取阿里云语音合成token
6. 将故事文本转换为语音并播放

### 仅获取故事

如果你只想获取故事而不进行语音转换，可以运行：

```bash
python getStoryFromCoze.py
```

这将从Coze平台获取一个新故事并保存到story文件夹中。

## 文件结构说明

- `main.py`：主程序，协调整个流程的执行
- `getStoryFromCoze.py`：从Coze平台获取故事内容
- `getCosyVoiceToken.py`：获取阿里云语音合成服务的token
- `cosyVoiceTTS.py`：阿里云语音合成SDK，将文本转换为语音
- `getusercomment.py`：抓取直播评论（可选功能）
- `requirements.txt`：项目依赖列表

## 故事文件格式

故事文件保存在项目根目录的`story`文件夹中，文件直接使用故事标题作为文件名（如`这是一个故事的标题.txt`）。

语音文件命名格式为：`voice_故事标题_XXX.wav`，其中：
- `故事标题`：故事的文件名（不含扩展名）
- `XXX`：句子编号（如001、002等）

## 常见问题

1. **获取token失败**
   - 检查`.env`文件中的阿里云AccessKey是否正确
   - 确认阿里云账号有足够的语音合成服务权限

2. **虚拟声卡不工作**
   - 运行`list_devices()`检查虚拟声卡是否被正确识别
   - 更新`VIRTUAL_OUTPUT_DEVICE_ID`为正确的设备ID
   - 尝试切换到pygame模式（设置`USE_PYGAME = True`）

3. **无法获取故事**
   - 检查Coze平台token是否有效
   - 确认workflow_id是否正确
   - 检查网络连接是否正常

## 许可证

[MIT License](LICENSE)

## 致谢

- 阿里云语音合成服务
- Coze平台API
- 所有开源依赖项的贡献者 