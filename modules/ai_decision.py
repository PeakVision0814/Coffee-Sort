# -*- coding: utf-8 -*-
# Copyright (c) 2026 Hangzhou Zhicheng Technology Co., Ltd. All rights reserved.
# 
# This code is proprietary and confidential.
# Unauthorized copying of this file, via any medium is strictly prohibited.
# 
# System: Coffee Intelligent Sorting System
# Author: Hangzhou Zhicheng Technology Co., Ltd
# modules\ai_decision.py

import json
import os
import re
from openai import OpenAI

SIMULATION_MODE = False 

class AIDecisionMaker:
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(base_dir, "config", "ai_config.json")
        self.config = {}
        # 🔥 移除 self.history
        self.load_config()
        print(f">>> [AI] 决策模块已就绪 (无状态单轮对话模式)")

    def load_config(self):
        if not os.path.exists(self.config_path): return
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"❌ [AI] 配置读取失败: {e}")

    def process_text_stream(self, user_input, inventory=None):
        self.load_config()
        print(f"👂 [AI] 收到指令: '{user_input}'")

        api_key = self.config.get("api_key", "")
        base_url = self.config.get("base_url", "https://api.deepseek.com")
        model_name = self.config.get("model_name", "deepseek-chat")
        system_prompt = self.config.get("system_prompt", "")

        # 1. 构建库存状态提示
        status_prompt = ""
        if inventory:
            status_list = []
            for i in range(1, 7):
                status = "【已满】" if inventory.get(i) == 1 else "空闲"
                status_list.append(f"{i}号{status}")
            status_str = ", ".join(status_list)
            status_prompt = f"[当前实时库存]: {status_str}\n"

        # 2. 🔥 核心修改：构建无状态的消息列表
        # 每次只发两条：System Prompt + User Input
        # 这样 AI 永远不会被之前的对话干扰，也永远不会“偷懒”
        
        final_user_content = f"{status_prompt}用户指令: {user_input}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": final_user_content}
        ]

        if not api_key:
            yield "❌ API Key 未配置。"
            return

        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.0, # 🔥 温度设为 0，让输出最稳定、最机械化
                stream=True 
            )

            for chunk in response:
                if chunk.choices[0].delta.content is not None:
                    text_chunk = chunk.choices[0].delta.content
                    yield text_chunk

            # 🔥 移除 history.append 操作

        except Exception as e:
            yield f"❌ AI 调用出错: {str(e)}"

    def extract_command(self, full_text):
        """提取 JSON 指令"""
        try:
            # 1. 优先找 Markdown 代码块
            json_match = re.search(r'```json\s*((\[|\{).*?(\]|\}))\s*```', full_text, re.DOTALL)
            if json_match:
                return self._parse_json_cmd(json_match.group(1))
            
            # 2. 备用：找大括号/中括号
            matches = list(re.finditer(r'(\[.*\]|\{.*\})', full_text, re.DOTALL))
            if matches:
                return self._parse_json_cmd(matches[-1].group(0))
                
            return None
        except Exception as e:
            print(f"⚠️ 指令解析警告: {e}")
            return None

    def _parse_json_cmd(self, json_str):
        try:
            cmd_data = json.loads(json_str)
            if isinstance(cmd_data, list): return cmd_data
            if isinstance(cmd_data, dict): return [cmd_data] # 统一转为列表
            return None
        except:
            return None
    
    def extract_reply(self, full_text):
        """移除 JSON，只返回自然语言部分用于显示"""
        clean_text = re.sub(r'```json\s*.*?```', '', full_text, flags=re.DOTALL)
        return clean_text.strip()