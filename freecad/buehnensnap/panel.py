"""FreeCAD dock panel for placing and snapping stage decks."""

import FreeCAD as App
from pivy import coin
from PySide import QtCore, QtWidgets

from .decks import (
    CATALOG, Deck, deck_from_pick, dock_deck, insert_deck, is_deck, read_deck, seed_placement,
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
        self.mouse_type = coin.SoMouseButtonEvent.getClassTypeId()
        self.monitor = QtCore.QTimer(self)
        self.monitor.setInterval(200)
        self.monitor.timeout.connect(self.check_document)

        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        intro = QtWidgets.QLabel(
            "Podesttyp wählen. Zum Andocken im Plan knapp innerhalb der gewünschten "
            "Kante eines vorhandenen BühnenSnap-Podests klicken."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        library = QtWidgets.QGroupBox("Podestbibliothek")
        form = QtWidgets.QFormLayout(library)
        self.catalog = QtWidgets.QComboBox()
        self.catalog.addItems([deck.label for deck in CATALOG] + ["Eigenes Maß"])
        form.addRow("Typ", self.catalog)
        self.length = self.number_field(1, 100000, 2000)
        self.width = self.number_field(1, 100000, 1000)
        self.depth = self.number_field(1, 10000, 90)
        form.addRow("Länge", self.length)
        form.addRow("Breite", self.width)
        form.addRow("Körperhöhe", self.depth)
        self.rotation = QtWidgets.QComboBox()
        self.rotation.addItems(["0°", "90°"])
        self.rotation.setToolTip("Beim Andocken relativ zum Zielpodest, sonst relativ zur X-Achse.")
        form.addRow("Drehung", self.rotation)
        self.catalog.currentIndexChanged.connect(self.update_catalog)
        self.update_catalog(self.catalog.currentIndex())
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

        docking = QtWidgets.QGroupBox("Andocken im Plan")
        form = QtWidgets.QFormLayout(docking)
        self.alignment = QtWidgets.QComboBox()
        self.alignment.addItems(["Kantenanfang", "Kantenmitte", "Kantenende"])
        self.alignment.setCurrentIndex(1)
        self.alignment.setToolTip("Vom kleineren zum größeren X-/Y-Wert am Zielpodest (lokale Achsen).")
        form.addRow("Ausrichtung", self.alignment)
        self.snap_button = QtWidgets.QPushButton("Andocken starten")
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

    @staticmethod
    def number_field(minimum, maximum, value):
        field = QtWidgets.QDoubleSpinBox()
        field.setDecimals(1)
        field.setRange(minimum, maximum)
        field.setValue(value)
        field.setSuffix(" mm")
        return field

    def update_catalog(self, index):
        custom = index == len(CATALOG)
        fields = (self.length, self.width, self.depth)
        if not custom:
            for field, dimension in zip(fields, CATALOG[index].dimensions):
                field.setValue(dimension)
        for field in fields:
            field.setEnabled(custom)

    def current_deck(self):
        index = self.catalog.currentIndex()
        if index < len(CATALOG):
            return CATALOG[index]
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
            document = App.ActiveDocument or App.newDocument("Buehnenplan")
            first_object = not document.Objects
            deck = self.current_deck()
            placement = seed_placement(deck, self.x.value(), self.y.value(), self.z.value(),
                                       self.rotation.currentIndex())
            obj = insert_deck(document, deck, placement, plan_view=is_plan_view(document))
            if first_object:
                self.show_top()
            self.status.setText(f"{obj.Label} gesetzt. Zum Anbauen „Andocken starten“ wählen.")
        except Exception as error:
            self.status.setText(str(error))

    def toggle_snap(self, enabled):
        if not enabled:
            self.stop_snap()
            self.status.setText("Andocken beendet.")
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
            self.snap_button.setText("Andocken beenden")
            self.status.setText("Klicke auf die gewünschte Podestkante. Der Modus bleibt aktiv.")
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
        self.snap_button.setText("Andocken starten")
        self.snap_button.blockSignals(False)

    def check_document(self):
        document = App.ActiveDocument
        if document is None or document.Name != self.document_name or active_3d_view() is None:
            self.stop_snap()
            self.status.setText("Die Ansicht hat gewechselt. Starte das Andocken erneut.")
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
            placement, side = dock_deck(read_deck(target), target.getGlobalPlacement(), deck,
                                        pick, self.rotation.currentIndex(),
                                        self.alignment.currentIndex() - 1)
            obj = insert_deck(document, deck, placement, plan_view=is_plan_view(document))
            self.status.setText(f"{obj.Label} gesetzt · Zielkante {side.lower()}.")
        except Exception as error:
            self.status.setText(str(error))

    def stop_when_hidden(self, visible):
        if not visible and self.mouse_handle is not None:
            self.stop_snap()
            self.status.setText("Andocken beendet.")
