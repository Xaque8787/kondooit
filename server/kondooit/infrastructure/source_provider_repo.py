"""SQLAlchemy repository for source provider configuration.

Uses the same provider_settings table as metadata providers, distinguished
by the key value. Source providers store their credentials in the
credentials JSONB column rather than the api_key text column.
"""

from __future__ import annotations

import json

from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from kondooit.application.source_provider_ports import SourceProviderConfig, SourceProviderStatus
from kondooit.application.source_provider_service import SourceProviderConfigRepository
from kondooit.infrastructure.models import ProviderSettingModel


class SqlAlchemySourceProviderConfigRepository(SourceProviderConfigRepository):

    async def get(self, session: AsyncSession, key: str) -> SourceProviderConfig | None:
        result = await session.execute(
            select(ProviderSettingModel).where(ProviderSettingModel.key == key)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def get_all(self, session: AsyncSession) -> list[SourceProviderConfig]:
        result = await session.execute(select(ProviderSettingModel))
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def save(self, session: AsyncSession, config: SourceProviderConfig) -> SourceProviderConfig:
        result = await session.execute(
            select(ProviderSettingModel).where(ProviderSettingModel.key == config.key)
        )
        model = result.scalar_one_or_none()
        if model is None:
            model = ProviderSettingModel(
                key=config.key,
                api_key="",
                status=config.status.value,
                priority=config.priority,
                credentials=config.credentials,
            )
            session.add(model)
        else:
            model.status = config.status.value
            model.priority = config.priority
            model.credentials = config.credentials
        await session.flush()
        return config

    async def delete(self, session: AsyncSession, key: str) -> bool:
        result = await session.execute(
            sa_delete(ProviderSettingModel).where(ProviderSettingModel.key == key)
        )
        return result.rowcount > 0

    @staticmethod
    def _to_domain(model: ProviderSettingModel) -> SourceProviderConfig:
        creds = model.credentials if model.credentials else {}
        if isinstance(creds, str):
            creds = json.loads(creds)
        return SourceProviderConfig(
            key=model.key,
            credentials=creds,
            status=SourceProviderStatus(model.status) if model.status in ("enabled", "disabled") else SourceProviderStatus.DISABLED,
            priority=model.priority,
        )
