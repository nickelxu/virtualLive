import asyncio
import os
from datetime import datetime
from getStoryFromCoze import get_story
from getCosyVoiceToken import get_token
from cosyVoiceTTS import process_tts
import sounddevice as sd
import soundfile as sf
import pygame
import time

# 配置参数
USE_PYGAME = True  # 设置为 True 使用 pygame 播放，False 使用虚拟声卡
# 虚拟声卡输出设备ID， 如需更改请修改此值
# 注意：请使用 list_devices() 函数查看您系统中的设备列表，找到虚拟声卡的ID
# 对于抖音直播伴侣：请在抖音直播伴侣中选择与此虚拟声卡相同的音频输入设备
VIRTUAL_OUTPUT_DEVICE_ID = 17

# 初始化 pygame 混音器
pygame.mixer.init()

def list_devices():
    """
    列出系统中所有可用的音频设备。
    
    这个函数使用 sounddevice 库查询并打印所有可用的音频输入和输出设备，
    包括它们的ID、名称和通道数等信息。在配置虚拟声卡时非常有用。
    
    Returns:
        None: 直接打印设备信息到控制台
    """
    print("音频设备列表：")
    print(sd.query_devices())

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

def delete_old_files(current_dir, keep_files=10):
    """
    清理story文件夹中的旧文件
    
    保留story文件夹中最新的几个故事文件和相关的语音文件，删除较旧的文件。
    
    Args:
        current_dir (str): 当前工作目录
        keep_files (int, optional): 要保留的故事文件数量。默认为10个。
        
    Returns:
        None
    """
    try:
        # 获取story文件夹路径
        story_folder = os.path.join(current_dir, "story")
        if not os.path.exists(story_folder):
            print("未找到story文件夹，跳过清理")
            return
        
        # 获取所有txt文件（故事文件）
        story_files = [f for f in os.listdir(story_folder) if f.endswith('.txt')]
        if not story_files:
            print("未找到任何故事文件，跳过清理")
            return
        
        # 按文件创建时间排序（最新的在前面）
        story_files.sort(key=lambda x: os.path.getctime(os.path.join(story_folder, x)), reverse=True)
        
        # 保留最新的几个文件，删除其余的
        files_to_delete = story_files[keep_files:]
        if not files_to_delete:
            print("没有需要删除的旧文件")
            return
        
        print(f"将删除 {len(files_to_delete)} 个旧故事文件及相关语音文件")
        for file in files_to_delete:
            # 删除故事文件
            file_path = os.path.join(story_folder, file)
            try:
                os.remove(file_path)
                print(f"已删除故事文件: {file}")
                
                # 删除与此故事相关的语音文件
                file_base = os.path.splitext(file)[0]  # 获取不带扩展名的文件名
                voice_pattern = f"voice_{file_base}_*.wav"
                for voice_file in os.listdir(story_folder):
                    if voice_file.startswith(f"voice_{file_base}_") and voice_file.endswith(".wav"):
                        voice_path = os.path.join(story_folder, voice_file)
                        os.remove(voice_path)
                        print(f"已删除语音文件: {voice_file}")
            except Exception as e:
                print(f"删除文件 {file} 时出错: {str(e)}")
                
    except Exception as e:
        print(f"清理旧文件时出错: {str(e)}")

# 清理旧的日期文件夹（兼容旧版本）
def delete_old_folders(current_dir, keep_days=7):
    """
    清理旧的日期文件夹 (仅用于兼容旧版本)
    
    检查并删除超过指定保留天数的日期文件夹，仅保留最近的几个文件夹。
    本函数仅用于兼容旧版本，新版本将所有故事保存在story文件夹中。
    
    Args:
        current_dir (str): 当前工作目录
        keep_days (int, optional): 保留的文件夹数量。默认为7天。
        
    Returns:
        None
    """
    try:
        # 获取所有日期命名的文件夹（8位数字作为文件夹名）
        date_folders = [f for f in os.listdir(current_dir) if len(f) == 8 and f.isdigit()]
        if not date_folders:
            return  # 没有日期文件夹，直接返回
        
        # 按日期排序
        date_folders.sort(reverse=True)
        
        # 保留最近的文件夹，删除其余的
        folders_to_delete = date_folders[keep_days:]
        for folder in folders_to_delete:
            folder_path = os.path.join(current_dir, folder)
            try:
                print(f"删除旧文件夹: {folder}")
                # 删除文件夹及其所有内容
                for root, dirs, files in os.walk(folder_path, topdown=False):
                    for name in files:
                        os.remove(os.path.join(root, name))
                    for name in dirs:
                        os.rmdir(os.path.join(root, name))
                os.rmdir(folder_path)
            except Exception as e:
                print(f"删除文件夹 {folder} 时出错: {str(e)}")
                
    except Exception as e:
        print(f"清理旧文件夹时出错: {str(e)}")

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

async def main():
    """
    主函数，协调整个程序的执行流程。
    
    执行以下步骤：
    1. 列出所有音频设备
    2. 清理story文件夹中的旧文件
    3. 清理旧版本的日期文件夹（兼容旧版本）
    4. 获取语音合成token
    5. 使用story文件夹
    6. 读取故事文件
    7. 为每个故事的每个句子生成语音并实时播放
    
    整个过程是异步的，使用asyncio协程实现。
    
    Raises:
        Exception: 如果在执行过程中发生错误
    """
    try:
        print("列出所有音频设备，确保虚拟声卡设置正确：")
        list_devices()
        
        # 显示虚拟声卡设置指南
        find_virtual_audio_device()
        
        # 获取当前目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 1. 清理story文件夹中的旧文件
        print("\n开始清理story文件夹中的旧文件...")
        delete_old_files(current_dir)
        print("story文件夹清理完成")
        
        # 2. 清理旧版本的日期文件夹（兼容旧版本）
        print("\n开始检查旧版本的日期文件夹...")
        delete_old_folders(current_dir)
        print("旧版本文件夹检查完成")
        
        # 3. 获取语音转换token
        print("正在获取语音转换token...")
        token = get_token()
        if not token:
            raise Exception("获取token失败")
        print("成功获取语音token")
        
        # 4. 使用story文件夹
        story_folder = os.path.join(current_dir, "story")
        if not os.path.exists(story_folder):
            raise Exception("未找到story文件夹")
        
        # 5. 读取故事文件
        stories = load_story_files(story_folder)
        if not stories:
            raise Exception("未找到任何故事文件")
        
        # 6. 处理每个故事
        print("\n开始生成并播放语音...")
        for story_file, story_content in stories:
            # 使用文件名（不含扩展名）作为故事标识和标题
            story_id = os.path.splitext(story_file)[0]
            story_title = story_id  # 使用文件名作为故事标题显示
            
            print(f"\n{'='*50}")
            print(f"开始播放故事: 【{story_title}】")
            print(f"{'='*50}\n")
            
            # 将故事分割成句子
            sentences = split_into_sentences(story_content)
            print(f"故事共有 {len(sentences)} 个句子")
            
            # 为每个句子生成语音并实时播放
            for i, sentence in enumerate(sentences, 1):
                # 构建一个临时路径（实际上不会用于保存文件）
                temp_output_path = os.path.join(
                    story_folder, 
                    f"voice_{story_id}_{i:03d}.wav"
                )
                
                print(f"\n{'-'*40}")
                print(f"播放进度: [{i}/{len(sentences)}]")
                print(f"文本: {sentence}")
                
                # 使用直接播放模式，传递故事标题和句子信息
                # 语音合成SDK会通过回调通知播放完成，无需额外等待
                process_tts(
                    token, 
                    temp_output_path, 
                    [sentence],
                    story_title=story_title,
                    sentence_number=i,
                    total_sentences=len(sentences)
                )
                
                # 不再需要额外的等待时间，回调机制会确保播放完成后再继续
                
            # 故事播放完成后的分隔
            print(f"\n{'*'*50}")
            print(f"故事 【{story_title}】 播放完成!")
            print(f"{'*'*50}\n")
            
    except Exception as e:
        print(f"运行出错：{str(e)}")

if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())
