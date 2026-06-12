from admin.admin_config import ADMIN_CONFIG
from sqladmin import Admin


def setup_admin(admin: Admin) -> None:

    admin.templates.env.globals["admin_config"] = ADMIN_CONFIG
    from admin.admin_view import UserAdmin

    admin.add_view(UserAdmin)
