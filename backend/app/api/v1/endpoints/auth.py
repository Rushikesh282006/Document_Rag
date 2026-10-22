from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentUser, DatabaseSession
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with unique email and hashed password.",
)
@limiter.limit("5/minute")
async def register_user(
    request: Request,
    user_in: UserCreate,
    db: DatabaseSession,
) -> UserResponse:
    # Check if user with this email already exists
    stmt = select(User).where(User.email == user_in.email)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    # Create new user
    new_user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user


@router.post(
    "/login",
    response_model=Token,
    summary="OAuth2 Password Login",
    description="OAuth2 compatible token login (form data). In Swagger UI, enter email as username.",
)
@limiter.limit("10/minute")
async def login_access_token(
    request: Request,
    db: DatabaseSession,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Token:
    stmt = select(User).where(User.email == form_data.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account.",
        )

    access_token = create_access_token(subject=user.id)
    return Token(access_token=access_token, token_type="bearer")


@router.post(
    "/login/json",
    response_model=Token,
    summary="JSON Login",
    description="JSON payload login for programmatic API clients.",
)
@limiter.limit("10/minute")
async def login_json(
    request: Request,
    credentials: UserLogin,
    db: DatabaseSession,
) -> Token:
    stmt = select(User).where(User.email == credentials.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account.",
        )

    access_token = create_access_token(subject=user.id)
    return Token(access_token=access_token, token_type="bearer")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Retrieve the profile of the currently authenticated tenant.",
)
async def get_current_user_profile(
    current_user: CurrentUser,
) -> UserResponse:
    return current_user
