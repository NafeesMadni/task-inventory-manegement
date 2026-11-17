from app.api.v1.types import UserRef
from app.database.models import User


def _user_ref(u: User | None) -> UserRef | None:
    return (
        UserRef(id=u.id, username=u.username, role=u.role, email=u.email) if u else None
    )
