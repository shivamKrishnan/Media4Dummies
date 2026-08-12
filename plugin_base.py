# plugin_base.py
from PySide6.QtWidgets import QWidget

class FeaturePlugin:
    @property
    def name(self) -> str:
        """The display name in the sidebar menu."""
        raise NotImplementedError

    @property
    def description(self) -> str:
        """A brief description of the feature."""
        raise NotImplementedError

    def get_ui(self, parent: QWidget = None) -> QWidget:
        """
        Must return a valid QWidget containing the feature's user interface.
        """
        raise NotImplementedError