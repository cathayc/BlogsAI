"""Dependency registry for GUI components."""

from typing import Dict, Any, Type


class ComponentRegistry:
    """Registry for managing component dependencies."""

    def __init__(self):
        self._components: Dict[str, Any] = {}
        self._factories: Dict[str, callable] = {}

    def register(self, name: str, component: Any):
        """Register a component instance."""
        self._components[name] = component

    def register_factory(self, name: str, factory: callable):
        """Register a component factory."""
        self._factories[name] = factory

    def get(self, name: str):
        """Get a component by name."""
        if name in self._components:
            return self._components[name]
        elif name in self._factories:
            component = self._factories[name]()
            self._components[name] = component
            return component
        else:
            raise KeyError(f"Component '{name}' not found")


# Global registry instance
registry = ComponentRegistry()

# Usage example:
# registry.register('database', get_db)
# registry.register('settings_manager', SettingsManager)
#
# # In components:
# db = registry.get('database')
# settings = registry.get('settings_manager')
