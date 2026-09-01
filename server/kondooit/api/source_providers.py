"""Source provider API controller.

Provides endpoints for listing, configuring, and testing source
providers (TorBox, Easynews). Also provides the unified source
search endpoint that runs scrapers + cache checks + direct search.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

import httpx
from litestar import Controller, get, put, post, delete
from litestar.response import Stream
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from kondooit.application.source_provider_ports import SourceProviderConfig, SourceProviderStatus, SourceSearchRequest
from kondooit.application.source_provider_service import SourceProviderService, ScraperModuleManager
from kondooit.infrastructure.scraper_loader import load_module
from kondooit.infrastructure.scraper_module_repo import ScraperModuleRepository

logger = logging.getLogger(__name__)


class CredentialFieldResponse(BaseModel):
    name: str
    label: str
    field_type: str
    required: bool
    placeholder: str


class SourceProviderInfoResponse(BaseModel):
    key: str
    name: str
    description: str
    capabilities: list[str]
    credential_fields: list[CredentialFieldResponse]


class SourceProviderConfigResponse(BaseModel):
    key: str
    credentials: dict[str, str]
    status: str
    priority: int


class SourceProviderConfigRequest(BaseModel):
    credentials: dict[str, str] = {}
    status: str = "disabled"
    priority: int = 100


class TestConnectionResponse(BaseModel):
    key: str
    connected: bool


class SourceSearchRequestBody(BaseModel):
    title: str
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    tmdb_id: int | None = None
    content_type: str = "movie"


class ResolveRequest(BaseModel):
    info_hash: str
    provider_key: str = "torbox"
    file_index: int | None = None
    season: int | None = None
    episode: int | None = None


class ResolveResponse(BaseModel):
    success: bool
    detail: str
    stream_url: str | None = None


class AddTorrentRequest(BaseModel):
    info_hash: str
    provider_key: str = "torbox"


class AddTorrentResponse(BaseModel):
    success: bool
    detail: str


class SourceResultResponse(BaseModel):
    provider_key: str
    filename: str
    size_bytes: int
    quality: str
    codec: str
    duration_seconds: int | None = None
    info_hash: str | None = None
    seeders: int | None = None
    source_type: str = "direct"
    scraper_source: str | None = None
    stream_url: str | None = None
    is_season_pack: bool = False
    file_count: int = 0


class ScraperInfoResponse(BaseModel):
    key: str
    name: str
    tier: int
    category: str
    content_types: list[str]
    enabled: bool


class ScraperModuleResponse(BaseModel):
    module_id: str
    name: str
    version: str
    description: str
    scrapers: list[ScraperInfoResponse]


class ScraperToggleRequest(BaseModel):
    enabled: bool


class ModuleInstallRequest(BaseModel):
    source_path: str


class ModuleInstallResponse(BaseModel):
    module_id: str
    name: str
    version: str
    description: str
    scrapers: list[ScraperInfoResponse]


class SourceProviderController(Controller):
    path = "/source-providers"

    @get("/")
    async def list_providers(
        self,
        source_provider_service: SourceProviderService,
    ) -> list[SourceProviderInfoResponse]:
        providers = source_provider_service.list_providers()
        return [
            SourceProviderInfoResponse(
                key=p.key,
                name=p.name,
                description=p.description,
                capabilities=[c.value for c in p.capabilities],
                credential_fields=[
                    CredentialFieldResponse(
                        name=f.name,
                        label=f.label,
                        field_type=f.field_type,
                        required=f.required,
                        placeholder=f.placeholder,
                    )
                    for f in p.credential_fields
                ],
            )
            for p in providers
        ]

    @get("/easynews/stream")
    async def easynews_stream(
        self,
        post_hash: str,
        filename: str,
        session: AsyncSession,
        source_provider_service: SourceProviderService,
        dl_farm: str = "",
        dl_port: str = "",
        sig: str = "",
        ext: str = "",
    ) -> Stream:
        """Proxy an Easynews download through the server with stored credentials.

        Clients call this endpoint instead of hitting Easynews directly,
        so they never need to handle authentication.
        """
        config = await source_provider_service.get_config(session, "easynews")
        if config is None or config.status != SourceProviderStatus.ENABLED:
            from litestar.exceptions import NotFoundException
            raise NotFoundException("Easynews provider not configured")

        username = config.credentials.get("username", "")
        password = config.credentials.get("password", "")
        if not username or not password:
            from litestar.exceptions import NotFoundException
            raise NotFoundException("Easynews credentials not configured")

        ext_suffix = f".{ext}" if ext else ""
        safe_name = quote(filename, safe="")
        if dl_farm and dl_port:
            upstream_url = f"https://{dl_farm}/dl/{dl_port}/{post_hash}{ext_suffix}/{safe_name}"
        else:
            upstream_url = f"https://members.easynews.com/dl/{post_hash}/{safe_name}"
        if sig:
            upstream_url += f"?sig={sig}&ns=N"

        async def stream_generator():
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                async with client.stream(
                    "GET",
                    upstream_url,
                    auth=(username, password),
                ) as resp:
                    if resp.status_code != 200:
                        logger.warning("Easynews upstream returned %d for %s", resp.status_code, post_hash)
                        return
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        yield chunk

        content_type = "video/mp4"
        if ext in ("mkv",):
            content_type = "video/x-matroska"
        elif ext in ("avi",):
            content_type = "video/x-msvideo"
        elif ext in ("ts", "m2ts"):
            content_type = "video/mp2t"
        elif ext in ("webm",):
            content_type = "video/webm"

        return Stream(
            stream_generator(),
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "Accept-Ranges": "none",
            },
        )

    @get("/{key:str}")
    async def get_config(
        self,
        key: str,
        session: AsyncSession,
        source_provider_service: SourceProviderService,
    ) -> SourceProviderConfigResponse:
        config = await source_provider_service.get_config(session, key)
        if config is None:
            return SourceProviderConfigResponse(
                key=key, credentials={}, status="disabled", priority=100
            )
        return SourceProviderConfigResponse(
            key=config.key,
            credentials=config.credentials,
            status=config.status.value,
            priority=config.priority,
        )

    @put("/{key:str}")
    async def save_config(
        self,
        key: str,
        data: SourceProviderConfigRequest,
        session: AsyncSession,
        source_provider_service: SourceProviderService,
    ) -> SourceProviderConfigResponse:
        config = SourceProviderConfig(
            key=key,
            credentials=data.credentials,
            status=SourceProviderStatus(data.status),
            priority=data.priority,
        )
        saved = await source_provider_service.save_config(session, config)
        return SourceProviderConfigResponse(
            key=saved.key,
            credentials=saved.credentials,
            status=saved.status.value,
            priority=saved.priority,
        )

    @delete("/{key:str}")
    async def delete_config(
        self,
        key: str,
        session: AsyncSession,
        source_provider_service: SourceProviderService,
    ) -> None:
        await source_provider_service.delete_config(session, key)

    @post("/{key:str}/test")
    async def test_connection(
        self,
        key: str,
        session: AsyncSession,
        source_provider_service: SourceProviderService,
    ) -> TestConnectionResponse:
        connected = await source_provider_service.test_provider(session, key)
        return TestConnectionResponse(key=key, connected=connected)

    @post("/search")
    async def search_sources(
        self,
        data: SourceSearchRequestBody,
        session: AsyncSession,
        source_provider_service: SourceProviderService,
    ) -> list[SourceResultResponse]:
        query = SourceSearchRequest(
            title=data.title,
            year=data.year,
            season=data.season,
            episode=data.episode,
            tmdb_id=data.tmdb_id,
            content_type=data.content_type,
        )
        results = await source_provider_service.search_sources(session, query)
        return [
            SourceResultResponse(
                provider_key=r.provider_key,
                filename=r.filename,
                size_bytes=r.size_bytes,
                quality=r.quality,
                codec=r.codec,
                duration_seconds=r.duration_seconds,
                info_hash=r.info_hash,
                seeders=r.seeders,
                source_type=r.source_type,
                scraper_source=r.scraper_source,
                stream_url=r.stream_url,
                is_season_pack=r.is_season_pack,
                file_count=r.file_count,
            )
            for r in results
        ]

    @post("/add-torrent")
    async def add_torrent(
        self,
        data: AddTorrentRequest,
        session: AsyncSession,
        source_provider_service: SourceProviderService,
    ) -> AddTorrentResponse:
        result = await source_provider_service.add_torrent(session, data.provider_key, data.info_hash)
        return AddTorrentResponse(success=result["success"], detail=result["detail"])

    @post("/resolve")
    async def resolve_stream(
        self,
        data: ResolveRequest,
        session: AsyncSession,
        source_provider_service: SourceProviderService,
    ) -> ResolveResponse:
        result = await source_provider_service.resolve_stream(
            session, data.provider_key, data.info_hash, data.file_index,
            season=data.season, episode=data.episode,
        )
        return ResolveResponse(
            success=result.get("success", False),
            detail=result.get("detail", ""),
            stream_url=result.get("stream_url"),
        )

    @get("/scrapers")
    async def list_scrapers(
        self,
        source_provider_service: SourceProviderService,
    ) -> list[ScraperModuleResponse]:
        modules = source_provider_service.scraper_manager.get_modules()
        return [
            ScraperModuleResponse(
                module_id=m.manifest.module_id,
                name=m.manifest.name,
                version=m.manifest.version,
                description=m.manifest.description,
                scrapers=[
                    ScraperInfoResponse(
                        key=s.key,
                        name=s.name,
                        tier=s.tier,
                        category=s.category,
                        content_types=s.content_types,
                        enabled=source_provider_service.scraper_manager.is_scraper_enabled(s.key),
                    )
                    for s in m.scrapers
                ],
            )
            for m in modules
        ]

    @post("/scrapers/install")
    async def install_module(
        self,
        data: ModuleInstallRequest,
        session: AsyncSession,
        source_provider_service: SourceProviderService,
        scraper_module_repo: ScraperModuleRepository,
    ) -> ModuleInstallResponse:
        loaded = load_module(data.source_path)
        if loaded is None:
            from litestar.exceptions import ValidationException
            raise ValidationException("Invalid module path or manifest at: " + data.source_path)

        existing = await scraper_module_repo.get_module(session, loaded.manifest.module_id)
        if existing:
            from litestar.exceptions import ValidationException
            raise ValidationException("Module already installed: " + loaded.manifest.module_id)

        await scraper_module_repo.save_module(
            session, loaded.manifest.module_id, loaded.manifest.name,
            loaded.manifest.version, loaded.manifest.description,
            "local", data.source_path,
        )
        for s in loaded.scrapers:
            await scraper_module_repo.save_setting(session, loaded.manifest.module_id, s.key, True)
        await session.commit()

        source_provider_service.scraper_manager.add_module(loaded)

        return ModuleInstallResponse(
            module_id=loaded.manifest.module_id,
            name=loaded.manifest.name,
            version=loaded.manifest.version,
            description=loaded.manifest.description,
            scrapers=[
                ScraperInfoResponse(
                    key=s.key, name=s.name, tier=s.tier,
                    category=s.category, content_types=s.content_types, enabled=True,
                )
                for s in loaded.scrapers
            ],
        )

    @delete("/scrapers/{module_id:str}")
    async def uninstall_module(
        self,
        module_id: str,
        session: AsyncSession,
        source_provider_service: SourceProviderService,
        scraper_module_repo: ScraperModuleRepository,
    ) -> None:
        await scraper_module_repo.delete_module(session, module_id)
        await session.commit()
        source_provider_service.scraper_manager.remove_module(module_id)

    @put("/scrapers/{key:str}")
    async def toggle_scraper(
        self,
        key: str,
        data: ScraperToggleRequest,
        session: AsyncSession,
        source_provider_service: SourceProviderService,
        scraper_module_repo: ScraperModuleRepository,
    ) -> ScraperInfoResponse:
        source_provider_service.scraper_manager.set_scraper_enabled(key, data.enabled)

        modules = source_provider_service.scraper_manager.get_modules()
        module_id = None
        for m in modules:
            for s in m.scrapers:
                if s.key == key:
                    module_id = m.manifest.module_id
                    break
        if module_id:
            await scraper_module_repo.save_setting(session, module_id, key, data.enabled)
            await session.commit()

        for m in modules:
            for s in m.scrapers:
                if s.key == key:
                    return ScraperInfoResponse(
                        key=s.key,
                        name=s.name,
                        tier=s.tier,
                        category=s.category,
                        content_types=s.content_types,
                        enabled=data.enabled,
                    )
        return ScraperInfoResponse(
            key=key, name=key, tier=1, category="unknown",
            content_types=[], enabled=data.enabled,
        )
