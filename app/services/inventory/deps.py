from typing import Annotated

from fastapi import Depends

from app.services.inventory.service import InventoryAdminService, InventoryService


async def get_inventory_service() -> InventoryService:
    return InventoryService()


async def get_inventory_admin_service() -> InventoryAdminService:
    return InventoryAdminService()


InventoryServiceDep = Annotated[InventoryService, Depends(get_inventory_service)]
InventoryAdminServiceDep = Annotated[
    InventoryAdminService, Depends(get_inventory_admin_service)
]
