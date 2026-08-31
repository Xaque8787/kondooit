"""Scraper module repository — persistence for installed modules and settings."""

from __future__ import annotations

from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from kondooit.infrastructure.models import ScraperModuleModel, ScraperSettingModel


class ScraperModuleRepository:
    """Database access for scraper module and setting records."""

    async def list_modules(self, session: AsyncSession) -> list[ScraperModuleModel]:
        stmt = select(ScraperModuleModel).order_by(ScraperModuleModel.installed_at)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_module(self, session: AsyncSession, module_id: str) -> ScraperModuleModel | None:
        stmt = select(ScraperModuleModel).where(ScraperModuleModel.module_id == module_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_module(
        self, session: AsyncSession, module_id: str, name: str,
        version: str, description: str, source_type: str, source_path: str,
    ) -> ScraperModuleModel:
        existing = await self.get_module(session, module_id)
        if existing:
            existing.name = name
            existing.version = version
            existing.description = description
            existing.source_type = source_type
            existing.source_path = source_path
        else:
            existing = ScraperModuleModel(
                module_id=module_id,
                name=name,
                version=version,
                description=description,
                source_type=source_type,
                source_path=source_path,
            )
            session.add(existing)
        await session.flush()
        return existing

    async def delete_module(self, session: AsyncSession, module_id: str) -> bool:
        model = await self.get_module(session, module_id)
        if model is None:
            return False
        await session.execute(
            sa_delete(ScraperSettingModel).where(ScraperSettingModel.module_id == module_id)
        )
        await session.delete(model)
        await session.flush()
        return True

    async def list_settings(self, session: AsyncSession, module_id: str) -> list[ScraperSettingModel]:
        stmt = select(ScraperSettingModel).where(
            ScraperSettingModel.module_id == module_id
        ).order_by(ScraperSettingModel.scraper_key)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_setting(
        self, session: AsyncSession, module_id: str, scraper_key: str
    ) -> ScraperSettingModel | None:
        stmt = select(ScraperSettingModel).where(
            ScraperSettingModel.module_id == module_id,
            ScraperSettingModel.scraper_key == scraper_key,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_setting(
        self, session: AsyncSession, module_id: str, scraper_key: str,
        enabled: bool, config: dict | None = None,
    ) -> ScraperSettingModel:
        existing = await self.get_setting(session, module_id, scraper_key)
        if existing:
            existing.enabled = enabled
            existing.config = config
        else:
            existing = ScraperSettingModel(
                module_id=module_id,
                scraper_key=scraper_key,
                enabled=enabled,
                config=config,
            )
            session.add(existing)
        await session.flush()
        return existing
