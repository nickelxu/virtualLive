# 虚拟主播系统

这是一个虚拟主播系统，可以播放本地故事文件，同时监控直播间评论并使用AI自动回复。系统采用内存中音频处理技术，无需占用本地存储空间。

## 功能特点

1. **故事播放**：自动读取本地故事文件并使用语音合成技术播放
2. **直播评论监控**：实时监控抖音直播间的用户评论和礼物
3. **AI智能回复**：使用千问大模型对用户评论生成智能回复
4. **语音合成**：使用阿里云语音合成服务将文本转换为自然语音
5. **多任务协调**：故事播放和评论处理可以同时进行，互不干扰
6. **内存中音频处理**：所有音频数据在内存中处理，无需占用本地存储空间
7. **评论缓存机制**：智能缓存评论，确保在故事播放过程中不错过用户互动

## 系统架构

系统由以下几个主要模块组成：

1. **主控模块** (`main.py`): 协调整个系统的运行，管理故事播放和评论处理
2. **评论获取模块** (`getusercomment.py`): 负责从抖音直播间获取实时评论
3. **AI回复模块** (`getResponseFromQianwen.py`): 使用千问大模型生成回复
4. **语音合成模块** (`cosyVoiceTTS.py`): 将文本转换为语音数据

## 使用方法

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置环境变量

在项目根目录创建 `.env` 文件，填入以下内容：

```
ALIYUN_AK_ID="您的阿里云AccessKey ID"
ALIYUN_AK_SECRET="您的阿里云AccessKey Secret"
DASHSCOPE_API_KEY="您的千问API密钥"
```

### 准备故事文件

1. 在项目根目录创建 `story` 文件夹
2. 将故事文本文件（.txt格式）放入该文件夹
3. 每个故事文件应包含完整的故事内容，系统会自动分割成句子播放

### 配置直播间

直播间URL需要通过命令行参数提供：

```bash
python main.py https://live.douyin.com/您的直播间ID
```

### 配置虚拟声卡（可选）

如果您需要将语音输出到直播软件（如抖音直播伴侣），请配置虚拟声卡：

1. 在 `main.py` 中设置 `USE_PYGAME = False`
2. 找到您的虚拟声卡设备ID，并设置 `VIRTUAL_OUTPUT_DEVICE_ID` 变量
3. 在直播软件中选择同一个虚拟声卡作为音频输入

## 工作流程

1. 系统启动后，会初始化语音合成服务和评论监控模块
2. 启动直播评论监控线程，开始获取直播间评论
3. 开始播放故事文件，使用语音合成技术朗读故事内容
4. 当收到用户评论时，系统会将评论添加到缓存队列
5. 在每句故事播放完成后，系统会检查是否有评论需要处理
6. 如果有评论，系统会暂停故事播放，使用千问AI生成回复
7. 将AI回复转换为语音播放
8. 回复完成后，继续播放故事

## 评论处理机制

系统采用智能评论缓存机制，确保在故事播放过程中不错过用户互动：

1. 当收到评论时，系统会将评论添加到缓存队列并显示"缓存评论"信息
2. 在每句故事播放完成后，系统会检查缓存队列
3. 如果队列中有评论，系统会处理最新的一条评论（优先处理最近的互动）
4. 处理评论时，系统会显示"回复评论"信息，包含原始评论和AI回复内容
5. 处理完成后，系统会清空缓存队列，继续播放故事

## 内存中音频处理

系统采用内存中音频处理技术，无需占用本地存储空间：

1. 语音合成模块将文本转换为音频数据，直接存储在内存中
2. 音频播放模块从内存中读取音频数据并播放
3. 播放完成后，内存中的音频数据会被自动释放
4. 整个过程不会在本地磁盘上生成临时文件

## 注意事项

1. 请确保您的网络连接稳定，以便系统能够正常获取直播评论和调用AI服务
2. 语音合成和AI回复功能需要消耗API额度，请注意控制使用量
3. 抖音直播评论获取功能可能会因抖音网站结构变化而失效，请及时更新
4. 如果使用虚拟声卡，请确保正确配置，否则语音可能无法被直播软件捕获
5. 系统在内存中处理音频数据，如果故事文件过大，可能会占用较多内存

## 自定义与扩展

### 修改AI回复风格

在 `process_interaction` 函数中修改 `system_prompt` 变量，可以调整AI回复的风格和内容：

```python
system_prompt = "你是一个[您期望的风格]的直播助手，负责回答直播间观众的问题和评论。回复要[您期望的特点]。"
```

### 添加新功能

您可以通过修改代码添加更多功能，例如：

1. 支持更多直播平台（如B站、快手等）
2. 添加特定关键词的自动回复
3. 集成更多AI模型，提供多样化的回复风格
4. 添加用户互动游戏功能
5. 实现评论优先级排序，优先回复特定类型的评论

## 故障排除

如果系统无法正常工作，请检查以下几点：

1. 确保所有依赖包已正确安装
2. 检查环境变量是否正确配置
3. 确保直播间URL正确且直播间处于开播状态
4. 检查网络连接是否稳定
5. 查看控制台输出的错误信息，根据提示解决问题
6. 如果浏览器驱动出错，尝试下载与您Chrome版本匹配的驱动

## 许可证

本项目采用 MIT 许可证。详情请参阅 LICENSE 文件。

## 联系方式

如有问题或建议，请联系：[您的联系方式]