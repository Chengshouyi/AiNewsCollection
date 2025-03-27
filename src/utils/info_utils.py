import os
import ast
import inspect
import importlib.util
import sys
import traceback

# 確保 src 目錄在 Python 路徑中
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

def analyze_class_details(folder_path):
    """
    深入分析類別的詳細資訊，包含關係、方法和屬性
    
    參數:
    folder_path (str): 要掃描的資料夾路徑
    
    回傳:
    dict: 包含類別詳細資訊的字典
    """
    class_details = {}
    
    # 收集所有 Python 檔案
    python_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    # 第一階段：解析所有檔案的 AST
    for file_path in python_files:
        with open(file_path, 'r', encoding='utf-8') as file:
            try:
                tree = ast.parse(file.read())
            except SyntaxError:
                continue
            
            # 找出所有類別定義
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_name = node.name
                    
                    # 初始化類別詳細資訊字典
                    class_details[class_name] = {
                        'file_path': file_path,
                        'inherits_from': [],
                        'has_a': [],
                        'uses': [],
                        'methods': [],
                        'attributes': [],
                        'class_methods': [],
                        'static_methods': []
                    }
                    
                    # 分析繼承關係
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            class_details[class_name]['inherits_from'].append(base.id)
                    
                    # 分析方法和屬性
                    for child in node.body:
                        # 方法分析
                        if isinstance(child, ast.FunctionDef):
                            method_name = child.name
                            
                            # 檢測方法類型
                            if method_name == '__init__':
                                # 在建構函式中找屬性
                                for sub_node in ast.walk(child):
                                    if isinstance(sub_node, ast.Attribute) and isinstance(sub_node.value, ast.Name) and sub_node.value.id == 'self':
                                        class_details[class_name]['attributes'].append(sub_node.attr)
                            
                            # 檢測方法裝飾器
                            is_class_method = False
                            is_static_method = False
                            for decorator in child.decorator_list:
                                if isinstance(decorator, ast.Name):
                                    if decorator.id == 'classmethod':
                                        is_class_method = True
                                    elif decorator.id == 'staticmethod':
                                        is_static_method = True
                            
                            # 記錄方法
                            if is_class_method:
                                class_details[class_name]['class_methods'].append(method_name)
                            elif is_static_method:
                                class_details[class_name]['static_methods'].append(method_name)
                            else:
                                class_details[class_name]['methods'].append(method_name)
                        
                        # 屬性分析（類別層級）
                        elif isinstance(child, ast.Assign):
                            for target in child.targets:
                                if isinstance(target, ast.Name):
                                    class_details[class_name]['attributes'].append(target.id)
    
    # 動態導入模組以獲取更多詳細資訊
    for class_name, details in class_details.items():
        try:
            module_path = os.path.relpath(details['file_path'], project_root).replace('/', '.').replace('\\', '.')[:-3]
            module = importlib.import_module(module_path)
            
            # 獲取類別
            cls = getattr(module, class_name, None)
            if cls and inspect.isclass(cls):
                # 使用關係分析
                methods_to_analyze = details['methods'] + details['class_methods'] + details['static_methods']
                
                # 添加 __init__ 方法到分析列表
                if hasattr(cls, '__init__'):
                    methods_to_analyze.append('__init__')
                
                for method_name in methods_to_analyze:
                    method = getattr(cls, method_name, None)
                    if method:
                        try:
                            # 嘗試獲取源代碼，如果失敗則跳過
                            source_code = inspect.getsource(method)
                            for other_class_name in class_details.keys():
                                if other_class_name in source_code and other_class_name != class_name:
                                    if other_class_name not in details['uses']:
                                        details['uses'].append(other_class_name)
                        except (OSError, TypeError) as e:
                            # 如果無法獲取源代碼，則打印更詳細的錯誤信息
                            print(f"無法獲取 {class_name} 的 {method_name} 方法源代碼: {e}")
                            # 可以選擇性地記錄方法信息
                            print(f"方法信息：{method}")
                            continue
        
        except ImportError as e:
            print(f"導入錯誤 {class_name}: {e}")
            print(traceback.format_exc())
        except Exception as e:
            print(f"無法完全分析 {class_name}: {e}")
            print(traceback.format_exc())
    
    return class_details

# 使用範例
if __name__ == '__main__':
    folder_path = './src'  # 替換成你要掃描的資料夾路徑
    class_analysis = analyze_class_details(folder_path)
    
    # 印出類別詳細資訊
    for cls, details in class_analysis.items():
        print(f"類別: {cls}")
        print(f"檔案路徑: {details['file_path']}")
        print("繼承自:", details['inherits_from'])
        print("普通方法:", details['methods'])
        print("類別方法:", details['class_methods'])
        print("靜態方法:", details['static_methods'])
        print("屬性:", details['attributes'])
        print("使用關係:", details['uses'])
        print("---")
