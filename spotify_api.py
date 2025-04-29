import base64
import requests
import json
import random
import os
from dotenv import load_dotenv

# Spotify API配置
SPOTIFY_CLIENT_ID = "036473f257b543c8956060e7147a4624"
SPOTIFY_CLIENT_SECRET = "c5978c45956445c89bc2268144ce1994"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"

class SpotifyAPI:
    def __init__(self):
        self.token_data = None
        self.get_token()
    
    def get_token(self):
        """获取Spotify访问令牌"""
        try:
            # 准备认证信息
            auth_string = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
            auth_bytes = auth_string.encode("utf-8")
            auth_base64 = base64.b64encode(auth_bytes).decode("utf-8")
            
            # 准备请求头
            headers = {
                "Authorization": f"Basic {auth_base64}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            # 准备请求数据
            data = {"grant_type": "client_credentials"}
            
            # 发送请求
            response = requests.post(SPOTIFY_TOKEN_URL, headers=headers, data=data)
            
            if response.status_code == 200:
                # 保存完整的令牌信息
                self.token_data = response.json()
                print("成功获取Spotify访问令牌")
                return self.token_data
            else:
                print(f"获取Spotify访问令牌失败: {response.status_code}")
                print(response.text)
                return None
                
        except Exception as e:
            print(f"获取Spotify访问令牌时出错: {str(e)}")
            return None
    
    def get_headers(self):
        """获取带有认证信息的请求头"""
        if not self.token_data:
            self.get_token()
        return {
            "Authorization": f"Bearer {self.token_data['access_token']}"
        }
    
    def get_playlist_tracks(self, playlist_id):
        """获取歌单中的所有歌曲"""
        try:
            headers = self.get_headers()
            url = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                return response.json()['items']
            else:
                print(f"获取歌单歌曲失败: {response.status_code}")
                return None
        except Exception as e:
            print(f"获取歌单歌曲时出错: {str(e)}")
            return None
    
    def get_random_track(self, playlist_id):
        """从歌单中随机获取一首歌曲"""
        tracks = self.get_playlist_tracks(playlist_id)
        if tracks:
            random_track = random.choice(tracks)
            return {
                'name': random_track['track']['name'],
                'artist': random_track['track']['artists'][0]['name'],
                'uri': random_track['track']['uri']
            }
        return None

# 直接运行获取访问令牌
if __name__ == "__main__":
    spotify = SpotifyAPI()
    if spotify.token_data:
        print("\n完整的访问令牌信息：")
        print(json.dumps(spotify.token_data, indent=2, ensure_ascii=False))
        
        # 将令牌信息保存到.env文件
        with open('.env', 'a') as f:
            f.write(f"\nSPOTIFY_ACCESS_TOKEN={spotify.token_data['access_token']}\n")
            f.write(f"SPOTIFY_TOKEN_TYPE={spotify.token_data['token_type']}\n")
            f.write(f"SPOTIFY_EXPIRES_IN={spotify.token_data['expires_in']}\n")
        print("\n令牌信息已保存到.env文件")
    else:
        print("访问令牌获取失败") 