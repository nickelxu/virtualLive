#! /usr/bin/env python
# coding=utf-8
"""
阿里云语音合成服务Token获取模块

此模块用于从阿里云获取语音合成服务的访问Token。
Token是调用阿里云语音合成服务的必要凭证，有一定的有效期。

作者: nickelxu
"""
import os
import time
import json
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from dotenv import load_dotenv

# 加载环境变量文件中的配置
load_dotenv()

def get_token():
    """
    获取阿里云语音合成服务的访问Token
    
    使用阿里云SDK从元数据服务获取语音合成服务的访问Token。
    需要在环境变量中设置ALIYUN_AK_ID和ALIYUN_AK_SECRET。
    
    Returns:
        str or None: 成功返回Token字符串，失败返回None
        
    Raises:
        Exception: 当API响应中没有找到Token时抛出异常
    """
    # 创建AcsClient实例，用于与阿里云API通信
    client = AcsClient(
        os.getenv('ALIYUN_AK_ID'),        # 阿里云AccessKey ID
        os.getenv('ALIYUN_AK_SECRET'),    # 阿里云AccessKey Secret
        "cn-shanghai"                      # 区域ID，固定为上海区域
    )

    # 创建请求并设置参数
    request = CommonRequest()
    request.set_method('POST')                             # 设置HTTP方法为POST
    request.set_domain('nls-meta.cn-shanghai.aliyuncs.com')  # 设置API域名
    request.set_version('2019-02-28')                      # 设置API版本
    request.set_action_name('CreateToken')                 # 设置API操作名称

    try:
        # 发送请求并获取响应
        response = client.do_action_with_exception(request)
        # 解析JSON响应
        jss = json.loads(response)
        # 检查响应中是否包含Token
        if 'Token' in jss and 'Id' in jss['Token']:
            return jss['Token']['Id']
        else:
            raise Exception("Token not found in response")
    except Exception as e:
        # 捕获并记录错误
        print(f"Error getting token: {str(e)}")
        return None

if __name__ == "__main__":
    # 当直接运行此脚本时，获取并打印Token
    token = get_token()
    print(f"Token: {token}")


