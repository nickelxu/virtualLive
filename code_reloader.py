import os
import sys
import time
import importlib
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 存储被监视的模块
watched_modules = {}
# 存储初始的修改时间
module_mtimes = {}
# 监控是否活跃
monitoring_active = False
# 监视线程
watcher_thread = None
# 重新加载的回调函数
reload_callback = None

class CodeChangeHandler(FileSystemEventHandler):
    """监听文件变化的处理器"""
    
    def on_modified(self, event):
        """当文件被修改时触发"""
        if event.is_directory:
            return
            
        # 检查是否是Python文件
        if not event.src_path.endswith('.py'):
            return
            
        # 获取模块名
        module_path = event.src_path
        module_name = os.path.basename(module_path)[:-3]  # 移除.py后缀
        
        # 检查这个模块是否在我们监视的列表中
        if module_name in watched_modules:
            module = watched_modules[module_name]
            print(f"检测到模块 {module_name} 变化，正在重新加载...")
            
            try:
                # 重新加载模块
                importlib.reload(module)
                print(f"模块 {module_name} 重新加载成功")
                
                # 如果有回调函数，调用它
                if reload_callback:
                    reload_callback(module_name)
                    
            except Exception as e:
                print(f"重新加载模块 {module_name} 失败: {str(e)}")

def start_monitoring(modules_to_watch=None, callback=None):
    """
    开始监控模块变化
    
    Args:
        modules_to_watch (list): 要监控的模块名列表，如果为None则监控所有已导入模块
        callback (function): 当模块重新加载时调用的函数
    """
    global monitoring_active, watcher_thread, reload_callback
    
    if monitoring_active:
        print("监控已经在运行中")
        return
        
    reload_callback = callback
    
    # 如果没有指定模块，监控所有已导入模块
    if modules_to_watch is None:
        modules_to_watch = [m.__name__ for m in sys.modules.values() 
                          if hasattr(m, '__file__') and m.__file__ 
                          and m.__file__.endswith('.py')]
                          
    # 保存要监控的模块
    for module_name in modules_to_watch:
        try:
            if module_name in sys.modules:
                module = sys.modules[module_name]
            else:
                module = importlib.import_module(module_name)
                
            watched_modules[module_name] = module
            
            # 记录模块文件的修改时间
            if hasattr(module, '__file__') and module.__file__:
                module_mtimes[module_name] = os.path.getmtime(module.__file__)
                
        except Exception as e:
            print(f"无法监视模块 {module_name}: {str(e)}")
    
    # 创建一个观察者来监控文件系统
    event_handler = CodeChangeHandler()
    observer = Observer()
    
    # 获取当前目录，并监控其中的Python文件
    current_dir = os.path.dirname(os.path.abspath(__file__))
    observer.schedule(event_handler, current_dir, recursive=True)
    observer.start()
    
    monitoring_active = True
    print(f"开始监控以下模块的变化: {', '.join(watched_modules.keys())}")
    
    # 创建线程来检查模块变化
    def monitor_thread():
        try:
            while monitoring_active:
                # 检查是否有模块被修改
                for module_name, module in list(watched_modules.items()):
                    if hasattr(module, '__file__') and module.__file__:
                        try:
                            mtime = os.path.getmtime(module.__file__)
                            if module_name in module_mtimes and mtime > module_mtimes[module_name]:
                                # 模块被修改，重新加载
                                print(f"检测到模块 {module_name} 变化，正在重新加载...")
                                try:
                                    importlib.reload(module)
                                    module_mtimes[module_name] = mtime
                                    print(f"模块 {module_name} 重新加载成功")
                                    
                                    # 如果有回调函数，调用它
                                    if reload_callback:
                                        reload_callback(module_name)
                                        
                                except Exception as e:
                                    print(f"重新加载模块 {module_name} 失败: {str(e)}")
                        except OSError:
                            # 文件可能被删除
                            pass
                
                # 每秒检查一次
                time.sleep(1)
        except Exception as e:
            print(f"监控线程出错: {str(e)}")
        finally:
            observer.stop()
    
    # 启动监控线程
    watcher_thread = threading.Thread(target=monitor_thread, daemon=True)
    watcher_thread.start()
    
    return observer

def stop_monitoring():
    """停止监控模块变化"""
    global monitoring_active, watcher_thread
    
    if not monitoring_active:
        print("监控未运行")
        return
        
    monitoring_active = False
    
    if watcher_thread:
        watcher_thread.join(timeout=2)
        watcher_thread = None
        
    print("已停止模块变化监控")

# 简单测试
if __name__ == "__main__":
    print("测试代码重载系统...")
    
    # 定义模块重新加载时的回调
    def on_module_reloaded(module_name):
        print(f"模块 {module_name} 已重新加载，这里可以添加额外的处理逻辑")
    
    # 开始监控
    observer = start_monitoring(callback=on_module_reloaded)
    
    try:
        print("请修改Python文件以测试重新加载功能 (按Ctrl+C退出)")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_monitoring()
        observer.join()
        print("测试结束") 