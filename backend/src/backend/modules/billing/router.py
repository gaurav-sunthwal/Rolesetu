import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import BadRequestError
from backend.db.session import get_db
from backend.modules.billing import funnel, service, subscriptions
from backend.modules.billing.funnel import FunnelEventWrite
from backend.modules.billing.schemas import OrderCreate, OrderRead, PaymentVerify, PlanRead
from backend.modules.billing.subscriptions import SubscriptionCheckout, SubscriptionVerify
from backend.modules.users.dependencies import get_db_user
from backend.modules.users.models import User

router = APIRouter(prefix="/billing", tags=["billing"])

# Razorpay's webhook bodies are small; anything far larger is not from them.
_MAX_WEBHOOK_BYTES = 256 * 1024


@router.get("/me", response_model=PlanRead)
async def my_plan(
    user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)
) -> PlanRead:
    return await service.get_plan(db, user_id=user.id)


@router.post("/orders", response_model=OrderRead)
async def create_order(
    payload: OrderCreate, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)
) -> OrderRead:
    """Starts a payment. The price is the server's, never the caller's."""
    return await service.create_order(db, user_id=user.id, email=user.email, plan=payload.plan)


@router.post("/orders/verify", response_model=PlanRead)
async def verify_payment(
    payload: PaymentVerify, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)
) -> PlanRead:
    """Turns on Pro once the checkout's signature and Razorpay both confirm the payment."""
    return await service.verify_payment(db, user_id=user.id, payload=payload)


class AutopayStart(BaseModel):
    attempt_id: uuid.UUID | None = None


@router.post("/subscriptions", response_model=SubscriptionCheckout)
async def start_autopay(
    payload: AutopayStart, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)
) -> SubscriptionCheckout:
    """Starts monthly autopay. The price is the server's, never the caller's."""
    return await subscriptions.start(
        db, user_id=user.id, email=user.email, attempt_id=payload.attempt_id
    )


@router.post("/subscriptions/verify", response_model=PlanRead)
async def verify_autopay(
    payload: SubscriptionVerify,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> PlanRead:
    """Turns on Pro once the mandate's signature and Razorpay both confirm it."""
    await subscriptions.verify(db, user_id=user.id, payload=payload)
    return await service.get_plan(db, user_id=user.id)


@router.post("/subscriptions/cancel", response_model=PlanRead)
async def cancel_autopay(
    user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)
) -> PlanRead:
    """Stops future charges; the month already paid for keeps running."""
    await subscriptions.cancel(db, user_id=user.id)
    return await service.get_plan(db, user_id=user.id)


@router.post("/funnel", status_code=204)
async def record_funnel_event(
    payload: FunnelEventWrite,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """A step of the upgrade the browser saw: the page, the payment window, a failure."""
    await funnel.record_from_client(db, user_id=user.id, event=payload)


@router.post("/webhooks/razorpay", status_code=200, include_in_schema=False)
async def razorpay_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Called by Razorpay, not by people: no sign-in, the signature is the permission."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > _MAX_WEBHOOK_BYTES:
        raise BadRequestError("Too large.")
    body = await request.body()
    if len(body) > _MAX_WEBHOOK_BYTES:
        raise BadRequestError("Too large.")
    await service.handle_webhook(
        db, body=body, signature=request.headers.get("x-razorpay-signature")
    )
    return {"status": "ok"}
