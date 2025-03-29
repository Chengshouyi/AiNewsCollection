from src.models import Articles, ArticleLinks, Crawlers, CrawlerTasks, CrawlerTaskHistory

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