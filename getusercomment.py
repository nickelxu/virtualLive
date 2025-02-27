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

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
import time
import random
import re

# 配置Chrome浏览器选项
chrome_options = Options()
chrome_options.add_argument("--headless")  # 启用无头模式，不显示浏览器界面
chrome_options.add_argument("--disable-gpu")  # 禁用GPU加速
chrome_options.add_argument("--no-sandbox")  # 禁用沙箱模式
chrome_options.add_argument("--disable-dev-shm-usage")  # 禁用/dev/shm使用
chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # 禁用自动化控制检测
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
    # 初始化Chrome浏览器，使用webdriver_manager自动管理ChromeDriver版本
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # 设置页面加载超时时间
    driver.set_page_load_timeout(60)
    
    # 设置要访问的直播间URL
    url = "https://live.douyin.com/373297491977"
    print(f"正在访问直播间: {url}")
    driver.get(url)
    
    # 执行JavaScript来绕过反爬虫检测
    print("执行JavaScript绕过反爬虫检测...")
    driver.execute_script("""
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
    
    
    try:
        # 等待页面加载完成
        print("等待页面加载完成...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        
        print("页面已加载，正在查找评论区...")
        
        # 打印页面标题，用于调试
        print(f"页面标题: {driver.title}")
        
        # 检查是否被重定向到反爬虫页面
        if "Eden" in driver.title:
            print("警告: 可能被抖音反爬虫机制检测，页面被重定向")
            print("尝试等待更长时间...")
            time.sleep(10)  # 给页面更多时间加载
        
        # 查找并切换到直播间iframe（如果存在）
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        if iframes:
            print(f"找到 {len(iframes)} 个iframe，尝试切换...")
            driver.switch_to.frame(iframes[0])
            print("已切换到iframe")
            
            # 打印iframe内的页面源码片段，用于调试
            print("iframe内容片段:")
            try:
                print(driver.page_source[:200] + "...")
            except:
                print("无法获取iframe内容")
        else:
            print("未找到iframe")
        
        # 等待评论区加载完成
        print("等待评论区加载...")
        comment_area = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='webcast-chatroom___list']"))
        )
        
        print("评论区已加载")
        
        # 用于存储已处理过的评论，避免重复处理
        seen_comments = set()  
        
        # 持续监控评论区
        print("开始监控评论区...")
        while True:
            try:
                # 使用JavaScript获取所有评论元素的文本内容
                comments = driver.execute_script("""
                    return Array.from(document.querySelectorAll('[class*="webcast-chatroom___item"]')).map(el => el.textContent);
                """)
                
                # 处理每条评论
                for comment in comments:
                    if comment not in seen_comments:  # 检查是否已经处理过
                        seen_comments.add(comment)  # 添加到已处理集合中
                        
                        # 根据内容判断是礼物还是评论
                        if "送出了" in comment:
                            interaction_type, username, content = parse_gift(comment)
                        else:
                            interaction_type, username, content = parse_comment(comment)
                        
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
            print(driver.page_source[:500] + "...")
        except:
            print("无法获取页面源码")

except WebDriverException as e:
    print(f"WebDriver错误: {e}")
except Exception as e:
    print(f"发生未知错误: {e}")

finally:
    # 确保浏览器正常关闭
    try:
        print("正在关闭浏览器...")
        driver.quit()
        print("浏览器已关闭")
    except:
        print("关闭浏览器时出错")
