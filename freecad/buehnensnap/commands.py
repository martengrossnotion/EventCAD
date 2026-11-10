"""Toolbar commands for the Event workbench."""

from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui


PODEST_COMMAND = "BuehnenSnap_Podeste"
ICON_DIRECTORY = Path(__file__).resolve().parent / "resources" / "icons"
PODEST_ICON = str(ICON_DIRECTORY / "podest.png")


class PodestCommand:
    def __init__(self):
        self.panel = None

    def GetResources(self):
        return {
            "Pixmap": PODEST_ICON,
            "MenuText": "BühnenSnap · Podeste",
            "ToolTip": "Podestbibliothek öffnen und Podeste aneinander andocken",
        }

    def IsActive(self):
        return True

    def Activated(self):
        if self.panel is None:
            from PySide import QtCore

            from .panel import StageSnapDock

            window = Gui.getMainWindow()
            self.panel = StageSnapDock(window)
            window.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.panel)
        self.panel.show()
        self.panel.raise_()

    def hide_panel(self):
        if self.panel is not None:
            self.panel.hide()


class ViewModeCommand:
    def __init__(self, mode, label, tooltip):
        self.mode = mode
        self.label = label
        self.tooltip = tooltip

    def GetResources(self):
        return {
            "Pixmap": str(ICON_DIRECTORY / f"view-{self.mode.lower()}.svg"),
            "MenuText": self.label,
            "ToolTip": self.tooltip,
        }

    def IsActive(self):
        document = Gui.activeDocument()
        return document is not None and hasattr(document.activeView(), "viewTop")

    def Activated(self):
        from .view_modes import active_3d_view, show_mode

        document, view = App.ActiveDocument, active_3d_view()
        if document is not None and view is not None:
            show_mode(document, view, self.mode)
