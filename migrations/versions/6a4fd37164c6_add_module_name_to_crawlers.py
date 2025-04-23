"""add_module_name_to_crawlers

Revision ID: [自動生成的ID]
Revises: 
Create Date: [自動生成的日期]

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column


# revision identifiers, used by Alembic.
revision: str = '6a4fd37164c6'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('crawlers', sa.Column('module_name', sa.String(100), nullable=True))
    
    # 創建一個臨時表對象用於更新
    crawlers = table('crawlers',
        column('crawler_name', sa.String),
        column('module_name', sa.String)
    )
    
    # 更新現有資料
    # 將 BnextCrawler 的 module_name 設置為 'bnext'
    op.execute(
        """
        UPDATE crawlers
        SET module_name = 'bnext'
        WHERE crawler_name = 'BnextCrawler'
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('crawlers', 'module_name')
