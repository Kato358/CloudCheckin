import time
import re
import base64
import rsa
import requests
import os
import sys
from datetime import datetime, timedelta
from typing import Tuple, List

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

# 全局消息
start_time = datetime.now() + timedelta(hours=8)
message = start_time.strftime("%Y/%m/%d %H:%M:%S") + " from TianYiCloud\n"

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

def login(session: requests.Session, username: str, password: str, account_id: str) -> bool:
    """执行登录"""
    global message
    
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
            message += f"[{account_id}] 登录失败: 凭证错误\n"
            return False
            
        session.get(res.json()["toUrl"])
        message += f"[{account_id}] 用户 {username[:3]}*** 登录成功\n"
        return True
    except Exception as e:
        message += f"[{account_id}] 登录异常: {str(e)}\n"
        return False

def sign_in(session: requests.Session, account_id: str) -> bool:
    """执行签到"""
    global message
    
    try:
        url = SIGN_URL_TEMPLATE.format(str(round(time.time() * 1000)))
        res = session.get(url)
        data = res.json()
        
        if data.get("isSign", False):
            msg = f"今日已签到，获得{data.get('netdiskBonus', 0)}M空间"
        else:
            msg = f"签到成功，获得{data.get('netdiskBonus', 0)}M空间"
            
        message += f"[{account_id}] {msg}\n"
        return True
    except Exception as e:
        err_msg = f"[{account_id}] 签到失败: {str(e)}"
        message += err_msg + "\n"
        return False

def draw_prize(session: requests.Session, url: str, round_num: int, account_id: str) -> bool:
    """执行抽奖"""
    global message
    
    try:
        res = session.get(url)
        data = res.json()
        
        if "prizeName" in data:
            msg = f"第{round_num}次抽奖: 获得{data['prizeName']}"
        else:
            msg = f"第{round_num}次抽奖: 失败({data.get('errorCode', '未知错误')})"
            
        message += f"[{account_id}] {msg}\n"
        return True
    except Exception as e:
        err_msg = f"[{account_id}] 第{round_num}次抽奖异常: {str(e)}"
        message += err_msg + "\n"
        return False

def process_account(username: str, password: str, account_id: str):
    """处理单个账户的签到流程"""
    session = requests.Session()
    
    # 执行登录
    if not login(session, username, password, account_id):
        return False
    
    # 执行签到
    sign_in(session, account_id)
    
    # 执行抽奖
    for i, url in enumerate(DRAW_URLS, 1):
        time.sleep(1)  # 请求间隔
        draw_prize(session, url, i, account_id)
    
    return True

# 主流程
if __name__ == "__main__":
    try:
        # 获取环境变量
        usernames = os.environ.get('TYYP_USERNAME', '').strip().split('&')
        passwords = os.environ.get('TYYP_PSW', '').strip().split('&')
        
        if not usernames or not passwords:
            raise ValueError("未设置TYYP_USERNAME或TYYP_PSW环境变量")
        
        if len(usernames) != len(passwords):
            raise ValueError("用户名和密码数量不匹配")
        
        # 处理每个账户
        for i, (username, password) in enumerate(zip(usernames, passwords)):
            account_id = f"账户{i+1}"
            message += f"\n===== 开始处理 {account_id} =====\n"
            process_account(username, password, account_id)
        
        # 添加执行统计
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        message += f"\n===== 执行统计 =====\n"
        message += f"处理账户数: {len(usernames)}\n"
        message += f"开始时间: {start_time.strftime('%Y/%m/%d %H:%M:%S')}\n"
        message += f"结束时间: {end_time.strftime('%Y/%m/%d %H:%M:%S')}\n"
        message += f"总耗时: {duration:.2f}秒\n"
        
        # 输出最终结果
        print(message)
        
    except Exception as e:
        error_msg = f"执行失败: {str(e)}"
        message += error_msg
        print(message, file=sys.stderr)
        sys.exit(1)
