from flask import Blueprint, render_template
# from flask_login import login_required # 如果需要登入

# 注意：template_folder 和 static_folder 是相對於藍圖定義檔案的位置
# 如果 views.py 在 src/web/routes/，而 templates 在 src/web/templates/
# 則 template_folder='../templates' 是正確的
# static_folder 同理
view_bp = Blueprint('views', __name__,
                    template_folder='../templates',
                    static_folder='../static',
                    static_url_path='/web/static') # 指定靜態文件的 URL 路徑，避免衝突

@view_bp.route('/')
# @login_required # 保護路由
def index():
    # 可能需要從服務獲取一些初始數據
    return render_template('index.html')

@view_bp.route('/crawlers')
# @login_required
def crawlers_page():
    return render_template('crawlers.html')

@view_bp.route('/tasks')
# @login_required
def tasks_page():
    return render_template('tasks.html')

@view_bp.route('/articles')
# @login_required
def articles_page():
     return render_template('articles.html') # 文章列表

@view_bp.route('/articles/<int:article_id>')
# @login_required
def article_view_page(article_id):
     # 可以先傳遞 ID，讓 JS 去加載數據
     # 或者後端先加載部分數據
     return render_template('article_view.html', article_id=article_id)
