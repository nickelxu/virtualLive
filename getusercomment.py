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
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import random
import re

# 配置Chrome浏览器选项
chrome_options = Options()
chrome_options.add_argument("--headless")  # 启用无头模式，不显示浏览器界面
chrome_options.add_argument("--disable-gpu")  # 禁用GPU加速
chrome_options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")  # 设置用户代理

# 初始化Chrome浏览器
driver = webdriver.Chrome(options=chrome_options)

# 设置要访问的直播间URL
url = "https://live.douyin.com/80017709309"
driver.get(url)


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
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
    )

    # 查找并切换到直播间iframe（如果存在）
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    if iframes:
        driver.switch_to.frame(iframes[0])

    # 等待评论区加载完成
    comment_area = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='webcast-chatroom___list']"))
    )

    # 用于存储已处理过的评论，避免重复处理
    seen_comments = set()  

    # 持续监控评论区
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
                        interaction = parse_gift(comment)
                    else:
                        interaction = parse_comment(comment)

                    # 输出解析结果
                    print(interaction)
        except Exception as e:
            print(f"获取评论时出错，跳过本次循环: {e}")

        # 随机延迟，避免请求过于频繁
        time.sleep(random.uniform(0.5, 1.5))

except TimeoutException:
    print("加载超时")

finally:
    # 确保浏览器正常关闭
    driver.quit()
