"""Source provider API controller.

Provides endpoints for listing, configuring, and testing source
providers (TorBox, Easynews). Also provides the unified source
search endpoint that runs scrapers + cache checks + direct search.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

import httpx
from litestar import Controller, Request, get, put, post, delete
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


class ScraperConfigFieldSchema(BaseModel):
    type: str
    label: str
    description: str
    options: list[str] | None = None
    default: str | None = None


class ScraperInfoResponse(BaseModel):
    key: str
    name: str
    tier: int
    category: str
    content_types: list[str]
    enabled: bool
    config_schema: dict[str, ScraperConfigFieldSchema] | None = None
    config: dict[str, str] | None = None


class ScraperModuleResponse(BaseModel):
    module_id: str
    name: str
    version: str
    description: str
    scrapers: list[ScraperInfoResponse]


class ScraperToggleRequest(BaseModel):
    enabled: bool
    config: dict[str, str] | None = None


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
        request: Request,
        post_hash: str,
        filename: str,
        down_url: str,
        dl_farm: str,
        dl_port: str,
        session: AsyncSession,
        source_provider_service: SourceProviderService,
        ext: str = "",
    ) -> Stream:
        """Proxy an Easynews download through the server with stored credentials.

        Resolves the Easynews URL (follows redirects to CDN) then streams
        the content back. Supports HTTP Range requests for seeking.
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

        from kondooit.infrastructure.providers.easynews import build_easynews_download_url
        upstream_url = build_easynews_download_url(
            down_url=down_url, dl_farm=dl_farm, dl_port=dl_port,
            post_hash=post_hash, ext=ext, filename=filename,
        )

        resolved_url = await self._resolve_easynews_url(upstream_url, username, password)
        if not resolved_url:
            from litestar.exceptions import ServiceUnavailableException
            raise ServiceUnavailableException("Failed to resolve Easynews download URL")

        upstream_headers: dict[str, str] = {}
        range_header = request.headers.get("range")
        if range_header:
            upstream_headers["Range"] = range_header

        content_type = "video/mp4"
        if ext in ("mkv",):
            content_type = "video/x-matroska"
        elif ext in ("avi",):
            content_type = "video/x-msvideo"
        elif ext in ("ts", "m2ts"):
            content_type = "video/mp2t"
        elif ext in ("webm",):
            content_type = "video/webm"

        client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, read=300.0),
            follow_redirects=True,
        )

        try:
            upstream_resp = await client.send(
                client.build_request("GET", resolved_url, headers=upstream_headers),
                stream=True,
            )
        except Exception as e:
            await client.aclose()
            logger.error("Easynews CDN connection failed for %s: %s", post_hash, e)
            from litestar.exceptions import ServiceUnavailableException
            raise ServiceUnavailableException("Failed to connect to Easynews CDN")

        if upstream_resp.status_code not in (200, 206):
            await upstream_resp.aclose()
            await client.aclose()
            logger.warning("Easynews CDN returned %d for %s", upstream_resp.status_code, post_hash)
            from litestar.exceptions import ServiceUnavailableException
            raise ServiceUnavailableException("Easynews returned an error")

        response_headers: dict[str, str] = {
            "Content-Disposition": f'inline; filename="{filename}"',
            "Accept-Ranges": "bytes",
        }
        content_length = upstream_resp.headers.get("content-length")
        if content_length:
            response_headers["Content-Length"] = content_length
        content_range = upstream_resp.headers.get("content-range")
        if content_range:
            response_headers["Content-Range"] = content_range

        status_code = upstream_resp.status_code

        async def stream_generator():
            try:
                async for chunk in upstream_resp.aiter_bytes(chunk_size=131072):
                    yield chunk
            finally:
                await upstream_resp.aclose()
                await client.aclose()

        return Stream(
            stream_generator(),
            status_code=status_code,
            media_type=content_type,
            headers=response_headers,
        )

    @staticmethod
    async def _resolve_easynews_url(url: str, username: str, password: str) -> str | None:
        """Resolve an Easynews download URL to its final CDN endpoint.

        Easynews redirects the initial authenticated URL to a CDN. We follow
        the redirect chain and return the final URL. This mirrors Umbrella's
        unrestrict_link method.
        """
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(60.0),
                follow_redirects=True,
                auth=(username, password),
            ) as client:
                resp = await client.send(
                    client.build_request("GET", url),
                    stream=True,
                )
                if not resp.is_success:
                    await resp.aclose()
                    return None
                resolved = str(resp.url)
                await resp.aclose()
                return resolved
        except Exception as e:
            logger.error("Easynews URL resolution failed: %s", e)
            return None

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
        session: AsyncSession,
        scraper_module_repo: ScraperModuleRepository,
    ) -> list[ScraperModuleResponse]:
        modules = source_provider_service.scraper_manager.get_modules()
        result = []
        for m in modules:
            settings = await scraper_module_repo.list_settings(session, m.manifest.module_id)
            settings_by_key = {s.scraper_key: s for s in settings}
            scraper_responses = []
            for s in m.scrapers:
                saved = settings_by_key.get(s.key)
                schema = None
                if s.config_schema:
                    schema = {
                        k: ScraperConfigFieldSchema(
                            type=v.get("type", "text"),
                            label=v.get("label", k),
                            description=v.get("description", ""),
                            options=v.get("options"),
                            default=v.get("default"),
                        )
                        for k, v in s.config_schema.items()
                    }
                scraper_responses.append(ScraperInfoResponse(
                    key=s.key,
                    name=s.name,
                    tier=s.tier,
                    category=s.category,
                    content_types=s.content_types,
                    enabled=source_provider_service.scraper_manager.is_scraper_enabled(s.key),
                    config_schema=schema,
                    config=saved.config if saved and saved.config else None,
                ))
            result.append(ScraperModuleResponse(
                module_id=m.manifest.module_id,
                name=m.manifest.name,
                version=m.manifest.version,
                description=m.manifest.description,
                scrapers=scraper_responses,
            ))
        return result

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

        scraper_responses = []
        for s in loaded.scrapers:
            schema = None
            if s.config_schema:
                schema = {
                    k: ScraperConfigFieldSchema(
                        type=v.get("type", "text"),
                        label=v.get("label", k),
                        description=v.get("description", ""),
                        options=v.get("options"),
                        default=v.get("default"),
                    )
                    for k, v in s.config_schema.items()
                }
            scraper_responses.append(ScraperInfoResponse(
                key=s.key, name=s.name, tier=s.tier,
                category=s.category, content_types=s.content_types, enabled=True,
                config_schema=schema,
            ))

        return ModuleInstallResponse(
            module_id=loaded.manifest.module_id,
            name=loaded.manifest.name,
            version=loaded.manifest.version,
            description=loaded.manifest.description,
            scrapers=scraper_responses,
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
        if data.config is not None:
            source_provider_service.scraper_manager.set_scraper_config(key, data.config)

        modules = source_provider_service.scraper_manager.get_modules()
        module_id = None
        for m in modules:
            for s in m.scrapers:
                if s.key == key:
                    module_id = m.manifest.module_id
                    break
        if module_id:
            saved_config = data.config if data.config is not None else source_provider_service.scraper_manager.get_scraper_config(key)
            await scraper_module_repo.save_setting(session, module_id, key, data.enabled, saved_config)
            await session.commit()

        for m in modules:
            for s in m.scrapers:
                if s.key == key:
                    schema = None
                    if s.config_schema:
                        schema = {
                            k: ScraperConfigFieldSchema(
                                type=v.get("type", "text"),
                                label=v.get("label", k),
                                description=v.get("description", ""),
                                options=v.get("options"),
                                default=v.get("default"),
                            )
                            for k, v in s.config_schema.items()
                        }
                    return ScraperInfoResponse(
                        key=s.key,
                        name=s.name,
                        tier=s.tier,
                        category=s.category,
                        content_types=s.content_types,
                        enabled=data.enabled,
                        config_schema=schema,
                        config=data.config or source_provider_service.scraper_manager.get_scraper_config(key),
                    )
        return ScraperInfoResponse(
            key=key, name=key, tier=1, category="unknown",
            content_types=[], enabled=data.enabled,
        )
