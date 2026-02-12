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

# 模拟模式开关
SIMULATION_MODE = False 

class AIDecisionMaker:
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(base_dir, "config", "ai_config.json")
        self.config = {}
        self.history = []
        self.max_history = 10 # 最近 5 轮对话 (5条user + 5条assistant)
        self.load_config()
        print(f">>> [AI] 决策模块已就绪 (模型: {self.config.get('model_name', 'Unknown')})")

    def load_config(self):
        if not os.path.exists(self.config_path): return
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"❌ [AI] 配置读取失败: {e}")

    def _clean_response_for_history(self, text):
        """🔥 核心优化：剥离 JSON 块，节省历史记录 Token"""
        # 移除 ```json ... ``` 及其内部所有内容
        clean_text = re.sub(r'```json\s*.*?```', '', text, flags=re.DOTALL)
        # 移除可能残余的空行
        return clean_text.strip()

    def process_text_stream(self, user_input, inventory=None):
        self.load_config()
        print(f"👂 [AI] 收到指令: '{user_input}'")

        api_key = self.config.get("api_key", "")
        base_url = self.config.get("base_url", "https://api.deepseek.com")
        model_name = self.config.get("model_name", "deepseek-chat")
        system_prompt = self.config.get("system_prompt", "")

        # 1. 构建当前库存状态 (不存入 history，仅作为当前上下文)
        status_prompt = ""
        if inventory:
            status_list = []
            for i in range(1, 7):
                status = "【已满】" if inventory.get(i) == 1 else "空闲"
                status_list.append(f"{i}号{status}")
            status_str = ", ".join(status_list)
            status_prompt = f"[当前实时库存]: {status_str}\n"

        # 2. 准备本次请求的消息列表
        # 消息结构：System Prompt + 历史记忆 + 当前库存及输入
        messages = [{"role": "system", "content": system_prompt}]
        
        # 加入历史记录
        messages.extend(self.history)
        
        # 加入当前最新的输入 (带上实时库存)
        current_user_content = f"{status_prompt}用户指令: {user_input}"
        messages.append({"role": "user", "content": current_user_content})

        if not api_key:
            yield "❌ API Key 未配置。"
            return

        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.1,
                stream=True 
            )

            full_reply = ""
            for chunk in response:
                if chunk.choices[0].delta.content is not None:
                    text_chunk = chunk.choices[0].delta.content
                    full_reply += text_chunk
                    yield text_chunk

            # 🔥 3. 对话结束后，更新滑动窗口记忆
            # 记录用户原始输入 (不带库存提示，节省空间)
            self.history.append({"role": "user", "content": user_input})
            # 记录 AI 清理后的回复 (不带 JSON)
            self.history.append({"role": "assistant", "content": self._clean_response_for_history(full_reply)})
            
            # 裁剪历史记录
            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history:]

        except Exception as e:
            yield f"❌ AI 调用出错: {str(e)}"

    def extract_command(self, full_text):
        """
        从混合文本中提取 JSON 指令
        支持格式：
        1. "好的... ```json {...} ```"
        2. "好的... \n {...}"
        3. 纯 JSON
        """
        try:
            # 1. 尝试找代码块 ```json ... ```
            code_block = re.search(r'```json\s*(\{.*?\})\s*```', full_text, re.DOTALL)
            if code_block:
                json_str = code_block.group(1)
                return self._parse_json_cmd(json_str)

            # 2. 尝试找最后一个大括号包围的内容
            matches = list(re.finditer(r'\{.*\}', full_text, re.DOTALL))
            if matches:
                # 取最后一个，防止正文里也有大括号
                json_str = matches[-1].group(0)
                return self._parse_json_cmd(json_str)
                
            return None
        except Exception as e:
            print(f"⚠️ 指令解析警告: {e}")
            return None

    def _parse_json_cmd(self, json_str):
        """辅助解析函数"""
        try:
            cmd_data = json.loads(json_str)
            # 兼容处理
            if "command" in cmd_data: return cmd_data["command"]
            if "action" in cmd_data or "type" in cmd_data: return cmd_data
            return None
        except:
            return None
    
    # 🔥 新增：提取回复文本
    def extract_reply(self, full_text):
        """尝试从 JSON 中提取 'reply' 字段，如果不是 JSON 则返回原文本"""
        try:
            matches = list(re.finditer(r'\{.*\}', full_text, re.DOTALL))
            if matches:
                last_match = matches[-1]
                json_str = last_match.group(0)
                data = json.loads(json_str)
                if "reply" in data:
                    return data["reply"]
            return full_text # 如果提取失败，返回原始文本
        except:
            return full_text