from sources.base import BaseSource


class SourceRegistry:
    def __init__(self) -> None:
        self._sources: list = []

    def register(self, source: BaseSource) -> None:
        self._sources.append(source)

    def all(self) -> list:
        return list(self._sources)

    def by_name(self, name: str):
        for s in self._sources:
            if s.name.lower() == name.lower():
                return s
        return None


registry = SourceRegistry()

MODULES = (
    "github", "gitlab", "reddit", "hackernews", "devto", "keybase",
    "gravatar", "linktree", "youtube", "tiktok", "instagram", "twitter",
    "pinterest", "telegram_public", "aboutme", "hashnode", "medium",
    "codeberg", "replit", "dockerhub", "soundcloud", "twitch",
    "bluesky", "mastodon", "npm", "pypi", "stackoverflow", "bitbucket",
    "huggingface", "mixcloud", "codepen", "bandcamp", "behance",
    "dribbble", "steam", "goodreads", "producthunt",
    "vk", "tumblr", "flickr", "vimeo", "dailymotion", "lastfm",
    "sourceforge", "orcid", "arxiv", "kaggle", "habr", "vc_ru",
    "rutube", "quora", "dzen",
    "trello", "disqus", "kick", "patreon", "kofi", "buymeacoffee",
    "carrd", "spreaker", "scribd",
)


def register_all() -> None:
    import importlib
    for mod_name in MODULES:
        mod = importlib.import_module(f"sources.{mod_name}")
        for attr in dir(mod):
            obj = getattr(mod, attr)
            if (isinstance(obj, type) and issubclass(obj, BaseSource)
                    and obj is not BaseSource and obj.__module__ == mod.__name__):
                registry.register(obj())