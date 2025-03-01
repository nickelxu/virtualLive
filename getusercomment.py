"""
抖音直播评论和礼物抓取模块

此模块用于从抖音直播页面抓取实时评论和礼物信息。
使用Selenium模拟浏览器访问直播页面，解析并提取评论和礼物信息。

主要功能：
1. 自动访问指定的抖音直播页面
2. 实时抓取观众发送的评论
3. 实时抓取观众赠送的礼物
4. 解析并格式化评论和礼物信息

作者: nickelxu
"""

import asyncio
import os
import threading
import time
import random
import re
import sys
import subprocess
from contextlib import contextmanager
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# 全局变量，用于控制评论监控线程
_monitoring_thread = None
_stop_monitoring = False
_driver = None

# 全局变量，用于存储所有互动记录
_all_interactions = []
_interaction_keys = set()  # 用于快速检查重复

@contextmanager
def suppress_stderr():
    """
    上下文管理器，用于临时抑制标准错误输出
    
    在执行可能产生大量无关警告的代码时使用，
    例如WebGL相关警告或Selenium的调试信息
    
    用法:
        with suppress_stderr():
            # 可能产生大量stderr输出的代码
    """
    # 保存当前的标准错误
    original_stderr = sys.stderr
    
    try:
        # 如果是Windows系统
        if sys.platform.startswith('win'):
            # 将标准错误重定向到NUL设备
            with open('NUL', 'w') as devnull:
                sys.stderr = devnull
                yield
        else:
            # 对于Unix/Linux/Mac系统，重定向到/dev/null
            with open('/dev/null', 'w') as devnull:
                sys.stderr = devnull
                yield
    finally:
        # 恢复原始的标准错误
        sys.stderr = original_stderr

def parse_comment(comment):
    """
    解析评论文本，提取用户名和评论内容
    
    从评论文本中分离出用户名和评论内容，格式通常为"用户名:评论内容"。
    如果无法分离，则将整个文本作为评论内容返回。
    
    Args:
        comment (str): 原始评论文本
        
    Returns:
        tuple: 包含类型("评论")、用户名和评论内容的元组
    """
    match = re.match(r'^(.*?)[:：](.*)', comment)
    if match:
        return "评论", match.group(1).strip(), match.group(2).strip()
    else:
        return "评论", "", comment.strip()


def parse_gift(gift):
    """
    解析礼物文本，提取赠送者和礼物信息
    
    从礼物文本中分离出赠送者和礼物信息，格式通常为"用户名送出了礼物名称"。
    如果无法分离，则将整个文本作为礼物信息返回。
    
    Args:
        gift (str): 原始礼物文本
        
    Returns:
        tuple: 包含类型("礼物")、赠送者和礼物信息的元组
    """
    match = re.match(r'^(.*?)送出了(.*)', gift)
    if match:
        return "礼物", match.group(1).strip(), f"送出了{match.group(2).strip()}"
    else:
        return "礼物", "", gift.strip()

def add_interaction(interaction_type, username, content, timestamp=None, callback_function=None):
    """
    将互动添加到全局数据结构中，避免重复
    
    Args:
        interaction_type (str): 互动类型，如"评论"或"礼物"
        username (str): 用户名
        content (str): 互动内容
        timestamp (float, optional): 时间戳，默认为当前时间
        callback_function (function, optional): 处理互动的回调函数
        
    Returns:
        bool: 是否成功添加（True表示新增，False表示重复）
    """
    global _all_interactions, _interaction_keys
    
    # 生成唯一键
    interaction_key = f"{username}:{content}"
    
    # 检查是否已存在
    if interaction_key in _interaction_keys:
        return False
    
    # 添加到集合中，用于快速查重
    _interaction_keys.add(interaction_key)
    
    # 创建互动记录
    interaction = {
        "type": interaction_type,
        "username": username,
        "content": content,
        "timestamp": timestamp or time.time()
    }
    
    # 添加到列表中
    _all_interactions.append(interaction)
    
    # 如果提供了回调函数，立即调用
    if callback_function:
        callback_function(username, content, interaction_type)
    
    return True

def get_all_interactions():
    """
    获取所有互动记录
    
    Returns:
        list: 包含所有互动记录的列表
    """
    global _all_interactions
    return _all_interactions

def clear_interactions():
    """
    清空互动记录
    """
    global _all_interactions, _interaction_keys
    _all_interactions = []
    _interaction_keys = set()

def _monitor_comments(live_url, callback_function):
    """
    监控直播评论的内部函数
    
    持续监控直播间评论，并通过回调函数处理新评论
    
    Args:
        live_url (str): 直播间URL
        callback_function (function): 处理评论的回调函数，接收用户名、评论内容和评论类型参数
    """
    global _driver, _stop_monitoring
    
    # 配置Chrome浏览器选项
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 启用无头模式，不显示浏览器界面
    chrome_options.add_argument("--disable-gpu")  # 禁用GPU加速
    chrome_options.add_argument("--no-sandbox")  # 禁用沙箱模式
    chrome_options.add_argument("--disable-dev-shm-usage")  # 禁用/dev/shm使用
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # 禁用自动化控制检测
    chrome_options.add_argument("--enable-unsafe-swiftshader")  # 启用SwiftShader软件渲染，解决WebGL警告
    chrome_options.add_argument("--disable-software-rasterizer")  # 禁用软件光栅化器
    chrome_options.add_argument("--log-level=3")  # 设置日志级别为3(ERROR)，减少日志输出
    chrome_options.add_argument("--disable-logging")  # 禁用Chrome的日志记录
    chrome_options.add_argument("--silent")  # 静默模式
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])  # 禁用DevTools日志
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36")  # 设置用户代理为最新版本

    # 添加更多反检测选项
    chrome_options.add_argument("--disable-extensions")  # 禁用扩展
    chrome_options.add_argument("--disable-infobars")  # 禁用信息栏
    chrome_options.add_argument("--window-size=1920,1080")  # 设置窗口大小
    chrome_options.add_argument("--start-maximized")  # 最大化窗口
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])  # 排除自动化开关
    chrome_options.add_experimental_option("useAutomationExtension", False)  # 不使用自动化扩展

    print("正在初始化Chrome浏览器...")

    try:
        # 初始化Chrome浏览器，使用Chrome自带的驱动机制
        print("尝试使用Chrome浏览器内置驱动启动...")
        _driver = webdriver.Chrome(options=chrome_options)
        
        # 如果上面的方法失败，再尝试其他方式
        if not _driver:
            # 尝试显式指定一个驱动程序的路径
            driver_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chromedriver.exe")
            print(f"尝试使用本地驱动: {driver_path}")
            if os.path.exists(driver_path):
                service = Service(driver_path)
                _driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                print("本地驱动不存在，请下载适合您Chrome版本的驱动并放置在项目目录")
                print("您可以从 https://googlechromelabs.github.io/chrome-for-testing/ 下载驱动")
                raise FileNotFoundError("ChromeDriver不存在")
        
        print(f"浏览器初始化状态: {'成功' if _driver else '失败'}")
        
        # 设置页面加载超时时间
        _driver.set_page_load_timeout(60)
        
        # 设置要访问的直播间URL
        print(f"正在访问直播间: {live_url}")
        _driver.get(live_url)
        
        # 执行JavaScript来绕过反爬虫检测
        print("执行JavaScript绕过反爬虫检测...")
        _driver.execute_script("""
        // 覆盖WebDriver属性
        Object.defineProperty(navigator, 'webdriver', {
            get: () => false,
        });
        
        // 覆盖navigator属性
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        
        // 添加假的插件
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
        
        // 添加假的语言
        Object.defineProperty(navigator, 'languages', {
            get: () => ['zh-CN', 'zh', 'en'],
        });
        """)
        
        try:
            # 等待页面加载完成
            print("等待页面加载完成...")
            WebDriverWait(_driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )
            
            print("页面已加载，正在查找评论区...")
            
            # 打印页面标题，用于调试
            print(f"页面标题: {_driver.title}")
            
            # 检查是否被重定向到反爬虫页面
            if "Eden" in _driver.title:
                print("警告: 可能被抖音反爬虫机制检测，页面被重定向")
                print("尝试等待更长时间...")
                time.sleep(10)  # 给页面更多时间加载
            
            # 查找并切换到直播间iframe（如果存在）
            iframes = _driver.find_elements(By.TAG_NAME, "iframe")
            if iframes:
                print(f"找到 {len(iframes)} 个iframe，尝试切换...")
                _driver.switch_to.frame(iframes[0])
                print("已切换到iframe")
                
                # 打印iframe内的页面源码片段，用于调试
                print("iframe内容片段:")
                try:
                    print(_driver.page_source[:200] + "...")
                except:
                    print("无法获取iframe内容")
            else:
                print("未找到iframe")
            
            # 等待评论区加载完成
            print("等待评论区加载...")
            comment_area = WebDriverWait(_driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='webcast-chatroom___list']"))
            )
            
            print("评论区已加载")
            
            # 用于存储已处理过的评论，避免重复处理
            seen_comments = set()
            
            # 持续监控评论区
            print("开始监控评论区...")
            while not _stop_monitoring:
                try:
                    # 检查驱动状态
                    if _driver is None:
                        print("错误: 浏览器驱动为None，尝试重新初始化...")
                        break
                        
                    # 使用JavaScript获取所有评论元素的文本内容
                    with suppress_stderr():
                        comments = _driver.execute_script("""
                            return Array.from(document.querySelectorAll('[class*="webcast-chatroom___item"]')).map(el => el.textContent);
                        """)
                    
                    # 处理每条评论
                    for comment in comments:
                        if comment not in seen_comments:  # 检查是否已经处理过
                            seen_comments.add(comment)  # 添加到已处理集合中
                            
                            # 检查是否是合并的多条评论（通常很长且包含多个冒号）
                            if len(comment) > 100 and comment.count('：') > 2:
                                # 这可能是合并的多条评论，跳过处理
                                # 因为这些评论会在后续单独出现
                                continue
                            
                            # 根据内容判断是礼物还是评论
                            if "送出了" in comment:
                                interaction_type, username, content = parse_gift(comment)
                            else:
                                interaction_type, username, content = parse_comment(comment)
                            
                            # 如果用户名和内容都不为空，则添加到互动记录中
                            if username and content:
                                # 尝试添加到互动记录中，如果成功（不是重复的）则处理
                                # 直接将回调函数传递给add_interaction，实现实时响应
                                if add_interaction(interaction_type, username, content, callback_function=callback_function):
                                    # 格式化输出解析结果
                                    if interaction_type == "评论":
                                        print(f"[评论] {username}: {content}")
                                    else:
                                        print(f"[礼物] {username} {content}")
                except Exception as e:
                    print(f"获取评论时出错，跳过本次循环: {e}")
                
                # 随机延迟，避免请求过于频繁
                time.sleep(random.uniform(0.5, 1.5))
        
        except TimeoutException:
            print("加载超时，可能原因:")
            print("1. 网络连接问题")
            print("2. 直播间可能已关闭或不存在")
            print("3. 抖音网站结构可能已更改")
            print("4. 可能被抖音反爬虫机制检测")
            
            # 尝试获取当前页面源码的一部分，用于调试
            try:
                print("\n页面源码片段:")
                print(_driver.page_source[:500] + "...")
            except:
                print("无法获取页面源码")

    except WebDriverException as e:
        print(f"WebDriver错误: {e}")
    except Exception as e:
        print(f"发生未知错误: {e}")

    finally:
        # 确保浏览器正常关闭
        try:
            if _driver:
                print("正在关闭浏览器...")
                _driver.quit()
                print("浏览器已关闭")
                _driver = None
        except:
            print("关闭浏览器时出错")

def start_comment_monitoring(live_url, callback_function):
    """
    启动评论监控线程
    
    创建并启动一个新线程来监控直播评论
    
    Args:
        live_url (str): 直播间URL
        callback_function (function): 处理评论的回调函数
        
    Returns:
        bool: 是否成功启动监控
    """
    global _monitoring_thread, _stop_monitoring, _driver
    
    # 确保驱动为None，以便在新线程中重新初始化
    if _driver is not None:
        try:
            _driver.quit()
        except:
            pass
        _driver = None
        print("已重置浏览器驱动，准备在新线程中重新初始化")
    
    # 如果已经有监控线程在运行，先停止它
    if _monitoring_thread and _monitoring_thread.is_alive():
        stop_comment_monitoring()
    
    # 重置停止标志
    _stop_monitoring = False
    
    # 创建并启动新的监控线程
    _monitoring_thread = threading.Thread(
        target=_monitor_comments,
        args=(live_url, callback_function),
        daemon=True  # 设置为守护线程，主线程结束时自动结束
    )
    _monitoring_thread.start()
    
    print(f"已启动评论监控线程，监控直播间: {live_url}")
    return True

def stop_comment_monitoring():
    """
    停止评论监控线程
    
    设置停止标志并等待监控线程结束
    
    Returns:
        bool: 是否成功停止监控
    """
    global _monitoring_thread, _stop_monitoring, _driver
    
    if not _monitoring_thread or not _monitoring_thread.is_alive():
        print("没有正在运行的评论监控线程")
        return False
    
    print("正在停止评论监控...")
    _stop_monitoring = True
    
    # 等待线程结束，最多等待5秒
    _monitoring_thread.join(timeout=5)
    
    # 确保浏览器已关闭
    if _driver:
        try:
            _driver.quit()
            _driver = None
        except:
            pass
    
    print("评论监控已停止")
    return True

def main():
    """
    主函数，用于测试模块功能
    
    启动评论监控并打印收到的评论
    必须通过命令行参数指定直播间URL
    """
    def test_callback(username, comment, comment_type):
        print(f"收到{comment_type}: {username} - {comment}")
    
    # 检查是否提供了命令行参数
    if len(sys.argv) > 1:
        live_url = sys.argv[1]
        print(f"使用直播间URL: {live_url}")
        
        # 启动评论监控
        start_comment_monitoring(live_url, test_callback)
        
        try:
            # 运行60秒后停止
            print("监控将在60秒后自动停止...")
            time.sleep(60)
            
            # 打印收集到的所有互动
            interactions = get_all_interactions()
            print(f"\n共收集到 {len(interactions)} 条互动记录:")
            for idx, interaction in enumerate(interactions, 1):
                print(f"{idx}. [{interaction['type']}] {interaction['username']}: {interaction['content']}")
        finally:
            # 确保停止监控
            stop_comment_monitoring()
    else:
        print("错误: 未指定直播间URL")
        print("用法: python getusercomment.py https://live.douyin.com/您的直播间ID")
        sys.exit(1)

if __name__ == "__main__":
    main()
