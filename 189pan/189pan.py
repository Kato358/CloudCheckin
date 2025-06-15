import time
import re
import json
import base64
import hashlib
import rsa
import requests
import os
import sys
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv
from telegram.notify import send_tg_notification


class Config:
    """配置类，管理所有常量和URL"""
    # ... (保持原有Config类不变) ...

class CryptoUtils:
    """加密工具类"""
    # ... (保持原有CryptoUtils类不变) ...

class TianYiCloudBot:
    """天翼云盘自动签到抽奖机器人"""
    # ... (保持原有__init__和_extract_login_params方法不变) ...

    def login(self) -> bool:
        """登录天翼云盘"""
        try:
            # 获取登录token
            response = self.session.get(Config.LOGIN_TOKEN_URL)
            send_tg_notification(f"{self.account_id}: 正在获取登录token...")

            # ... (保持原有登录流程不变) ...

            if result['result'] == 0:
                # 访问重定向URL完成登录
                self.session.get(result['toUrl'])
                send_tg_notification(f"{self.account_id}: ✅ 登录成功")
                return True
            else:
                send_tg_notification(f"{self.account_id}: ❌ 登录失败: {result.get('msg', '未知错误')}")
                return False

        except Exception as e:
            error_msg = f"{self.account_id}: ❌ 登录过程出错: {e}"
            print(error_msg)
            send_tg_notification(error_msg)
            return False

    def sign_in(self) -> Tuple[bool, str]:
        """执行签到"""
        try:
            rand = str(round(time.time() * 1000))
            sign_url = Config.SIGN_URL_TEMPLATE.format(rand)
            send_tg_notification(f"{self.account_id}: 正在执行签到...")

            response = self.session.get(sign_url, headers=Config.SIGN_HEADERS, timeout=10)
            result = response.json()

            netdisk_bonus = result.get('netdiskBonus', 0)
            is_signed = result.get('isSign', False)

            if is_signed:
                message = f"{self.account_id}: ✅ 已签到，获得{netdisk_bonus}M空间"
            else:
                message = f"{self.account_id}: ✅ 签到成功，获得{netdisk_bonus}M空间"

            send_tg_notification(message)
            return True, message

        except Exception as e:
            error_msg = f"{self.account_id}: ❌ 签到失败: {e}"
            print(error_msg)
            send_tg_notification(error_msg)
            return False, error_msg

    def draw_prize(self, round_num: int, url: str) -> Tuple[bool, str]:
        """执行抽奖"""
        try:
            send_tg_notification(f"{self.account_id}: 正在进行第{round_num}次抽奖...")
            response = self.session.get(url, headers=Config.SIGN_HEADERS, timeout=10)
            data = response.json()

            if "errorCode" in data:
                message = f"{self.account_id}: ⚠️ 第{round_num}次抽奖失败，次数不足"
                send_tg_notification(message)
                return False, message
            else:
                prize_name = data.get("prizeName", "未知奖品")
                message = f"{self.account_id}: 🎉 第{round_num}次抽奖成功，获得{prize_name}"
                send_tg_notification(message)
                return True, message

        except Exception as e:
            error_msg = f"{self.account_id}: ❌ 第{round_num}次抽奖出错: {e}"
            print(error_msg)
            send_tg_notification(error_msg)
            return False, error_msg

    def run(self) -> Dict[str, str]:
        """执行完整的签到抽奖流程"""
        results = {
            'account_id': self.account_id,
            'login': '',
            'sign_in': '',
            'draws': []
        }

        # 登录
        if not self.login():
            results['login'] = '登录失败'
            return results

        results['login'] = '登录成功'

        # 签到
        sign_success, sign_msg = self.sign_in()
        results['sign_in'] = sign_msg

        # 抽奖
        for i, draw_url in enumerate(Config.DRAW_URLS, 1):
            if i > 1:  # 第一次抽奖后等待5秒
                time.sleep(5)

            draw_success, draw_msg = self.draw_prize(i, draw_url)
            results['draws'].append(draw_msg)

        return results


def load_accounts() -> List[Tuple[str, str]]:
    """加载账户信息"""
    load_dotenv()

    username_env = os.getenv("TYYP_USERNAME")
    password_env = os.getenv("TYYP_PSW")

    if not username_env or not password_env:
        error_msg = "错误：环境变量TYYP_USERNAME或TYYP_PSW未设置\n请确保.env文件存在并包含正确的配置"
        print(error_msg)
        send_tg_notification(error_msg)
        sys.exit(1)

    usernames = username_env.split('&')
    passwords = password_env.split('&')

    if len(usernames) != len(passwords):
        error_msg = "错误：用户名和密码数量不匹配"
        print(error_msg)
        send_tg_notification(error_msg)
        sys.exit(1)

    return list(zip(usernames, passwords))


def main():
    """主程序"""
    # 记录开始时间
    start_time = datetime.now()
    
    print("# 天翼云盘自动签到抽奖程序")
    print()
    
    # 加载账户信息
    accounts = load_accounts()
    print(f"## 执行概览")
    print(f"- **启动时间**: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"- **账户数量**: {len(accounts)} 个")
    print()
    
    # 存储所有账户结果
    all_results = []
    
    # 处理每个账户
    for i, (username, password) in enumerate(accounts, 1):
        account_id = f"账户{i}"
        print(f"## {account_id}")
        
        bot = TianYiCloudBot(username, password, account_id)
        results = bot.run()
        all_results.append(results)
        
        # 输出结果摘要
        print(f"### 执行结果")
        print(f"- **登录状态**: {results['login']}")
        print(f"- **签到结果**: {results['sign_in']}")
        
        # 抽奖结果
        if results['draws']:
            print(f"- **抽奖结果**:")
            for j, draw_result in enumerate(results['draws'], 1):
                # 提取关键信息，去除重复的"第X次"
                clean_result = draw_result.replace(f"第{j}次", "").strip()
                if "成功" in draw_result:
                    print(f"  - 🎉 第{j}次: {clean_result}")
                else:
                    print(f"  - ❌ 第{j}次: {clean_result}")
        
        print()
    
    # 记录结束时间并计算运行时间
    end_time = datetime.now()
    duration = end_time - start_time
    
    # 构建TG通知消息
    report_date = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    tg_message = f"{report_date} 天翼云签到报告\n\n"
    tg_message += f"📅 执行时间: {start_time.strftime('%Y-%m-%d %H:%M')} - {end_time.strftime('%H:%M')}\n"
    tg_message += f"⏱️ 运行时长: {duration.total_seconds():.2f}秒\n"
    tg_message += f"👤 账户总数: {len(accounts)}个\n\n"
    
    # 添加每个账户的摘要
    for i, result in enumerate(all_results, 1):
        tg_message += f"🔹 账户{i}:\n"
        tg_message += f"   - 登录: {result['login']}\n"
        tg_message += f"   - 签到: {result['sign_in']}\n"
        
        if result['draws']:
            for j, draw in enumerate(result['draws'], 1):
                # 提取状态图标
                status_icon = "🎉" if "成功" in draw else "❌"
                tg_message += f"   - 抽奖{j}: {status_icon} {draw.split(':')[-1].strip()}\n"
        tg_message += "\n"
    
    # 发送TG通知
    send_tg_notification(tg_message)
    
    print("---")
    print("## 执行统计")
    print(f"- **结束时间**: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"- **运行时长**: {duration.total_seconds():.2f} 秒")
    print()
    print("✅ **所有账户处理完成！**")
    print(f"📨 已发送TG通知")

if __name__ == "__main__":
    main()
