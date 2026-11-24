from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import text

from app.api.stops import StopResponse
from app.services.geometry_service import trip_geometry


router = APIRouter(prefix="/routes", tags=["routes"])


class GeometryResponse(BaseModel):
    status: str
    reason: str | None = None
    coordinates: list[tuple[float, float]]
    shapeId: str | None = None


class TripResponse(BaseModel):
    id: str
    serviceId: str
    headsign: str | None
    directionId: str | None
    shapeId: str | None


class RouteResponse(BaseModel):
    id: str
    shortName: str | None
    longName: str | None
    description: str | None
    agencyId: str


@router.get("", response_model=list[RouteResponse])
def routes(request: Request, q: str | None = Query(None, max_length=100), limit: int = Query(100, ge=1, le=3000), offset: int = Query(0, ge=0, le=100000)):
    sql = ('SELECT id, short_name AS "shortName", long_name AS "longName", '
           'description, agency_id AS "agencyId" FROM routes')
    if q:
        sql += " WHERE LOWER(short_name) LIKE LOWER(:q) OR LOWER(long_name) LIKE LOWER(:q)"
    sql += " ORDER BY short_name NULLS FIRST, id LIMIT :limit OFFSET :offset"
    with request.app.state.engine.connect() as db:
        rows = db.execute(text(sql), {"q": f"%{q}%", "limit": limit, "offset": offset}).mappings().all()
    return [RouteResponse(**row) for row in rows]


@router.get("/{route_id}", response_model=RouteResponse)
def route_by_id(route_id: str, request: Request):
    with request.app.state.engine.connect() as db:
        row = db.execute(text('''
            SELECT id, short_name AS "shortName", long_name AS "longName",
                   description, agency_id AS "agencyId" FROM routes WHERE id=:id
        '''), {"id": route_id}).mappings().first()
    if not row:
        raise HTTPException(404, "Route not found")
    return RouteResponse(**row)


@router.get("/{route_id}/trips", response_model=list[TripResponse])
def route_trips(route_id: str, request: Request, limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0, le=100000)):
    with request.app.state.engine.connect() as db:
        if not db.execute(text("SELECT 1 FROM routes WHERE id=:id"), {"id": route_id}).first():
            raise HTTPException(404, "Route not found")
        rows = db.execute(text('''
            SELECT id, service_id AS "serviceId", headsign,
                   direction_id AS "directionId", shape_id AS "shapeId"
            FROM trips WHERE route_id=:id ORDER BY id LIMIT :limit OFFSET :offset
        '''), {"id": route_id, "limit": limit, "offset": offset}).mappings().all()
    return [dict(row) for row in rows]


@router.get("/{route_id}/stops", response_model=list[StopResponse])
def route_stops(route_id: str, request: Request):
    with request.app.state.engine.connect() as db:
        if not db.execute(text("SELECT 1 FROM routes WHERE id=:id"), {"id": route_id}).first():
            raise HTTPException(404, "Route not found")
        rows = db.execute(text("SELECT DISTINCT s.id,s.name,s.lat,s.lng,s.code FROM trips t JOIN stop_times st ON st.trip_id=t.id JOIN stops s ON s.id=st.stop_id WHERE t.route_id=:id ORDER BY s.name"), {"id": route_id}).mappings().all()
    return [dict(row) for row in rows]


@router.get("/{route_id}/geometry", response_model=GeometryResponse)
def route_geometry(route_id: str, request: Request, trip_id: str | None = None,
                   from_stop_id: str | None = None, to_stop_id: str | None = None,
                   from_stop_sequence: int | None = Query(None, ge=0),
                   to_stop_sequence: int | None = Query(None, ge=0)):
    sequences_supplied = from_stop_sequence is not None or to_stop_sequence is not None
    if sequences_supplied and (
        not trip_id or from_stop_sequence is None or to_stop_sequence is None
        or from_stop_sequence >= to_stop_sequence
    ):
        raise HTTPException(422, "Segment geometry requires a trip and two increasing stop sequences")

    with request.app.state.engine.connect() as db:
        if sequences_supplied:
            result = trip_geometry(db, route_id, trip_id, from_stop_sequence, to_stop_sequence)
            if result is None:
                raise HTTPException(404, "Route or trip not found")
            return result

        if trip_id:
            row = db.execute(text("SELECT shape_id FROM trips WHERE id=:trip AND route_id=:route"),
                             {"trip": trip_id, "route": route_id}).first()
        else:
            row = db.execute(text("""
                SELECT t.shape_id FROM routes r LEFT JOIN trips t ON t.route_id=r.id
                WHERE r.id=:route ORDER BY t.shape_id IS NULL, t.id LIMIT 1
            """), {"route": route_id}).first()
        if row is None:
            raise HTTPException(404, "Route or trip not found")
        if from_stop_id is not None or to_stop_id is not None:
            return GeometryResponse(status="unavailable", reason="Stop sequences required for segment geometry",
                                    coordinates=[])
        shape_id = row[0]
        if not shape_id:
            return GeometryResponse(status="unavailable", reason="No shape is published", coordinates=[])
        points = db.execute(text("SELECT lat,lng FROM shape_points WHERE shape_id=:shape ORDER BY sequence"),
                            {"shape": shape_id}).all()
    if len(points) < 2:
        return GeometryResponse(status="unavailable", reason="Insufficient shape points",
                                coordinates=[], shapeId=shape_id)
    return GeometryResponse(status="available", coordinates=[tuple(point) for point in points], shapeId=shape_id)
