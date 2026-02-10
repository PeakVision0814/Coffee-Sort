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
        self.load_config()
        print(f">>> [AI] 决策模块已就绪 (模型: {self.config.get('model_name', 'Unknown')})")

    def load_config(self):
        if not os.path.exists(self.config_path): return
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"❌ [AI] 配置读取失败: {e}")

    # 🔥 修改点：增加 inventory 参数
    def process_text_stream(self, user_input, inventory=None):
        """
        流式处理核心
        """
        self.load_config()
        print(f"👂 [AI] 收到指令: '{user_input}'")

        if SIMULATION_MODE:
            yield "⚠️ 模拟模式回复: " + user_input
            return

        api_key = self.config.get("api_key", "")
        base_url = self.config.get("base_url", "https://api.deepseek.com")
        model_name = self.config.get("model_name", "deepseek-chat")
        system_prompt = self.config.get("system_prompt", "")

        # 🔥 核心增强：构建动态的库存状态提示
        status_prompt = ""
        if inventory:
            status_list = []
            for i in range(1, 7):
                status = "【已满】" if inventory.get(i) == 1 else "空闲"
                status_list.append(f"{i}号{status}")
            status_str = ", ".join(status_list)
            
            # 🔥 修改这里：把警告语写得更直白、更严厉
            status_prompt = (
                f"\n[系统实时数据]: {status_str}\n"
                f"⚠️ 重要安全规则：\n"
                f"1. 如果用户要求的槽位显示【已满】，你必须拒绝！\n"
                f"2. 严禁擅自更换槽位！例如用户说3号，3号满了，你就报错，绝对不能自作主张放到1号！\n"
                f"3. 拒绝时，不要输出任何 JSON 代码块。\n"
            )

        final_user_input = f"{status_prompt}\n用户指令: {user_input}"

        if not api_key:
            yield "❌ API Key 未配置。"
            return

        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
            
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": final_user_input}, # 使用带库存信息的输入
                ],
                temperature=0.1,
                max_tokens=500,
                stream=True 
            )

            for chunk in response:
                if chunk.choices[0].delta.content is not None:
                    text_chunk = chunk.choices[0].delta.content
                    yield text_chunk

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