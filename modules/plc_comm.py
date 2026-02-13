# -*- coding: utf-8 -*-
# Copyright (c) 2026 Hangzhou Zhicheng Technology Co., Ltd. All rights reserved.
# 
# This code is proprietary and confidential.
# Unauthorized copying of this file, via any medium is strictly prohibited.
# 
# System: Coffee Intelligent Sorting System
# Author: Hangzhou Zhicheng Technology Co., Ltd
# modules\plc_comm.py

# -*- coding: utf-8 -*-
# modules/plc_client.py

import snap7
from snap7.util import get_bool
import time

class PLCClient:
    def __init__(self, ip='192.168.0.10', rack=0, slot=1, db_number=1):
        self.ip = ip
        self.rack = rack
        self.slot = slot
        self.db_number = db_number
        self.client = snap7.client.Client()
        self.connected = False
        
        # 尝试初次连接
        self._connect()

    def _connect(self):
        """内部连接方法"""
        try:
            if self.client.get_connected():
                return
            self.client.connect(self.ip, self.rack, self.slot)
            self.connected = self.client.get_connected()
            if self.connected:
                print(f"✅ [PLC] 已连接到 {self.ip} (DB{self.db_number})")
            else:
                print(f"❌ [PLC] 连接失败: {self.ip}")
        except Exception as e:
            print(f"❌ [PLC] 连接异常: {e}")
            self.connected = False

    def get_slots_status(self):
        """
        读取 6 个槽位的状态
        返回字典: {1: 1, 2: 0, ...} (1=满, 0=空)
        如果通讯失败，返回 None
        """
        if not self.connected:
            self._connect()
            if not self.connected:
                return None

        try:
            # 读取 DB1, 从 0 开始, 读 2 个字节
            # 你的测试代码：client.db_read(db_number, 0, 2)
            data = self.client.db_read(self.db_number, 0, 2)
            
            status = {}

            # --- Byte 0 (Slot 1-4) ---
            # 映射关系: 1->0.4, 2->0.5, 3->0.6, 4->0.7
            status[1] = 1 if get_bool(data, 0, 4) else 0
            status[2] = 1 if get_bool(data, 0, 5) else 0
            status[3] = 1 if get_bool(data, 0, 6) else 0
            status[4] = 1 if get_bool(data, 0, 7) else 0

            # --- Byte 1 (Slot 5-6) ---
            # 映射关系: 5->1.0, 6->1.1
            status[5] = 1 if get_bool(data, 1, 0) else 0
            status[6] = 1 if get_bool(data, 1, 1) else 0
            
            return status
            
        except Exception as e:
            print(f"⚠️ [PLC] 读取错误: {e}")
            self.connected = False # 标记断开，下次自动重连
            return None

    def close(self):
        if self.connected:
            self.client.disconnect()
            print("[PLC] 连接已关闭")