import asyncio
import os
import threading
import time
import sys
from datetime import datetime
from cosyVoiceTTS import process_tts, get_token
import sounddevice as sd
import soundfile as sf
import pygame
import queue
import importlib
from getusercomment import start_comment_monitoring, stop_comment_monitoring
from getResponseFromQianwen import process_live_comment

# 配置参数
USE_PYGAME = False  # 设置为 False 使用虚拟声卡播放，让直播伴侣可以捕获音频
# 虚拟声卡输出设备ID， 如需更改请修改此值
# 注意：请使用 list_devices() 函数查看您系统中的设备列表，找到虚拟声卡的ID
# 对于抖音直播伴侣：请在抖音直播伴侣中选择与此虚拟声卡相同的音频输入设备
VIRTUAL_OUTPUT_DEVICE_ID = 17  # CABLE Input (VB-Audio Virtual Cable), Windows DirectSound

# 直播间URL需要通过命令行参数提供，不再硬编码

# 初始化 pygame 混音器
pygame.mixer.init()

# 创建一个事件用于控制故事播放和评论处理的协调
story_paused = threading.Event()
story_paused.clear()  # 初始状态为不暂停

# 全局变量，用于存储语音token
global_token = None
# 互动处理锁，防止多个互动同时处理导致冲突
interaction_lock = threading.Lock()
# 当前是否正在处理互动
is_processing_interaction = False

def play_wav_file_virtual(file_path, device):
    """
    通过虚拟声卡播放WAV音频文件。
    
    使用 sounddevice 和 soundfile 库通过指定的虚拟声卡设备播放WAV文件。
    播放完成后会自动删除音频文件以节省磁盘空间。
    
    Args:
        file_path (str): WAV文件的路径
        device (int): 虚拟声卡设备的ID
        
    Raises:
        FileNotFoundError: 如果指定的音频文件不存在
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"音频文件不存在: {file_path}")
    try:
        data, samplerate = sf.read(file_path)
        sd.play(data, samplerate=samplerate, device=device)
        sd.wait()
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

def play_wav_file_pygame(file_path):
    """
    使用pygame播放WAV音频文件。
    
    通过pygame库播放WAV文件，播放完成后会自动删除音频文件以节省磁盘空间。
    相比虚拟声卡方式，pygame方式兼容性更好，适用于没有配置虚拟声卡的环境。
    
    Args:
        file_path (str): WAV文件的路径
        
    Raises:
        FileNotFoundError: 如果指定的音频文件不存在
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"音频文件不存在: {file_path}")
    try:
        sound = pygame.mixer.Sound(file_path)
        sound.play()
        pygame.time.wait(int(sound.get_length() * 1000))  # 等待音频播放完成
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

async def play_audio(audio_file_path):
    """
    异步播放音频文件。
    
    根据配置选择使用pygame或虚拟声卡方式播放音频文件。
    这个函数是异步的，可以在异步环境中调用而不会阻塞主线程。
    
    Args:
        audio_file_path (str): 音频文件的路径
        
    Returns:
        None
    """
    if USE_PYGAME:
        await asyncio.to_thread(play_wav_file_pygame, audio_file_path)
    else:
        await asyncio.to_thread(play_wav_file_virtual, audio_file_path, VIRTUAL_OUTPUT_DEVICE_ID)

def get_latest_audio_file(folder_path):
    """
    获取指定文件夹中最新的WAV文件。
    
    搜索指定文件夹中所有以'voice_'开头且以'.wav'结尾的文件，
    并返回按文件名排序后的最新文件的完整路径。
    
    Args:
        folder_path (str): 要搜索的文件夹路径
        
    Returns:
        str or None: 最新WAV文件的完整路径，如果没有找到则返回None
    """
    audio_files = [f for f in os.listdir(folder_path) if f.startswith('voice_') and f.endswith('.wav')]
    if not audio_files:
        return None
    return os.path.join(folder_path, sorted(audio_files)[-1])

def load_story_files(folder_path):
    """
    从文件夹中读取所有故事文本文件。
    
    读取指定文件夹中所有.txt文件的内容，并按文件名排序返回。
    
    Args:
        folder_path (str): 包含故事文本文件的文件夹路径
        
    Returns:
        list: 包含(文件名, 文本内容)元组的列表
    """
    story_files = [f for f in os.listdir(folder_path) if f.endswith('.txt')]
    story_files.sort()  # 按文件名排序
    stories = []
    
    for file in story_files:
        try:
            with open(os.path.join(folder_path, file), 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    stories.append((file, content))
        except Exception as e:
            print(f"读取文件 {file} 时出错: {str(e)}")
    
    return stories

def split_into_sentences(text):
    """
    将文本分割成句子。
    
    按句号分割文本，并确保每个句子都以适当的标点符号结尾。
    
    Args:
        text (str): 要分割的文本
        
    Returns:
        list: 分割后的句子列表
    """
    sentences = []
    for sentence in text.split('。'):
        sentence = sentence.strip()
        if sentence:
            # 检查是否以标点符号结尾
            if not sentence[-1] in ['。', '！', '？', '…']:
                sentence += '。'
            sentences.append(sentence)
    return sentences

def find_virtual_audio_device():
    """
    帮助用户找到虚拟声卡设备。
    
    此函数列出所有音频设备，并提供指导帮助用户找到合适的虚拟声卡设备ID。
    对于抖音直播伴侣，用户需要选择同一个虚拟声卡作为音频输入。
    
    Returns:
        None: 直接打印设备信息和指导到控制台
    """
    print("\n" + "="*80)
    print("虚拟声卡设置指南")
    print("="*80)
    print("1. 以下是您系统中的所有音频设备:")
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        print(f"   设备 {i}: {device['name']} ({'输入' if device['max_input_channels'] > 0 else ''}{'输出' if device['max_output_channels'] > 0 else ''})")
    
    print("\n2. 如何选择正确的虚拟声卡:")
    print("   - 寻找带有 'Virtual', 'VB-Audio', 'Soundflower' 等关键词的设备")
    print("   - 确保选择的是输出设备（有'输出'标记）")
    print(f"   - 当前配置的虚拟声卡设备ID是: {VIRTUAL_OUTPUT_DEVICE_ID}")
    
    print("\n3. 如何配置抖音直播伴侣:")
    print("   - 在抖音直播伴侣中，选择与上面相同的虚拟声卡作为音频输入")
    print("   - 这样，本程序输出的音频就会被抖音直播伴侣捕获并播放")
    
    print("\n4. 如何修改设置:")
    print("   - 如需更改虚拟声卡设备ID，请修改main.py中的VIRTUAL_OUTPUT_DEVICE_ID值")
    print("   - 如果您没有虚拟声卡，可以将USE_PYGAME设置为True，但这样抖音直播伴侣将无法捕获音频")
    print("="*80 + "\n")

def comment_handler(username, comment_text, comment_type="评论"):
    """
    处理直播间评论的回调函数
    
    当收到直播间评论时，直接处理评论而不是放入队列
    
    Args:
        username (str): 评论用户名
        comment_text (str): 评论内容
        comment_type (str): 评论类型，默认为"评论"
    """
    # 如果已经在处理互动，则跳过
    if is_processing_interaction:
        print(f"跳过: {username} - {comment_text}")
        return
    
    # 使用线程来处理互动，而不是尝试创建异步任务
    # 这是因为comment_handler是在非异步环境中被调用的
    threading.Thread(
        target=lambda: asyncio.run(process_interaction(username, comment_text, comment_type)),
        daemon=True
    ).start()

async def process_interaction(username, comment_text, comment_type="评论"):
    """
    处理用户互动
    
    使用千问AI生成回复，并播放回复语音
    
    Args:
        username (str): 用户名
        comment_text (str): 评论内容
        comment_type (str): 互动类型，默认为"评论"
    """
    global is_processing_interaction, global_token
    
    # 使用锁确保同一时间只处理一个互动
    with interaction_lock:
        # 设置正在处理互动的标志
        is_processing_interaction = True
        
        try:
            # 暂停故事播放，让AI回复评论
            story_paused.set()
            
            print(f"\n处理{comment_type}: {username}: {comment_text}")
            
            # 使用千问AI生成回复
            system_prompt = "你是一个友好、幽默的直播助手，负责回答直播间观众的问题和评论。回复要简洁、有趣，不超过50个字。"
            if comment_type == "礼物":
                system_prompt += "这是一个礼物，请表达感谢。"
            
            response = process_live_comment(f"{username}: {comment_text}", system_prompt)
            
            print(f"AI回复: {response}")
            
            # 生成回复语音
            temp_output_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "story",
                f"response_{int(time.time())}.wav"
            )
            
            # 获取token，如果全局token不可用则重新获取
            token = global_token
            if not token:
                token = get_token()
                if token:
                    # 如果成功获取了新token，更新全局token
                    global_token = token
            
            if not token:
                print("无法获取语音token，跳过语音生成")
                return
            
            # 使用TTS生成语音
            process_tts(
                token,
                temp_output_path,
                [response],
                story_title=f"回复{username}",
                sentence_number=1,
                total_sentences=1
            )
            
            # 播放语音回复
            if os.path.exists(temp_output_path):
                if USE_PYGAME:
                    play_wav_file_pygame(temp_output_path)
                else:
                    play_wav_file_virtual(temp_output_path, VIRTUAL_OUTPUT_DEVICE_ID)
            else:
                print(f"警告: 语音文件未生成: {temp_output_path}")
            
        except Exception as e:
            print(f"处理互动时出错: {str(e)}")
        finally:
            # 处理完成后，恢复故事播放
            story_paused.clear()
            # 重置处理标志
            is_processing_interaction = False

async def play_stories():
    """
    异步播放故事
    
    读取story文件夹中的故事文件，并使用TTS播放
    在播放过程中会检查是否需要暂停以处理评论
    """
    try:
        # 获取当前目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 获取语音转换token，优先使用全局token
        token = global_token or get_token()
        if not token:
            raise Exception("获取token失败")
        
        # 使用story文件夹
        story_folder = os.path.join(current_dir, "story")
        if not os.path.exists(story_folder):
            raise Exception("未找到story文件夹")
        
        # 读取故事文件
        stories = load_story_files(story_folder)
        if not stories:
            raise Exception("未找到任何故事文件")
        
        # 处理每个故事
        print("\n开始播放故事...")
        for story_file, story_content in stories:
            # 使用文件名（不含扩展名）作为故事标识和标题
            story_id = os.path.splitext(story_file)[0]
            story_title = story_id  # 使用文件名作为故事标题显示
            
            print(f"\n开始播放故事: 【{story_title}】")
            
            # 将故事分割成句子
            sentences = split_into_sentences(story_content)
            print(f"故事共有 {len(sentences)} 个句子")
            
            # 为每个句子生成语音并实时播放
            for i, sentence in enumerate(sentences, 1):
                # 如果有评论需要处理，暂停故事播放
                while story_paused.is_set():
                    await asyncio.sleep(0.5)  # 等待评论处理完成
                
                # 构建一个临时路径
                temp_output_path = os.path.join(
                    story_folder, 
                    f"voice_{story_id}_{i:03d}.wav"
                )
                
                # 简化输出，不再打印分隔线和进度信息
                # 使用直接播放模式，传递故事标题和句子信息
                process_tts(
                    token, 
                    temp_output_path, 
                    [sentence],
                    story_title=story_title,
                    sentence_number=i,
                    total_sentences=len(sentences)
                )
                
            # 故事播放完成后的分隔
            print(f"故事 【{story_title}】 播放完成!")
            
    except Exception as e:
        print(f"播放故事时出错：{str(e)}")

async def main():
    """
    主函数，协调整个程序的执行流程。
    
    执行以下步骤：
    1. 启动直播评论监控
    2. 启动故事播放协程
    
    整个过程是异步的，使用asyncio协程实现。
    
    Raises:
        Exception: 如果在执行过程中发生错误
    """
    global global_token
    
    try:
        # 检查是否提供了直播间URL
        if len(sys.argv) <= 1:
            print("错误: 未指定直播间URL")
            print("用法: python main.py https://live.douyin.com/您的直播间ID")
            sys.exit(1)
            
        # 获取直播间URL
        douyin_live_url = sys.argv[1]
        print(f"使用直播间URL: {douyin_live_url}")
        
        # 获取语音转换token并保存到全局变量
        global_token = get_token()
        if not global_token:
            raise Exception("获取token失败")
        
        # 启动直播评论监控
        print("\n启动直播评论监控...")
        start_comment_monitoring(douyin_live_url, comment_handler)
        
        # 创建并启动故事播放任务
        story_task = asyncio.create_task(play_stories())
        
        # 等待故事播放任务完成
        await story_task
            
    except Exception as e:
        print(f"运行出错：{str(e)}")
    finally:
        # 确保停止评论监控
        stop_comment_monitoring()

if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())
