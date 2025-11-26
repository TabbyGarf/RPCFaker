import sys
import os
import json
import shutil
import subprocess
from pathlib import Path

from PyQt5 import QtWidgets, QtCore, QtGui
import requests

# check pour bundle SRC avec pyinstaller (facultatif)

if getattr(sys, 'frozen', False):
    BASE_PATH = Path(sys._MEIPASS)
else:
    BASE_PATH = Path(".")

ICON_PATH = BASE_PATH / "src/icon.ico"
FEXE_PATH = BASE_PATH / "src/dummy.exe"

# nettoyage de nom de fichier - filtrage pour detect. apps et crea exe.
VALID_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-./()+{}[]"
VALID_APPNAME_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-.()+{}[]"

def is_valid(name: str) -> bool:
    return all(c in VALID_CHARS for c in name)
   
def clean(name: str) -> str:
    cd = "".join(c if c in VALID_APPNAME_CHARS else " " for c in name).strip()
    return cd or "Unknown"


class Launcher(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("RPCFaker")
        self.setWindowIcon(QtGui.QIcon(str(ICON_PATH)))
        self.resize(1100, 680)

        # root pour les apps gens
        self.genapps = Path("gen_apps")
        self.genapps.mkdir(exist_ok=True)

        # fausses apps lancés
        self.running_processes = {}

        # UI
        container = QtWidgets.QWidget()
        self.setCentralWidget(container)
        main_layout = QtWidgets.QHBoxLayout(container)
        left_panel = QtWidgets.QVBoxLayout()

        # recherche
        self.search_bar = QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("Search a verified app.")
        self.search_bar.textChanged.connect(self.verifiedList)
        left_panel.addWidget(self.search_bar)

        # liste des apps verifs
        self.app_list_widget = QtWidgets.QListWidget()
        self.app_list_widget.itemSelectionChanged.connect(self.selectedApp)
        left_panel.addWidget(self.app_list_widget, 1)

        main_layout.addLayout(left_panel, 2)

        center_panel = QtWidgets.QVBoxLayout()

        # label appli
        self.label_app_title = QtWidgets.QLabel("Select an app...")
        self.label_app_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        center_panel.addWidget(self.label_app_title)

        # exes disponibles
        self.exec_list_widget = QtWidgets.QListWidget()
        self.exec_list_widget.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        center_panel.addWidget(self.exec_list_widget, 1)

        # bouton lancer
        self.btn_launch = QtWidgets.QPushButton("Launch")
        self.btn_launch.clicked.connect(self.launchEXE)
        center_panel.addWidget(self.btn_launch)

        main_layout.addLayout(center_panel, 2)


        # processus lancés

        right_panel = QtWidgets.QVBoxLayout()

        self.proc_title = QtWidgets.QLabel("Running processes (0)")
        self.proc_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        right_panel.addWidget(self.proc_title)

        
        self.proc_table = QtWidgets.QTableWidget(0, 4)
        self.proc_table.setHorizontalHeaderLabels(["PID", "Path", "Application Name", "  "])
        self.proc_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        self.proc_table.setColumnWidth(0, 20)
        self.proc_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.proc_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.proc_table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.Fixed)
        self.proc_table.setColumnWidth(3, 40)
        right_panel.addWidget(self.proc_table, 1)

        main_layout.addLayout(right_panel, 4)


        # statut

        self.status = QtWidgets.QStatusBar()
        self.setStatusBar(self.status)
        
        c_label = QtWidgets.QLabel("RPCFaker by LasagnaFelidae")
        self.status.addPermanentWidget(c_label)

        # télécharge la liste depuis API discord
        self.detectable_apps = []
        self.fetchVerifiedApps()
    
    def updateProcessCount(self):
        count = len(self.running_processes)
        self.proc_title.setText(f"Running processes ({count})")

    def closeEvent(self, event):
        if self.running_processes:
            for pid, proc in list(self.running_processes.items()):
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    try:
                        proc.kill()
                    except:
                        pass

        
        event.accept()

    def fetchVerifiedApps(self):
        self.status.showMessage("Fetching verified games list...")

        try:
            r = requests.get(
                "https://discord.com/api/v9/applications/detectable",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            data = r.json()
        except Exception as e:
            self.status.showMessage("Network error: Are you connected to the Internet?")
            return

        filtered_apps = []

        for app in data:
            execs = app.get("executables") or []
            cleaned_exes = []
            for e in execs:
                path = None
                
                if isinstance(e, str):
                    path = e
                elif isinstance(e, dict):
                    path = e.get("name")
                if path and path.lower().endswith(".exe") and is_valid(path):
                    cleaned_exes.append(path)

            if cleaned_exes:
                app["executables"] = [{"name": p} for p in cleaned_exes]
                filtered_apps.append(app)

        self.detectable_apps = sorted(
            filtered_apps,
            key=lambda a: a.get("name", "").lower()
        )
        
        self.verifiedList()
        self.status.showMessage(f"Loaded {len(self.detectable_apps)} apps with .exe executables")


    def verifiedList(self):
        text = self.search_bar.text().lower()
        self.app_list_widget.clear()

        for app in self.detectable_apps:
            name = app.get("name", "Unknown")
            if text not in name.lower():
                continue

            item = QtWidgets.QListWidgetItem(name)
            item.setData(QtCore.Qt.UserRole, app)
            self.app_list_widget.addItem(item)

    def selectedApp(self):
        self.exec_list_widget.clear()

        item = self.app_list_widget.currentItem()
        if not item:
            return

        app = item.data(QtCore.Qt.UserRole)
        name = app.get("name", "Unknown")
        self.label_app_title.setText(f"Detected executables list")

        execs = app.get("executables", [])

        for ex in execs:
            path = ex.get("name")  # executable path
            if not path:
               continue
            if not path.lower().endswith(".exe"):
               continue

            lw_item = QtWidgets.QListWidgetItem(path)
            lw_item.setData(QtCore.Qt.UserRole, path)
            self.exec_list_widget.addItem(lw_item)


    #  creation et lancement des exes sélectionnés
    def createEXE(self, app_id: str, exec_path: str) -> Path:

        final_path = self.genapps / app_id / exec_path
        final_path.parent.mkdir(parents=True, exist_ok=True)

        if not final_path.exists():
            src = Path(str(FEXE_PATH))
            if not src.exists():
                QtWidgets.QMessageBox.critical(
                    self, "Err", "src/dumme can't be found."
                )
                return final_path

            shutil.copyfile(src, final_path)


        return final_path


    

    def launchEXE(self):
        item = self.app_list_widget.currentItem()
        if not item:
            return

        app = item.data(QtCore.Qt.UserRole)
        app_id = str(app.get("id"))
        app_name = app.get("name", "Unknown")
        
        

        exe_i = self.exec_list_widget.selectedItems()
        if not exe_i:
            exe_i = [
                self.exec_list_widget.item(i)
                for i in range(self.exec_list_widget.count())
            ]

        count = 0

        for i in exe_i:
            exec_path = i.data(QtCore.Qt.UserRole)

            full_path = self.createEXE(clean(app_name), clean(exec_path))
            # je pourrais faire via id mais c'est + facile de trouver 
            # ce qu'on veut supp via nom lol

            try:
                kwargs = {"cwd": str(full_path.parent)}
                if os.name == "nt":
                    kwargs["creationflags"] = 0x00000008  # DETACHED_PROCESS

                proc = subprocess.Popen(
                    [str(full_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    **kwargs
                )

                self.addProcess(proc, str(full_path), app_name)
                count += 1

            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Erreur",
                    f"Impossible de lancer :\n{full_path}\n\n{e}"
                )




    # gérage de processus

    def addProcess(self, proc, path: str, app_name: str):
        pid = proc.pid
        row = self.proc_table.rowCount()
        self.proc_table.insertRow(row)

        self.running_processes[pid] = proc
        self.updateProcessCount()
        
        self.proc_table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(pid)))
        self.proc_table.setItem(row, 1, QtWidgets.QTableWidgetItem(path))
        self.proc_table.setItem(row, 2, QtWidgets.QTableWidgetItem(app_name))
        
        btn_widget = QtWidgets.QWidget()
        btn_layout = QtWidgets.QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setAlignment(QtCore.Qt.AlignCenter)

        btn = QtWidgets.QPushButton("Kill")
        btn.setFixedWidth(40)
        btn.clicked.connect(lambda _, pid=pid: self.killProcess(pid))

        btn_layout.addWidget(btn)
        self.proc_table.setCellWidget(row, 3, btn_widget)

    def killProcess(self, pid: int):
        proc = self.running_processes.get(pid)
        if not proc:
            return

        try:
            proc.terminate()
        except:
            pass

        del self.running_processes[pid]
        self.updateProcessCount()


        for r in range(self.proc_table.rowCount()):
            if self.proc_table.item(r, 0).text() == str(pid):
                self.proc_table.removeRow(r)
                break
                
    


def main():
    app = QtWidgets.QApplication(sys.argv)
    w = Launcher()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
