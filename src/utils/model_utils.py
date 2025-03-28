from src.models.articles_model import Articles
from src.models.article_links_model import ArticleLinks
from src.models.crawlers_model import Crawlers
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.crawler_task_history_model import CrawlerTaskHistory
from typing import Optional, Any, Callable
from datetime import datetime
from src.error.errors import ValidationError
from croniter import croniter
import re

def validate_str(
    field_name: str, 
    max_length: int = 255, 
    min_length: int = 0, 
    required: bool = False,
    regex: Optional[str] = None
):
    """
    字串驗證器
    
    Args:
        field_name: 欄位名稱
        max_length: 最大長度限制
        min_length: 最小長度限制
        required: 是否為必填
        regex: 可選的正則表達式驗證
    """
    import re

    def validator(value: Optional[str]) -> Optional[str]:
        # 處理 None 值
        if value is None:
            if required:
                raise ValidationError(f"{field_name}: 不能為 None")
            return None
        
        # 轉換並去除空白
        value = str(value).strip()
        
        # 檢查是否為空
        if not value:
            if required:
                raise ValidationError(f"{field_name}: 不能為空")
            return None
        
        # 長度驗證
        if len(value) > max_length:
            raise ValidationError(f"{field_name}: 長度不能超過 {max_length} 字元")
        
        if len(value) < min_length:
            raise ValidationError(f"{field_name}: 長度不能小於 {min_length} 字元")
        
        # 正則表達式驗證
        if regex:
            if not re.match(regex, value):
                raise ValidationError(f"{field_name}: 不符合指定的格式")
        
        return value
    
    return validator

def validate_cron_expression(
    field_name: str, 
    max_length: int = 255, 
    min_length: int = 0, 
    required: bool = False,
    regex: Optional[str] = None
) -> Callable[[Optional[str]], Optional[str]]:
    """
    Cron 表達式驗證器

    Args:
        field_name: 欄位名稱
        max_length: 最大長度限制
        min_length: 最小長度限制
        required: 是否為必填
        regex: 可選的正則表達式驗證 (預設為標準的 5 字段 cron 格式)

    Returns:
        驗證函數
    """
    
    def validator(value: Optional[str]) -> Optional[str]:
        # 允許 None 值，但不是必填
        if value is None:
            if required:
                raise ValidationError(f"{field_name}: 不能為 None")
            return None

        # 轉換為字串並去除空白
        value = str(value).strip()

        # 檢查是否為空
        if not value:
            if required:
                raise ValidationError(f"{field_name}: 不能為空")
            return None

        # 長度驗證
        if len(value) > max_length:
            raise ValidationError(f"{field_name}: 長度不能超過 {max_length} 字元")
        
        if len(value) < min_length:
            raise ValidationError(f"{field_name}: 長度不能小於 {min_length} 字元")

        # 檢查字段數量
        parts = value.split()
        if len(parts) != 5:
            raise ValidationError(f"{field_name}: Cron 表達式必須包含 5 個字段")
        
# 更靈活的 cron 格式正則表達式
        default_regex = r'^(\*|(\*\/\d+)|([0-5]?\d)(-([0-5]?\d))?(/\d+)?)(,(\*|(\*\/\d+)|([0-5]?\d)(-([0-5]?\d))?(/\d+)?))* ' + \
                       r'(\*|(\*\/\d+)|([01]?\d|2[0-3])(-([01]?\d|2[0-3]))?(/\d+)?)(,(\*|(\*\/\d+)|([01]?\d|2[0-3])(-([01]?\d|2[0-3]))?(/\d+)?))* ' + \
                       r'(\*|(\*\/\d+)|([0-2]?\d|3[01])(-([0-2]?\d|3[01]))?(/\d+)?)(,(\*|(\*\/\d+)|([0-2]?\d|3[01])(-([0-2]?\d|3[01]))?(/\d+)?))* ' + \
                       r'(\*|(\*\/\d+)|([1-9]|1[0-2])(-([1-9]|1[0-2]))?(/\d+)?)(,(\*|(\*\/\d+)|([1-9]|1[0-2])(-([1-9]|1[0-2]))?(/\d+)?))* ' + \
                       r'(\*|(\*\/\d+)|([0-7])(-([0-7]))?(/\d+)?)(,(\*|(\*\/\d+)|([0-7])(-([0-7]))?(/\d+)?))*$'

        # 如果提供了自定義 regex，則使用自定義 regex
        # 否則使用預設的 cron 格式 regex
        check_regex = regex or default_regex

        # 正則表達式驗證
        if not re.match(check_regex, value):
            raise ValidationError(f"{field_name}: 不符合標準 cron 格式")
        
        # 詳細驗證每個字段的範圍和格式
        field_ranges = [
            (0, 59),   # 分鐘
            (0, 23),   # 小時
            (1, 31),   # 日
            (1, 12),   # 月
            (0, 7)     # 星期 (0 和 7 都表示星期日)
        ]

        for i, (part, (min_val, max_val)) in enumerate(zip(parts, field_ranges)):
            # 驗證個別字段
            _validate_cron_field(field_name, i, part, min_val, max_val)

        # 使用 croniter 進行額外驗證
        try:
            croniter.expand(value)
        except (ValueError, TypeError) as e:
            raise ValidationError(f"{field_name}: Croniter 驗證失敗 - {str(e)}")

        return value

    def _validate_cron_field(field_name: str, field_index: int, part: str, min_val: int, max_val: int):
        """
        驗證個別 cron 字段
        """
        # 處理通配符和步進情況
        if part == '*':
            return  # 簡單的 * 是完全合法的，直接返回

        if part.startswith('*/'):
            try:
                step = int(part[2:])
                if step < 1:
                    raise ValidationError(f"{field_name}: 步進值必須大於0")
                    
                # 檢查步進值是否超出範圍
                if field_index == 0 and step > 59:  # 分鐘字段
                    raise ValidationError(f"{field_name}: 分鐘字段的步進值不能超過59")
                elif field_index == 1 and step > 23:  # 小時字段
                    raise ValidationError(f"{field_name}: 小時字段的步進值不能超過23")
                elif field_index == 2 and step > 31:  # 日字段
                    raise ValidationError(f"{field_name}: 日字段的步進值不能超過31")
                elif field_index == 3 and step > 12:  # 月字段
                    raise ValidationError(f"{field_name}: 月字段的步進值不能超過12")
                elif field_index == 4 and step > 7:  # 星期字段
                    raise ValidationError(f"{field_name}: 星期字段的步進值不能超過7")
                    
                return  # 步進通配符也是合法的，直接返回
            except ValueError:
                raise ValidationError(f"{field_name}: 無效的步進值")

        # 對於非通配符的情況，繼續後續驗證
        # 分割多個值
        sub_parts = part.split(',')
        for sub_part in sub_parts:
            # 處理範圍
            if '-' in sub_part:
                try:
                    start, end = map(int, sub_part.split('-'))
                    if not (min_val <= start <= max_val and min_val <= end <= max_val):
                        raise ValidationError(f"{field_name}: 欄位 {field_index + 1} 的範圍必須在 {min_val}-{max_val} 之間")
                    if start > end:
                        raise ValidationError(f"{field_name}: 欄位 {field_index + 1} 的起始值不能大於結束值")
                except ValueError:
                    raise ValidationError(f"{field_name}: 無效的範圍")
                continue

            # 處理單個值
            try:
                val = int(sub_part)
                if not (min_val <= val <= max_val):
                    raise ValidationError(f"{field_name}: 欄位 {field_index + 1} 的值必須在 {min_val}-{max_val} 之間")
            except ValueError:
                raise ValidationError(f"{field_name}: 無效的值")

    return validator

def validate_boolean(field_name: str, required: bool = False):
    """布林值驗證"""
    def validator(value: Any) -> Optional[bool]:
        if value is None:
            if required:
                raise ValidationError(f"{field_name}: 不能為 None")
            return None
        if value is not None and not isinstance(value, bool):
            try:
                # 嘗試轉換常見的布爾值字符串
                if isinstance(value, str):
                    value = value.lower()
                    if value in ('true', '1', 'yes'):
                        return True
                    if value in ('false', '0', 'no'):
                        return False
            except:
                pass
            raise ValidationError(f"{field_name}: 必須是布爾值")
        return value
    return validator

def validate_positive_int(field_name: str, required: bool = False):
    """正整數驗證"""
    def validator(value: Any) -> Optional[int]:
        if value is None:
            if required:
                raise ValidationError(f"{field_name}: 不能為空")
            return 0
        
        # 檢查浮點數
        if isinstance(value, float) and value != int(value):
            raise ValidationError(f"{field_name}: 必須是整數")
        
        # 字串轉換檢查
        if isinstance(value, str):
            try:
                # 檢查是否包含小數點
                if '.' in value:
                    raise ValidationError(f"{field_name}: 必須是整數")
                value = int(value)
            except ValueError:
                raise ValidationError(f"{field_name}: 必須是整數")
        
        # 其他類型轉換
        try:
            value = int(value)
        except (ValueError, TypeError):
            raise ValidationError(f"{field_name}: 必須是整數")
        
        if value <= 0:
            raise ValidationError(f"{field_name}: 必須大於0")
        
        return value
    return validator

def validate_datetime(field_name: str, required: bool = False):
    """日期時間驗證"""
    def validator(value: Any) -> Optional[datetime]:
        if value is None:
            if required:
                raise ValidationError(f"{field_name}: 不能為空")
            return None
        
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                raise ValidationError(f"{field_name}: 無效的日期時間格式。請使用 ISO 格式。")
        
        if isinstance(value, datetime):
            return value
        
        raise ValidationError(f"{field_name}: 必須是字串或日期時間。")
    
    return validator

def validate_url(
    field_name: str, 
    max_length: int = 1000, 
    required: bool = False,
    regex: Optional[str] = None
):
    """
    URL驗證器
    
    Args:
        field_name: 欄位名稱
        max_length: 最大長度限制
        required: 是否為必填
        regex: 可選的正則表達式驗證
    """

    def validator(value: Optional[str]) -> Optional[str]:
        if not value:
            if required:
                raise ValidationError(f"{field_name}: URL不能為空")
            return None
        
        # 先檢查長度
        if len(value) > max_length:
            raise ValidationError(f"{field_name}: 長度不能超過 {max_length} 字元")
        
        # 檢查 URL 格式
        if regex:
            if not re.match(regex, value):
                raise ValidationError(f"{field_name}: 無效的URL格式")    
        else:
            url_pattern = re.compile(
                r'^https?://'
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
                r'localhost|'
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
                r'(?::\d+)?'
                r'(?:/?|[/?]\S+)?$', re.IGNORECASE)
        
            if not url_pattern.match(value):
                raise ValidationError(f"{field_name}: 無效的URL格式")
        
        return value
    
    return validator

def print_model_constraints():
    """顯示模型約束信息的工具函數"""
    models = [Articles, ArticleLinks, Crawlers, CrawlerTasks, CrawlerTaskHistory]
    
    for model in models:
        # 打印表格相關資訊
        print(f"\n模型: {model.__name__}")
        print(f"表名: {model.__tablename__}")
        
        # 檢查列約束
        print("\n欄位約束:")
        for column in model.__table__.columns:
            nullable = "可為空" if column.nullable else "必填"
            unique = "唯一" if column.unique else "非唯一"
            default = f"預設值: {column.default}" if column.default is not None else "無預設值"
            print(f" - {column.name}: {column.type} - {nullable}, {unique}, {default}")
        
        # 檢查主鍵
        pk = [c.name for c in model.__table__.primary_key.columns]
        print(f"\n主鍵: {', '.join(pk)}")
        
        # 檢查外鍵
        fks = []
        for constraint in model.__table__.foreign_key_constraints:
            for fk in constraint.elements:
                fks.append({
                    'constrained_columns': [fk.parent.name],
                    'referred_table': fk.column.table.name,
                    'referred_columns': [fk.column.name]
                })
        
        if fks:
            print("\n外鍵:")
            for fk in fks:
                print(f" - {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}")
        
        # 檢查索引
        print("\n索引:")
        for index in model.__table__.indexes:
            unique_str = "唯一" if index.unique else "非唯一"
            columns = [c.name for c in index.columns]
            print(f" - {index.name}: {', '.join(columns)} ({unique_str})")
        
        # 檢查表級約束
        print("\n表級約束:")
        for constraint in model.__table__.constraints:
            constraint_type = constraint.__class__.__name__
            if hasattr(constraint, 'columns') and len(constraint.columns) > 0:
                columns = [col.name for col in constraint.columns]
                print(f" - {constraint_type}: {', '.join(columns)}")
            else:
                print(f" - {constraint_type}: {constraint}")
        
        # 檢查CheckConstraint約束
        check_constraints = [c for c in model.__table__.constraints if c.__class__.__name__ == 'CheckConstraint']
        if check_constraints:
            print("\nCheck約束:")
            for check in check_constraints:
                print(f" - {check.name}: {check.sqltext}")

def print_all_model_info():
    """打印所有模型信息"""
    all_model_info = get_all_model_info()
    for model_info in all_model_info:
        print(f"\n模型: {model_info['name']}")
        print(f"表名: {model_info['table']}")
        print(f"主鍵: {model_info['primary_key']}")
        print(f"外鍵: {model_info['foreign_keys']}")
        print(f"索引: {model_info['indexes']}")
        print(f"約束: {model_info['constraints']}")
        
        print("欄位:")
        for col_name, col_details in model_info['columns'].items():
            print(f" - {col_name}:")
            print(f"   類型: {col_details['type']}")
            print(f"   可為空: {col_details['nullable']}")
            print(f"   唯一: {col_details['unique']}")
            print(f"   預設值: {col_details['default']}")

def get_all_model_info():
    """獲取所有模型信息並返回字典結構，便於程式化處理"""
    models = [Articles, ArticleLinks, Crawlers, CrawlerTasks, CrawlerTaskHistory]
    return [get_model_info(model) for model in models]

def get_model_info(model_class):
    """獲取模型信息並返回字典結構，便於程式化處理"""
    info = {
        'name': model_class.__name__,
        'table': model_class.__tablename__,
        'columns': {},
        'primary_key': [],
        'foreign_keys': [],
        'indexes': [],
        'constraints': []
    }
    
    # 收集欄位信息
    for column in model_class.__table__.columns:
        info['columns'][column.name] = {
            'type': str(column.type),
            'nullable': column.nullable,
            'unique': column.unique,
            'default': str(column.default) if column.default is not None else None
        }
    
    # 主鍵
    info['primary_key'] = [c.name for c in model_class.__table__.primary_key.columns]
    
    # 外鍵
    for constraint in model_class.__table__.foreign_key_constraints:
        for fk in constraint.elements:
            info['foreign_keys'].append({
                'constrained_columns': [fk.parent.name],
                'referred_table': fk.column.table.name,
                'referred_columns': [fk.column.name]
            })
    
    # 索引
    for index in model_class.__table__.indexes:
        info['indexes'].append({
            'name': index.name,
            'column_names': [c.name for c in index.columns],
            'unique': index.unique
        })
    
    # 約束
    for constraint in model_class.__table__.constraints:
        constraint_info = {
            'type': constraint.__class__.__name__,
            'name': getattr(constraint, 'name', None)
        }
        
        if hasattr(constraint, 'columns') and len(constraint.columns) > 0:
            constraint_info['columns'] = [col.name for col in constraint.columns]
        
        if hasattr(constraint, 'sqltext'):
            constraint_info['sqltext'] = str(constraint.sqltext)
            
        info['constraints'].append(constraint_info)
    
    return info


if __name__ == "__main__":
    print_all_model_info()
    #print_model_constraints()
    
    # 示範如何獲取和處理模型信息
    #article_info = get_model_info(Article)
    #print(f"\n\n文章模型必填欄位:")
    #for col_name, col_info in article_info['columns'].items():
    #    if not col_info['nullable'] and ('default' not in col_info or col_info['default'] is None):
    #        print(f" - {col_name}")