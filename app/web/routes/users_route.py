### ----------------------------- USER ROUTERS ------------------------- ###
# Handle HTTP requests related to users. Routes call services to perform 
# business logic and return responses. Schemas are used for request validation 
# and response models. Repositories are NEVER called directly by routes, only by 
# services.
# NOTE 1: User services are explicitly permission-aware for deeper defense.
# Any changes in the routes have to be duplicated in # the service layer, so there are
# no mismatches between routes and services.
# NOTE 2: routers still use dependencies markers for authentication and
# authorization -> overkill (dependency injection takes care of this), but
# kept for consistency and clarity of the routes.
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated

# Local imports
from core.dependencies import CurrentUserDep, SessionDep, AdminUserDep, get_admin_user, get_current_user
from schemas.users_schemas import UserCreate, UserRead, UserCreatedResponse, UserUpdate
from services import users_service
from core.config import settings

# Define the router for user-related endpoints
router = APIRouter(prefix="/users", tags=["users"])

def to_user_read(user) -> UserRead:
    """Convert a user model to a UserRead schema.
    Args:
        user: The user model instance to convert.
    Returns:
        UserRead: The converted user data.
    """
    return UserRead(
        id=user.id,
        username=user.username,
        is_admin=user.is_admin,
        roles=[role.name for role in user.roles],
    )

###--------------------------- CREATE USER ------------------------- ###

@router.post("/register", 
             tags=["users"], 
             response_model=UserCreatedResponse, 
             dependencies=[Depends(get_admin_user)], # Only admins can create users, throws 403 if not admin
             status_code=201)
async def create_user(user_data: UserCreate, session: SessionDep, admin_user: AdminUserDep):
    """Create a new user. Admins only.
    Args:
        user_data (UserCreate): The data for the new user.
        session (SessionDep): The database session dependency.
        admin_user (AdminUserDep): The currently authenticated admin user, provided by dependency injection.
    Returns:
        UserCreatedResponse: The response containing the created user's information.
    Raises:
        HTTPException: If there is an error during user creation (400)."""
    try:
        user = await users_service.create_user_service(user_data, session, admin_user)
        return UserCreatedResponse(
            ok=True,
            user=to_user_read(user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    

###--------------------------- LOGIN ROUTE ------------------------- ###    

@router.post("/login", tags=["users"], status_code=200)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep):
    """Authenticate user and return access token.
    Args:
        form_data (OAuth2PasswordRequestForm): The username and password provided in the login form.
        session (SessionDep): Database session dependency.
    Returns:
        dict: Access token and token type if authentication is successful.
    Raises:
        HTTPException: If authentication fails with status code 400 and error message.    
    """
    try:
        access_token, token_type = await users_service.user_login_service(
            form_data.username, 
            form_data.password, 
            session=session)
        return {"access_token": access_token, "token_type": token_type}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

###--------------------------- GET USER INFO ----------------------- ###

@router.get("/me", tags=["users"], 
            dependencies=[Depends(get_current_user)], # authenticated users only, throws 401 if not authenticated 
            response_model=UserRead, status_code=200)
async def get_me_user(current_user: CurrentUserDep):
    """Get the current authenticated user's information.
    Args:
        current_user (CurrentUserDep): The currently authenticated user, provided by dependency injection.
    Returns:
        UserRead: The current user's information, including id, username, admin status, and roles
    """
    return to_user_read(current_user)

###--------------------------- LIST USERS ----------------------- ###

@router.get("/", tags=["users"],
            dependencies=[Depends(get_admin_user)],
            response_model=list[UserRead], status_code=200)
async def get_all_users(session: SessionDep, admin_user: AdminUserDep):
    """Get a list of all users. Admins only.
    Args:
        session (SessionDep): Database session dependency.
        admin_user (AdminUserDep): The currently authenticated admin user, provided by dependency injection.
    Returns:
        list[UserRead]: A list of all users.
    Raises:
        HTTPException: If the user is not authorized (403)."""
    try:
        users = await users_service.get_all_users_service(session, admin_user)
        return [to_user_read(user) for user in users]
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

###------------------------ GET USER INFO BY USERNAME --------------------- ###

@router.get("/{username}", 
            tags=["users"], 
            dependencies=[Depends(get_admin_user)], # Admins only, throws 403 if not admin
            response_model=UserRead, status_code=200)
async def get_user_by_username(username: str, session: SessionDep):
    """Get user information by username.
    Args:
        username (str): The username of the user to retrieve.
        session (SessionDep): Database session dependency.
    Returns:
        UserRead: The user's information, including id, username, admin status, and roles.
    Raises:
        HTTPException: If the user is not found with status code 404.
    """
    user = await users_service.get_user_by_username_service(username, session)

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    return to_user_read(user)

###---------------------------- UPDATE USER ------------------------ ###

@router.patch("/{user_id}", 
              tags=["users"], 
              response_model=UserRead, 
              dependencies=[Depends(get_admin_user)], # Only admins can update users, throws 403 if not admin
              status_code=200)
async def update_user(user_id: int, user_data: UserUpdate, session: SessionDep, admin_user: AdminUserDep):
    """Update user information. Only admins can update users.
    Args:
        user_id (int): The ID of the user to update.
        user_data (UserCreate): The new data for the user.
        session (SessionDep): Database session dependency.
        admin_user (AdminUserDep): The currently authenticated admin user, provided by dependency injection.
    Returns:
        UserRead: The updated user's information, including id, username, admin status, and roles
    Raises:
        HTTPException: If the user is not found with status code 404 or if validation fails with status code 400.  
    """
    try:
        user_update = await users_service.update_user_service(user_id, user_data, session, admin_user)
        return to_user_read(user_update)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

###--------------------------- DELETE USER ------------------------- ###

@router.delete("/{user_id}", 
               tags=["users"], 
               dependencies=[Depends(get_admin_user)], # Only admins can delete users, throws 403 if not admin
               status_code=204)
async def delete_user(user_id: int, session: SessionDep, admin_user: AdminUserDep):
    """Delete a user. Only admins can delete users.
    Args:
        user_id (int): The ID of the user to delete.
        session (SessionDep): Database session dependency.
        admin_user (AdminUserDep): The currently authenticated admin user, provided by dependency injection.
    Raises:
        HTTPException: If the user is not found with status code 404.
    """
    try:
        await users_service.delete_user_service(user_id, session, admin_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
