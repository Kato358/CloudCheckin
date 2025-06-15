from curl_cffi import requests
import re
import os
from datetime import datetime, timedelta
import sys
from telegram.notify import send_tg_notification

cookie = os.environ.get('V2EX_COOKIE').strip()
# 初始化消息时间
time = datetime.now() + timedelta(hours=8)
message = time.strftime("%Y/%m/%d %H:%M:%S") + " V2EX签到报告\n"
headers = {
    "Referer": "https://www.v2ex.com/mission/daily",
    "Host": "www.v2ex.com",
    "user-agent": "Mozilla/5.0 (Linux; Android 10; Redmi K30) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.83 Mobile Safari/537.36",
    "cookie": f"'{cookie}'"
}

def get_once() -> tuple[str, bool]:
    """获取once值并检查签到状态
    
    Returns:
        tuple: once值和签到状态(True表示已签到)
    """
    global message
    url = "https://www.v2ex.com/mission/daily"
    res = requests.get(url, headers=headers)
    content = res.text
    
    # 检查Cookie有效性
    if re.search(r"需要先登录", content):
        message += "❌ Cookie已失效\n"
        return None, False
    
    # 检查是否已签到
    if re.search(r"每日登录奖励已领取", content):
        message += "✅ 今日已签到\n"
        return None, True
    
    # 尝试获取once值
    once_match = re.search(r"redeem\?once=(.*?)'", content)
    if once_match:
        once = once_match.group(1)
        message += f"🔄 成功获取once值: {once}\n"
        return once, False
    
    message += "❌ 未签到但获取once值失败\n"
    return None, False

def check_in(once: str) -> bool:
    """执行签到操作
    
    Args:
        once: 签到所需的once值
        
    Returns:
        bool: 签到是否成功
    """
    global message
    url = f"https://www.v2ex.com/mission/daily/redeem?once={once}"
    res = requests.get(url, headers=headers)
    
    if re.search(r"已成功领取每日登录奖励", res.text):
        message += "🎉 签到成功\n"
        return True
    
    message += "❌ 签到失败\n"
    return False

def get_balance() -> tuple[str, str]:
    """查询账户余额
    
    Returns:
        tuple: (签到时间, 余额)
    """
    url = "https://www.v2ex.com/balance"
    res = requests.get(url, headers=headers)
    pattern = r'每日登录奖励.*?<small class="gray">(.*?)</small>.*?<td class="d" style="text-align: right;">.*?</td>.*?<td class="d" style="text-align: right;">(.*?)</td>'
    match = re.search(pattern, res.text, re.DOTALL)
    
    return (match.group(1).strip(), match.group(2).strip()) if match else (None, None)

if __name__ == "__main__":
    try:
        # 验证Cookie是否设置
        if not cookie:
            raise ValueError("❌ 环境变量V2EX_COOKIE未设置")
        
        once, signed = get_once()
        
        # 根据状态执行不同操作
        if signed:
            # 已签到状态获取余额
            time_str, balance_val = get_balance()
            if time_str and balance_val:
                message += f"⏰ 最近签到时间: {time_str}\n💰 当前余额: {balance_val}"
            else:
                message += "⚠️ 获取余额信息失败"
            send_tg_notification(message)
            
        elif once:
            # 执行签到操作
            if check_in(once):
                # 签到成功后获取余额
                time_str, balance_val = get_balance()
                if time_str and balance_val:
                    message += f"⏰ 最近签到时间: {time_str}\n💰 当前余额: {balance_val}"
                else:
                    message += "⚠️ 获取余额信息失败"
            send_tg_notification(message)
        else:
            # 未签到且未获取到once值
            message += "❌ 无法执行签到操作"
            send_tg_notification(message)
            sys.exit(1)
            
    except Exception as err:
        message += f"❗️ 发生异常: {str(err)}"
        send_tg_notification(message)
        print(err, flush=True)
        sys.exit(1)
