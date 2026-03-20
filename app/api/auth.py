import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Users
from app.schemas.auth import Token, UserCreate
from app.core.security import (
    verify_password, 
    get_password_hash, 
    create_access_token, 
    decode_access_token
)
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("json_logger")

router = APIRouter(prefix="/auth", tags=["Authentication"])
oauth2_schema = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(token: str=Depends(oauth2_schema),db= Depends(get_db)):
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
        logger.error({"event": "registration_failed", "error": str(e)})
        raise HTTPException(status_code=500, detail="Database transaction failed")
    
@router.post("/login", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(Users).filter(Users.username ==form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning({"event": "login_failed", "reason": "invalid_credentials"})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token= create_access_token(user_id= str(user.id), username=user.username, role=user.role)

    logger.info({"event": "user_logged_in", "user_id": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}



