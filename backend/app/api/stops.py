from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import text


router = APIRouter(prefix="/stops", tags=["stops"])


class StopResponse(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    code: str | None = None


@router.get("", response_model=list[StopResponse])
def stops(request: Request, q: str | None = Query(None, max_length=100), limit: int = Query(100, ge=1, le=10000), offset: int = Query(0, ge=0, le=100000)):
    with request.app.state.engine.connect() as db:
        if q:
            rows = db.execute(text("SELECT id,name,lat,lng,code FROM stops WHERE LOWER(name) LIKE LOWER(:q) ORDER BY name, id LIMIT :limit OFFSET :offset"), {"q": f"%{q}%", "limit": limit, "offset": offset}).mappings().all()
        else:
            rows = db.execute(text("SELECT id,name,lat,lng,code FROM stops ORDER BY name, id LIMIT :limit OFFSET :offset"), {"limit": limit, "offset": offset}).mappings().all()
    return [StopResponse(**row) for row in rows]


@router.get("/{stop_id}", response_model=StopResponse)
def stop_by_id(stop_id: str, request: Request):
    with request.app.state.engine.connect() as db:
        row = db.execute(text("SELECT id,name,lat,lng,code FROM stops WHERE id=:id"), {"id": stop_id}).mappings().first()
    if not row:
        raise HTTPException(404, "Stop not found")
    return StopResponse(**row)
