from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import csrf_protect, get_current_user
from app.directory import ad_authenticate
from app.models import User
from app.schemas import LoginIn, ProfileUpdateIn, UserOut
from app.services.auth_service import AuthService, NO_LOCAL_PASSWORD

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    return AuthService.login(db, data.cuid, data.password, request, response, ad_auth_fn=ad_authenticate)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(csrf_protect)])
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    AuthService.logout(db, user, request, response)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.put("/profile", response_model=UserOut, dependencies=[Depends(csrf_protect)])
def update_profile(
    data: ProfileUpdateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return AuthService.update_profile(db, user, data, request)
