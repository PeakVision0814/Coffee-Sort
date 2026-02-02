import sys
import cv2
from pymycobot import MyCobot
from config.settings import VERSION

def system_check():
    print(f"咖啡分拣系统 v{VERSION} 启动中...")
    print(f"OpenCV Version: {cv2.__version__}")
    print("环境依赖检查通过。")

if __name__ == "__main__":
    system_check()