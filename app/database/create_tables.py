import app.models 

from app.database.session import engine
from app.models.base import Base

Base.metadata.create_all(
    bind=engine
)

print("Banco criado")