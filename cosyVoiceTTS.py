# coding=utf-8
"""
阿里云语音合成服务模块

此模块用于将文本转换为语音，使用阿里云的语音合成服务。
主要功能包括：
1. 从story文件夹中读取内容
2. 将文本内容转换为语音
3. 保存语音为WAV文件或实时播放
4. 获取阿里云语音合成服务的访问Token

安装说明：
- APPLE Mac OS X: brew install portaudio && pip install pyaudio
- Debian/Ubuntu: sudo apt-get install python-pyaudio python3-pyaudio 或 pip install pyaudio
- CentOS: sudo yum install -y portaudio portaudio-devel && pip install pyaudio
- Microsoft Windows: python -m pip install pyaudio

作者: nickelxu
"""

# 阿里云语音合成服务相关链接
# 示例代码参考文档
# https://help.aliyun.com/zh/isi/developer-reference/stream-input-tts-sdk-quick-start

# 获取appkey和accesstoken的链接
# appkey申请地址: https://nls-portal.console.aliyun.com/applist  
# accesstoken申请地址: https://nls-portal.console.aliyun.com/overview

# 示例代码使用注意事项:
# 1. SDK方法名更新 - 示例代码中的方法名与最新SDK不一致,需参考SDK源码进行修改
# 2. SSL证书缺失 - 需要安装SSL证书才能连接NLS服务
# 3. 声音ID无效 - 示例代码中使用的声音ID不存在,需要更换为有效的声音ID
# 4. 将每句话分别保存为音频文件的能力始终无法实现

import nls
import time
import os
import json
from datetime import datetime
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from dotenv import load_dotenv

# 加载环境变量文件中的配置
load_dotenv()

# 设置打开日志输出
nls.enableTrace(False)

# 配置选项
# 将音频保存进文件
SAVE_TO_FILE = False
# 将音频通过播放器实时播放，需要具有声卡。在服务器上运行请将此开关关闭
PLAY_REALTIME_RESULT = True
if PLAY_REALTIME_RESULT:
    import pyaudio

def get_token():
    """
    获取阿里云语音合成服务的访问Token
    
    使用阿里云SDK从元数据服务获取语音合成服务的访问Token。
    需要在环境变量中设置ALIYUN_AK_ID和ALIYUN_AK_SECRET。
    
    Returns:
        str or None: 成功返回Token字符串，失败返回None
        
    Raises:
        Exception: 当API响应中没有找到Token时抛出异常
    """
    # 创建AcsClient实例，用于与阿里云API通信
    client = AcsClient(
        os.getenv('ALIYUN_AK_ID'),        # 阿里云AccessKey ID
        os.getenv('ALIYUN_AK_SECRET'),    # 阿里云AccessKey Secret
        "cn-shanghai"                      # 区域ID，固定为上海区域
    )

    # 创建请求并设置参数
    request = CommonRequest()
    request.set_method('POST')                             # 设置HTTP方法为POST
    request.set_domain('nls-meta.cn-shanghai.aliyuncs.com')  # 设置API域名
    request.set_version('2019-02-28')                      # 设置API版本
    request.set_action_name('CreateToken')                 # 设置API操作名称

    try:
        # 发送请求并获取响应
        response = client.do_action_with_exception(request)
        # 解析JSON响应
        jss = json.loads(response)
        # 检查响应中是否包含Token
        if 'Token' in jss and 'Id' in jss['Token']:
            return jss['Token']['Id']
        else:
            raise Exception("Token not found in response")
    except Exception as e:
        # 捕获并记录错误
        print(f"Error getting token: {str(e)}")
        return None

def get_story_folder():
    """
    获取story文件夹路径
    
    返回项目根目录中的story文件夹路径。如果不存在则创建该文件夹。
    
    Returns:
        str: story文件夹的完整路径
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    story_folder = os.path.join(current_dir, "story")
    if not os.path.exists(story_folder):
        os.makedirs(story_folder)
    return story_folder

def load_text_from_story_folder():
    """
    从story文件夹中读取所有txt文件的内容
    
    读取story文件夹中的所有文本文件，将内容按句子分割，并返回句子列表。
    如果没有找到文件或内容为空，则返回默认文本。
    
    Returns:
        list: 文本句子列表
    """
    story_folder = get_story_folder()
    if not os.path.exists(story_folder):
        print("未找到story文件夹，使用默认文本")
        return [
            "这是一个示例故事。",
            "当无法获取到实际故事内容时，将播放这段默认文本。",
            "请确保story文件夹中有有效的文本文件，或检查故事生成服务是否正常工作。"
        ]
    
    text_content = []
    files_processed = 0
    
    # 获取文件夹中所有txt文件
    txt_files = [f for f in os.listdir(story_folder) if f.endswith('.txt')]
    # 按文件的创建时间排序，最新的文件排在前面
    txt_files.sort(key=lambda x: os.path.getctime(os.path.join(story_folder, x)), reverse=True)
    
    # 如果有文件，只处理最新的一个文件
    if txt_files:
        latest_file = txt_files[0]
        file_path = os.path.join(story_folder, latest_file)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # 将内容按句号分割，确保每段都是完整的句子
                sentences = []
                for sentence in content.split('。'):
                    sentence = sentence.strip()
                    if sentence:
                        # 如果句子不以标点符号结尾，添加句号
                        if not sentence[-1] in ['。', '！', '？', '…']:
                            sentence += '。'
                        sentences.append(sentence)
                text_content.extend(sentences)
                files_processed += 1
                print(f"已加载文件: {latest_file}")
        except Exception as e:
            print(f"读取文件 {latest_file} 时出错: {str(e)}")
    
    print(f"从story文件夹中加载了 {files_processed} 个文件")
    
    if not text_content:
        print("所有文件为空，使用默认文本")
        return [
            "这是一个示例故事。",
            "当无法获取到实际故事内容时，将播放这段默认文本。",
            "请确保story文件夹中有有效的文本文件，或检查故事生成服务是否正常工作。"
        ]
    
    return text_content

# 替换原来的 test_text 定义
test_text = load_text_from_story_folder()

def process_tts(token, output_path, test_text, story_title=None, sentence_number=None, total_sentences=None):
    """
    处理文本到语音的转换
    
    使用阿里云语音合成服务将文本转换为语音，并实时播放或保存为WAV文件。
    
    Args:
        token (str): 阿里云语音合成服务的访问Token
        output_path (str): 输出音频文件的路径（当SAVE_TO_FILE为True时使用）
        test_text (list): 要转换的文本列表
        story_title (str, optional): 故事标题，用于控制台输出
        sentence_number (int, optional): 当前句子编号，用于控制台输出
        total_sentences (int, optional): 总句子数，用于控制台输出
        
    Returns:
        None
    """
    file = None
    player = None
    stream = None
    # 创建一个事件标志，用于通知播放完成
    completed = False
    
    try:
        # 如果需要保存到文件，打开文件句柄
        if SAVE_TO_FILE:
            file = open(output_path, "wb")
        
        # 如果需要实时播放，初始化PyAudio
        if PLAY_REALTIME_RESULT:
            player = pyaudio.PyAudio()
            stream = player.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=24000,
                output=True,
                frames_per_buffer=1024
            )

        # 在控制台显示播放信息
        if story_title and sentence_number and total_sentences:
            print(f"\n===== 正在播放: 【{story_title}】 第 {sentence_number}/{total_sentences} 句 =====")

        def test_on_data(data, *args):
            """
            数据回调函数，处理接收到的音频数据
            
            当接收到音频数据时，将数据写入文件或发送到音频播放设备。
            
            Args:
                data (bytes): 接收到的音频数据
                *args: 其他参数
            """
            nonlocal stream, file
            if SAVE_TO_FILE and file:
                file.write(data)
            if PLAY_REALTIME_RESULT and stream:
                stream.write(data)

        def test_on_message(message, *args):
            """
            消息回调函数，处理接收到的消息
            
            注意：当前SDK版本不再支持on_message回调，此函数保留仅供参考。
            
            Args:
                message: 接收到的消息
                *args: 其他参数
            """
            # 只在调试模式下打印消息
            if "debug" in str(message).lower():
                print("on message=>{}".format(message))

        def test_on_close(*args):
            """
            关闭回调函数，处理连接关闭事件
            
            Args:
                *args: 其他参数
            """
            nonlocal completed
            completed = True
            if story_title and sentence_number:
                print(f"✓ 完成播放: 【{story_title}】 第 {sentence_number}/{total_sentences} 句")
            else:
                print("on_close: args=>{}".format(args))

        def test_on_error(message, *args):
            """
            错误回调函数，处理错误事件
            
            Args:
                message: 错误消息
                *args: 其他参数
            """
            nonlocal completed
            completed = True
            print("on_error message=>{} args=>{}".format(message, args))

        # 初始化语音合成SDK
        sdk = nls.NlsSpeechSynthesizer(
            url="wss://nls-gateway-cn-beijing.aliyuncs.com/ws/v1",  # 阿里云语音合成服务的WebSocket URL
            token=token,                                            # 访问Token
            appkey="dB2VfKnIiLeJT9j7",                              # 应用的AppKey
            on_data=test_on_data,                                   # 数据回调函数
            on_close=test_on_close,                                 # 关闭回调函数
            on_error=test_on_error,                                 # 错误回调函数
            callback_args=[]                                        # 回调函数的额外参数
        )

        start_time = time.time()
        # 处理每个文本片段
        for text in test_text:
            # 开始语音合成
            completed = False
            sdk.start(
                text=text,                # 要合成的文本
                voice="zhixiaobai",       # 语音角色，这里使用"知小白"
                aformat="wav",            # 音频格式，这里使用WAV
                sample_rate=24000,        # 采样率，24kHz
                volume=50,                # 音量，范围0-100
                speech_rate=0,            # 语速，0表示正常语速
                pitch_rate=0,             # 音调，0表示正常音调
            )
            
            # 使用回调机制等待播放完成，而不是预估时间
            # 等待语音合成完成（通过回调设置completed标志）
            max_wait = 30  # 最大等待时间，秒
            wait_start = time.time()
            while not completed and time.time() - wait_start < max_wait:
                time.sleep(0.01)  # 短暂睡眠，避免CPU使用率过高
            
            end_time = time.time()
            actual_time = end_time - start_time
            # 输出实际花费的时间
            if story_title and sentence_number:
                print(f"句子实际用时: {actual_time:.2f}秒")

        # 关闭SDK连接
        sdk.shutdown()
        
    finally:
        # 清理资源
        if SAVE_TO_FILE and file:
            file.close()
        if PLAY_REALTIME_RESULT and stream:
            stream.stop_stream()
            stream.close()
        if PLAY_REALTIME_RESULT and player:
            player.terminate()

if __name__ == "__main__":
    # 首先获取Token
    token = get_token()
    if not token:
        print("Failed to get token. Exiting...")
        exit(1)

    # 获取story文件夹路径
    story_folder = get_story_folder()
    if not os.path.exists(story_folder):
        print("未找到story文件夹，将在当前目录创建输出文件")
        base_path = "output_{}.wav"
    else:
        base_path = os.path.join(story_folder, "voice_{}.wav")

    # 获取要处理的文本
    sentences = load_text_from_story_folder()
    if not sentences:
        print("未找到任何文本内容，退出...")
        exit(1)
        
    print(f"共找到 {len(sentences)} 个句子，开始处理...")

    # 为每句话单独处理TTS转换
    for index, text in enumerate(sentences, 1):
        # 使用序号创建唯一的文件名
        output_path = base_path.format(f"{index:03d}")  # 使用3位数字格式化，如001, 002等
        print(f"正在处理第 {index} 句话，输出至: {output_path}")
        
        # 每句话单独调用TTS转换
        process_tts(token, output_path, [text], story_title="示例故事", sentence_number=index, total_sentences=len(sentences))