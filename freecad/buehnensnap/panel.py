"""FreeCAD dock panel for placing and snapping stage decks."""

import FreeCAD as App
from pivy import coin
from PySide import QtCore, QtWidgets

from .decks import (
    Deck, deck_for_model, deck_from_pick, insert_deck, is_deck, model_systems, plan_symbol_models,
    seed_placement, snap_deck,
)
from .view_modes import active_3d_view, is_plan_view


class StageSnapDock(QtWidgets.QDockWidget):
    def __init__(self, parent):
        super().__init__("BühnenSnap · Podeste", parent)
        self.setObjectName("BuehnenSnapPodestPanel")
        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        self.view = None
        self.mouse_handle = None
        self.document_name = None
        self.pending = None
        self.selected_deck = None
        self.model_error = None
        self.mouse_type = coin.SoMouseButtonEvent.getClassTypeId()
        self.monitor = QtCore.QTimer(self)
        self.monitor.setInterval(200)
        self.monitor.timeout.connect(self.check_document)

        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        intro = QtWidgets.QLabel(
            "Podestsystem und Plansymbol wählen. Für Autosnap knapp innerhalb der gewünschten "
            "Kante eines vorhandenen BühnenSnap-Podests klicken."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        library = QtWidgets.QGroupBox("Podestbibliothek")
        form = QtWidgets.QFormLayout(library)
        self.system = QtWidgets.QComboBox()
        form.addRow("Podestsystem", self.system)
        self.plan_symbol = QtWidgets.QComboBox()
        form.addRow("Plansymbol", self.plan_symbol)
        self.length = self.number_field(1, 100000, 2000)
        self.width = self.number_field(1, 100000, 1000)
        self.depth = self.number_field(1, 10000, 90)
        form.addRow("Länge", self.length)
        form.addRow("Breite", self.width)
        form.addRow("Körperhöhe", self.depth)
        self.rotation = QtWidgets.QComboBox()
        self.rotation.addItems(["0° Hochkant", "90° Quer"])
        self.rotation.setToolTip("Ausrichtung neuer Podeste im Grundriss, auch beim Andocken.")
        form.addRow("Drehung", self.rotation)
        self.system.currentIndexChanged.connect(self.update_plan_symbols)
        self.plan_symbol.currentIndexChanged.connect(self.update_dimensions)
        layout.addWidget(library)

        start = QtWidgets.QGroupBox("Startpodest oder separate Fläche")
        form = QtWidgets.QFormLayout(start)
        self.x, self.y, self.z = [self.number_field(-1000000, 1000000, 0) for _ in range(3)]
        form.addRow("Mitte X", self.x)
        form.addRow("Mitte Y", self.y)
        form.addRow("Oberkante Z", self.z)
        button = QtWidgets.QPushButton("Podest an Koordinaten setzen")
        button.clicked.connect(self.add_seed)
        form.addRow(button)
        layout.addWidget(start)

        docking = QtWidgets.QGroupBox("Autosnap")
        form = QtWidgets.QFormLayout(docking)
        self.snap_button = QtWidgets.QPushButton("Autosnap starten")
        self.snap_button.setCheckable(True)
        self.snap_button.toggled.connect(self.toggle_snap)
        form.addRow(self.snap_button)
        top = QtWidgets.QPushButton("Draufsicht einpassen")
        top.clicked.connect(self.show_top)
        form.addRow(top)
        layout.addWidget(docking)
        self.status = QtWidgets.QLabel("Setze ein Startpodest oder öffne einen vorhandenen Plan.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch()

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(panel)
        self.setWidget(scroll)
        self.visibilityChanged.connect(self.stop_when_hidden)
        self.refresh_models()

    @staticmethod
    def number_field(minimum, maximum, value):
        field = QtWidgets.QDoubleSpinBox()
        field.setDecimals(1)
        field.setRange(minimum, maximum)
        field.setValue(value)
        field.setSuffix(" mm")
        return field

    def refresh_models(self):
        selected_system = self.system.currentData()
        self.system.blockSignals(True)
        self.system.clear()
        for system_id, label in model_systems().items():
            self.system.addItem(label, system_id)
        self.system.setCurrentIndex(max(0, self.system.findData(selected_system)))
        self.system.blockSignals(False)
        self.update_plan_symbols()

    def update_plan_symbols(self):
        system_id = self.system.currentData()
        selected_model = self.plan_symbol.currentData()
        had_selection = self.plan_symbol.currentIndex() >= 0
        self.plan_symbol.blockSignals(True)
        self.plan_symbol.clear()
        for label, model_file in plan_symbol_models(system_id, self.system.currentText()):
            self.plan_symbol.addItem(label, model_file)
            self.plan_symbol.setItemData(self.plan_symbol.count() - 1, model_file, QtCore.Qt.ToolTipRole)
        if system_id == "planning":
            self.plan_symbol.addItem("Eigenes Maß")
        if had_selection and self.plan_symbol.count():
            self.plan_symbol.setCurrentIndex(max(0, self.plan_symbol.findData(selected_model)))
        self.plan_symbol.setEnabled(bool(self.plan_symbol.count()))
        self.plan_symbol.blockSignals(False)
        self.update_dimensions()

    def update_dimensions(self):
        if self.model_error and self.status.text() == self.model_error:
            self.status.clear()
        self.selected_deck = None
        self.model_error = None
        model_file = self.plan_symbol.currentData()
        if model_file is not None:
            try:
                self.selected_deck = deck_for_model(self.system.currentText(), model_file)
            except ValueError as error:
                self.model_error = str(error)
        elif self.plan_symbol.currentIndex() < 0:
            self.model_error = "Für dieses Podestsystem wurden keine STEP-Modelle gefunden."
        if self.model_error:
            self.status.setText(self.model_error)

        fields = (self.length, self.width, self.depth)
        if self.selected_deck is not None:
            for field, value in zip(fields, self.selected_deck.dimensions):
                field.setValue(value)
        for field in fields:
            field.setEnabled(model_file is None and self.model_error is None)

    def current_deck(self):
        if self.model_error:
            raise ValueError(self.model_error)
        if self.selected_deck is not None:
            return self.selected_deck
        length, width, depth = self.length.value(), self.width.value(), self.depth.value()
        return Deck("custom", f"{length:g} × {width:g} mm", length, width, depth)

    def show_top(self):
        view = active_3d_view()
        if view is None:
            self.status.setText("Öffne zuerst eine 3D-Ansicht deines Plans.")
            return
        view.setCameraType("Orthographic")
        view.viewTop()
        view.fitAll()

    def add_seed(self):
        try:
            deck = self.current_deck()
            document = App.ActiveDocument or App.newDocument("Buehnenplan")
            first_object = not document.Objects
            placement = seed_placement(deck, self.x.value(), self.y.value(), self.z.value(),
                                       self.rotation.currentIndex())
            obj = insert_deck(document, deck, placement, plan_view=is_plan_view(document))
            if first_object:
                self.show_top()
            self.status.setText(f"{obj.Label} gesetzt. Zum Anbauen „Autosnap starten“ wählen.")
        except Exception as error:
            self.status.setText(str(error))

    def toggle_snap(self, enabled):
        if not enabled:
            self.stop_snap()
            self.status.setText("Autosnap beendet.")
            return
        document = App.ActiveDocument
        view = active_3d_view()
        if document is None or view is None or not any(is_deck(obj) for obj in document.Objects):
            self.stop_snap()
            self.status.setText("Setze zuerst ein BühnenSnap-Podest im aktuellen Plan.")
            return
        try:
            self.view = view
            self.document_name = document.Name
            self.mouse_handle = view.addEventCallbackPivy(self.mouse_type, self.on_click)
            self.monitor.start()
            self.snap_button.setText("Autosnap beenden")
            self.status.setText("Klicke am Zielpodest in die Nähe der gewünschten Kante und Ecke.")
        except Exception as error:
            self.stop_snap()
            self.status.setText(str(error))

    def stop_snap(self):
        self.monitor.stop()
        self.pending = None
        if self.mouse_handle is not None:
            try:
                self.view.removeEventCallbackPivy(self.mouse_type, self.mouse_handle)
            except (RuntimeError, ReferenceError):
                # The bound FreeCAD view can already have been closed.
                pass
        self.view, self.mouse_handle, self.document_name = None, None, None
        self.snap_button.blockSignals(True)
        self.snap_button.setChecked(False)
        self.snap_button.setText("Autosnap starten")
        self.snap_button.blockSignals(False)

    def check_document(self):
        document = App.ActiveDocument
        if document is None or document.Name != self.document_name or active_3d_view() is None:
            self.stop_snap()
            self.status.setText("Die Ansicht hat gewechselt. Starte Autosnap erneut.")
            return False
        return True

    def on_click(self, callback):
        event = callback.getEvent()
        if (event.getButton() != coin.SoMouseButtonEvent.BUTTON1
                or event.getState() != coin.SoButtonEvent.DOWN
                or event.wasShiftDown() or event.wasCtrlDown() or event.wasAltDown()
                or self.pending is not None):
            return
        document = App.ActiveDocument
        if document is None or document.Name != self.document_name:
            return
        try:
            hit = self.view.getObjectInfo(tuple(event.getPosition().getValue()))
            if not hit or hit.get("Document") != document.Name:
                return
            target = deck_from_pick(document.getObject(hit["Object"]))
            if target is None:
                return
            pick = App.Vector(hit["x"], hit["y"], hit["z"])
            callback.getAction().setHandled()
            self.pending = (target.Name, pick)
            # Updating the scene from inside the Coin event traversal is unsafe.
            QtCore.QTimer.singleShot(0, self.finish_click)
        except Exception as error:
            self.status.setText(str(error))

    def finish_click(self):
        if self.pending is None or not self.check_document():
            return
        name, pick = self.pending
        self.pending = None
        document = App.ActiveDocument
        target = document.getObject(name)
        if not is_deck(target):
            return
        try:
            deck = self.current_deck()
            obj, side = snap_deck(document, target, deck, pick, self.rotation.currentIndex(),
                                  plan_view=is_plan_view(document))
            self.status.setText(f"{obj.Label} gesetzt · Zielkante {side.lower()}.")
        except Exception as error:
            self.status.setText(str(error))

    def stop_when_hidden(self, visible):
        if not visible and self.mouse_handle is not None:
            self.stop_snap()
            self.status.setText("Autosnap beendet.")
