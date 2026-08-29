from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
import uuid
from app.schemas.dashboard import UserCreate, Token
from app.core.security import get_password_hash, verify_password, create_access_token

router = APIRouter()
MOCK_USERS_DB = {}

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(payload: UserCreate):
    if payload.email in MOCK_USERS_DB:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_pwd = get_password_hash(payload.password)
    MOCK_USERS_DB[payload.email] = {
        "id": str(uuid.uuid4()),
        "email": payload.email,
        "password": hashed_pwd,
        "full_name": payload.full_name
    }
    return {"message": "User created successfully"}

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = MOCK_USERS_DB.get(form_data.username)
    if not user or not verify_password(form_data.password, user["password"]):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token = create_access_token(data={"sub": user["email"]})
    return {"access_token": access_token, "token_type": "bearer"}