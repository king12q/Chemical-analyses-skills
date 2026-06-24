#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gui_automation.py — GUI 自动化核心模块

功能：
  - 窗口查找与激活
  - 键盘快捷键模拟
  - 菜单导航（Alt 键序列）
  - 鼠标点击（坐标/控件定位）
  - 截图与图像识别
  - 弹窗处理与错误恢复
  - 剪贴板操作

依赖：
  pip install pywinauto pyautogui pyperclip Pillow opencv-python

使用示例：
  from gui_automation import GUIAutomation
  gui = GUIAutomation()
  gui.open_application("C:/Program Files/Mestrenova/Mestrenova.exe")
  gui.press_keys("Ctrl", "O")
  gui.wait_for_window("Mestrenova")
"""

import os
import sys
import time
import logging
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any, Union
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("gui_automation")

# 尝试导入 GUI 自动化库
try:
    import pyautogui
    import pyperclip
    PYAUTOGUI_AVAILABLE = True
    # 安全设置：pyautogui 的默认超时和防护
    pyautogui.FAILSAFE = True  # 鼠标移到角落触发异常，停止所有操作
    pyautogui.PAUSE = 0.5  # 每次操作后暂停 0.5 秒
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    logger.warning("[警告] pyautogui 未安装，鼠标操作将不可用。安装命令: pip install pyautogui pyperclip")

try:
    from pywinauto import Application, timings, WindowSpecification
    from pywinauto.keyboard import send_keys
    from pywinauto.mouse import click, move
    PYWINAUTO_AVAILABLE = True
except ImportError:
    PYWINAUTO_AVAILABLE = False
    logger.warning("[警告] pywinauto 未安装，窗口操作将受限。安装命令: pip install pywinauto")


class WaitStrategy(Enum):
    """等待策略"""
    WINDOW_ACTIVE = "active"       # 窗口激活
    WINDOW_VISIBLE = "visible"     # 窗口可见
    WINDOW_EXISTS = "exists"       # 窗口存在
    CONTROL_EXISTS = "control"     # 控件存在


@dataclass
class WindowInfo:
    """窗口信息"""
    title: str
    process_id: int
    handle: int
    rect: Tuple[int, int, int, int]  # left, top, right, bottom
    is_active: bool


class GUIAutomation:
    """
    GUI 自动化核心类
    
    提供跨软件的通用 GUI 操作能力，支持：
    - 启动和关闭应用程序
    - 窗口查找和焦点管理
    - 键盘快捷键模拟
    - 菜单操作（通过 Alt 键序列）
    - 鼠标点击和拖拽
    - 剪贴板操作
    - 弹窗处理
    - 截图和日志记录
    """
    
    # 常用快捷键映射（适用于大多数 Windows 软件）
    COMMON_SHORTCUTS = {
        "open": "Ctrl+O",
        "save": "Ctrl+S",
        "save_as": "Ctrl+Shift+S",
        "print": "Ctrl+P",
        "quit": "Ctrl+Q",
        "undo": "Ctrl+Z",
        "redo": "Ctrl+Y",
        "cut": "Ctrl+X",
        "copy": "Ctrl+C",
        "paste": "Ctrl+V",
        "select_all": "Ctrl+A",
        "find": "Ctrl+F",
        "refresh": "F5",
    }
    
    def __init__(self, 
                 timeout: float = 10.0,
                 screenshot_dir: Optional[str] = None):
        """
        初始化 GUI 自动化模块
        
        Args:
            timeout: 默认超时时间（秒）
            screenshot_dir: 截图保存目录
        """
        self.timeout = timeout
        self.screenshot_dir = Path(screenshot_dir) if screenshot_dir else Path("./outputs/screenshots")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        self.app: Optional[Application] = None
        self.current_window: Optional[WindowSpecification] = None
        
        logger.info(f"[初始化] GUI 自动化模块已加载")
        logger.info(f"  - pywinauto: {'✓' if PYWINAUTO_AVAILABLE else '✗'}")
        logger.info(f"  - pyautogui: {'✓' if PYAUTOGUI_AVAILABLE else '✗'}")
        logger.info(f"  - 截图目录: {self.screenshot_dir}")
    
    # =========================================================================
    # 应用管理
    # =========================================================================
    
    def open_application(self, 
                         executable_path: str,
                         arguments: Optional[List[str]] = None,
                         wait_for_ready: bool = True) -> bool:
        """
        打开应用程序
        
        Args:
            executable_path: 可执行文件路径
            arguments: 命令行参数
            wait_for_ready: 是否等待应用就绪
            
        Returns:
            bool: 是否成功
        """
        try:
            path = Path(executable_path)
            if not path.exists():
                logger.error(f"[错误] 文件不存在: {executable_path}")
                return False
            
            cmd = [str(path)]
            if arguments:
                cmd.extend(arguments)
            
            logger.info(f"[启动] {' '.join(cmd)}")
            
            if PYWINAUTO_AVAILABLE:
                self.app = Application(backend="win32").start(
                    " ".join(cmd),
                    timeout=timings.Timings.app_start_timeout
                )
                
                if wait_for_ready:
                    self.app.wait_cpu_usage(
                        interval=0.5,
                        threshold=5,
                        timeout=30
                    )
                
                # 获取主窗口
                time.sleep(1)  # 等待窗口创建
                self.current_window = self.app.window(title_re=".*")
                logger.info(f"[成功] 应用已启动，窗口: {self.get_window_title()}")
                return True
            else:
                # 使用 subprocess 启动（备用方案）
                subprocess.Popen(cmd, shell=True)
                logger.info("[成功] 应用已启动（subprocess 模式）")
                return True
                
        except Exception as e:
            logger.error(f"[错误] 启动应用失败: {e}")
            return False
    
    def close_application(self, force: bool = False) -> bool:
        """关闭当前应用程序"""
        try:
            if self.app:
                if force:
                    self.app.kill()
                else:
                    self.app.close()
                logger.info("[成功] 应用已关闭")
                return True
            return False
        except Exception as e:
            logger.error(f"[错误] 关闭应用失败: {e}")
            return False
    
    def connect_to_application(self, process_id: Optional[int] = None,
                              window_title: Optional[str] = None) -> bool:
        """
        连接到已运行的应用程序
        
        Args:
            process_id: 进程 ID
            window_title: 窗口标题（支持正则）
            
        Returns:
            bool: 是否成功
        """
        try:
            if PYWINAUTO_AVAILABLE:
                if process_id:
                    self.app = Application(backend="win32").connect(process=process_id)
                elif window_title:
                    self.app = Application(backend="win32").connect(title_re=window_title)
                else:
                    logger.error("[错误] 必须提供 process_id 或 window_title")
                    return False
                
                self.current_window = self.app.window(title_re=".*")
                logger.info(f"[成功] 已连接到应用: {self.get_window_title()}")
                return True
            return False
        except Exception as e:
            logger.error(f"[错误] 连接应用失败: {e}")
            return False
    
    # =========================================================================
    # 窗口操作
    # =========================================================================
    
    def get_window_title(self) -> str:
        """获取当前窗口标题"""
        try:
            if self.current_window:
                return self.current_window.window_text()
        except Exception:
            pass
        return ""
    
    def wait_for_window(self, 
                        title_pattern: str,
                        timeout: Optional[float] = None,
                        strategy: WaitStrategy = WaitStrategy.WINDOW_EXISTS) -> bool:
        """
        等待窗口出现
        
        Args:
            title_pattern: 窗口标题（支持正则）
            timeout: 超时时间
            strategy: 等待策略
            
        Returns:
            bool: 是否成功等到
        """
        timeout = timeout or self.timeout
        
        try:
            if PYWINAUTO_AVAILABLE and self.app:
                if strategy == WaitStrategy.WINDOW_ACTIVE:
                    self.current_window = self.app.window(
                        title_re=title_pattern
                    ).wait('active', timeout=timeout)
                elif strategy == WaitStrategy.WINDOW_VISIBLE:
                    self.current_window = self.app.window(
                        title_re=title_pattern
                    ).wait('visible', timeout=timeout)
                else:
                    self.current_window = self.app.window(
                        title_re=title_pattern
                    ).wait('exists', timeout=timeout)
                
                logger.info(f"[成功] 窗口已就绪: {self.get_window_title()}")
                return True
        except Exception as e:
            logger.warning(f"[超时] 等待窗口 '{title_pattern}' 超时: {e}")
        
        return False
    
    def activate_window(self, title_pattern: Optional[str] = None) -> bool:
        """激活窗口（获取焦点）"""
        try:
            if PYWINAUTO_AVAILABLE:
                if title_pattern and self.app:
                    self.app.window(title_re=title_pattern).set_focus()
                elif self.current_window:
                    self.current_window.set_focus()
                
                time.sleep(0.3)
                logger.info(f"[成功] 窗口已激活: {self.get_window_title()}")
                return True
        except Exception as e:
            logger.error(f"[错误] 激活窗口失败: {e}")
        return False
    
    def maximize_window(self) -> bool:
        """最大化窗口"""
        try:
            if self.current_window:
                self.current_window.maximize()
                time.sleep(0.3)
                logger.info("[成功] 窗口已最大化")
                return True
        except Exception as e:
            logger.error(f"[错误] 最大化窗口失败: {e}")
        return False
    
    def minimize_window(self) -> bool:
        """最小化窗口"""
        try:
            if self.current_window:
                self.current_window.minimize()
                time.sleep(0.3)
                logger.info("[成功] 窗口已最小化")
                return True
        except Exception as e:
            logger.error(f"[错误] 最小化窗口失败: {e}")
        return False
    
    def restore_window(self) -> bool:
        """恢复窗口"""
        try:
            if self.current_window:
                self.current_window.restore()
                time.sleep(0.3)
                logger.info("[成功] 窗口已恢复")
                return True
        except Exception as e:
            logger.error(f"[错误] 恢复窗口失败: {e}")
        return False
    
    # =========================================================================
    # 键盘操作
    # =========================================================================
    
    def press_keys(self, *keys: str, hold_time: float = 0.1) -> bool:
        """
        模拟按键（支持组合键）
        
        Args:
            *keys: 按键序列，如 "Ctrl", "O" 表示 Ctrl+O
            hold_time: 按住时间（秒）
            
        Examples:
            gui.press_keys("Ctrl", "O")       # Ctrl+O
            gui.press_keys("Ctrl", "Shift", "S")  # Ctrl+Shift+S
            gui.press_keys("F5")              # F5
            gui.press_keys("Alt", "F", "X")   # Alt+F, X (文件菜单退出)
        """
        try:
            if PYWINAUTO_AVAILABLE:
                # pywinauto 的 send_keys 使用特殊语法
                # % 表示 Alt, ^ 表示 Ctrl, + 表示 Shift
                key_str = ""
                for key in keys:
                    if key.lower() == "ctrl":
                        key_str += "^"
                    elif key.lower() == "alt":
                        key_str += "%"
                    elif key.lower() == "shift":
                        key_str += "+"
                    elif key.lower() == "win":
                        key_str += "^"  # Windows key
                    else:
                        key_str += key
                
                send_keys(key_str, with_spaces=True, with_tabs=True, with_newlines=True)
                time.sleep(hold_time)
                logger.debug(f"[按键] {key_str}")
                return True
            elif PYAUTOGUI_AVAILABLE:
                # pyautogui 模式
                for key in keys:
                    pyautogui.keyDown(key)
                    time.sleep(0.05)
                time.sleep(hold_time)
                for key in reversed(keys):
                    pyautogui.keyUp(key)
                logger.debug(f"[按键] {'+'.join(keys)}")
                return True
            else:
                logger.error("[错误] 没有可用的键盘模拟库")
                return False
                
        except Exception as e:
            logger.error(f"[错误] 模拟按键失败: {e}")
            return False
    
    def type_text(self, text: str, interval: float = 0.05) -> bool:
        """
        输入文本
        
        Args:
            text: 要输入的文本
            interval: 每个字符间隔（秒）
        """
        try:
            if PYAUTOGUI_AVAILABLE:
                pyautogui.write(text, interval=interval)
                logger.debug(f"[输入] {text[:50]}{'...' if len(text) > 50 else ''}")
                return True
            else:
                logger.error("[错误] pyautogui 未安装")
                return False
        except Exception as e:
            logger.error(f"[错误] 输入文本失败: {e}")
            return False
    
    def press_common_shortcut(self, action: str) -> bool:
        """
        执行常用快捷操作
        
        Args:
            action: 操作名称，见 COMMON_SHORTCUTS
        """
        if action not in self.COMMON_SHORTCUTS:
            logger.error(f"[错误] 未知的快捷操作: {action}")
            return False
        
        shortcut = self.COMMON_SHORTCUTS[action]
        keys = shortcut.replace("Ctrl", "ctrl").replace("Shift", "shift").replace("Alt", "alt").split("+")
        return self.press_keys(*keys)
    
    def send_menu_sequence(self, menu_keys: List[str]) -> bool:
        """
        发送菜单序列（通过 Alt+字母访问菜单项）
        
        Args:
            menu_keys: 菜单按键序列
                      如 ["F", "S"] 表示 Alt+F, S（文件-保存）
                      如 ["F", "A"] 表示 Alt+F, A（文件-另存为）
        
        Examples:
            gui.send_menu_sequence(["F", "S"])  # Alt+F, S (文件-保存)
            gui.send_menu_sequence(["E", "P"])  # Alt+E, P (编辑-粘贴)
            gui.send_menu_sequence(["V", "I"])  # Alt+V, I (视图-积分)
        """
        try:
            keys = ["Alt"] + menu_keys
            return self.press_keys(*keys)
        except Exception as e:
            logger.error(f"[错误] 菜单操作失败: {e}")
            return False
    
    # =========================================================================
    # 鼠标操作
    # =========================================================================
    
    def click(self, 
             x: Optional[int] = None,
             y: Optional[int] = None,
             button: str = "left",
             clicks: int = 1,
             interval: float = 0.1) -> bool:
        """
        鼠标点击
        
        Args:
            x, y: 坐标（如果为 None，使用当前鼠标位置）
            button: 按钮 ("left", "right", "middle")
            clicks: 点击次数
            interval: 每次点击间隔
        """
        try:
            if PYAUTOGUI_AVAILABLE:
                pyautogui.click(x=x, y=y, clicks=clicks, interval=interval, button=button)
                logger.debug(f"[点击] ({x}, {y}) {button} x{clicks}")
                return True
            elif PYWINAUTO_AVAILABLE and x is not None and y is not None:
                click(coords=(x, y))
                logger.debug(f"[点击] ({x}, {y}) {button}")
                return True
            else:
                logger.error("[错误] 无法执行鼠标点击")
                return False
        except Exception as e:
            logger.error(f"[错误] 鼠标点击失败: {e}")
            return False
    
    def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        """双击"""
        return self.click(x=x, y=y, clicks=2)
    
    def right_click(self, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        """右键点击"""
        return self.click(x=x, y=y, button="right")
    
    def move_to(self, x: int, y: int, duration: float = 0.5) -> bool:
        """移动鼠标到指定位置"""
        try:
            if PYAUTOGUI_AVAILABLE:
                pyautogui.moveTo(x, y, duration=duration)
                logger.debug(f"[移动] 鼠标移至 ({x}, {y})")
                return True
            elif PYWINAUTO_AVAILABLE:
                move(coords=(x, y))
                return True
        except Exception as e:
            logger.error(f"[错误] 移动鼠标失败: {e}")
        return False
    
    def get_screen_size(self) -> Tuple[int, int]:
        """获取屏幕尺寸"""
        if PYAUTOGUI_AVAILABLE:
            return pyautogui.size()
        return (1920, 1080)  # 默认值
    
    def get_current_mouse_position(self) -> Tuple[int, int]:
        """获取当前鼠标位置"""
        if PYAUTOGUI_AVAILABLE:
            return pyautogui.position()
        return (0, 0)
    
    # =========================================================================
    # 剪贴板操作
    # =========================================================================
    
    def copy_to_clipboard(self, text: str) -> bool:
        """复制文本到剪贴板"""
        try:
            if PYAUTOGUI_AVAILABLE:
                pyperclip.copy(text)
                logger.debug(f"[剪贴板] 已复制 {len(text)} 个字符")
                return True
        except Exception as e:
            logger.error(f"[错误] 复制到剪贴板失败: {e}")
        return False
    
    def paste_from_clipboard(self) -> str:
        """从剪贴板粘贴"""
        try:
            if PYAUTOGUI_AVAILABLE:
                return pyperclip.paste()
        except Exception as e:
            logger.error(f"[错误] 从剪贴板粘贴失败: {e}")
        return ""
    
    # =========================================================================
    # 截图与图像识别
    # =========================================================================
    
    def take_screenshot(self, filename: Optional[str] = None) -> Optional[str]:
        """
        截取当前屏幕
        
        Args:
            filename: 保存文件名（不含路径）
            
        Returns:
            保存的文件路径，失败返回 None
        """
        try:
            if PYAUTOGUI_AVAILABLE:
                if filename is None:
                    filename = f"screenshot_{int(time.time())}.png"
                
                filepath = self.screenshot_dir / filename
                img = pyautogui.screenshot()
                img.save(str(filepath))
                logger.info(f"[截图] 已保存: {filepath}")
                return str(filepath)
        except Exception as e:
            logger.error(f"[错误] 截图失败: {e}")
        return None
    
    def find_image_on_screen(self, 
                             image_path: str,
                             confidence: float = 0.8) -> Optional[Tuple[int, int]]:
        """
        在屏幕上查找图像
        
        Args:
            image_path: 要查找的图像路径
            confidence: 匹配置信度（0-1）
            
        Returns:
            图像中心坐标 (x, y)，未找到返回 None
        """
        try:
            if PYAUTOGUI_AVAILABLE and Path(image_path).exists():
                location = pyautogui.locateOnScreen(
                    image_path, 
                    confidence=confidence
                )
                if location:
                    center = pyautogui.center(location)
                    logger.info(f"[图像识别] 找到目标: ({center.x}, {center.y})")
                    return (center.x, center.y)
                else:
                    logger.debug(f"[图像识别] 未找到: {image_path}")
        except Exception as e:
            logger.warning(f"[图像识别] 查找失败: {e}")
        return None
    
    # =========================================================================
    # 弹窗与对话框处理
    # =========================================================================
    
    def handle_dialog(self, 
                     action: str = "ok",
                     timeout: float = 5.0) -> bool:
        """
        处理对话框
        
        Args:
            action: 操作 ("ok", "cancel", "yes", "no", "close")
            timeout: 等待对话框超时
        """
        try:
            time.sleep(0.5)  # 等待对话框出现
            
            if action == "ok":
                self.press_keys("Enter")
            elif action == "cancel":
                self.press_keys("Escape")
            elif action == "yes":
                self.press_keys("y")
            elif action == "no":
                self.press_keys("n")
            elif action == "close":
                self.press_keys("Alt", "F4")
            
            logger.info(f"[对话框] 执行操作: {action}")
            return True
        except Exception as e:
            logger.error(f"[错误] 处理对话框失败: {e}")
            return False
    
    def wait_and_handle_dialog(self, 
                               expected_text: Optional[str] = None,
                               action: str = "ok",
                               timeout: float = 10.0) -> bool:
        """
        等待对话框并处理
        
        Args:
            expected_text: 期望的对话框文本（用于确认）
            action: 处理动作
            timeout: 超时时间
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # 检测是否有对话框出现
            # 这里简化处理，实际可能需要更复杂的检测
            
            # 尝试按 Enter 关闭常见的"确定"对话框
            if action in ["ok", "yes"]:
                self.press_keys("Enter")
                time.sleep(0.3)
                return True
        
        logger.warning(f"[对话框] 等待超时: {timeout}秒")
        return False
    
    def input_text_in_dialog(self, text: str) -> bool:
        """在对话框中输入文本"""
        try:
            time.sleep(0.3)
            self.type_text(text)
            time.sleep(0.2)
            return True
        except Exception as e:
            logger.error(f"[错误] 在对话框中输入文本失败: {e}")
            return False
    
    # =========================================================================
    # 等待与延时
    # =========================================================================
    
    def wait(self, seconds: float) -> None:
        """等待指定秒数"""
        time.sleep(seconds)
    
    def wait_for_idle(self, timeout: float = 10.0) -> bool:
        """等待应用程序空闲"""
        try:
            if self.app:
                self.app.wait_cpu_usage(
                    interval=0.5,
                    threshold=5,
                    timeout=timeout
                )
                return True
        except Exception:
            pass
        return False
    
    # =========================================================================
    # 日志与调试
    # =========================================================================
    
    def log_state(self, message: str = "") -> None:
        """记录当前状态快照"""
        state = {
            "timestamp": time.time(),
            "window_title": self.get_window_title(),
            "mouse_position": self.get_current_mouse_position(),
            "screen_size": self.get_screen_size(),
            "message": message
        }
        self.take_screenshot(f"state_{int(time.time())}.png")
        logger.info(f"[状态] {state}")
    
    def get_window_info(self) -> Optional[WindowInfo]:
        """获取当前窗口信息"""
        try:
            if self.current_window:
                rect = self.current_window.rectangle()
                return WindowInfo(
                    title=self.get_window_title(),
                    process_id=self.app.process_id() if self.app else 0,
                    handle=self.current_window.handle,
                    rect=(rect.left, rect.top, rect.right, rect.bottom),
                    is_active=self.current_window.is_active()
                )
        except Exception:
            pass
        return None
    
    # =========================================================================
    # 便捷方法
    # =========================================================================
    
    def open_file(self, filepath: str) -> bool:
        """通用文件打开操作（Ctrl+O）"""
        try:
            # 获取文件路径的目录和文件名
            path = Path(filepath)
            if not path.exists():
                logger.error(f"[错误] 文件不存在: {filepath}")
                return False
            
            # 1. 打开文件对话框
            self.press_keys("Ctrl", "O")
            time.sleep(1)
            
            # 2. 输入文件路径
            self.type_text(str(path.absolute()))
            time.sleep(0.5)
            
            # 3. 按 Enter 确认
            self.press_keys("Enter")
            time.sleep(1)
            
            logger.info(f"[成功] 已打开文件: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 打开文件失败: {e}")
            return False
    
    def save_file(self, filepath: Optional[str] = None, save_as: bool = False) -> bool:
        """
        通用文件保存操作
        
        Args:
            filepath: 保存路径（如果为 None，只执行 Ctrl+S）
            save_as: 是否使用"另存为"
        """
        try:
            if save_as and filepath:
                self.press_keys("Ctrl", "Shift", "S")
                time.sleep(1)
                self.type_text(str(Path(filepath).absolute()))
                time.sleep(0.5)
                self.press_keys("Enter")
            else:
                self.press_keys("Ctrl", "S")
            
            time.sleep(1)
            logger.info(f"[成功] {'另存为' if save_as else '保存'}: {filepath or '(当前文件)'}")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 保存文件失败: {e}")
            return False
    
    def close_window(self) -> bool:
        """关闭窗口（Ctrl+W 或 Alt+F4）"""
        try:
            # 先尝试 Ctrl+W（大多数软件支持）
            self.press_keys("Ctrl", "W")
            time.sleep(0.5)
            
            # 如果没反应，尝试 Alt+F4
            self.press_keys("Alt", "F4")
            time.sleep(0.5)
            
            logger.info("[成功] 窗口已关闭")
            return True
        except Exception as e:
            logger.error(f"[错误] 关闭窗口失败: {e}")
            return False


# =============================================================================
# 独立测试
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s"
    )
    
    parser = argparse.ArgumentParser(description="GUI 自动化核心模块测试")
    parser.add_argument("--screenshot", action="store_true", help="执行截图测试")
    parser.add_argument("--window-info", action="store_true", help="显示窗口信息")
    parser.add_argument("--mouse-pos", action="store_true", help="显示鼠标位置")
    
    args = parser.parse_args()
    
    gui = GUIAutomation()
    
    if args.screenshot:
        print("执行截图测试...")
        path = gui.take_screenshot("test_screenshot.png")
        print(f"截图保存至: {path}")
    
    if args.window_info:
        print("获取窗口信息...")
        info = gui.get_window_info()
        if info:
            print(f"  标题: {info.title}")
            print(f"  PID: {info.process_id}")
            print(f"  位置: {info.rect}")
    
    if args.mouse_pos:
        print("获取鼠标位置...")
        pos = gui.get_current_mouse_position()
        print(f"  位置: {pos}")
    
    if not any(vars(args).values()):
        print("GUI 自动化模块已加载成功！")
        print(f"  - pywinauto: {'可用' if PYWINAUTO_AVAILABLE else '不可用'}")
        print(f"  - pyautogui: {'可用' if PYAUTOGUI_AVAILABLE else '不可用'}")
