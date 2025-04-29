import asyncio
import os
import threading
import time
import sys
import io
from datetime import datetime
from cosyVoiceTTS import process_tts, get_token
import sounddevice as sd
import soundfile as sf
import pygame
import queue
import importlib
import numpy as np
from getusercomment import start_comment_monitoring, stop_comment_monitoring
from getResponseFromQianwen import process_live_comment
from dotenv import load_dotenv
import struct
from spotify_api import SpotifyAPI
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import random
import json
import requests

# 缓存文件路径
CACHE_PATH = ".spotify_cache"

# https://live.douyin.com/769032284842
class StoryPlayer:
    def __init__(self):
        # 强制重新加载环境变量
        load_dotenv(override=True)
        
        # 配置参数
        self.use_pygame = False  # 设置为 False 使用虚拟声卡播放
        self.virtual_output_device_id = 17  # CABLE Input (VB-Audio Virtual Cable)
        
        # 初始化 pygame 混音器
        pygame.mixer.init()
        
        # 创建事件和锁
        self.story_paused = threading.Event()
        self.story_paused.clear()
        self.sentence_completed = threading.Event()
        self.sentence_completed.set()
        self.interaction_lock = threading.Lock()
        self.comment_cache_lock = threading.Lock()
        
        # 状态变量
        self.is_processing_interaction = False
        self.global_token = None
        self.comment_cache = []
        
        # 初始化Spotify API
        self.spotify_api = SpotifyAPI()
        
        # 初始化Spotify播放器
        self.sp = self._init_spotify()
        
        # 新增：保存被中断的句子信息
        self.interrupted_sentence = None
        self.interrupted_sentence_index = None
        self.interrupted_story_title = None
        
    def _init_spotify(self):
        """初始化Spotify客户端"""
        try:
            # 设置Spotify API凭证
            client_id = "036473f257b543c8956060e7147a4624"
            client_secret = "c5978c45956445c89bc2268144ce1994"
            username = "shanxutech@foxmail.com"
            
            # 创建SpotifyOAuth对象
            sp_oauth = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri="http://127.0.0.1:8000/callback",
                scope="user-read-playback-state,user-modify-playback-state,playlist-read-private",
                username=username,
                open_browser=True
            )
            
            # 获取token
            token_info = sp_oauth.get_access_token()
            if not token_info:
                raise Exception("获取访问令牌失败")
            
            # 使用token初始化Spotify客户端
            return spotipy.Spotify(auth=token_info['access_token'])
            
        except Exception as e:
            print(f"Spotify授权失败: {str(e)}")
            print("请确保：")
            print("1. 已在Spotify开发者平台添加重定向URI: http://127.0.0.1:8000/callback")
            print("2. 已登录正确的Spotify账号")
            print("3. 已安装并运行Spotify客户端")
            raise
    
    async def play_audio(self, audio_data):
        """异步播放音频数据"""
        try:
            # 添加WAV文件头（如果需要）
            audio_data = self.add_wav_header_if_needed(audio_data)
            
            # 创建临时文件
            temp_file = "temp_audio.wav"
            with open(temp_file, "wb") as f:
                f.write(audio_data)
            
            # 加载并播放音频
            sound = pygame.mixer.Sound(temp_file)
            sound.play()
            
            # 等待播放完成
            while pygame.mixer.get_busy():
                # 检查是否需要暂停
                if self.story_paused.is_set():
                    print("检测到暂停事件，等待当前音频播放完成...")
                    # 等待当前音频播放完成
                    while pygame.mixer.get_busy():
                        await asyncio.sleep(0.05)
                    break
                await asyncio.sleep(0.05)
            
            # 清理临时文件
            try:
                os.remove(temp_file)
            except:
                pass
                
            # 只有在音频成功播放完成且未被暂停时才设置sentence_completed事件
            if not self.story_paused.is_set():
                self.sentence_completed.set()
                
        except Exception as e:
            print(f"播放音频时出错: {str(e)}")
            print("尝试使用备用播放方法...")
            try:
                # 备用播放方法：使用sounddevice
                with io.BytesIO(audio_data) as audio_buffer:
                    data, samplerate = sf.read(audio_buffer)
                    sd.play(data, samplerate=samplerate)
                    sd.wait()
                
                # 只有在备用方法也成功播放后才设置sentence_completed事件
                if not self.story_paused.is_set():
                    self.sentence_completed.set()
            except Exception as e2:
                print(f"备用播放方法也失败: {str(e2)}")
                print("音频播放失败，请检查系统音频设备")
                # 音频播放失败时，不设置sentence_completed事件
    
    def add_wav_header_if_needed(self, audio_data, sample_rate=24000, channels=1, bits_per_sample=16):
        """
        检查音频数据是否包含WAV文件头，如果没有则添加
        
        Args:
            audio_data (bytes): 原始音频数据
            sample_rate (int): 采样率，默认24000Hz
            channels (int): 通道数，默认1（单声道）
            bits_per_sample (int): 位深度，默认16位
            
        Returns:
            bytes: 包含WAV文件头的音频数据
        """
        # 检查是否已经有WAV文件头
        if len(audio_data) > 44 and audio_data[:4] == b'RIFF' and audio_data[8:12] == b'WAVE':          
            return audio_data
        
        print("音频数据不包含WAV文件头，正在添加...")
        
        # 计算数据大小
        data_size = len(audio_data)
        
        # 创建WAV文件头
        header = bytearray()
        
        # RIFF头
        header.extend(b'RIFF')
        header.extend(struct.pack('<I', 36 + data_size))  # 文件总大小
        header.extend(b'WAVE')
        
        # fmt子块
        header.extend(b'fmt ')
        header.extend(struct.pack('<I', 16))  # fmt子块大小
        header.extend(struct.pack('<H', 1))   # 音频格式，1表示PCM
        header.extend(struct.pack('<H', channels))  # 通道数
        header.extend(struct.pack('<I', sample_rate))  # 采样率
        header.extend(struct.pack('<I', sample_rate * channels * bits_per_sample // 8))  # 字节率
        header.extend(struct.pack('<H', channels * bits_per_sample // 8))  # 块对齐
        header.extend(struct.pack('<H', bits_per_sample))  # 位深度
        
        # data子块
        header.extend(b'data')
        header.extend(struct.pack('<I', data_size))  # 数据大小
        
        # 合并文件头和音频数据
        return header + audio_data
    
    def load_story_files(self, folder_path):
        """从文件夹中读取所有故事文本文件"""
        story_files = [f for f in os.listdir(folder_path) if f.endswith('.txt')]
        story_files.sort()
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
    
    def split_into_sentences(self, text):
        """将文本分割成句子"""
        sentences = []
        for sentence in text.split('。'):
            sentence = sentence.strip()
            if sentence:
                if not sentence[-1] in ['。', '！', '？', '…']:
                    sentence += '。'
                sentences.append(sentence)
        return sentences
    
    def comment_handler(self, username, comment_text, comment_type="评论"):
        """处理直播间评论的回调函数"""
        # 将评论添加到缓存队列
        with self.comment_cache_lock:
            # 检查是否已存在相同的评论
            if not any(c[0] == username and c[1] == comment_text for c in self.comment_cache):
                self.comment_cache.append((username, comment_text, comment_type))
                print(f"缓存评论: {username}: {comment_text}")
                
                # 设置暂停事件，但等待当前句子播放完成
                if not self.sentence_completed.is_set():
                    print("等待当前句子播放完成...")
                    self.story_paused.set()
                else:
                    # 如果当前句子已经播放完成，立即处理评论
                    print(f"当前句子已播放完成，立即处理评论: {username}: {comment_text}")
                    self.story_paused.set()
                    asyncio.create_task(self.process_comment_cache())
    
    def handle_welcome(self,username):
        # """处理用户进入直播间的欢迎消息"""
        return f"欢迎{username}来到直播间，天天开心喔"
    
    async def process_interaction(self, username, comment_text, comment_type="评论"):
        """处理用户互动"""
        # 使用锁确保同一时间只处理一个互动
        with self.interaction_lock:
            # 设置正在处理互动的标志
            self.is_processing_interaction = True
            
            try:
                # 检查是否是"来了"的评论
                if comment_text == "来了":
                    response = self.handle_welcome(username)
                else:               
                    # 使用千问AI生成回复
                    system_prompt = "你是一个友好、幽默的直播助手，负责回答直播间观众的问题和评论。回复要简洁、有趣，不超过50个字。"
                    if comment_type == "礼物":
                        system_prompt += "这是一个礼物，请表达感谢。"
                    
                    response = process_live_comment(f"{username}: {comment_text}", system_prompt)
                    
                    # 只打印评论原文和回复信息
                    print(f"回复评论 - {username}: {comment_text} -> {response}")
                    
                    # 获取token，如果全局token不可用则重新获取
                    token = self.global_token
                    if not token:
                        token = get_token()
                        if token:
                            # 如果成功获取了新token，更新全局token
                            self.global_token = token
                    
                    if not token:
                        print("无法获取语音token，跳过语音生成")
                        return
                    
                    # 使用TTS生成语音数据
                    audio_data = process_tts(
                        token,
                        [response],
                        story_title=f"回复{username}",
                        sentence_number=1,
                        total_sentences=1
                    )
                    
                    # 播放语音回复
                    if audio_data:
                        await self.play_audio(audio_data)
                    else:
                        print(f"警告: 语音数据生成失败")
                
            except Exception as e:
                print(f"处理互动时出错: {str(e)}")
            finally:
                # 处理完成后，清空评论缓存
                with self.comment_cache_lock:
                    self.comment_cache.clear()
                
                # 重置处理标志
                self.is_processing_interaction = False
                
                # 确保sentence_completed事件被设置
                self.sentence_completed.set()
                
                # 恢复故事播放
                self.story_paused.clear()
    
    async def process_comment_cache(self):
        """处理评论缓存中的评论"""
        # 如果已经在处理互动，直接返回
        if self.is_processing_interaction:
            print("已经在处理互动，跳过")
            return
        
        # 从缓存中获取评论
        with self.comment_cache_lock:
            if not self.comment_cache:
                # 如果缓存为空，清除暂停事件
                print("评论缓存为空，清除暂停事件")
                self.story_paused.clear()
                return
            
            # 获取所有未处理的评论
            comments_to_process = self.comment_cache.copy()
            # 清空缓存，准备接收新评论
            self.comment_cache.clear()
        
        # 按顺序处理每条评论
        for comment in comments_to_process:
            username, comment_text, comment_type = comment
            print(f"处理评论: {username}: {comment_text}")
            await self.process_interaction(username, comment_text, comment_type)
            
            # 处理完一条评论后，检查是否有新评论加入
            with self.comment_cache_lock:
                if self.comment_cache:
                    # 如果有新评论，先处理新评论
                    break
    
    async def play_spotify_music(self):
        """异步播放Spotify音乐"""
        try:
            # 获取用户的所有歌单
            playlists = self.sp.current_user_playlists(limit=50)
            old_songs_playlist = None
            
            # 遍历所有歌单，找到用户自己创建的"old songs"歌单
            while playlists:
                for playlist in playlists['items']:
                    # 检查是否是用户自己创建的歌单（owner.id与当前用户相同）
                    if (playlist['name'].lower() == 'old songs' and 
                        playlist['owner']['id'] == self.sp.current_user()['id']):
                        old_songs_playlist = playlist
                        break
                
                if old_songs_playlist:
                    break
                
                # 如果有下一页，继续获取
                if playlists['next']:
                    playlists = self.sp.next(playlists)
                else:
                    break
            
            if not old_songs_playlist:
                print("未找到用户创建的'old songs'歌单")
                return
            
            print(f"找到歌单: {old_songs_playlist['name']} (创建者: {old_songs_playlist['owner']['display_name']})")
            
            # 获取歌单中的所有歌曲
            tracks = self.spotify_api.get_playlist_tracks(old_songs_playlist['id'])
            if not tracks:
                print("无法获取歌单歌曲")
                return
            
            # 随机选择一首歌曲
            random_track = random.choice(tracks)
            track_name = random_track['track']['name']
            artist_name = random_track['track']['artists'][0]['name']
            track_uri = random_track['track']['uri']
            
            print(f"正在播放: {track_name} - {artist_name}")
            
            try:
                # 获取当前设备
                devices = self.sp.devices()
                if not devices['devices']:
                    print("未找到可用的Spotify设备，请确保Spotify客户端已打开")
                    raise Exception("No available devices")
                
                # 使用第一个可用设备
                device_id = devices['devices'][0]['id']
                
                # 开始播放
                self.sp.start_playback(device_id=device_id, uris=[track_uri])
                
                # 等待歌曲播放完成
                while True:
                    current_playback = self.sp.current_playback()
                    if not current_playback or not current_playback['is_playing']:
                        break
                    await asyncio.sleep(1)
                    
            except Exception as e:
                print(f"使用Premium播放失败: {str(e)}")
                print("请确保：")
                print("1. Spotify客户端已打开")
                print("2. 已登录正确的Premium账号")
                print("3. 设备已正确连接")
            
        except Exception as e:
            print(f"播放Spotify音乐时出错: {str(e)}")

    async def search_and_play_song(self, query):
        """搜索并播放Spotify歌曲"""
        try:
            # 停止当前正在播放的音乐
            pygame.mixer.stop()
            
            # 搜索歌曲
            results = self.sp.search(q=query, type='track', limit=1)
            if not results['tracks']['items']:
                print(f"未找到歌曲: {query}")
                return
            
            # 获取第一首匹配的歌曲
            track = results['tracks']['items'][0]
            track_name = track['name']
            artist_name = track['artists'][0]['name']
            track_uri = track['uri']
            preview_url = track['preview_url']
            
            print(f"正在播放: {track_name} - {artist_name}")
            
            try:
                # 获取当前设备
                devices = self.sp.devices()
                if not devices['devices']:
                    print("未找到可用的Spotify设备，请确保Spotify客户端已打开")
                    raise Exception("No available devices")
                
                # 使用第一个可用设备
                device_id = devices['devices'][0]['id']
                
                # 开始播放
                self.sp.start_playback(device_id=device_id, uris=[track_uri])
                
                # 等待歌曲播放完成
                while True:
                    current_playback = self.sp.current_playback()
                    if not current_playback or not current_playback['is_playing']:
                        break
                    await asyncio.sleep(1)
                    
            except Exception as e:
                print("Spotify Premium播放失败，尝试使用预览音频...")
                if not preview_url:
                    print(f"歌曲 {track_name} 没有预览音频")
                    return
                
                try:
                    # 下载预览音频
                    response = requests.get(preview_url)
                    if response.status_code != 200:
                        print("下载预览音频失败")
                        return
                    
                    # 保存为临时文件
                    temp_file = "temp_preview.mp3"
                    with open(temp_file, "wb") as f:
                        f.write(response.content)
                    
                    # 使用pygame播放预览音频
                    sound = pygame.mixer.Sound(temp_file)
                    sound.play()
                    
                    # 等待播放完成
                    while pygame.mixer.get_busy():
                        await asyncio.sleep(0.1)
                    
                    # 清理临时文件
                    try:
                        os.remove(temp_file)
                    except:
                        pass
                        
                except Exception as e2:
                    print(f"播放预览音频时出错: {str(e2)}")
            
        except Exception as e:
            print(f"搜索并播放歌曲时出错: {str(e)}")
    
    async def play_stories(self):
        """异步播放故事"""
        try:
            # 获取当前目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            
            # 获取语音转换token，优先使用全局token
            token = self.global_token or get_token()
            if not token:
                raise Exception("获取token失败")
            
            # 使用story文件夹
            story_folder = os.path.join(current_dir, "story")
            if not os.path.exists(story_folder):
                os.makedirs(story_folder)
                print(f"创建story文件夹: {story_folder}")
            
            # 读取故事文件
            stories = self.load_story_files(story_folder)
            if not stories:
                raise Exception("未找到任何故事文件")
            
            # 处理每个故事
            for story_file, story_content in stories:
                # 使用文件名（不含扩展名）作为故事标识和标题
                story_id = os.path.splitext(story_file)[0]
                story_title = story_id
                
                print(f"\n开始播放故事: 【{story_title}】")
                
                # 将故事分割成句子
                sentences = self.split_into_sentences(story_content)
                
                # 为每个句子生成语音并实时播放
                i = 0
                while i < len(sentences):
                    # 如果有被中断的句子，先处理它
                    if self.interrupted_sentence is not None and self.interrupted_story_title == story_title:
                        sentence = self.interrupted_sentence
                        i = self.interrupted_sentence_index
                        # 清除中断信息
                        self.interrupted_sentence = None
                        self.interrupted_sentence_index = None
                        self.interrupted_story_title = None
                    else:
                        sentence = sentences[i]
                    
                    # 清除sentence_completed事件，表示新句子开始播放
                    self.sentence_completed.clear()
                    
                    # 检查是否需要处理评论
                    if self.story_paused.is_set():
                        # 保存当前句子信息
                        self.interrupted_sentence = sentence
                        self.interrupted_sentence_index = i
                        self.interrupted_story_title = story_title
                        
                        # 处理评论缓存
                        await self.process_comment_cache()
                        continue  # 继续处理被中断的句子
                    
                    print(f"生成第 {i+1}/{len(sentences)} 句语音: {sentence[:30]}...")
                    
                    # 使用TTS生成语音数据
                    audio_data = process_tts(
                        token, 
                        [sentence],
                        story_title=story_title,
                        sentence_number=i+1,
                        total_sentences=len(sentences)
                    )
                    
                    # 播放生成的语音
                    if audio_data:
                        await self.play_audio(audio_data)
                        
                        # 检查是否需要处理评论
                        if self.story_paused.is_set():
                            # 保存当前句子信息
                            self.interrupted_sentence = sentence
                            self.interrupted_sentence_index = i
                            self.interrupted_story_title = story_title
                            
                            # 处理评论缓存
                            await self.process_comment_cache()
                            continue  # 继续处理被中断的句子
                        
                        # 如果成功播放完成且没有被中断，移动到下一句
                        i += 1
                    else:
                        print(f"警告: 第 {i+1} 句语音数据生成失败，跳过")
                        i += 1
                
                # 故事播放完成后的分隔
                print(f"故事 【{story_title}】 播放完成!")
                
        except Exception as e:
            print(f"播放故事时出错：{str(e)}")
    
    async def run(self):
        """运行故事播放器"""
        try:
            # 获取语音转换token并保存到全局变量
            self.global_token = get_token()
            if not self.global_token:
                raise Exception("获取token失败")
            
            # 提示用户输入直播间URL
            print("请输入抖音直播间URL (直接按回车跳过，将不进行评论监控):")
            douyin_live_url = input().strip()
            
            # 如果用户提供了URL，启动直播评论监控
            if douyin_live_url:
                print(f"使用直播间URL: {douyin_live_url}")
                # 确保评论监控成功启动
                if not start_comment_monitoring(douyin_live_url, self.comment_handler):
                    print("评论监控启动失败，请检查URL是否正确")
                    return
                print("评论监控已成功启动")
            else:
                print("跳过评论监控，仅播放故事")
            
            # 创建并启动故事播放任务
            story_task = asyncio.create_task(self.play_stories())
            
            # 创建并启动Spotify音乐播放任务
            music_task = asyncio.create_task(self.play_spotify_music())
            
            # 创建并启动用户输入处理任务
            input_task = asyncio.create_task(self.handle_user_input())
            
            # 等待所有任务完成
            await asyncio.gather(story_task, music_task, input_task)
                
        except Exception as e:
            print(f"运行出错：{str(e)}")
        finally:
            # 如果启动了评论监控，确保停止
            if 'douyin_live_url' in locals() and douyin_live_url:
                stop_comment_monitoring()

    async def handle_user_input(self):
        """处理用户输入"""
        while True:
            try:
                # 使用asyncio.get_event_loop().run_in_executor来异步获取用户输入
                query = await asyncio.get_event_loop().run_in_executor(None, input, "请输入要搜索的歌曲名称（输入'q'退出）: ")
                
                if query.lower() == 'q':
                    break
                
                if query.strip():
                    await self.search_and_play_song(query)
            except Exception as e:
                print(f"处理用户输入时出错: {str(e)}")
                await asyncio.sleep(1)  # 出错时等待1秒后继续


if __name__ == "__main__":
    # 创建故事播放器实例并运行
    player = StoryPlayer()
    asyncio.run(player.run()) 