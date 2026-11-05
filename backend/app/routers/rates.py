from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

from ..nbrb import get_rate, refresh_rate
from ..security import get_current_user

router = APIRouter(prefix="/api/rates", tags=["rates"])


@router.get("/current")
def current(user: dict = Depends(get_current_user)):
    return {"usd_byn": get_rate(), "date": date.today().isoformat()}


@router.post("/refresh")
def refresh(user: dict = Depends(get_current_user)):
    try:
        rate = refresh_rate()
    except Exception:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Не удалось получить курс с НБРБ")
    return {"usd_byn": rate, "date": date.today().isoformat()}
