from sqlalchemy.orm import DeclarativeBase
from src.error.errors import ValidationError, DataOperationError, NotFoundError, OptionError

class Base(DeclarativeBase):
    pass

