"""
千问大模型回复生成模块

这个模块的目的是使用千问大模型对直播间用户评论生成回复，并将回复存储在全局变量中，以便整个项目可以调用。
主要功能包括：
1. 调用千问大模型API获取对用户评论的回复
2. 将获取的回复存储在全局变量中，供其他模块访问
3. 提供接口函数获取最新回复和历史回复

作者：nickelxu
"""

import os
from datetime import datetime
import re
import time
from dotenv import load_dotenv
from openai import OpenAI
from typing import Dict, List, Tuple

# 加载环境变量
load_dotenv()

# 初始化OpenAI客户端（用于调用千问API）
client = OpenAI(
    api_key=os.getenv('DASHSCOPE_API_KEY'),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

# 全局变量，用于存储所有回复
# 格式: [(timestamp, comment, response), ...]
RESPONSES_HISTORY: List[Tuple[datetime, str, str]] = []

# 最新回复
LATEST_RESPONSE: Dict[str, str] = {
    "comment": "",
    "response": "",
    "timestamp": ""
}

def get_response_from_qianwen(comment, system_prompt=None):
    """
    从千问大模型获取对用户评论的回复
    
    调用千问API获取对用户评论的回复。
    
    Args:
        comment (str): 用户评论
        system_prompt (str, optional): 系统提示词，用于指导模型回复的风格和内容
        
    Returns:
        str: 模型生成的回复
    """
    if system_prompt is None:
        system_prompt = "你是一个友好、幽默的直播助手，负责回答直播间观众的问题和评论。回复要简洁、有趣，不超过50个字。"
    
    try:
        # 调用千问API
        completion = client.chat.completions.create(
            model="qwen-plus",  # 可按需更换模型名称
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': comment}
            ],
            stream=False
        )
        
        # 获取回复内容
        response = completion.choices[0].message.content
        return response
    
    except Exception as e:
        print(f"调用千问API时发生错误: {str(e)}")
        return f"抱歉，我暂时无法回答这个问题。错误信息: {str(e)}"

def store_response(comment, response):
    """
    存储回复到全局变量
    
    将用户评论和模型回复存储到全局变量中，以便其他模块访问。
    
    Args:
        comment (str): 用户评论
        response (str): 模型回复内容
    """
    # 获取当前时间
    current_time = datetime.now()
    timestamp = current_time.strftime('%Y-%m-%d %H:%M:%S')
    
    # 更新最新回复
    global LATEST_RESPONSE
    LATEST_RESPONSE = {
        "comment": comment,
        "response": response,
        "timestamp": timestamp
    }
    
    # 添加到历史记录
    global RESPONSES_HISTORY
    RESPONSES_HISTORY.append((current_time, comment, response))
    
    print(f"回复已存储 - 时间: {timestamp}")

def process_live_comment(comment, system_prompt=None):
    """
    处理直播评论并获取回复
    
    处理用户在直播间的评论，调用千问模型获取回复，并存储回复内容。
    
    Args:
        comment (str): 用户评论
        system_prompt (str, optional): 系统提示词
        
    Returns:
        str: 模型生成的回复
    """
    print(f"\n收到用户评论: {comment}")
    
    try:
        # 获取千问模型的回复
        response = get_response_from_qianwen(comment, system_prompt)
        
        # 存储回复
        store_response(comment, response)
        
        print("回复生成和存储操作完成")
        return response
    
    except Exception as e:
        print(f"处理评论时发生错误: {str(e)}")
        import traceback
        print(f"详细错误信息: {traceback.format_exc()}")
        return f"处理评论时发生错误: {str(e)}"

def get_latest_response():
    """
    获取最新回复
    
    返回最新的用户评论和模型回复。
    
    Returns:
        Dict[str, str]: 包含评论、回复和时间戳的字典
    """
    return LATEST_RESPONSE

def get_response_history(limit=None):
    """
    获取回复历史记录
    
    返回所有历史回复记录，可以限制返回数量。
    
    Args:
        limit (int, optional): 限制返回的记录数量，默认返回所有记录
        
    Returns:
        List[Tuple[datetime, str, str]]: 包含时间戳、评论和回复的元组列表
    """
    if limit is None:
        return RESPONSES_HISTORY
    else:
        return RESPONSES_HISTORY[-limit:]

def clear_response_history():
    """
    清除回复历史记录
    
    清空全局变量中存储的所有回复记录。
    
    Returns:
        None
    """
    global RESPONSES_HISTORY
    RESPONSES_HISTORY = []
    print("回复历史记录已清空")

def main():
    """
    主函数，用于测试
    
    处理示例评论并获取回复，测试全局变量存储功能。
    
    Returns:
        None
    """
    print("程序启动，开始测试千问模型回复...")
    
    # 示例评论
    test_comments = [
        "主播今天看起来好漂亮啊！",
        "这个游戏怎么玩的？我是新手",
        "你能给我讲个笑话吗？"
    ]
    
    # 测试每条评论
    for comment in test_comments:
        response = process_live_comment(comment)
        print(f"千问回复: {response}\n")
    
    # 测试获取最新回复
    latest = get_latest_response()
    print(f"最新回复: {latest['response']}")
    
    # 测试获取历史记录
    history = get_response_history()
    print(f"历史记录数量: {len(history)}")
    
    print("测试完成")

if __name__ == "__main__":
    main() 