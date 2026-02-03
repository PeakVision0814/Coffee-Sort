import json
import os
import sys
import re

# 尝试导入 OpenAI 库
try:
    from openai import OpenAI
except ImportError:
    print("❌ 错误: 未安装 openai 库。请运行 'pip install openai'")
    OpenAI = None

# --- 🔥 关键开关 ---
# True = 不花钱，用假数据测试逻辑
# False = 真正调用 DeepSeek API (需要配置 api_key)
SIMULATION_MODE = False 

class AIDecisionMaker:
    def __init__(self):
        # 1. 确定配置文件路径
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(base_dir, "config", "ai_config.json")
        
        # 2. 初始化配置缓存
        self.config = {}
        
        # 3. 加载配置
        self.load_config()
        print(f">>> [AI] 决策模块已就绪 (模型: {self.config.get('model_name', 'Unknown')})")
        print(f">>> [AI] 当前模式: {'⚠️ 模拟模式 (不消耗Token)' if SIMULATION_MODE else '✅ 在线模式 (DeepSeek API)'}")

    def load_config(self):
        """从 JSON 文件加载最新的配置"""
        if not os.path.exists(self.config_path):
            print(f"⚠️ [AI] 配置文件未找到: {self.config_path}")
            return
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"❌ [AI] 配置文件读取失败: {e}")

    def save_config(self, new_config_dict):
        """更新配置并保存"""
        try:
            self.config.update(new_config_dict)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            print("💾 [AI] 配置已更新并保存")
            return True
        except Exception as e:
            print(f"❌ [AI] 配置保存失败: {e}")
            return False

    def process_text(self, user_input):
        """
        处理用户指令，返回字典:
        {
            "reply": "好的，正在执行...",
            "command": {"type": "sort", "slot_id": 3} 或 None
        }
        """
        # 每次调用前重新加载配置（支持前端热修改）
        self.load_config()
        
        print(f"👂 [AI] 收到指令: '{user_input}'")
        
        # 1. 模拟模式 (用于调试)
        if SIMULATION_MODE:
            return self._mock_response(user_input)

        # 2. 真实 API 调用
        return self._call_deepseek_api(user_input)

    def _call_deepseek_api(self, user_input):
        """🔥 真实的 DeepSeek API 调用逻辑"""
        if not OpenAI:
            return {"reply": "系统错误：缺少 openai 依赖库", "command": None}

        api_key = self.config.get("api_key", "")
        base_url = self.config.get("base_url", "https://api.deepseek.com")
        model_name = self.config.get("model_name", "deepseek-chat")
        system_prompt = self.config.get("system_prompt", "")

        if not api_key or "your-key" in api_key:
            return {"reply": "❌ API Key 未配置，请在代码或网页中填入 Key。", "command": None}

        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
            
            # 发起请求
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input},
                ],
                temperature=0.1, # 低温度，保证指令稳定性
                max_tokens=200,   # 不用太长
                stream=False
            )

            # 获取原始内容
            raw_content = response.choices[0].message.content.strip()
            print(f"🧠 [AI原始返回]: {raw_content}")

            # 清洗数据 (防止 AI 返回 ```json ... ``` 格式)
            clean_json = self._extract_json(raw_content)
            
            # 解析 JSON
            result = json.loads(clean_json)
            
            # 确保返回格式包含 reply 和 command
            if "reply" not in result:
                result["reply"] = "指令已执行。"
            if "command" not in result:
                result["command"] = None
                
            return result

        except Exception as e:
            print(f"❌ [AI] API 调用失败: {e}")
            return {"reply": f"AI 连接失败: {str(e)}", "command": None}

    def _extract_json(self, text):
        """
        辅助函数：从 AI 返回的文本中提取纯 JSON 字符串
        去掉可能存在的 Markdown 代码块标记 ```json ... ```
        """
        # 尝试通过正则寻找大括号包围的内容
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return match.group(0)
        return text

    def _mock_response(self, text):
        """本地模拟回复 (用于测试)"""
        if "3" in text or "三" in text:
            return {
                "reply": "好的，正在为您将物品放入 3 号槽位。", 
                "command": {"type": "sort", "slot_id": 3}
            }
        elif "开始" in text:
            return {
                "reply": "收到，系统启动，开始自动分拣。",
                "command": {"type": "sys", "action": "start"}
            }
        elif "停止" in text:
             return {
                "reply": "已紧急停止。",
                "command": {"type": "sys", "action": "stop"}
            }
        return {
            "reply": "模拟模式：我听到了，但不知道做什么。", 
            "command": None
        }

# --- 单元测试 ---
if __name__ == "__main__":
    ai = AIDecisionMaker()
    
    # 可以在这里测试一下
    # 注意：如果 SIMULATION_MODE = False，这里会真的消耗 Token
    print(">>> 测试发送指令: '把这个放到5号'")
    res = ai.process_text("把这个放到5号")
    print(f">>> 解析结果: {res}")