"""SQLAlchemy repository implementations.

These classes implement the application-layer port interfaces using
SQLAlchemy ORM models. They handle the mapping between infrastructure
ORM models and pure domain entities. The application and domain layers
never see the ORM models.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from kondooit.application.ports import (
    CollectionRepository,
    EpisodeRepository,
    GenreRepository,
    MovieRepository,
    ProviderConfigRepository,
    SeasonRepository,
    SeriesRepository,
    UserRepository,
)
from kondooit.application.provider_ports import ProviderConfig, ProviderStatus
from kondooit.domain.content import Collection, Episode, Genre, Movie, Season, Series
from kondooit.domain.user import User, UserRole
from kondooit.infrastructure.models import (
    CollectionModel,
    EpisodeModel,
    GenreModel,
    MovieModel,
    ProviderSettingModel,
    SeasonModel,
    SeriesModel,
    UserModel,
)


def _genre_to_domain(model: GenreModel) -> Genre:
    return Genre(
        id=model.id,
        name=model.name,
        tmdb_id=model.tmdb_id,
        tvdb_id=model.tvdb_id,
    )


def _movie_to_domain(model: MovieModel) -> Movie:
    return Movie(
        id=model.id,
        title=model.title,
        overview=model.overview,
        release_date=model.release_date,
        poster_path=model.poster_path,
        backdrop_path=model.backdrop_path,
        runtime_minutes=model.runtime_minutes,
        vote_average=model.vote_average,
        genres=[_genre_to_domain(g) for g in model.genres],
        collection_id=model.collection_id,
        tmdb_id=model.tmdb_id,
        tvdb_id=model.tvdb_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _season_to_domain(model: SeasonModel) -> Season:
    return Season(
        id=model.id,
        series_id=model.series_id,
        season_number=model.season_number,
        name=model.name,
        overview=model.overview,
        poster_path=model.poster_path,
        episode_count=model.episode_count,
        air_date=model.air_date,
        tmdb_id=model.tmdb_id,
        tvdb_id=model.tvdb_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _episode_to_domain(model: EpisodeModel) -> Episode:
    return Episode(
        id=model.id,
        series_id=model.series_id,
        season_id=model.season_id,
        episode_number=model.episode_number,
        name=model.name,
        overview=model.overview,
        still_path=model.still_path,
        runtime_minutes=model.runtime_minutes,
        air_date=model.air_date,
        vote_average=model.vote_average,
        tmdb_id=model.tmdb_id,
        tvdb_id=model.tvdb_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _series_to_domain(model: SeriesModel, include_seasons: bool = True) -> Series:
    return Series(
        id=model.id,
        title=model.title,
        overview=model.overview,
        first_air_date=model.first_air_date,
        last_air_date=model.last_air_date,
        poster_path=model.poster_path,
        backdrop_path=model.backdrop_path,
        status=model.status,
        vote_average=model.vote_average,
        genres=[_genre_to_domain(g) for g in model.genres],
        seasons=[_season_to_domain(s) for s in model.seasons] if include_seasons else [],
        tmdb_id=model.tmdb_id,
        tvdb_id=model.tvdb_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _collection_to_domain(model: CollectionModel) -> Collection:
    return Collection(
        id=model.id,
        name=model.name,
        description=model.description,
        poster_url=model.poster_url,
        backdrop_url=model.backdrop_url,
        tmdb_id=model.tmdb_id,
    )


def _user_to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        username=model.username,
        email=model.email,
        password_hash=model.password_hash,
        role=UserRole(model.role),
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyUserRepository(UserRepository):
    async def get_by_id(self, session: AsyncSession, user_id) -> User | None:
        model = await session.get(UserModel, user_id)
        return _user_to_domain(model) if model else None

    async def get_by_username(self, session: AsyncSession, username: str) -> User | None:
        stmt = select(UserModel).where(UserModel.username == username)
        result = await session.execute(stmt)
        model = result.scalar_one_or_none()
        return _user_to_domain(model) if model else None

    async def create(self, session: AsyncSession, user: User) -> User:
        model = UserModel(
            id=user.id,
            username=user.username,
            email=user.email,
            password_hash=user.password_hash,
            role=user.role.value,
            is_active=user.is_active,
        )
        session.add(model)
        await session.flush()
        return _user_to_domain(model)


    async def count(self, session: AsyncSession) -> int:
        from sqlalchemy import func
        stmt = select(func.count()).select_from(UserModel)
        result = await session.execute(stmt)
        return result.scalar_one()


class SqlAlchemyMovieRepository(MovieRepository):
    async def get_by_id(self, session: AsyncSession, movie_id) -> Movie | None:
        stmt = select(MovieModel).options(selectinload(MovieModel.genres)).where(MovieModel.id == movie_id)
        result = await session.execute(stmt)
        model = result.scalar_one_or_none()
        return _movie_to_domain(model) if model else None

    async def get_by_tmdb_id(self, session: AsyncSession, tmdb_id: int) -> Movie | None:
        stmt = select(MovieModel).options(selectinload(MovieModel.genres)).where(MovieModel.tmdb_id == tmdb_id)
        result = await session.execute(stmt)
        model = result.scalar_one_or_none()
        return _movie_to_domain(model) if model else None

    async def get_by_tvdb_id(self, session: AsyncSession, tvdb_id: int) -> Movie | None:
        stmt = select(MovieModel).options(selectinload(MovieModel.genres)).where(MovieModel.tvdb_id == tvdb_id)
        result = await session.execute(stmt)
        model = result.scalar_one_or_none()
        return _movie_to_domain(model) if model else None

    async def create(self, session: AsyncSession, movie: Movie) -> Movie:
        model = MovieModel(
            id=movie.id,
            title=movie.title,
            overview=movie.overview,
            release_date=movie.release_date,
            poster_path=movie.poster_path,
            backdrop_path=movie.backdrop_path,
            runtime_minutes=movie.runtime_minutes,
            vote_average=movie.vote_average,
            collection_id=movie.collection_id,
            tmdb_id=movie.tmdb_id,
            tvdb_id=movie.tvdb_id,
        )
        if movie.genres:
            genre_stmt = select(GenreModel).where(GenreModel.id.in_([g.id for g in movie.genres]))
            genre_result = await session.execute(genre_stmt)
            model.genres = list(genre_result.scalars().all())
        session.add(model)
        await session.flush()
        return Movie(
            id=model.id,
            title=model.title,
            overview=model.overview,
            release_date=model.release_date,
            poster_path=model.poster_path,
            backdrop_path=model.backdrop_path,
            runtime_minutes=model.runtime_minutes,
            vote_average=model.vote_average,
            genres=movie.genres,
            collection_id=model.collection_id,
            tmdb_id=model.tmdb_id,
            tvdb_id=model.tvdb_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list(self, session: AsyncSession, limit: int = 20, offset: int = 0) -> list[Movie]:
        stmt = select(MovieModel).options(selectinload(MovieModel.genres)).order_by(MovieModel.title).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return [_movie_to_domain(m) for m in result.scalars().all()]

    async def search(self, session: AsyncSession, query: str, limit: int = 20) -> list[Movie]:
        stmt = (
            select(MovieModel)
            .options(selectinload(MovieModel.genres))
            .where(MovieModel.title.ilike(f"%{query}%"))
            .order_by(MovieModel.title)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return [_movie_to_domain(m) for m in result.scalars().all()]


class SqlAlchemySeriesRepository(SeriesRepository):
    async def get_by_id(self, session: AsyncSession, series_id) -> Series | None:
        stmt = (
            select(SeriesModel)
            .options(selectinload(SeriesModel.genres), selectinload(SeriesModel.seasons))
            .where(SeriesModel.id == series_id)
        )
        result = await session.execute(stmt)
        model = result.scalar_one_or_none()
        return _series_to_domain(model) if model else None

    async def get_by_tmdb_id(self, session: AsyncSession, tmdb_id: int) -> Series | None:
        stmt = (
            select(SeriesModel)
            .options(selectinload(SeriesModel.genres), selectinload(SeriesModel.seasons))
            .where(SeriesModel.tmdb_id == tmdb_id)
        )
        result = await session.execute(stmt)
        model = result.scalar_one_or_none()
        return _series_to_domain(model) if model else None

    async def get_by_tvdb_id(self, session: AsyncSession, tvdb_id: int) -> Series | None:
        stmt = (
            select(SeriesModel)
            .options(selectinload(SeriesModel.genres), selectinload(SeriesModel.seasons))
            .where(SeriesModel.tvdb_id == tvdb_id)
        )
        result = await session.execute(stmt)
        model = result.scalar_one_or_none()
        return _series_to_domain(model) if model else None

    async def create(self, session: AsyncSession, series: Series) -> Series:
        model = SeriesModel(
            id=series.id,
            title=series.title,
            overview=series.overview,
            first_air_date=series.first_air_date,
            last_air_date=series.last_air_date,
            poster_path=series.poster_path,
            backdrop_path=series.backdrop_path,
            status=series.status,
            vote_average=series.vote_average,
            tmdb_id=series.tmdb_id,
            tvdb_id=series.tvdb_id,
        )
        if series.genres:
            genre_stmt = select(GenreModel).where(GenreModel.id.in_([g.id for g in series.genres]))
            genre_result = await session.execute(genre_stmt)
            model.genres = list(genre_result.scalars().all())
        session.add(model)
        await session.flush()
        return Series(
            id=model.id,
            title=model.title,
            overview=model.overview,
            first_air_date=model.first_air_date,
            last_air_date=model.last_air_date,
            poster_path=model.poster_path,
            backdrop_path=model.backdrop_path,
            status=model.status,
            vote_average=model.vote_average,
            genres=series.genres,
            seasons=[],
            tmdb_id=model.tmdb_id,
            tvdb_id=model.tvdb_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list(self, session: AsyncSession, limit: int = 20, offset: int = 0) -> list[Series]:
        stmt = (
            select(SeriesModel)
            .options(selectinload(SeriesModel.genres))
            .order_by(SeriesModel.title)
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        return [_series_to_domain(m, include_seasons=False) for m in result.scalars().all()]

    async def search(self, session: AsyncSession, query: str, limit: int = 20) -> list[Series]:
        stmt = (
            select(SeriesModel)
            .options(selectinload(SeriesModel.genres))
            .where(SeriesModel.title.ilike(f"%{query}%"))
            .order_by(SeriesModel.title)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return [_series_to_domain(m, include_seasons=False) for m in result.scalars().all()]


class SqlAlchemySeasonRepository(SeasonRepository):
    async def get_by_id(self, session: AsyncSession, season_id) -> Season | None:
        model = await session.get(SeasonModel, season_id)
        return _season_to_domain(model) if model else None

    async def get_by_series(self, session: AsyncSession, series_id) -> list[Season]:
        stmt = select(SeasonModel).where(SeasonModel.series_id == series_id).order_by(SeasonModel.season_number)
        result = await session.execute(stmt)
        return [_season_to_domain(s) for s in result.scalars().all()]

    async def create(self, session: AsyncSession, season: Season) -> Season:
        model = SeasonModel(
            id=season.id,
            series_id=season.series_id,
            season_number=season.season_number,
            name=season.name,
            overview=season.overview,
            poster_path=season.poster_path,
            episode_count=season.episode_count,
            air_date=season.air_date,
            tmdb_id=season.tmdb_id,
            tvdb_id=season.tvdb_id,
        )
        session.add(model)
        await session.flush()
        return _season_to_domain(model)


class SqlAlchemyEpisodeRepository(EpisodeRepository):
    async def get_by_id(self, session: AsyncSession, episode_id) -> Episode | None:
        model = await session.get(EpisodeModel, episode_id)
        return _episode_to_domain(model) if model else None

    async def get_by_season(self, session: AsyncSession, season_id) -> list[Episode]:
        stmt = (
            select(EpisodeModel)
            .where(EpisodeModel.season_id == season_id)
            .order_by(EpisodeModel.episode_number)
        )
        result = await session.execute(stmt)
        return [_episode_to_domain(e) for e in result.scalars().all()]

    async def create(self, session: AsyncSession, episode: Episode) -> Episode:
        model = EpisodeModel(
            id=episode.id,
            series_id=episode.series_id,
            season_id=episode.season_id,
            episode_number=episode.episode_number,
            name=episode.name,
            overview=episode.overview,
            still_path=episode.still_path,
            runtime_minutes=episode.runtime_minutes,
            air_date=episode.air_date,
            vote_average=episode.vote_average,
            tmdb_id=episode.tmdb_id,
            tvdb_id=episode.tvdb_id,
        )
        session.add(model)
        await session.flush()
        return _episode_to_domain(model)


class SqlAlchemyGenreRepository(GenreRepository):
    async def get_all(self, session: AsyncSession) -> list[Genre]:
        stmt = select(GenreModel).order_by(GenreModel.name)
        result = await session.execute(stmt)
        return [_genre_to_domain(g) for g in result.scalars().all()]

    async def get_by_id(self, session: AsyncSession, genre_id) -> Genre | None:
        model = await session.get(GenreModel, genre_id)
        return _genre_to_domain(model) if model else None

    async def get_by_tmdb_id(self, session: AsyncSession, tmdb_id: int) -> Genre | None:
        stmt = select(GenreModel).where(GenreModel.tmdb_id == tmdb_id)
        result = await session.execute(stmt)
        model = result.scalar_one_or_none()
        return _genre_to_domain(model) if model else None

    async def create(self, session: AsyncSession, genre: Genre) -> Genre:
        model = GenreModel(
            id=genre.id,
            name=genre.name,
            tmdb_id=genre.tmdb_id,
            tvdb_id=genre.tvdb_id,
        )
        session.add(model)
        await session.flush()
        return _genre_to_domain(model)


class SqlAlchemyCollectionRepository(CollectionRepository):
    async def get_by_id(self, session: AsyncSession, collection_id) -> Collection | None:
        model = await session.get(CollectionModel, collection_id)
        return _collection_to_domain(model) if model else None

    async def list(self, session: AsyncSession, limit: int = 20, offset: int = 0) -> list[Collection]:
        stmt = select(CollectionModel).order_by(CollectionModel.name).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return [_collection_to_domain(c) for c in result.scalars().all()]

    async def create(self, session: AsyncSession, collection: Collection) -> Collection:
        model = CollectionModel(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            poster_url=collection.poster_url,
            backdrop_url=collection.backdrop_url,
            tmdb_id=collection.tmdb_id,
        )
        session.add(model)
        await session.flush()
        return _collection_to_domain(model)


def _provider_config_to_domain(model: ProviderSettingModel) -> ProviderConfig:
    return ProviderConfig(
        key=model.key,
        api_key=model.api_key,
        status=ProviderStatus(model.status),
        priority=model.priority,
    )


class SqlAlchemyProviderConfigRepository(ProviderConfigRepository):
    async def get(self, session: AsyncSession, key: str) -> ProviderConfig | None:
        model = await session.get(ProviderSettingModel, key)
        return _provider_config_to_domain(model) if model else None

    async def get_all(self, session: AsyncSession) -> list[ProviderConfig]:
        stmt = select(ProviderSettingModel).order_by(ProviderSettingModel.priority, ProviderSettingModel.key)
        result = await session.execute(stmt)
        return [_provider_config_to_domain(m) for m in result.scalars().all()]

    async def save(self, session: AsyncSession, config: ProviderConfig) -> ProviderConfig:
        model = await session.get(ProviderSettingModel, config.key)
        if model is None:
            model = ProviderSettingModel(
                key=config.key,
                api_key=config.api_key,
                status=config.status.value,
                priority=config.priority,
            )
            session.add(model)
        else:
            model.api_key = config.api_key
            model.status = config.status.value
            model.priority = config.priority
        await session.flush()
        return _provider_config_to_domain(model)

    async def delete(self, session: AsyncSession, key: str) -> bool:
        model = await session.get(ProviderSettingModel, key)
        if model is None:
            return False
        await session.delete(model)
        await session.flush()
        return True
