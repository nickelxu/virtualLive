import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from spotify_api import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
import re

# Spotify API凭证
SPOTIFY_REDIRECT_URI = 'http://127.0.0.1:8000/callback'

def get_playlist_by_name(playlist_name):
    """
    通过歌单名称获取歌单ID
    :param playlist_name: 歌单名称
    :return: 歌单ID
    """
    try:
        # 创建Spotify客户端
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope='playlist-read-private'
        ))
        
        # 获取用户的所有歌单
        playlists = sp.current_user_playlists()
        
        # 查找匹配的歌单
        for playlist in playlists['items']:
            if playlist['name'].lower() == playlist_name.lower():
                return playlist['id']
        
        print(f"未找到名为 '{playlist_name}' 的歌单")
        return None
        
    except Exception as e:
        print(f"搜索歌单时出错: {str(e)}")
        return None

def get_playlist_tracks(playlist_id):
    """
    获取指定歌单的所有歌曲信息
    :param playlist_id: Spotify歌单ID
    :return: 包含歌曲信息的列表
    """
    try:
        # 创建Spotify客户端
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope='playlist-read-private'
        ))
        
        # 获取歌单信息
        results = sp.playlist_tracks(playlist_id)
        tracks = results['items']
        
        # 处理分页
        while results['next']:
            results = sp.next(results)
            tracks.extend(results['items'])
        
        # 提取歌曲信息
        track_info = []
        for track in tracks:
            if track['track']:
                track_info.append({
                    'name': track['track']['name'],
                    'artist': track['track']['artists'][0]['name'],
                    'album': track['track']['album']['name'],
                    'duration_ms': track['track']['duration_ms'],
                    'track_id': track['track']['id']
                })
        
        return track_info
    
    except spotipy.SpotifyException as e:
        print(f"Spotify API错误: {str(e)}")
        if e.http_status == 404:
            print("错误原因: 歌单不存在或无权访问")
        elif e.http_status == 400:
            print("错误原因: 无效的歌单ID")
        return None
    except Exception as e:
        print(f"获取歌单信息时出错: {str(e)}")
        return None

if __name__ == "__main__":
    # 获取名为"old songs"的歌单ID
    playlist_name = "old songs"
    playlist_id = get_playlist_by_name(playlist_name)
    
    if playlist_id:
        print(f"\n正在获取歌单 '{playlist_name}' 的歌曲信息...")
        tracks = get_playlist_tracks(playlist_id)
        
        if tracks:
            print(f"\n歌单中共有 {len(tracks)} 首歌曲:")
            for i, track in enumerate(tracks, 1):
                print(f"{i}. {track['name']} - {track['artist']} ({track['album']})") 