from curl_cffi import requests
import re
import os
from datetime import datetime, timedelta
import sys
from telegram.notify import send_tg_notification

cookie = os.environ.get('V2EX_COOKIE').strip()
# 初始化消息时间
time = datetime.now() + timedelta(hours=8)
message = f"⏰ {time.strftime('%Y/%m/%d %H:%M:%S')} V2EX 签到通知\n\n"
headers = {
    "Referer": "https://www.v2ex.com/mission/daily",
    "Host": "www.v2ex.com",
    "user-agent": "Mozilla/5.0 (Linux; Android 10; Redmi K30) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.83 Mobile Safari/537.36",
    "cookie": f"'{cookie}'"
}

def get_once() -> tuple[str, bool]:
    """获取 once 值和签到状态
    
    Returns:
        tuple: once 值和是否已签到
    """
    global message
    url = "https://www.v2ex.com/mission/daily"
    res = requests.get(url, headers=headers)
    content = res.text
    
    reg1 = r"需要先登录"
    if re.search(reg1, content):
        message += "❌ Cookie 已过期，请更新！"
        return None, False
    else:
        reg = r"每日登录奖励已领取"
        if re.search(reg, content):
            return None, True
        else:
            reg = r"redeem\?once=(.*?)'"
            once_match = re.search(reg, content)
            if once_match:
                once = once_match.group(1)
                return once, False
            else:
                message += "❌ 未签到但获取 once 值失败"
                return None, False

def check_in(once: str) -> bool:
    """执行签到并返回是否成功
    
    Args:
        once: once 值
        
    Returns:
        bool: 是否签到成功
    """
    global message
    url = f"https://www.v2ex.com/mission/daily/redeem?once={once}"
    res = requests.get(url, headers=headers)
    content = res.text
    
    reg = r"已成功领取每日登录奖励"
    if re.search(reg, content):
        return True
    else:
        message += "❌ 签到失败"
        return False

def get_balance() -> tuple[str, str]:
    """查询余额信息
    
    Returns:
        tuple: 签到时间和余额
    """
    url = "https://www.v2ex.com/balance"
    res = requests.get(url, headers=headers)
    content = res.text
    pattern = r'每日登录奖励.*?<small class="gray">(.*?)</small>.*?<td class="d" style="text-align: right;">.*?</td>.*?<td class="d" style="text-align: right;">(.*?)</td>'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        time = match.group(1).strip()
        balance = match.group(2).strip()
        return time, balance
    else:
        return None, None

def format_message(status: str, balance_info: tuple = None):
    """格式化通知消息
    
    Args:
        status: 签到状态描述
        balance_info: 余额信息元组 (时间, 余额)
    """
    global message
    message = f"🏷️ V2EX 自动签到通知\n"
    message += f"⏰ 时间: {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}\n"
    message += f"📌 状态: {status}\n"
    
    if balance_info and balance_info[0] and balance_info[1]:
        message += f"🕒 上次签到: {balance_info[0]}\n"
        message += f"💰 当前余额: {balance_info[1]}\n"
    
    message += "\n" + "-"*30 + "\n"
    message += "🔔 此通知由自动签到系统生成"

if __name__ == "__main__":
    try:
        if not cookie:
            raise ValueError("❌ 环境变量 V2EX_COOKIE 未设置")
        
        # 获取 once 值和签到状态
        once, signed = get_once()
        balance_info = get_balance()  # 总是尝试获取余额信息

        # 处理不同签到状态
        if signed:
            status = "✅ 今日已签到"
            format_message(status, balance_info)
        elif once:
            if check_in(once):
                # 重新获取最新的余额信息
                balance_info = get_balance()
                status = "🎉 签到成功！"
                format_message(status, balance_info)
            else:
                format_message("❌ 签到失败", balance_info)
        else:
            format_message("❌ 未签到且无法获取 once 值", balance_info)
        
        # 发送通知
        send_tg_notification(message)
        
    except Exception as err:
        error_msg = f"🚨 发生意外错误:\n{str(err)}"
        send_tg_notification(error_msg)
        print(err, flush=True)
        sys.exit(1)
