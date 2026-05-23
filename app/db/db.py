from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

# Local imports
from models.user_roles import Role
from models.users import User
from core.security import get_password_hash
from core.config import settings

### ---------------------------------------------------------------- ###
## ------------------- PostgreSQL Database Setup ------------------- ###

# Get the postgres database URL from the settings
ASYNC_DATABASE_URL = settings.ASYNC_DATABASE_URL

# Create the asynchronous engine and sessionmaker
engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=False,  # Set to True for debugging
    pool_size=20,  # Adjust based on expected load
    max_overflow=4, 
)
# Create an async sessionmaker factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def seed_roles_if_not_exist():
    """Seeds the database with fixed roles if they don't already exist. 
    This is useful for testing and initial setup.
    Args:
        None
    Returns:
        None
    """
    async with AsyncSessionLocal() as session:
        for role_name in settings.FIXED_ROLES:
            result = await session.exec(select(Role).where(Role.name == role_name))
            exists = result.first()
            if not exists:
                session.add(Role(name=role_name))
        await session.commit()
    
async def create_admin_if_not_exists():
    """
    Creates an admin user if it doesn't exist. 
    Uses the boolean field is_admin to identify admin users.
    Args:
        None
    Returns:
        None 
    """
    async with AsyncSessionLocal() as session:
        #uses the boolean field instead of user_roles -> design decision must be made
        result = await session.exec(select(User).where(User.is_admin == True)) 
        admin_user = result.first()
        if not admin_user:
            admin_user = User(
                username=settings.ADMIN_USERNAME,
                hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
                is_admin=True,
                roles=[Role(name="admin")]
            )
            session.add(admin_user)
            await session.commit()

async def create_db_and_tables():
    """
    Seeds startup data after Alembic has created and migrated the schema.
    """
    await seed_roles_if_not_exist()
    await create_admin_if_not_exists()



async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a new session for each request and ensures it's closed after the request is done.
    This is a common pattern for database sessions in FastAPI.
    """
    async with AsyncSessionLocal() as session:
        """
        Use a context manager to ensure the session is properly closed after 
        the request is done, even if an error occurs.
        """
        yield session

### ---------------------------------------------------------------- ###


### ---------------------------------------------------------------- ###
## ------------------- Neo4j Graph Database Setup ------------------- ##

from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
# Get Neo4j connection parameters from settings
NEO4J_URI = settings.NEO4J_URI
NEO4J_USERNAME = settings.NEO4J_USERNAME
NEO4J_PASSWORD = settings.NEO4J_PASSWORD

def create_neo4j_graph_store():
    """Creates a Neo4j graph store instance using the connection parameters 
    defined in the settings.
    Args:   
        None
    Returns:
        An instance of Neo4jPropertyGraphStore that can be used to interact with 
            the Neo4j graph database.
    """
    graph_store = Neo4jPropertyGraphStore(
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD,
        url=NEO4J_URI,
    )
    return graph_store
