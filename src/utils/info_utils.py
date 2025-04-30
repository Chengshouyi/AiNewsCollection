"""提供分析專案結構、類別和模組詳細資訊的工具函數。"""

import os
import ast
import inspect
import importlib.util
import sys
import traceback
from datetime import datetime
import logging


logger = logging.getLogger(__name__)  # 使用統一的 logger

# 確保 src 目錄在 Python 路徑中
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
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
    
    python_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    for file_path in python_files:
        with open(file_path, 'r', encoding='utf-8') as file:
            try:
                tree = ast.parse(file.read())
            except SyntaxError:
                logger.warning("檔案 %s 存在語法錯誤，跳過分析", file_path)
                continue
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_name = node.name
                    
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
                    
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            class_details[class_name]['inherits_from'].append(base.id)
                    
                    for child in node.body:
                        if isinstance(child, ast.FunctionDef):
                            method_name = child.name
                            
                            if method_name == '__init__':
                                for sub_node in ast.walk(child):
                                    if isinstance(sub_node, ast.Attribute) and \
                                       isinstance(sub_node.value, ast.Name) and \
                                       sub_node.value.id == 'self':
                                        if sub_node.attr not in class_details[class_name]['attributes']:
                                            class_details[class_name]['attributes'].append(sub_node.attr)
                            
                            is_class_method = False
                            is_static_method = False
                            for decorator in child.decorator_list:
                                if isinstance(decorator, ast.Name):
                                    if decorator.id == 'classmethod':
                                        is_class_method = True
                                    elif decorator.id == 'staticmethod':
                                        is_static_method = True
                            
                            if is_class_method:
                                class_details[class_name]['class_methods'].append(method_name)
                            elif is_static_method:
                                class_details[class_name]['static_methods'].append(method_name)
                            else:
                                class_details[class_name]['methods'].append(method_name)
                        
                        elif isinstance(child, ast.Assign):
                            for target in child.targets:
                                if isinstance(target, ast.Name):
                                    if target.id not in class_details[class_name]['attributes']:
                                        class_details[class_name]['attributes'].append(target.id)
                        elif isinstance(child, ast.AnnAssign):
                             if isinstance(child.target, ast.Name):
                                if child.target.id not in class_details[class_name]['attributes']:
                                    class_details[class_name]['attributes'].append(child.target.id)
    
    for class_name, details in class_details.items():
        try:
            rel_path = os.path.relpath(details['file_path'], project_root)
            module_path_parts = rel_path[:-3].split(os.sep)
            if '__init__' in module_path_parts:
                 module_path_parts.remove('__init__')
            module_path = '.'.join(filter(None, module_path_parts))

            if module_path not in sys.modules:
                module = importlib.import_module(module_path)
            else:
                module = sys.modules[module_path]

            cls = getattr(module, class_name, None)
            if cls and inspect.isclass(cls):
                methods_to_analyze = list(set(details['methods'] + details['class_methods'] + details['static_methods']))

                if hasattr(cls, '__init__') and '__init__' not in methods_to_analyze:
                    methods_to_analyze.append('__init__')

                for method_name in methods_to_analyze:
                    method = getattr(cls, method_name, None)
                    if method:
                        try:
                            source_code = inspect.getsource(method)
                            for other_class_name in class_details.keys():
                                if other_class_name in source_code and other_class_name != class_name:
                                    if other_class_name not in details['uses']:
                                        details['uses'].append(other_class_name)
                        except (OSError, TypeError) as e:
                            logger.warning("無法獲取 %s 的 %s 方法源代碼: %s", class_name, method_name, e)
                            logger.warning("方法資訊：%s", method)
                            continue
        except ImportError as e:
            logger.error("導入錯誤 %s (模組路徑: %s): %s", class_name, module_path, e)
            logger.error(traceback.format_exc())
        except Exception as e:
            logger.error("分析類 %s 時發生未預期錯誤: %s", class_name, e)
            logger.error(traceback.format_exc())

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
    all_classes = {}
    python_files = []
    
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
        for file in files:
            if file.endswith('.py') and not file.startswith('__'):
                python_files.append(os.path.join(root, file))
    
    for file_path in python_files:
        try:
            rel_path = os.path.relpath(file_path, project_root)
            module_path = rel_path.replace(os.sep, '.')[:-3]

            spec = importlib.util.spec_from_file_location(module_path, file_path)
            if spec is None or spec.loader is None:
                logger.warning("無法載入模組規格 %s", module_path)
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_path] = module
            spec.loader.exec_module(module)

            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and obj.__module__ == module.__name__:
                    all_classes[f"{module_path}.{name}"] = obj
        except Exception as e:
            logger.error("分析檔案 %s (模組 %s) 收集類別時發生錯誤: %s", file_path, module_path, e)
            logger.error(traceback.format_exc())
    
    for file_path in python_files:
        try:
            rel_path = os.path.relpath(file_path, project_root)
            module_path = rel_path.replace(os.sep, '.')[:-3]

            if module_path not in sys.modules:
                 logger.warning("模組 %s 未在階段一成功載入，可能無法完整分析。", module_path)
                 spec = importlib.util.spec_from_file_location(module_path, file_path)
                 if spec is None or spec.loader is None:
                     continue
                 module = importlib.util.module_from_spec(spec)
                 spec.loader.exec_module(module)
            else:
                module = sys.modules[module_path]

            module_info = {
                'file_path': file_path,
                'classes': {},
                'functions': [],
                'imports': [],
                'variables': []
            }

            for name, obj in inspect.getmembers(module):
                try:
                    is_defined_here = hasattr(obj, '__module__') and obj.__module__ == module.__name__
                except Exception:
                    is_defined_here = False

                if not is_defined_here:
                    continue

                if inspect.isclass(obj):
                    class_info = {
                        'docstring': inspect.getdoc(obj),
                        'methods': [],
                        'attributes': [],
                        'inherits_from': []
                    }

                    for method_name, method_obj in inspect.getmembers(obj, inspect.isfunction):
                        if hasattr(method_obj, '__qualname__') and method_obj.__qualname__.startswith(obj.__name__ + '.'):
                            try:
                                params = inspect.signature(method_obj).parameters
                            except ValueError:
                                params = {}
                            class_info['methods'].append({
                                'name': method_name,
                                'docstring': inspect.getdoc(method_obj),
                                'parameters': list(params.keys())
                            })

                    for attr_name, _ in inspect.getmembers(obj, lambda x: not inspect.isroutine(x)):
                        if not attr_name.startswith('__') and attr_name in obj.__dict__:
                             class_info['attributes'].append(attr_name)

                    for base in obj.__bases__:
                        if base != object:
                            base_full_name = f"{base.__module__}.{base.__name__}"
                            project_prefix = project_root.split(os.sep)[-1]
                            if base.__module__.startswith(project_prefix) or base_full_name in all_classes:
                                class_info['inherits_from'].append(base_full_name)
                            else:
                                class_info['inherits_from'].append(base_full_name + " (外部)")

                    module_info['classes'][name] = class_info

                elif inspect.isfunction(obj):
                    try:
                        params = inspect.signature(obj).parameters
                    except ValueError:
                        params = {}
                    module_info['functions'].append({
                        'name': name,
                        'docstring': inspect.getdoc(obj),
                        'parameters': list(params.keys())
                    })

                elif not inspect.isclass(obj) and not inspect.isfunction(obj) and not inspect.ismodule(obj) and not name.startswith('__'):
                    module_info['variables'].append(name)

            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    tree = ast.parse(file.read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            module_info['imports'].append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        module_name = node.module if node.module else '.' * node.level
                        for alias in node.names:
                            module_info['imports'].append(f"from {module_name} import {alias.name}")
            except Exception as e:
                logger.warning("讀取或解析檔案 %s 的 AST 時發生錯誤: %s", file_path, e)

            if module_info['classes'] or module_info['functions'] or module_info['variables'] or module_info['imports']:
                 module_details[module_path] = module_info

        except Exception as e:
            logger.error("分析模組 %s 時發生未預期錯誤: %s", file_path, e)
            logger.error(traceback.format_exc())

    return module_details

def save_module_details_to_markdown(module_details, output_path):
    """
    將模組詳細資訊保存為 Markdown 格式
    
    參數:
    module_details (dict): 模組詳細資訊
    output_path (str): 輸出檔案路徑
    """
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# 專案模組分析報告\n\n")
            f.write(f"生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            sorted_module_paths = sorted(module_details.keys())

            for module_path in sorted_module_paths:
                details = module_details[module_path]
                f.write(f"## 模組: `{module_path}`\n\n")
                relative_file_path = os.path.relpath(details['file_path'], project_root)
                f.write(f"檔案路徑: `{relative_file_path}`\n\n")

                if details['classes']:
                    f.write("### 類別\n\n")
                    sorted_class_names = sorted(details['classes'].keys())
                    for class_name in sorted_class_names:
                        class_info = details['classes'][class_name]
                        f.write(f"#### `{class_name}`\n\n")
                        if class_info['docstring']:
                            f.write(f"> {class_info['docstring']}\n\n")

                        if class_info['inherits_from']:
                            f.write("##### 繼承自\n")
                            for base in class_info['inherits_from']:
                                f.write(f"- `{base}`\n")
                            f.write("\n")

                        if class_info['methods']:
                            f.write("##### 方法\n")
                            sorted_methods = sorted(class_info['methods'], key=lambda m: m['name'])
                            for method in sorted_methods:
                                params_str = ', '.join(method['parameters'])
                                f.write(f"- `{method['name']}({params_str})`\n")
                                if method['docstring']:
                                    f.write(f"  - 說明: {method['docstring']}\n")
                            f.write("\n")

                        if class_info['attributes']:
                            f.write("##### 類屬性\n")
                            sorted_attributes = sorted(class_info['attributes'])
                            for attr in sorted_attributes:
                                f.write(f"- `{attr}`\n")
                            f.write("\n")
                    f.write("\n")

                if details['functions']:
                    f.write("### 函數\n\n")
                    sorted_functions = sorted(details['functions'], key=lambda func: func['name'])
                    for func in sorted_functions:
                        params_str = ', '.join(func['parameters'])
                        f.write(f"- `{func['name']}({params_str})`\n")
                        if func['docstring']:
                            f.write(f"  - 說明: {func['docstring']}\n")
                    f.write("\n")

                if details['imports']:
                    f.write("### 導入\n\n")
                    sorted_imports = sorted(details['imports'])
                    for imp in sorted_imports:
                        f.write(f"- `{imp}`\n")
                    f.write("\n")

                if details['variables']:
                    f.write("### 模組變數\n\n")
                    sorted_variables = sorted(details['variables'])
                    for var in sorted_variables:
                        f.write(f"- `{var}`\n")
                    f.write("\n")

                f.write("---\n\n")
        logger.info("模組分析報告已成功保存至 %s", output_path)
    except IOError as e:
        logger.error("儲存模組分析報告 %s 時發生 IO 錯誤: %s", output_path, e)
    except Exception as e:
        logger.error("儲存模組分析報告時發生未預期錯誤: %s", e)
        logger.error(traceback.format_exc())

def print_module_details(module_details):
    """
    在終端機中打印模組詳細資訊 (格式較簡單)
    
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
                    print(f"    說明: {class_info['docstring'][:80]}...")
                print(f"    繼承自: {', '.join(class_info['inherits_from']) if class_info['inherits_from'] else '無'}")
                if class_info['methods']:
                    print("    方法:")
                    for method in class_info['methods']:
                        print(f"      - {method['name']}({', '.join(method['parameters'])})")
                if class_info['attributes']:
                    print("    類屬性:")
                    for attr in class_info['attributes']:
                        print(f"      - {attr}")

        if details['functions']:
            print("\n函數:")
            for func in details['functions']:
                 print(f"  - {func['name']}({', '.join(func['parameters'])})")

        if details['imports']:
            print("\n導入:")
            for imp in details['imports']:
                print(f"  - {imp}")

        if details['variables']:
            print("\n模組變數:")
            for var in details['variables']:
                print(f"  - {var}")

        print("\n" + "="*80)

if __name__ == '__main__':
    print("開始分析專案模組...")
    start_time = datetime.now()

    exclude_dirs = [
        'tests',
        '__pycache__',
        '.git',
        '.github',
        '.vscode',
        'venv',
        'env',
        'node_modules',
        'build',
        'dist',
        '.pytest_cache'
    ]

    module_details = analyze_module_details(project_root, exclude_dirs)

    output_dir = os.path.join(project_root, 'logs')
    output_path = os.path.join(output_dir, 'module_analysis_report.md')
    save_module_details_to_markdown(module_details, output_path)

    end_time = datetime.now()
    print(f"分析完成，耗時: {end_time - start_time}")
    print(f"分析報告已保存至: {output_path}")