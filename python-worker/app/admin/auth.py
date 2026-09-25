from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
import secrets
from app.core.config.settings import settings


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username", "")
        password = form.get("password", "")
        ok_user = secrets.compare_digest(username, settings.ADMIN_USERNAME)
        ok_pass = secrets.compare_digest(password, settings.ADMIN_PASSWORD)
        if ok_user and ok_pass:
            request.session.update({"admin_user": username})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return "admin_user" in request.session
