from sqlalchemy import CheckConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def enum_column(enum_class, name: str) -> SAEnum:
    return SAEnum(
        enum_class,
        name=name,
        values_callable=lambda enum_cls: [item.value for item in enum_cls],
        native_enum=False,
        create_constraint=False,
        # create_constraint=True,
        validate_strings=True,
    )


def enum_check_constraint(enum_class, column_name: str, constraint_name: str):
    values = ", ".join(f"'{item.value}'" for item in enum_class)

    return CheckConstraint(
        f"{column_name} IN ({values})",
        name=constraint_name,
    )
