"""数据库管理脚本"""
import sys
import os
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from alembic.config import Config
from alembic import command
from db.session import sync_engine
from db.base import Base
import db.models  # noqa 导入所有模型以便 Base.metadata 能找到它们


def init_db():
    """初始化数据库 - 创建所有表"""
    print("🔧 初始化数据库...")
    try:
        Base.metadata.create_all(bind=sync_engine)
        print("✅ 数据库表创建成功！")
        print("\n📋 已创建的表：")
        for table in Base.metadata.sorted_tables:
            print(f"  - {table.name}")
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        sys.exit(1)


def migrate():
    """生成数据库迁移脚本"""
    print("🔧 生成数据库迁移脚本...")
    try:
        alembic_cfg = Config(str(project_root / "alembic.ini"))
        message = input("请输入迁移描述（回车使用默认）: ").strip()
        if not message:
            message = "auto migration"
        command.revision(alembic_cfg, autogenerate=True, message=message)
        print("✅ 迁移脚本生成成功！")
    except Exception as e:
        print(f"❌ 生成迁移脚本失败: {e}")
        sys.exit(1)


def upgrade():
    """应用数据库迁移（升级到最新版本）"""
    print("🔧 应用数据库迁移...")
    try:
        alembic_cfg = Config(str(project_root / "alembic.ini"))
        command.upgrade(alembic_cfg, "head")
        print("✅ 数据库迁移成功！")
    except Exception as e:
        print(f"❌ 数据库迁移失败: {e}")
        sys.exit(1)


def downgrade():
    """回滚数据库迁移（降级一个版本）"""
    print("🔧 回滚数据库迁移...")
    try:
        alembic_cfg = Config(str(project_root / "alembic.ini"))
        command.downgrade(alembic_cfg, "-1")
        print("✅ 数据库回滚成功！")
    except Exception as e:
        print(f"❌ 数据库回滚失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        action = sys.argv[1]
        if action == "init":
            init_db()
        elif action == "migrate":
            migrate()
        elif action == "upgrade":
            upgrade()
        elif action == "downgrade":
            downgrade()
        else:
            print(f"未知操作: {action}")
            print("可用操作: init, migrate, upgrade, downgrade")
            sys.exit(1)
    else:
        print("用法: python scripts/db.py <action>")
        print("可用操作:")
        print("  init      - 初始化数据库（创建所有表）")
        print("  migrate   - 生成迁移脚本")
        print("  upgrade   - 应用迁移（升级）")
        print("  downgrade - 回滚迁移（降级）")

