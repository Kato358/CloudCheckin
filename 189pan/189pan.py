import time
import re
import base64
import hashlib
import rsa
import requests
import os
import sys
from datetime import datetime, timedelta
from typing import Tuple, Optional

# 配置常量
BI_RM = list("0123456789abcdefghijklmnopqrstuvwxyz")
B64MAP = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

LOGIN_URL = "https://m.cloud.189.cn/udb/udb_login.jsp?pageId=1&clientType=wap"
LOGIN_SUBMIT_URL = "https://open.e.189.cn/api/logbox/oauth2/loginSubmit.do"
SIGN_URL_TEMPLATE = "https://api.cloud.189.cn/mkt/userSign.action?rand={}&clientType=TELEANDROID&version=8.6.3"
DRAW_URLS = [
    "https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action?taskId=TASK_SIGNIN",
    "https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action?taskId=TASK_SIGNIN_PHOTOS",
    "https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action?taskId=TASK_2022_FLDFS_KJ"
]

# 全局消息和会话
message = ""
session = requests.Session()
time = datetime.now() + timedelta(hours=8)
message = time.strftime("%Y/%m/%d %H:%M:%S") + " from TianYiCloud\n"

# 工具函数
def int2char(a: int) -> str:
    return BI_RM[a]

def b64tohex(a: str) -> str:
    d = ""
    e = 0
    c = 0
    for char in a:
        if char != "=":
            v = B64MAP.index(char)
            if e == 0:
                e = 1
                d += int2char(v >> 2)
                c = 3 & v
            elif e == 1:
                e = 2
                d += int2char(c << 2 | v >> 4)
                c = 15 & v
            elif e == 2:
                e = 3
                d += int2char(c)
                d += int2char(v >> 2)
                c = 3 & v
            else:
                e = 0
                d += int2char(c << 2 | v >> 4)
                d += int2char(15 & v)
    return d

def rsa_encode(j_rsakey: str, string: str) -> str:
    rsa_key = f"-----BEGIN PUBLIC KEY-----\n{j_rsakey}\n-----END PUBLIC KEY-----"
    pubkey = rsa.PublicKey.load_pkcs1_openssl_pem(rsa_key.encode())
    encrypted = rsa.encrypt(string.encode(), pubkey)
    return b64tohex(base64.b64encode(encrypted).decode())

# 业务函数
def extract_login_params(html: str) -> Tuple[str, str, str, str, str]:
    """获取登录参数"""
    try:
        captcha_token = re.search(r"captchaToken' value='(.+?)'", html).group(1)
        lt = re.search(r'lt = "(.+?)"', html).group(1)
        return_url = re.search(r"returnUrl= '(.+?)'", html).group(1)
        param_id = re.search(r'paramId = "(.+?)"', html).group(1)
        j_rsakey = re.search(r'j_rsaKey" value="(\S+)"', html).group(1)
        return captcha_token, lt, return_url, param_id, j_rsakey
    except Exception as e:
        raise ValueError(f"登录参数提取失败: {str(e)}")

def login(username: str, password: str) -> bool:
    """执行登录"""
    global message, session
    
    try:
        # 获取登录页面
        res = session.get(LOGIN_URL)
        redirect_url = re.search(r"https?://[^\s'\"]+", res.text).group()
        res = session.get(redirect_url)
        login_url = re.search(r'<a id="j-tab-login-link"[^>]*href="([^\"]+)"', res.text).group(1)
        res = session.get(login_url)
        
        # 提取并加密参数
        captcha_token, lt, return_url, param_id, j_rsakey = extract_login_params(res.text)
        session.headers.update({"lt": lt})
        
        # 构建登录数据
        login_data = {
            "appKey": "cloud",
            "accountType": "01",
            "userName": f"{{RSA}}{rsa_encode(j_rsakey, username)}",
            "password": f"{{RSA}}{rsa_encode(j_rsakey, password)}",
            "captchaToken": captcha_token,
            "returnUrl": return_url,
            "paramId": param_id
        }
        
        # 提交登录
        res = session.post(LOGIN_SUBMIT_URL, data=login_data)
        if res.json().get("result") != 0:
            message += "登录失败: 凭证错误\n"
            return False
            
        session.get(res.json()["toUrl"])
        message += f"用户 {username[:3]}*** 登录成功\n"
        return True
    except Exception as e:
        message += f"登录异常: {str(e)}\n"
        return False

def sign_in() -> Tuple[bool, str]:
    """执行签到"""
    global message, session
    
    try:
        url = SIGN_URL_TEMPLATE.format(str(round(time.time() * 1000)))
        res = session.get(url)
        data = res.json()
        
        if data.get("isSign", False):
            msg = f"今日已签到，获得{data.get('netdiskBonus', 0)}M空间"
        else:
            msg = f"签到成功，获得{data.get('netdiskBonus', 0)}M空间"
            
        message += msg + "\n"
        return True, msg
    except Exception as e:
        err_msg = f"签到失败: {str(e)}"
        message += err_msg + "\n"
        return False, err_msg

def draw_prize(url: str, round_num: int) -> Tuple[bool, str]:
    """执行抽奖"""
    global message, session
    
    try:
        res = session.get(url)
        data = res.json()
        
        if "prizeName" in data:
            msg = f"第{round_num}次抽奖: 获得{data['prizeName']}"
        else:
            msg = f"第{round_num}次抽奖: 失败({data.get('errorCode', '未知错误')})"
            
        message += msg + "\n"
        return True, msg
    except Exception as e:
        err_msg = f"第{round_num}次抽奖异常: {str(e)}"
        message += err_msg + "\n"
        return False, err_msg

# 主流程
if __name__ == "__main__":
    try:
        # 获取环境变量
        username = os.environ.get('TYYP_USERNAME', '').strip()
        password = os.environ.get('TYYP_PSW', '').strip()
        
        if not username or not password:
            raise ValueError("未设置TYYP_USERNAME或TYYP_PSW环境变量")
            
        # 执行登录
        if not login(username, password):
            raise ValueError("登录流程失败")
            
        # 执行签到
        sign_success, sign_msg = sign_in()
        
        # 执行抽奖
        for i, url in enumerate(DRAW_URLS, 1):
            time.sleep(1)  # 请求间隔
            draw_prize(url, i)
            
        # 显示最终结果
        print(message)
        
    except Exception as e:
        error_msg = f"执行失败: {str(e)}"
        message += error_msg
        print(message, file=sys.stderr)
        sys.exit(1)
