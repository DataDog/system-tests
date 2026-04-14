"""Singleton parser for K8s components configuration."""

import json
from pathlib import Path
from typing import Any


class K8sComponentsParser:
    """Singleton parser for K8s components JSON configuration."""

    _instance: "K8sComponentsParser | None" = None
    _components: dict[str, Any] = {}

    def __new__(cls) -> "K8sComponentsParser":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_components()  # noqa: SLF001
        return cls._instance

    def _load_components(self) -> None:
        """Load K8s components from JSON file."""
        config_file = Path(__file__).parent / "k8s_components.json"
        with open(config_file, encoding="utf-8") as f:
            self._components = json.load(f)

    def get_default_component_version(self, component: str, lang: str | None = None) -> str:
        """Get default component version or image URL."""
        component_data: dict[str, Any] = self._components[component]

        # Handle lib_init with language
        if component == "lib_init":
            if lang is None:
                raise ValueError("Language parameter required for lib_init component")
            component_data = component_data[lang]

        # Return pinned if exists, otherwise prod
        if "pinned" in component_data:
            result: str = component_data["pinned"]
        else:
            result = component_data["prod"]
        return result

    def get_all_component_versions(self, component: str, lang: str | None = None) -> list[str]:
        """Get all component versions (values only)."""
        component_data: dict[str, Any] = self._components[component]

        # Handle lib_init with language
        if component == "lib_init":
            if lang is None:
                raise ValueError("Language parameter required for lib_init component")
            component_data = component_data[lang]
        return list(component_data.values())

    def update_pinned_version(self, component: str, new_version: str) -> bool:
        """Update the pinned version for a component.

        Args:
            component: Component name (e.g., 'cluster_agent', 'helm_chart', 'helm_chart_operator')
            new_version: New version string to set

        Returns:
            True if the version was updated, False if it was already at that version

        """
        if component not in self._components:
            raise ValueError(f"Component '{component}' not found in configuration")

        component_data = self._components[component]

        if "pinned" not in component_data:
            raise ValueError(f"Component '{component}' does not have a 'pinned' field")

        # Check if version changed
        current_version = component_data["pinned"]
        if current_version == new_version:
            return False

        # Update in memory
        component_data["pinned"] = new_version

        # Save to file
        config_file = Path(__file__).parent / "k8s_components.json"
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(self._components, f, indent=4, ensure_ascii=False)
            f.write("\n")  # Add trailing newline

        return True
