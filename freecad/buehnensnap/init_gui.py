"""Register the Event workbench when FreeCAD starts."""

import FreeCADGui as Gui

from .commands import PODEST_COMMAND, PODEST_ICON, PodestCommand


class EventWorkbench(Gui.Workbench):
    MenuText = "Event"
    ToolTip = "Werkzeuge zur Veranstaltungsplanung"
    Icon = PODEST_ICON

    def Initialize(self):
        self.podest_command = PodestCommand()
        Gui.addCommand(PODEST_COMMAND, self.podest_command)
        commands = [PODEST_COMMAND]
        self.appendToolbar("Event", commands)
        self.appendMenu("Event", commands)

    def Deactivated(self):
        self.podest_command.hide_panel()

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(EventWorkbench())
