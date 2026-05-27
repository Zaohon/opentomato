"""Soul manager for unified agent personality framework."""

from pathlib import Path
from typing import Dict, Optional

from app.core.logging import get_logger

logger = get_logger("app.agent.soul")


class SoulManager:
    """Manages agent soul personalities loaded from disk with singleton pattern."""

    _instance: Optional["SoulManager"] = None
    _souls: Dict[str, str] = {}
    _default_soul: str = "default"
    _initialized: bool = False

    def __new__(cls) -> "SoulManager":
        """Singleton pattern - only one instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def initialize(cls, souls_dir: Optional[Path] = None) -> None:
        """
        Load all souls from disk on application startup.

        Args:
            souls_dir: Path to souls directory.
                      If None, defaults to app/souls/
        """
        instance = cls()

        # Prevent double initialization
        if instance._initialized:
            logger.debug("[SoulManager] Already initialized, skipping")
            return

        if souls_dir is None:
            souls_dir = Path(__file__).parent.parent.parent / "souls"

        if not souls_dir.exists():
            raise RuntimeError(f"Soul directory not found: {souls_dir}")

        # Scan .md files in souls directory
        for soul_file in sorted(souls_dir.glob("*.md")):
            soul_name = soul_file.stem  # Filename without extension
            try:
                content = soul_file.read_text(encoding="utf-8").strip()
                if content:  # Only load non-empty files
                    instance._souls[soul_name] = content
                    logger.info(f"[SoulManager] Loaded soul: {soul_name} ({len(content)} chars)")
                else:
                    logger.warning(f"[SoulManager] Soul file '{soul_name}' is empty")
            except Exception as e:
                logger.error(f"[SoulManager] Failed to load {soul_file.name}: {e}")

        if not instance._souls:
            raise RuntimeError(f"No soul markdown files loaded from: {souls_dir}")
        if instance._default_soul not in instance._souls:
            raise RuntimeError(
                f"Default soul '{instance._default_soul}' not found in loaded souls: {list(instance._souls.keys())}"
            )

        instance._initialized = True
        logger.info(f"[SoulManager] Initialization complete. Souls loaded: {list(instance._souls.keys())}")

    @classmethod
    def _require_initialized(cls) -> "SoulManager":
        instance = cls()
        if not instance._initialized:
            raise RuntimeError("SoulManager is not initialized. Initialize it during app startup.")
        return instance

    @classmethod
    def get_soul(cls, soul_name: str) -> str:
        """
        Get soul content by name.

        Args:
            soul_name: Name of soul (without .md extension).

        Returns:
            Soul markdown content as string.
        """
        instance = cls._require_initialized()

        name = str(soul_name or "").strip()
        if not name:
            raise ValueError("soul_name is required")

        soul_content = instance._souls.get(name)
        if soul_content is None:
            raise KeyError(f"Soul '{name}' not found")

        return soul_content

    @classmethod
    def list_souls(cls) -> Dict[str, str]:
        """
        Get metadata of all available souls.

        Returns:
            Dict mapping soul names to their first line (title/summary).
        """
        instance = cls._require_initialized()
        metadata = {}

        for soul_name, content in instance._souls.items():
            # Get first non-empty line as title
            first_line = ""
            for line in content.split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    first_line = line[:100]
                    break
            if not first_line:
                # Fallback to first line with markdown
                first_line = content.split("\n")[0][:100]

            metadata[soul_name] = first_line

        return metadata

    @classmethod
    def get_default_soul_name(cls) -> str:
        """Get the default soul name."""
        return cls._require_initialized()._default_soul

    @classmethod
    def soul_exists(cls, soul_name: str) -> bool:
        """Check if a soul exists by name."""
        instance = cls._require_initialized()
        if not isinstance(soul_name, str):
            return False
        return soul_name.strip() in instance._souls

    @classmethod
    def get_souls_count(cls) -> int:
        """Get total count of loaded souls."""
        return len(cls._require_initialized()._souls)
