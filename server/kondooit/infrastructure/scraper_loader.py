"""Scraper module loader.

Loads scraper modules from local filesystem paths. Each module is a
directory containing a manifest.json and individual scraper Python files.

Per ADR-0012, source resolvers are installable modules. This loader
handles local-path modules for development and initial deployment.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kondooit.application.scraper_ports import Scraper

logger = logging.getLogger(__name__)


@dataclass
class ScraperManifestEntry:
    """A single scraper declared in a module's manifest."""
    key: str
    name: str
    scraper_type: str  # "api" or "html"
    category: str
    content_types: list[str]
    tier: int
    default_enabled: bool
    config_schema: dict[str, Any] | None = None


@dataclass
class ScraperModuleManifest:
    """Parsed manifest.json from a scraper module."""
    module_id: str
    name: str
    version: str
    description: str
    min_kondooit_version: str
    scrapers: list[ScraperManifestEntry]


@dataclass
class LoadedScraper:
    """A scraper that has been loaded and is ready for use."""
    key: str
    name: str
    tier: int
    category: str
    content_types: list[str]
    default_enabled: bool
    config_schema: dict[str, Any] | None
    instance: Scraper


@dataclass
class LoadedModule:
    """A fully loaded scraper module."""
    manifest: ScraperModuleManifest
    path: str
    scrapers: list[LoadedScraper] = field(default_factory=list)


def parse_manifest(manifest_path: Path) -> ScraperModuleManifest | None:
    """Parse and validate a manifest.json file."""
    try:
        with open(manifest_path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.error("Failed to read manifest at %s: %s", manifest_path, e)
        return None

    required_fields = {"id", "name", "version", "scrapers"}
    if not required_fields.issubset(data.keys()):
        logger.error("Manifest missing required fields: %s", required_fields - data.keys())
        return None

    scrapers = []
    for entry in data.get("scrapers", []):
        if "key" not in entry or "name" not in entry:
            continue
        scrapers.append(ScraperManifestEntry(
            key=entry["key"],
            name=entry["name"],
            scraper_type=entry.get("type", "html"),
            category=entry.get("category", "general"),
            content_types=entry.get("content_types", ["movie", "series"]),
            tier=entry.get("tier", 1),
            default_enabled=entry.get("default_enabled", True),
            config_schema=entry.get("config_schema"),
        ))

    return ScraperModuleManifest(
        module_id=data["id"],
        name=data["name"],
        version=data["version"],
        description=data.get("description", ""),
        min_kondooit_version=data.get("min_kondooit_version", "0.0.1"),
        scrapers=scrapers,
    )


def load_scraper_from_file(scraper_path: Path, key: str) -> Scraper | None:
    """Dynamically load a scraper class from a Python file."""
    if not scraper_path.exists():
        logger.warning("Scraper file not found: %s", scraper_path)
        return None

    module_name = f"kondooit_scraper_{key}"
    spec = importlib.util.spec_from_file_location(module_name, scraper_path)
    if spec is None or spec.loader is None:
        logger.error("Cannot create module spec for %s", scraper_path)
        return None

    try:
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    except Exception as e:
        logger.error("Failed to load scraper %s: %s", key, e)
        sys.modules.pop(module_name, None)
        return None

    scraper_class = getattr(module, "ScraperImpl", None)
    if scraper_class is None:
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and attr_name != "Scraper"
                and hasattr(attr, "search_movie")
                and hasattr(attr, "search_episode")
            ):
                scraper_class = attr
                break

    if scraper_class is None:
        logger.error("No Scraper implementation found in %s", scraper_path)
        return None

    try:
        return scraper_class()
    except Exception as e:
        logger.error("Failed to instantiate scraper %s: %s", key, e)
        return None


def load_module(module_path: str) -> LoadedModule | None:
    """Load a scraper module from a local filesystem path.

    The path should point to a directory containing manifest.json
    and a scrapers/ subdirectory with Python files.
    """
    path = Path(module_path)
    if not path.is_dir():
        logger.error("Module path is not a directory: %s", module_path)
        return None

    manifest_file = path / "manifest.json"
    if not manifest_file.exists():
        logger.error("No manifest.json found in %s", module_path)
        return None

    manifest = parse_manifest(manifest_file)
    if manifest is None:
        return None

    loaded_module = LoadedModule(manifest=manifest, path=str(path))
    scrapers_dir = path / "scrapers"

    for entry in manifest.scrapers:
        scraper_file = scrapers_dir / f"{entry.key}.py"
        instance = load_scraper_from_file(scraper_file, entry.key)
        if instance is None:
            logger.warning("Skipping scraper %s — failed to load", entry.key)
            continue

        loaded_module.scrapers.append(LoadedScraper(
            key=entry.key,
            name=entry.name,
            tier=entry.tier,
            category=entry.category,
            content_types=entry.content_types,
            default_enabled=entry.default_enabled,
            config_schema=entry.config_schema,
            instance=instance,
        ))

    logger.info(
        "Loaded module '%s' v%s with %d/%d scrapers",
        manifest.name, manifest.version,
        len(loaded_module.scrapers), len(manifest.scrapers),
    )
    return loaded_module
