import asyncio
import sys
from decimal import Decimal
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.services.inventory.models import Product

OVERSELL_PRODUCT_ID = UUID('3fe44185-589a-4703-b640-40df8d7ea67f')
INITIAL_QTY = 50


async def seed() -> None:
    """
    Create or reset the oversell test product in the database.

    If a product with the predefined ID already exists, its quantity is reset
    to the initial value. Otherwise, a new product is created.

    Raises:
        Exception: If database operations fail.
    """
    engine = create_async_engine(url=str(settings.database_url), echo=False)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as session:
        result = await session.execute(
            select(Product).where(Product.id == OVERSELL_PRODUCT_ID)
        )
        product = result.scalar_one_or_none()

        if product:
            product.qty_available = INITIAL_QTY
            print(f'Product found, qty_available reset to {INITIAL_QTY}')
        else:
            product = Product(
                id=OVERSELL_PRODUCT_ID,
                name='Oversell Test Product',
                qty_available=INITIAL_QTY,
                price=Decimal('1.00'),
            )
            session.add(product)
            print(f'Created new product with qty_available={INITIAL_QTY}')

        await session.commit()
        print(f'Done. id={OVERSELL_PRODUCT_ID}, qty={INITIAL_QTY}')

    await engine.dispose()


asyncio.run(seed())
