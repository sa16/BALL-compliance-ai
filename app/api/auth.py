import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Users, InternalPolicy
from app.schemas.auth import Token, UserCreate
from app.core.security import (
    verify_password, 
    get_password_hash, 
    create_access_token, 
    decode_access_token, 
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from sqlalchemy.exc import IntegrityError
import os

logger = logging.getLogger("json_logger")

router = APIRouter(prefix="/auth", tags=["Authentication"])
oauth2_schema = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

#env check for cookie sercurity

IS_PROD = os.getenv("ENVIRONMENT","").lower=="production"

def get_token_from_request(request: Request, bearer_token: str = Depends(oauth2_schema)):
    cookie_token = request.cookies.get("access_token")
    if cookie_token: return cookie_token
    return bearer_token


def get_current_user(token: str=Depends(get_token_from_request),db= Depends(get_db)):
    credentials_exception=HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="could not validate credentials",
        headers={"WWW-authenticate": "Bearer"},

    )

    decoded = decode_access_token(token)
    if not decoded or not decoded.get("valid"):
        logger.warning({
            "event": "auth_failed", 
            "reason": decoded.get("error", "unknown") if decoded else "decode_failed"
        })
        raise credentials_exception
    
    payload = decoded.get("payload")
    user_id = payload.get("sub")

    #type checking
    if not isinstance(user_id, str):
        logger.warning({"event": "auth_failed", "reason": "invalid_sub_format"})
        raise credentials_exception
    
    user = db.query(Users).filter(Users.id == user_id).first() #not optimized, since each attempt leads to DB lookup , will refactor
    if user is None:
        logger.warning({"event": "auth_failed", "reason": "user_not_found"})
        raise credentials_exception

    if not user.is_active:
        logger.warning({"event": "auth_failed", "reason": "inactive_user"})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
        
    return user

def require_role(required_role: str):
    def role_checker(current_user: Users = Depends(get_current_user)):
        if current_user.role != required_role and current_user.role != "admin":
            logger.warning({
                "event": "rbac_blocked", 
                "user_id": str(current_user.id), 
                "attempted_role": required_role
            })
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operation not permitted. Insufficient privilege")
        return current_user
    return role_checker

@router.post("/register", response_model=dict)
def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    hashed_pw = get_password_hash(user_data.password)
    new_user = Users(username = user_data.username, hashed_password=hashed_pw, role="auditor")

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        logger.info({"event": "user_registered", "user_id": str(new_user.id)})
        return {"message": "User created successfully", "user_id": str(new_user.id)}
    except IntegrityError: 
        db.rollback()
        logger.warning({"event": "registration_failed", "reason": "username_taken"})
        raise HTTPException(status_code=400, detail="Username already registered")
    except Exception as e:
        db.rollback()
        logger.error({"event": "registration_failed", "error": type(e).__name__})
        raise HTTPException(status_code=500, detail="Database transaction failed")
    
@router.post("/login", response_model=Token)
def login_for_access_token(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(Users).filter(Users.username ==form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning({"event": "login_failed", "reason": "invalid_credentials"})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
            
        )
    access_token= create_access_token(user_id= str(user.id), username=user.username, role=user.role)

    response.set_cookie(
        secure=IS_PROD,
        samesite="none" if IS_PROD else "lax",
        httponly=True,
        key="access_token",
        value=access_token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES*60

    )

    logger.info({"event": "user_logged_in", "user_id": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer", "username": user.username, "role": user.role}

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token", secure=IS_PROD, samesite="strict" if IS_PROD else "lax")
    return {"message": "log out successful"}

@router.get("/bootstrap") #the Bootstrap Endpoint (Combines /me and /policies to cut latency)
def bootstrap_app(current_user: Users = Depends(get_current_user), db: Session = Depends(get_db)):
    """Single network call to initialize the frontend."""
    policies = db.query(InternalPolicy).all()
    return {
        "user": {
            "id": str(current_user.id),
            "username": current_user.username,
            "role": current_user.role
        },
        "policies": [{"id": str(p.id), "name": str(p.name)} for p in policies]
    }




