from fastapi import Header, HTTPException
from app.client import supabase

async def get_current_user(authorization: str = Header(...)):
    try:
        token = authorization.replace("Bearer ", "").strip()
        user_response = supabase.auth.get_user(token)
        if not user_response.user:
            raise HTTPException(status_code=401, detail="You are not allowed to do this.")
        return user_response.user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="You are not allowed to do this.")