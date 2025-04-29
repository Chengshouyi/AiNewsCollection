import sqlite3
import os

def fix_config_file_names():
    # 連接到資料庫
    conn = sqlite3.connect('/workspace/data/news.db')
    cursor = conn.cursor()
    
    try:
        # 獲取所有爬蟲記錄
        cursor.execute('SELECT id, crawler_name, config_file_name FROM crawlers;')
        crawlers = cursor.fetchall()
        
        print("當前爬蟲記錄:")
        for crawler in crawlers:
            print(f"ID: {crawler[0]}, 名稱: {crawler[1]}, 配置檔案: {crawler[2]}")
        
        # 修正配置檔案名稱
        for crawler in crawlers:
            crawler_id = crawler[0]
            crawler_name = crawler[1]
            old_config_name = crawler[2]
            
            # 使用固定的配置檔案名稱
            new_config_name = "bnext_crawler_config.json"
            
            if old_config_name != new_config_name:
                print(f"\n修正爬蟲 {crawler_name} 的配置檔案名稱:")
                print(f"從: {old_config_name}")
                print(f"到: {new_config_name}")
                
                # 更新資料庫
                cursor.execute(
                    'UPDATE crawlers SET config_file_name = ? WHERE id = ?',
                    (new_config_name, crawler_id)
                )
                
                # 檢查配置檔案是否存在
                config_path = os.path.join('/workspace/src/crawlers/configs', new_config_name)
                if not os.path.exists(config_path):
                    print(f"警告: 配置檔案 {new_config_name} 不存在於 {config_path}")
        
        # 提交更改
        conn.commit()
        print("\n資料庫更新完成")
        
    except Exception as e:
        print(f"錯誤: {str(e)}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    fix_config_file_names() 