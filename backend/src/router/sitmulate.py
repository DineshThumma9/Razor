





from fastapi.routing import APIRouter
router = APIRouter()


@router.post("/fake-evet")
def fake_event(event,amount,customer):
    return 



