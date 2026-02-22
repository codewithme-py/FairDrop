import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.main import logger
from app.services.inventory.models import Product, Reservation
from app.services.orders.internal import cancel_order_by_system
from app.services.orders.models import OrderStatus


async def release_expired_reservations(ctx: dict) -> None:
    session_maker: async_sessionmaker = ctx['session_maker']
    async with session_maker() as session:
        expired_reservations = await session.execute(
            select(Reservation.id).where(
                Reservation.status == OrderStatus.PENDING,
                Reservation.expires_at < datetime.datetime.now(datetime.UTC),
            )
        )
        expired_ids = expired_reservations.scalars().all()
        if not expired_ids:
            return
        logger.info(f'Found {len(expired_ids)} expired reservations. Processing...')
        for res_id in expired_ids:
            res_result = await session.execute(
                select(Reservation).with_for_update().where(Reservation.id == res_id)
            )
            reservation = res_result.scalar_one_or_none()
            if reservation is None:
                continue
            prod_result = await session.execute(
                select(Product)
                .with_for_update()
                .where(Product.id == reservation.product_id)
            )
            product = prod_result.scalar_one_or_none()
            if product:
                product.qty_available += reservation.qty_reserved
            reservation.status = OrderStatus.EXPIRED
            if reservation.order_id is not None:
                await cancel_order_by_system(session, reservation.order_id)
            await session.commit()
            logger.info(f'Released reservation {res_id}')
