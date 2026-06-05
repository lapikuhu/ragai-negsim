from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

# Local imports
from app.models.user_roles import Role, UserRoleLink
from app.models.users import User
from app.core.security import get_password_hash
from app.core.config import settings

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
    Creates an admin user if no user has the fixed admin role.
    Args:
        None
    Returns:
        None 
    """
    async with AsyncSessionLocal() as session:
        role_result = await session.exec(select(Role).where(Role.name == "admin"))
        admin_role = role_result.first()
        if not admin_role:
            admin_role = Role(name="admin")
            session.add(admin_role)
            await session.commit()
            await session.refresh(admin_role)

        admin_result = await session.exec(
            select(User)
            .join(UserRoleLink, User.id == UserRoleLink.user_id)
            .where(UserRoleLink.role_id == admin_role.id)
        )
        admin_user = admin_result.first()
        if not admin_user:
            username_result = await session.exec(select(User).where(User.username == settings.ADMIN_USERNAME))
            admin_user = username_result.first()
            if admin_user:
                session.add(UserRoleLink(user_id=admin_user.id, role_id=admin_role.id))
            else:
                admin_user = User(
                    username=settings.ADMIN_USERNAME,
                    hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
                    roles=[admin_role]
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
    from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore

    graph_store = Neo4jPropertyGraphStore(
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD,
        url=NEO4J_URI,
    )
    return graph_store
