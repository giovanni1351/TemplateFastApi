from admin.admin_config import ADMIN_CONFIG
from sqladmin import Admin


def setup_admin(admin: Admin) -> None:
    admin.templates.env.globals["admin_config"] = ADMIN_CONFIG
    from admin.admin_view import UserAdmin

    admin.add_view(UserAdmin)
    from admin.admin_view import PasswordResetAdmin

    admin.add_view(PasswordResetAdmin)
    # <rbac>
    from admin.admin_view import PermissionAdmin

    admin.add_view(PermissionAdmin)
    from admin.admin_view import PermissionGroupAdmin

    admin.add_view(PermissionGroupAdmin)
    from admin.admin_rbac import RBACAdmin

    admin.add_view(RBACAdmin)
    # </rbac>
