import os
import ast
import inspect
import importlib.util
import sys
import traceback
from datetime import datetime

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

def analyze_module_details(folder_path, exclude_dirs=None):
    """
    分析整個專案的模組詳細資訊
    
    參數:
    folder_path (str): 要掃描的資料夾路徑
    exclude_dirs (list): 要排除的資料夾列表
    
    回傳:
    dict: 包含模組詳細資訊的字典
    """
    if exclude_dirs is None:
        exclude_dirs = []
        
    module_details = {}
    
    # 收集所有 Python 檔案
    python_files = []
    for root, dirs, files in os.walk(folder_path):
        # 排除指定的資料夾
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if file.endswith('.py') and not file.startswith('__'):
                python_files.append(os.path.join(root, file))
    
    # 第一階段：收集所有類別資訊
    all_classes = {}
    for file_path in python_files:
        try:
            # 轉換檔案路徑為模組路徑
            rel_path = os.path.relpath(file_path, project_root)
            module_path = rel_path.replace('/', '.').replace('\\', '.')[:-3]
            
            # 動態導入模組
            spec = importlib.util.spec_from_file_location(module_path, file_path)
            if spec is None or spec.loader is None:
                print(f"無法載入模組 {module_path}")
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 收集模組中的類別
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and obj.__module__ == module.__name__:
                    all_classes[f"{module_path}.{name}"] = obj
        except Exception as e:
            print(f"分析模組 {file_path} 時發生錯誤: {e}")
            print(traceback.format_exc())
    
    # 第二階段：分析每個模組的詳細資訊
    for file_path in python_files:
        try:
            rel_path = os.path.relpath(file_path, project_root)
            module_path = rel_path.replace('/', '.').replace('\\', '.')[:-3]
            
            spec = importlib.util.spec_from_file_location(module_path, file_path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            module_info = {
                'file_path': file_path,
                'classes': {},
                'functions': [],
                'imports': [],
                'variables': []
            }
            
            for name, obj in inspect.getmembers(module):
                if not hasattr(obj, '__module__') or obj.__module__ != module.__name__:
                    continue
                    
                if inspect.isclass(obj):
                    class_info = {
                        'docstring': inspect.getdoc(obj),
                        'methods': [],
                        'attributes': [],
                        'inherits_from': []
                    }
                    
                    # 收集方法
                    for method_name, method in inspect.getmembers(obj, inspect.isfunction):
                        if not method_name.startswith('__') and method.__module__ == module.__name__:
                            class_info['methods'].append({
                                'name': method_name,
                                'docstring': inspect.getdoc(method),
                                'parameters': inspect.signature(method).parameters
                            })
                    
                    # 收集屬性
                    for attr_name, attr in inspect.getmembers(obj, lambda x: not inspect.isfunction(x)):
                        if not attr_name.startswith('__'):
                            class_info['attributes'].append(attr_name)
                    
                    # 分析繼承關係
                    for base in obj.__bases__:
                        if base != object:
                            # 檢查基類是否在專案中
                            base_class_path = None
                            for class_path, class_obj in all_classes.items():
                                if class_obj == base:
                                    base_class_path = class_path
                                    break
                            
                            if base_class_path:
                                # 如果是專案中的類別，使用相對路徑
                                base_module = base.__module__
                                if base_module.startswith(project_root.replace('/', '.').replace('\\', '.')):
                                    base_class_path = base_class_path.replace(project_root.replace('/', '.').replace('\\', '.'), '')
                                class_info['inherits_from'].append(base_class_path)
                            else:
                                # 如果是外部類別，使用完整路徑
                                class_info['inherits_from'].append(f"{base.__module__}.{base.__name__}")
                    
                    module_info['classes'][name] = class_info
                
                elif inspect.isfunction(obj) and not name.startswith('__'):
                    module_info['functions'].append({
                        'name': name,
                        'docstring': inspect.getdoc(obj),
                        'parameters': inspect.signature(obj).parameters
                    })
                
                elif not name.startswith('__'):
                    module_info['variables'].append(name)
            
            # 分析導入
            with open(file_path, 'r', encoding='utf-8') as file:
                tree = ast.parse(file.read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for name in node.names:
                            module_info['imports'].append(name.name)
                    elif isinstance(node, ast.ImportFrom):
                        module_info['imports'].append(f"{node.module}.{node.names[0].name}")
            
            if module_info['classes'] or module_info['functions'] or module_info['variables']:
                module_details[module_path] = module_info
            
        except Exception as e:
            print(f"分析模組 {file_path} 時發生錯誤: {e}")
            print(traceback.format_exc())
    
    return module_details

def save_module_details_to_markdown(module_details, output_path):
    """
    將模組詳細資訊保存為 Markdown 格式
    
    參數:
    module_details (dict): 模組詳細資訊
    output_path (str): 輸出檔案路徑
    """
    # 確保輸出目錄存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        # 寫入標題
        f.write(f"# 專案模組分析報告\n\n")
        f.write(f"生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # 寫入每個模組的資訊
        for module_path, details in module_details.items():
            f.write(f"## 模組: {module_path}\n\n")
            f.write(f"檔案路徑: {details['file_path']}\n\n")
            
            # 寫入類別資訊
            if details['classes']:
                f.write("### 類別\n\n")
                for class_name, class_info in details['classes'].items():
                    f.write(f"#### {class_name}\n\n")
                    if class_info['docstring']:
                        f.write(f"{class_info['docstring']}\n\n")
                    
                    f.write("##### 繼承關係\n")
                    f.write(f"- 繼承自: {', '.join(class_info['inherits_from']) if class_info['inherits_from'] else '無'}\n\n")
                    
                    f.write("##### 方法\n")
                    for method in class_info['methods']:
                        f.write(f"- {method['name']}\n")
                        if method['docstring']:
                            f.write(f"  - 說明: {method['docstring']}\n")
                        f.write(f"  - 參數: {', '.join(method['parameters'].keys())}\n")
                    f.write("\n")
                    
                    f.write("##### 屬性\n")
                    for attr in class_info['attributes']:
                        f.write(f"- {attr}\n")
                    f.write("\n")
            
            # 寫入函數資訊
            if details['functions']:
                f.write("### 函數\n\n")
                for func in details['functions']:
                    f.write(f"- {func['name']}\n")
                    if func['docstring']:
                        f.write(f"  - 說明: {func['docstring']}\n")
                    f.write(f"  - 參數: {', '.join(func['parameters'].keys())}\n")
                f.write("\n")
            
            # 寫入導入資訊
            if details['imports']:
                f.write("### 導入\n\n")
                for imp in details['imports']:
                    f.write(f"- {imp}\n")
                f.write("\n")
            
            # 寫入變數資訊
            if details['variables']:
                f.write("### 變數\n\n")
                for var in details['variables']:
                    f.write(f"- {var}\n")
                f.write("\n")
            
            f.write("---\n\n")

def print_module_details(module_details):
    """
    在終端機中打印模組詳細資訊
    
    參數:
    module_details (dict): 模組詳細資訊
    """
    for module_path, details in module_details.items():
        print(f"\n模組: {module_path}")
        print(f"檔案路徑: {details['file_path']}")
        
        if details['classes']:
            print("\n類別:")
            for class_name, class_info in details['classes'].items():
                print(f"\n  {class_name}")
                if class_info['docstring']:
                    print(f"    說明: {class_info['docstring']}")
                print(f"    繼承自: {', '.join(class_info['inherits_from']) if class_info['inherits_from'] else '無'}")
                print("    方法:")
                for method in class_info['methods']:
                    print(f"      - {method['name']}")
                print("    屬性:")
                for attr in class_info['attributes']:
                    print(f"      - {attr}")
        
        if details['functions']:
            print("\n函數:")
            for func in details['functions']:
                print(f"  - {func['name']}")
        
        if details['imports']:
            print("\n導入:")
            for imp in details['imports']:
                print(f"  - {imp}")
        
        if details['variables']:
            print("\n變數:")
            for var in details['variables']:
                print(f"  - {var}")
        
        print("\n" + "="*80)

if __name__ == '__main__':
    # 確保專案根目錄在 Python 路徑中
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    # 掃描整個專案，排除tests資料夾
    folder_path = project_root
    exclude_dirs = ['tests', '__pycache__', '.git', '.github', '.vscode']
    module_details = analyze_module_details(folder_path, exclude_dirs)
    
    # 輸出到終端機
    print_module_details(module_details)
    
    # 保存到檔案
    output_path = os.path.join(project_root, 'logs', 'class_data.md')
    save_module_details_to_markdown(module_details, output_path)
    print(f"\n分析報告已保存至: {output_path}")