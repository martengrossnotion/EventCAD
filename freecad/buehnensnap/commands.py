"""Toolbar commands for the Event workbench."""

from pathlib import Path

import FreeCADGui as Gui


PODEST_COMMAND = "BuehnenSnap_Podeste"
PODEST_ICON = str(Path(__file__).resolve().parent / "resources" / "icons" / "podest.png")


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
