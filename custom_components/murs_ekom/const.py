"""Konstante integracije MURS-EKOM Odvoz smeća."""

from __future__ import annotations

DOMAIN = "murs_ekom"

CONF_LOCATION = "location"
CONF_NOTIFY_ENABLED = "notify_enabled"
CONF_NOTIFY_DAYS_BEFORE = "notify_days_before"
CONF_NOTIFY_TIME = "notify_time"
CONF_NOTIFY_ENTITIES = "notify_entities"
CONF_PULL_INTERVAL_DAYS = "pull_interval_days"
CONF_REFRESH_NOW = "refresh_now"

DEFAULT_NOTIFY_ENABLED = True
DEFAULT_NOTIFY_DAYS_BEFORE = 1
DEFAULT_NOTIFY_TIME = "18:00:00"
DEFAULT_PULL_INTERVAL_DAYS = 7

STORAGE_KEY = f"{DOMAIN}_notify"
STORAGE_VERSION = 1
CALENDAR_STORAGE_VERSION = 1

ATTRIBUTION = "Kalendar: MURS-EKOM d.o.o."
AUTHOR = "Vrsho"
AUTHOR_EMAIL = "info@vrsho.com"
