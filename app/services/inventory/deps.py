from typing import Annotated

from fastapi import Depends

from app.services.inventory.service import InventoryAdminService, InventoryService


async def get_inventory_service() -> InventoryService:
    """
    Create and return an InventoryService instance.

    Returns:
        A new InventoryService instance for dependency injection.
    """
    return InventoryService()


async def get_inventory_admin_service() -> InventoryAdminService:
    """
    Create and return an InventoryAdminService instance.

    Returns:
        A new InventoryAdminService instance for dependency injection.
    """
    return InventoryAdminService()


InventoryServiceDep = Annotated[InventoryService, Depends(get_inventory_service)]
InventoryAdminServiceDep = Annotated[
    InventoryAdminService, Depends(get_inventory_admin_service)
]
