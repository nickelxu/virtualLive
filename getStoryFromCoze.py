"""
Coze平台故事获取模块

这个模块的目的是从Coze平台的工作流中获取生成的故事，并以文本形式保存在本地，以备后续语音转化使用。
主要功能包括：
1. 在项目根目录创建一个story文件夹用于存放所有故事
2. 从Coze工作流中获取单个完整故事
3. 将获取的故事保存到story文件夹中，使用故事标题作为文件名

作者：nickelxu
"""


import os
from datetime import datetime
import re
import time
from dotenv import load_dotenv
# Coze官方Python SDK
from cozepy import COZE_CN_BASE_URL

# 加载环境变量
load_dotenv()

# 通过个人访问令牌获取access_token
coze_api_token = os.getenv('COZE_TOKEN')
# 默认访问api.coze.com，如果需要访问api.coze.cn，请使用base_url配置API端点
coze_api_base = COZE_CN_BASE_URL

from cozepy import Coze, TokenAuth, Stream, WorkflowEvent, WorkflowEventType  # noqa

# 通过access_token初始化Coze客户端
coze = Coze(auth=TokenAuth(token=coze_api_token), base_url=coze_api_base)

# 在Coze中创建工作流实例，从网页链接中复制最后的数字作为工作流ID
workflow_id = '7453394870359818278'

def create_story_folder():
    """
    创建story文件夹
    
    在项目根目录下创建story文件夹（如果不存在）。
    
    Returns:
        str: 创建的文件夹路径
    """
    folder_path = os.path.join(os.getcwd(), "story")
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    return folder_path

def sanitize_filename(title):
    """
    清理文件名中的非法字符
    
    移除Windows和其他操作系统中不允许用于文件名的特殊字符。
    
    Args:
        title (str): 原始标题字符串
        
    Returns:
        str: 清理后的安全文件名
    """
    return re.sub(r'[<>:"/\\|?*]', '', title)

def save_story(message_content, story_number, folder_path):
    """
    保存故事内容到文本文件
    
    将从Coze获取的故事内容保存为文本文件，文件名使用故事标题
    
    Args:
        message_content (str): 故事内容
        story_number (int): 故事编号（已不再使用）
        folder_path (str): 保存文件的文件夹路径
    """
    # 从消息内容中提取故事标题 (假设标题在第一行)
    title = message_content.split('\n')[0]  # 不再限制标题长度
    safe_title = sanitize_filename(title)
    
    # 构建文件名：标题.txt
    filename = f"{safe_title}.txt"
    file_path = os.path.join(folder_path, filename)
    
    # 保存内容到文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(message_content)
    
    print(f"故事已保存: {filename}")
    return file_path

def handle_workflow_iterator(stream: Stream[WorkflowEvent]):
    """
    处理工作流迭代器，获取并保存故事内容
    
    迭代处理从Coze工作流返回的事件，提取消息内容并保存为故事文件。
    
    Args:
        stream (Stream[WorkflowEvent]): Coze工作流事件流
    """
    print("开始获取故事内容...")
    folder_path = create_story_folder()
    current_story = ""
    
    try:
        for event in stream:
            if event.event == WorkflowEventType.MESSAGE:
                # 累积消息内容
                if event.message and event.message.content:
                    current_story += event.message.content
                    
                    # 只有当node_is_finish为True时才保存文件
                    if event.message.node_is_finish:
                        # 提取标题并保存文件
                        title = current_story.split('\n')[0]
                        safe_title = sanitize_filename(title)
                        filename = f"{safe_title}.txt"
                        file_path = os.path.join(folder_path, filename)
                        
                        # 如果文件已存在，添加一个随机后缀以避免冲突
                        if os.path.exists(file_path):
                            import random
                            random_suffix = random.randint(1, 999)
                            safe_title = f"{safe_title}_{random_suffix}"
                            filename = f"{safe_title}.txt"
                            file_path = os.path.join(folder_path, filename)
                        
                        # 保存故事
                        save_story(current_story, 0, folder_path)
                        
                        # 重置当前故事内容
                        current_story = ""
                        
            elif event.event == WorkflowEventType.ERROR:
                print(f"获取故事时发生错误: {event.error}")
            elif event.event == WorkflowEventType.INTERRUPT:
                print("故事获取被中断，尝试恢复...")
                handle_workflow_iterator(
                    coze.workflows.runs.resume(
                        workflow_id=workflow_id,
                        event_id=event.interrupt.interrupt_data.event_id,
                        resume_data="hey",
                        interrupt_type=event.interrupt.interrupt_data.type,
                    )
                )
    except Exception as e:
        print(f"处理故事时发生异常: {str(e)}")
        raise

def get_story():
    """
    获取故事的主函数
    
    从Coze工作流获取新故事并保存到story文件夹中。
    
    Returns:
        None
    """
    print(f"\n开始获取故事 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    folder_path = create_story_folder()
    
    try:
        handle_workflow_iterator(coze.workflows.runs.stream(workflow_id=workflow_id))
        print("故事获取和保存操作完成")
    except Exception as e:
        print(f"获取故事时发生错误: {str(e)}")
        import traceback
        print(f"详细错误信息: {traceback.format_exc()}")

def main():
    """
    主函数，获取一个故事
    
    获取一个故事并保存到story文件夹中，无需定时功能。
    
    Returns:
        None
    """
    print("程序启动，开始获取故事...")
    get_story()
    print("故事获取完成")

if __name__ == "__main__":
    main()