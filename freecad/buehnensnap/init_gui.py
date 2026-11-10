"""Register the Event workbench when FreeCAD starts."""

import FreeCADGui as Gui

from .commands import PODEST_COMMAND, PODEST_ICON, PodestCommand, ViewModeCommand


class EventWorkbench(Gui.Workbench):
    MenuText = "Event"
    ToolTip = "Werkzeuge zur Veranstaltungsplanung"
    Icon = PODEST_ICON

    def Initialize(self):
        self.podest_command = PodestCommand()
        Gui.addCommand(PODEST_COMMAND, self.podest_command)
        Gui.addCommand("EventCAD_Grundriss", ViewModeCommand(
            "2D", "2D-Grundriss", "Flache Podestsymbole in der Draufsicht anzeigen"
        ))
        Gui.addCommand("EventCAD_Modell", ViewModeCommand(
            "3D", "3D-Modell", "Volumenkörper in der isometrischen Ansicht anzeigen"
        ))
        commands = [PODEST_COMMAND, "EventCAD_Grundriss", "EventCAD_Modell"]
        self.appendToolbar("Event", commands)
        self.appendMenu("Event", commands)

    def Deactivated(self):
        self.podest_command.hide_panel()

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(EventWorkbench())
