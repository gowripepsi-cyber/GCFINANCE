import sys
import datetime
import os
import shutil
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QTabWidget, 
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QDialog, QFormLayout, QLineEdit, QComboBox, 
                               QMessageBox, QDoubleSpinBox, QDateEdit, QFileDialog,
                               QStackedWidget, QFrame, QListWidget, QListWidgetItem,
                               QGraphicsDropShadowEffect, QTreeWidget, QTreeWidgetItem, QTextEdit, QTextBrowser)
from PySide6.QtCore import Qt, QDate, QSize, QTimer, QDateTime, QUrl
from PySide6.QtGui import QFont, QColor, QIcon, QPixmap, QPainter, QPainterPath, QBrush, QPen, QImage, QDragEnterEvent, QDropEvent
from PySide6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog

import scheme_db
import calendar
import json
import backup_restore

def calculate_due_date(start_date_str, month_offset):
    try:
        if not start_date_str: return ""
        parts = start_date_str.split('-')
        if len(parts) != 3: return start_date_str
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        
        month += month_offset
        year += (month - 1) // 12
        month = (month - 1) % 12 + 1
        
        last_day = calendar.monthrange(year, month)[1]
        day = min(day, last_day)
        
        return f"{year:04d}-{month:02d}-{day:02d}"
    except Exception as e:
        print(f"Error calculating due date: {e}")
        return start_date_str


def create_circular_avatar(image_path, size=40):
    pixmap = QPixmap(image_path)
    if pixmap.isNull():
        # Default avatar
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor("#e0e0e0")))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, size, size)
        painter.setPen(QPen(QColor("#757575")))
        font = painter.font()
        font.setPixelSize(int(size * 0.5))
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "?")
        painter.end()
        return QIcon(pixmap)
        
    # Scale and crop to circle
    pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    
    # Create circular image
    target = QPixmap(size, size)
    target.fill(Qt.transparent)
    
    painter = QPainter(target)
    painter.setRenderHint(QPainter.Antialiasing)
    
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)
    
    # Calculate offset to center the image
    x_offset = (size - pixmap.width()) // 2
    y_offset = (size - pixmap.height()) // 2
    painter.drawPixmap(x_offset, y_offset, pixmap)
    painter.end()
    
    return QIcon(target)

class PhotoDropLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        self.setText("Drag & Drop Photo Here\nor Click to Upload")
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #aaaaaa;
                border-radius: 8px;
                background-color: #f9f9f9;
                color: #777777;
                padding: 10px;
            }
            QLabel:hover {
                border-color: #1a73e8;
                background-color: #f0f4ff;
            }
        """)
        self.setMinimumSize(150, 150)
        self.setMaximumSize(200, 200)
        self.photo_path = None
        self.pixmap_data = None

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].isLocalFile():
                ext = urls[0].toLocalFile().lower().split('.')[-1]
                if ext in ['jpg', 'jpeg', 'png', 'webp']:
                    event.acceptProposedAction()
                    self.setStyleSheet("""
                        QLabel {
                            border: 2px dashed #1a73e8;
                            border-radius: 8px;
                            background-color: #e8f0fe;
                            color: #1a73e8;
                            padding: 10px;
                        }
                    """)
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #aaaaaa;
                border-radius: 8px;
                background-color: #f9f9f9;
                color: #777777;
                padding: 10px;
            }
            QLabel:hover {
                border-color: #1a73e8;
                background-color: #f0f4ff;
            }
        """)
        event.accept()

    def dropEvent(self, event: QDropEvent):
        self.dragLeaveEvent(event) # Reset style
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            file_path = urls[0].toLocalFile()
            self.load_image(file_path)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Customer Photo", "", "Images (*.jpg *.jpeg *.png *.webp)"
            )
            if file_path:
                self.load_image(file_path)

    def load_image(self, file_path):
        # Check size (Max 5MB)
        if os.path.getsize(file_path) > 5 * 1024 * 1024:
            QMessageBox.warning(self, "File Too Large", "Image size must be less than 5 MB.")
            return

        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            self.photo_path = file_path
            # Scale to fit label for preview
            scaled_pixmap = pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setPixmap(scaled_pixmap)
            self.setText("")

    def clear_image(self):
        self.photo_path = None
        self.clear()
        self.setText("Drag & Drop Photo Here\nor Click to Upload")

    def get_photo_path(self):
        return self.photo_path

class AddCustomerDialog(QDialog):
    def __init__(self, next_cif, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New CIF (Customer)")
        self.setMinimumWidth(450)
        
        layout = QHBoxLayout()
        
        # Left side: Photo Upload
        photo_layout = QVBoxLayout()
        self.photo_label = PhotoDropLabel()
        self.btn_remove_photo = QPushButton("Remove Photo")
        self.btn_remove_photo.clicked.connect(self.photo_label.clear_image)
        self.btn_remove_photo.setStyleSheet("background-color: #f44336; color: white;")
        photo_layout.addWidget(QLabel("Profile Photo:"))
        photo_layout.addWidget(self.photo_label)
        photo_layout.addWidget(self.btn_remove_photo)
        photo_layout.addStretch()
        
        # Right side: Form
        form_layout = QFormLayout()
        
        self.cif_input = QLineEdit()
        self.cif_input.setText(next_cif)
        self.cif_input.setReadOnly(True)
        self.cif_input.setStyleSheet("background-color: #f0f0f0; color: #555;")
        
        self.name_input = QLineEdit()
        self.surname_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.address_input = QTextEdit()
        self.address_input.setFixedHeight(80) # Approximately 4 rows
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        
        # Aadhar Fields
        self.aadhar_input = QLineEdit()
        self.aadhar_input.setPlaceholderText("XXXX XXXX XXXX")
        self.aadhar_input.setInputMask("0000 0000 0000") # Ensures 12 digits
        
        self.aadhar_doc_path = ""
        self.btn_upload_aadhar = QPushButton("Upload Aadhar Card (PDF/Image)")
        self.btn_upload_aadhar.clicked.connect(self.upload_document)
        self.lbl_image_status = QLabel("No file selected")
        
        form_layout.addRow("CIF Number (Auto):", self.cif_input)
        form_layout.addRow("Name:", self.name_input)
        form_layout.addRow("Surname:", self.surname_input)
        form_layout.addRow("Phone:", self.phone_input)
        form_layout.addRow("Address:", self.address_input)
        form_layout.addRow("Join Date:", self.date_input)
        form_layout.addRow("Aadhar Number (Mandatory):", self.aadhar_input)
        form_layout.addRow("Aadhar Card (PDF/Image):", self.btn_upload_aadhar)
        form_layout.addRow("", self.lbl_image_status)
        
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        form_layout.addRow(btn_layout)
        
        layout.addLayout(photo_layout)
        layout.addLayout(form_layout)
        self.setLayout(layout)

    def upload_document(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Aadhar Document", "", "Documents (*.pdf);;Images (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            self.aadhar_doc_path = file_path
            self.lbl_image_status.setText(os.path.basename(file_path))

    def get_data(self):
        # Validate Aadhar number length (removing spaces)
        aadhar = self.aadhar_input.text().replace(" ", "")
        return {
            'cif': self.cif_input.text().strip(),
            'name': self.name_input.text().strip(),
            'surname': self.surname_input.text().strip(),
            'phone': self.phone_input.text().strip(),
            'address': self.address_input.toPlainText().strip(),
            'join_date': self.date_input.date().toString("yyyy-MM-dd"),
            'aadhar_number': aadhar,
            'aadhar_image_path': self.aadhar_doc_path,
            'photo_path': self.photo_label.get_photo_path()
        }

    def set_data(self, data):
        self.cif_input.setText(data.get('cif', ''))
        self.name_input.setText(data.get('name', ''))
        self.surname_input.setText(data.get('surname', ''))
        self.phone_input.setText(data.get('phone', ''))
        self.address_input.setPlainText(data.get('address', ''))
        self.date_input.setDate(QDate.fromString(data['join_date'], "yyyy-MM-dd"))
        self.aadhar_input.setText(data['aadhar_number'])
        self.aadhar_doc_path = data.get('aadhar_image_path', '')
        if self.aadhar_doc_path:
            self.lbl_image_status.setText(os.path.basename(self.aadhar_doc_path))
            
        photo_path = data.get('photo_path', '')
        if photo_path and os.path.exists(photo_path):
            self.photo_label.load_image(photo_path)

class PaymentDialog(QDialog):
    def __init__(self, customer_id, current_month, due_amount, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Record Payment for Month {current_month}")
        self.setMinimumWidth(350)
        self.original_due = due_amount
        
        layout = QFormLayout()
        
        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0, 1000000)
        self.amount_input.setDecimals(2)
        self.amount_input.setValue(due_amount)
        self.amount_input.valueChanged.connect(self.update_arrears)
        
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        
        self.lbl_arrears = QLabel("Arrears: ₹0.00 (Will be added to next month)")
        self.lbl_arrears.setStyleSheet("color: #f44336; font-weight: bold;")
        
        layout.addRow(f"Actual Due:", QLabel(f"₹{due_amount:,.2f}"))
        layout.addRow("Paying Amount:", self.amount_input)
        layout.addRow("Payment Date:", self.date_input)
        layout.addRow("", self.lbl_arrears)
        
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Confirm Payment")
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addRow(btn_layout)
        self.setLayout(layout)
        self.update_arrears()

    def update_arrears(self):
        paid = self.amount_input.value()
        arrears = max(0, self.original_due - paid)
        self.lbl_arrears.setText(f"Arrears: ₹{arrears:,.2f} (Will be added to next month)")
        if arrears > 0:
            self.lbl_arrears.show()
        else:
            self.lbl_arrears.hide()

    def get_data(self):
        return {
            'amount': self.amount_input.value(),
            'date': self.date_input.date().toString("yyyy-MM-dd"),
            'arrears': max(0, self.original_due - self.amount_input.value())
        }

class CIFSelectorDialog(QDialog):
    def __init__(self, parent=None, multi_select=False):
        super().__init__(parent)
        self.setWindowTitle("Select Customer (CIF)")
        self.setMinimumSize(600, 400)
        self.multi_select = multi_select
        self.offset = 0
        self.limit = 10
        self.loading = False
        self.all_loaded = False
        self.current_search = ""
        
        layout = QVBoxLayout(self)
        
        # Search
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by Name, CIF or Phone...")
        self.search_input.textChanged.connect(self.filter_customers)
        search_layout.addWidget(QLabel("Search:"))
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "CIF", "Name", "Phone"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        
        if multi_select:
            self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        else:
            self.table.setSelectionMode(QTableWidget.SingleSelection)
            
        self.table.doubleClicked.connect(self.accept)
        self.table.verticalScrollBar().valueChanged.connect(self.on_scroll)
        layout.addWidget(self.table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.select_btn = QPushButton("Select")
        self.select_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.select_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        
        self.load_customers(reset=True)

    def on_scroll(self, value):
        if not self.loading and not self.all_loaded:
            if value >= self.table.verticalScrollBar().maximum() - 2:
                self.load_customers(reset=False)
        
    def load_customers(self, reset=True):
        if self.loading: return
        self.loading = True
        
        if reset:
            self.offset = 0
            self.table.setRowCount(0)
            self.all_loaded = False
        
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        
        query = "SELECT id, cif_number, name, phone FROM customers WHERE status = 'Active'"
        params = []
        if self.current_search:
            query += " AND (cif_number LIKE ? OR name LIKE ? OR phone LIKE ?)"
            p = f"%{self.current_search}%"
            params.extend([p, p, p])
        
        query += " LIMIT ? OFFSET ?"
        params.extend([self.limit, self.offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        if not rows:
            self.all_loaded = True
        else:
            self.display_rows(rows, append=not reset)
            self.offset += len(rows)
            
            # If no scrollbar is visible yet, load more to fill the screen
            QTimer.singleShot(100, self.check_more_needed)
            
        conn.close()
        self.loading = False
        
    def check_more_needed(self):
        if not self.all_loaded:
            if self.table.verticalScrollBar().maximum() == 0:
                self.load_customers(reset=False)
        
    def display_rows(self, rows, append=False):
        if not append:
            self.table.setRowCount(0)
        
        start_idx = self.table.rowCount()
        for r_idx, row in enumerate(rows):
            current_row = start_idx + r_idx
            self.table.insertRow(current_row)
            for c_idx, val in enumerate(row):
                self.table.setItem(current_row, c_idx, QTableWidgetItem(str(val)))
                
    def filter_customers(self):
        self.current_search = self.search_input.text().strip()
        self.load_customers(reset=True)
        
    def get_selected_customer(self):
        row = self.table.currentRow()
        if row >= 0:
            return {
                'id': int(self.table.item(row, 0).text()),
                'cif': self.table.item(row, 1).text(),
                'name': self.table.item(row, 2).text()
            }
        return None

    def get_selected_customers(self):
        items = self.table.selectedItems()
        if not items: return []
        
        # items are for every cell, get unique rows
        selected_rows = sorted(list(set(item.row() for item in items)))
        results = []
        for row in selected_rows:
            results.append({
                'id': int(self.table.item(row, 0).text()),
                'cif': self.table.item(row, 1).text(),
                'name': self.table.item(row, 2).text()
            })
        return results

        return None

class AddSHGGroupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New SHG Group")
        self.setMinimumSize(700, 500)
        
        layout = QVBoxLayout(self)
        
        # Basic Info
        form_layout = QFormLayout()
        self.name_input = QLineEdit()
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        
        form_layout.addRow("Group Name:", self.name_input)
        form_layout.addRow("Starting Date:", self.date_input)
        layout.addLayout(form_layout)
        
        # Members Section
        layout.addWidget(QLabel("<b>Group Members:</b>"))
        self.members_table = QTableWidget()
        self.members_table.setColumnCount(4)
        self.members_table.setHorizontalHeaderLabels(["ID", "CIF", "Name", "Phone"])
        self.members_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.members_table)
        
        member_btn_layout = QHBoxLayout()
        self.btn_add_member = QPushButton("Add Member")
        self.btn_add_member.clicked.connect(self.add_member)
        self.btn_remove_member = QPushButton("Remove Selected")
        self.btn_remove_member.clicked.connect(self.remove_member)
        member_btn_layout.addWidget(self.btn_add_member)
        member_btn_layout.addWidget(self.btn_remove_member)
        member_btn_layout.addStretch()
        layout.addLayout(member_btn_layout)
        
        # Role Assignment
        roles_layout = QFormLayout()
        self.leader_combo = QComboBox()
        self.deputy_combo = QComboBox()
        roles_layout.addRow("Group Leader:", self.leader_combo)
        roles_layout.addRow("Deputy Leader:", self.deputy_combo)
        layout.addLayout(roles_layout)
        
        # Save/Cancel
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Create Group")
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        
        self.members_data = [] # List of dicts

    def add_member(self):
        selector = CIFSelectorDialog(self, multi_select=True)
        if selector.exec_() == QDialog.Accepted:
            customers = selector.get_selected_customers()
            for customer in customers:
                # Check if already added
                if any(m['id'] == customer['id'] for m in self.members_data):
                    continue
                
                # Fetch full details for table
                conn = scheme_db.get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT phone FROM customers WHERE id = ?", (customer['id'],))
                phone = cursor.fetchone()[0]
                conn.close()
                
                member = {
                    'id': customer['id'],
                    'cif': customer['cif'],
                    'name': customer['name'],
                    'phone': phone
                }
                self.members_data.append(member)
            
            self.update_members_table()
            self.update_combos()

    def remove_member(self):
        row = self.members_table.currentRow()
        if row >= 0:
            self.members_data.pop(row)
            self.update_members_table()
            self.update_combos()

    def update_members_table(self):
        self.members_table.setRowCount(0)
        for r_idx, m in enumerate(self.members_data):
            self.members_table.insertRow(r_idx)
            self.members_table.setItem(r_idx, 0, QTableWidgetItem(str(m['id'])))
            self.members_table.setItem(r_idx, 1, QTableWidgetItem(str(m['cif'])))
            self.members_table.setItem(r_idx, 2, QTableWidgetItem(m['name']))
            self.members_table.setItem(r_idx, 3, QTableWidgetItem(str(m['phone'])))

    def update_combos(self):
        self.leader_combo.clear()
        self.deputy_combo.clear()
        for m in self.members_data:
            self.leader_combo.addItem(m['name'], m['id'])
            self.deputy_combo.addItem(m['name'], m['id'])

    def get_data(self):
        return {
            'name': self.name_input.text().strip(),
            'start_date': self.date_input.date().toString("yyyy-MM-dd"),
            'leader_id': self.leader_combo.currentData(),
            'deputy_id': self.deputy_combo.currentData(),
            'members': [m['id'] for m in self.members_data]
        }

class ChitBatchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Chit Batch")
        self.setMinimumWidth(350)
        
        layout = QFormLayout()
        
        self.name_input = QLineEdit()
        self.value_combo = QComboBox()
        for v in [200000, 500000, 1000000, 2000000]:
            self.value_combo.addItem(f"₹{v:,.0f}", v)
            
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        
        layout.addRow("Batch Name:", self.name_input)
        layout.addRow("Chit Value:", self.value_combo)
        layout.addRow("Starting Date:", self.date_input)
        
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Create")
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addRow(btn_layout)
        self.setLayout(layout)

    def get_data(self):
        return {
            'name': self.name_input.text().strip(),
            'value': self.value_combo.currentData(),
            'start_date': self.date_input.date().toString("yyyy-MM-dd")
        }

    def set_data(self, data):
        self.setWindowTitle("Edit Chit Batch")
        self.save_btn.setText("Update")
        self.name_input.setText(data['name'])
        idx = self.value_combo.findData(data['value'])
        if idx >= 0: self.value_combo.setCurrentIndex(idx)
        self.date_input.setDate(QDate.fromString(data['start_date'], "yyyy-MM-dd"))

class GlobalSearchResultsDialog(QDialog):
    def __init__(self, results, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Global Search Results")
        self.setMinimumSize(700, 400)
        self.parent_app = parent
        
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Type", "Name", "Details", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)
        
        self.load_results(results)
        
    def load_results(self, results):
        self.table.setRowCount(0)
        for r_idx, (r_type, r_id, r_name, r_detail, extra_id) in enumerate(results):
            self.table.insertRow(r_idx)
            self.table.setItem(r_idx, 0, QTableWidgetItem(r_type))
            self.table.setItem(r_idx, 1, QTableWidgetItem(str(r_name)))
            self.table.setItem(r_idx, 2, QTableWidgetItem(str(r_detail)))
            
            action_btn = QPushButton("Go To")
            action_btn.setStyleSheet("padding: 4px 8px;")
            action_btn.clicked.connect(lambda _, t=r_type, i=r_id, n=r_name, e=extra_id: self.navigate_to(t, i, n, e))
            
            widget = QWidget()
            h_layout = QHBoxLayout(widget)
            h_layout.setContentsMargins(0, 0, 0, 0)
            h_layout.addWidget(action_btn)
            
            self.table.setCellWidget(r_idx, 3, widget)
            
    def navigate_to(self, r_type, r_id, r_name, extra_id=None):
        if self.parent_app:
            if r_type == 'Customer (Profile)':
                self.parent_app.highlight_customer(r_id)
            elif r_type == 'Customer (Batch)':
                self.parent_app.view_ledger(r_id, extra_id)
            elif r_type == 'Customer (SHG)':
                self.parent_app.highlight_shg(extra_id)
            elif r_type == 'Customer (Ind. Loan)':
                self.parent_app.highlight_ind_loan(extra_id)
            elif r_type == 'Batch':
                self.parent_app.expand_batch(r_id, r_name)
            elif r_type == 'SHG':
                self.parent_app.highlight_shg(r_id)
        self.accept()

class ManageBatchMembersDialog(QDialog):
    def __init__(self, batch_id, batch_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Members of {batch_name}")
        self.setMinimumSize(600, 500)
        self.batch_id = batch_id
        
        layout = QVBoxLayout(self)
        
        self.members_table = QTableWidget()
        self.members_table.setColumnCount(4)
        self.members_table.setHorizontalHeaderLabels(["ID", "CIF", "Name", "Phone"])
        self.members_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.members_table)
        
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("Add Members (Multi)")
        self.btn_add.clicked.connect(self.add_members)
        self.btn_remove = QPushButton("Remove Selected")
        self.btn_remove.clicked.connect(self.remove_member)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_remove)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.load_members()

    def load_members(self):
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id, c.cif_number, c.name, c.phone 
            FROM customers c
            JOIN batch_enrollments e ON c.id = e.customer_id
            WHERE e.batch_id = ?
        """, (self.batch_id,))
        rows = cursor.fetchall()
        conn.close()
        
        self.members_table.setRowCount(0)
        for r_idx, row in enumerate(rows):
            self.members_table.insertRow(r_idx)
            for c_idx, val in enumerate(row):
                self.members_table.setItem(r_idx, c_idx, QTableWidgetItem(str(val)))

    def add_members(self):
        selector = CIFSelectorDialog(self, multi_select=True)
        if selector.exec_() == QDialog.Accepted:
            customers = selector.get_selected_customers()
            conn = scheme_db.get_connection()
            cursor = conn.cursor()
            try:
                for c in customers:
                    # Insert into batch_enrollments
                    cursor.execute("""
                        INSERT OR IGNORE INTO batch_enrollments (customer_id, batch_id, join_date) 
                        VALUES (?, ?, ?)
                    """, (c['id'], self.batch_id, QDate.currentDate().toString("yyyy-MM-dd")))
                conn.commit()
                self.load_members()
                # Notify parent to handle ledger allocation
                if hasattr(self.parent(), "allocate_batch_ledgers"):
                    self.parent().allocate_batch_ledgers(self.batch_id, [c['id'] for c in customers])
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))
            finally:
                conn.close()

    def remove_member(self):
        row = self.members_table.currentRow()
        if row >= 0:
            cid = int(self.members_table.item(row, 0).text())
            conn = scheme_db.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM batch_enrollments WHERE customer_id = ? AND batch_id = ?", (cid, self.batch_id))
            conn.commit()
            conn.close()
            self.load_members()

class CustomerLedgerDialog(QDialog):
    def __init__(self, customer_id, name, cif, chit_value, batch_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Ledger: {name} ({cif})")
        self.setMinimumSize(800, 600)
        self.customer_id = customer_id
        self.batch_id = batch_id
        
        layout = QVBoxLayout(self)
        
        header = QLabel(f"Batch Value: ₹{chit_value:,.0f}")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a73e8; margin-bottom: 10px;")
        layout.addWidget(header)
        
        self.ledger_table = QTableWidget()
        self.ledger_table.setColumnCount(8)
        self.ledger_table.setHorizontalHeaderLabels(["Due Date", "Due Amt", "Paid Amt", "Withdrawn", "Balance", "Date", "Receipt", "Status"])
        self.ledger_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.ledger_table)
        
        btn_layout = QHBoxLayout()
        self.btn_regenerate = QPushButton("Regenerate Due Dates")
        self.btn_regenerate.setStyleSheet("background-color: #ff9800; color: white; padding: 10px; font-weight: bold;")
        self.btn_regenerate.clicked.connect(self.regenerate_schedule)
        
        self.btn_pay = QPushButton("Record Payment for Next Due")
        self.btn_pay.setStyleSheet("background-color: #4caf50; color: white; padding: 10px; font-weight: bold;")
        self.btn_pay.clicked.connect(self.pay_next_month)
        
        btn_layout.addWidget(self.btn_regenerate)
        btn_layout.addWidget(self.btn_pay)
        layout.addLayout(btn_layout)
        
        self.load_ledger_data()

    def load_ledger_data(self):
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        
        # 1. Fetch enrollment info (withdrawn_month, chit_value)
        cursor.execute("""
            SELECT e.withdrawn_month, b.chit_value
            FROM batch_enrollments e
            JOIN chit_batches b ON e.batch_id = b.id
            WHERE e.customer_id = ? AND e.batch_id = ?
        """, (self.customer_id, self.batch_id))
        w_row = cursor.fetchone()
        w_month = w_row[0] if w_row else None
        chit_val = w_row[1] if w_row else 0
        
        w_amount = 0
        if w_month:
            cursor.execute("SELECT withdrawable_amount FROM scheme_master WHERE total_value = ? AND month_number = ?", (chit_val, w_month))
            w_res = cursor.fetchone()
            if w_res: w_amount = w_res[0]

        # 2. Fetch ledger rows for THIS batch
        cursor.execute("""
            SELECT id, month_number, due_date, due_amount, paid_amount, payment_date, receipt_number, status 
            FROM customer_ledgers 
            WHERE customer_id = ? AND batch_id = ?
            ORDER BY month_number
        """, (self.customer_id, self.batch_id))
        rows = cursor.fetchall()
        conn.close()
        
        self.ledger_table.setRowCount(0)
        self.next_month_data = None
        running_balance = 0
        
        for r_idx, row in enumerate(rows):
            l_id, month, due_date_str, due, paid, date, receipt, status = row
            
            # Logic: Balance = Total Withdrawn - Total Paid
            current_withdrawn = w_amount if month == w_month else 0
            running_balance += current_withdrawn
            running_balance -= (paid or 0)
            
            self.ledger_table.insertRow(r_idx)
            
            # Due Date DatePicker
            date_widget = QDateEdit()
            date_widget.setDisplayFormat("dd-MM-yyyy")
            date_widget.setCalendarPopup(True)
            if due_date_str:
                date_widget.setDate(QDate.fromString(due_date_str, "yyyy-MM-dd"))
            else:
                date_widget.setDate(QDate.currentDate())
            
            date_widget.dateChanged.connect(lambda new_d, lid=l_id: self.update_due_date(lid, new_d))
            self.ledger_table.setCellWidget(r_idx, 0, date_widget)
            
            # Display Data
            display_data = [
                f"₹{due:,.0f}", 
                f"₹{paid:,.0f}" if paid else "-",
                f"₹{current_withdrawn:,.0f}" if current_withdrawn > 0 else "-",
                f"₹{running_balance:,.0f}",
                date or "-",
                receipt or "-",
                status
            ]
            
            for c_idx, val in enumerate(display_data):
                item = QTableWidgetItem(str(val))
                if status == 'Paid':
                    item.setBackground(QColor("#e8f5e9"))
                    if c_idx == 0:  # Apply visual lock to date widget too
                        date_widget.setEnabled(False)
                        date_widget.setStyleSheet("color: #555; background-color: #e8f5e9;")
                        
                if c_idx == 3: # Balance Column (was 4, now shifted by 1 because col 0 is widget)
                    if running_balance > 0:
                        item.setForeground(QColor("#f44336")) # Red for Liability
                        item.setFont(QFont("Arial", weight=QFont.Bold))
                    elif running_balance < 0:
                        item.setForeground(QColor("#4caf50")) # Green for Surplus
                
                # +1 because 0 is the widget
                self.ledger_table.setItem(r_idx, c_idx + 1, item)
            
            # Track next pending month for payment button
            if status != 'Paid' and self.next_month_data is None:
                self.next_month_data = (month, due, due_date_str)

        self.btn_pay.setEnabled(self.next_month_data is not None)
        if self.next_month_data:
            due_str = QDate.fromString(self.next_month_data[2], "yyyy-MM-dd").toString("dd-MM-yyyy") if self.next_month_data[2] else f"Month {self.next_month_data[0]}"
            self.btn_pay.setText(f"Record Payment: Due on {due_str} (₹{self.next_month_data[1]:,.0f})")
        else:
            self.btn_pay.setText("Scheme Fully Paid")

    def update_due_date(self, ledger_id, new_date):
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE customer_ledgers SET due_date = ? WHERE id = ?", (new_date.toString("yyyy-MM-dd"), ledger_id))
        conn.commit()
        conn.close()

    def regenerate_schedule(self):
        reply = QMessageBox.question(self, 'Regenerate Schedule', 
            "This will recalculate all pending due dates based on the batch starting date. Continue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            conn = scheme_db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT starting_date FROM chit_batches WHERE id = ?", (self.batch_id,))
            start_date_str = cursor.fetchone()[0]
            
            if not start_date_str:
                QMessageBox.warning(self, "Error", "Batch does not have a starting date set.")
                conn.close()
                return
                
            cursor.execute("SELECT id, month_number, status FROM customer_ledgers WHERE customer_id = ? AND batch_id = ?", (self.customer_id, self.batch_id))
            ledgers = cursor.fetchall()
            for l_id, month, status in ledgers:
                if status != 'Paid':
                    new_date = calculate_due_date(start_date_str, month - 1)
                    cursor.execute("UPDATE customer_ledgers SET due_date = ? WHERE id = ?", (new_date, l_id))
            conn.commit()
            conn.close()
            self.load_ledger_data()
            QMessageBox.information(self, "Success", "Pending due dates have been regenerated.")

    def pay_next_month(self):
        if self.next_month_data:
            month, due, due_date_str = self.next_month_data
            # We call the parent's record_payment logic
            if hasattr(self.parent(), "record_payment"):
                if self.parent().record_payment(self.customer_id, month, due, self.batch_id):
                    self.load_ledger_data()

class ManageFundsDialog(QDialog):
    def __init__(self, batch_id, batch_name, batch_value_str, main_app, parent=None):
        super().__init__(parent)
        self.batch_id = batch_id
        self.main_app = main_app
        self.setWindowTitle(f"Manage Funds: {batch_name} ({batch_value_str})")
        self.resize(1000, 600)
        
        layout = QVBoxLayout(self)
        
        self.chit_tree = QTreeWidget()
        self.chit_tree.setColumnCount(5)
        self.chit_tree.setHeaderLabels(["Member", "Join Date", "Withdrawn Month", "Status", "Actions"])
        self.chit_tree.header().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.chit_tree)
        
        self.load_data()

    def load_data(self):
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        
        self.chit_tree.clear()
        
        cursor.execute("""
            SELECT c.id, c.cif_number, c.name, e.join_date, e.withdrawn_month, e.status 
            FROM customers c
            JOIN batch_enrollments e ON c.id = e.customer_id
            WHERE e.batch_id = ?
        """, (self.batch_id,))
        members = cursor.fetchall()
        
        for mid, mcif, mname, mjoin, mwithdrawn, mstatus in members:
            member_item = QTreeWidgetItem(self.chit_tree)
            member_item.setText(0, f"{mcif} - {mname}")
            member_item.setText(1, str(mjoin))
            member_item.setText(2, str(mwithdrawn) if mwithdrawn else "Not Withdrawn")
            member_item.setText(3, str(mstatus))
            
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(5, 2, 5, 2)
            action_layout.setSpacing(10)
            
            btn_view = QPushButton("Ledger")
            btn_view.setStyleSheet("padding: 4px 8px;")
            btn_view.clicked.connect(lambda _, cid=mid, bid_id=self.batch_id: self.main_app.view_ledger(cid, bid_id))
            
            btn_withdraw = QPushButton("Withdraw")
            btn_withdraw.setStyleSheet("padding: 4px 8px;")
            btn_withdraw.clicked.connect(lambda _, cid=mid, bid_id=self.batch_id: self.call_withdraw_and_reload(cid, bid_id))
            btn_withdraw.setEnabled(mwithdrawn is None)
            
            action_layout.addWidget(btn_view)
            action_layout.addWidget(btn_withdraw)
            self.chit_tree.setItemWidget(member_item, 4, action_widget)
            
        conn.close()
        
    def call_withdraw_and_reload(self, cid, bid):
        self.main_app.withdraw_loan(cid, bid)
        self.load_data()

class BatchManagementDialog(QDialog):
    def __init__(self, parent=None, filter_value=None):
        super().__init__(parent)
        self.filter_value = filter_value
        title = f"Chit Batch Management (₹{filter_value:,.0f} Scheme)" if filter_value else "Chit Batch Management"
        self.setWindowTitle(title)
        self.setMinimumSize(900, 500)
        self.resize(1200, 600)
        
        layout = QVBoxLayout(self)
        
        btn_layout = QHBoxLayout()
        self.btn_add_batch = QPushButton("Create New Batch")
        self.btn_add_batch.clicked.connect(self.add_chit_batch)
        btn_layout.addWidget(self.btn_add_batch)
        
        self.btn_manage_funds = QPushButton("Manage Funds")
        self.btn_manage_funds.clicked.connect(self.open_manage_funds)
        btn_layout.addWidget(self.btn_manage_funds)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.batches_table = QTableWidget()
        self.batches_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.batches_table.setSelectionMode(QTableWidget.SingleSelection)
        self.batches_table.setColumnCount(6)
        self.batches_table.setHorizontalHeaderLabels(["ID", "Batch Name", "Value", "Start Date", "Status", "Actions"])
        self.batches_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.batches_table)
        
        self.load_batches()

    def load_batches(self):
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        if getattr(self, 'filter_value', None):
            cursor.execute("SELECT id, batch_name, chit_value, starting_date, status FROM chit_batches WHERE chit_value = ?", (self.filter_value,))
        else:
            cursor.execute("SELECT id, batch_name, chit_value, starting_date, status FROM chit_batches")
        rows = cursor.fetchall()
        self.batches_table.setRowCount(0)
        for r_idx, row in enumerate(rows):
            self.batches_table.insertRow(r_idx)
            for c_idx, val in enumerate(row):
                if c_idx == 2: # Value
                    val = f"₹{val:,.0f}"
                self.batches_table.setItem(r_idx, c_idx, QTableWidgetItem(str(val)))
            
            # Action button
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(2, 2, 2, 2)
            action_layout.setSpacing(5)

            btn_manage = QPushButton("Members")
            btn_manage.setStyleSheet("padding: 4px 8px;")
            btn_manage.clicked.connect(lambda _, rid=row[0], rname=row[1]: self.manage_members(rid, rname))
            
            btn_edit = QPushButton("Edit")
            btn_edit.clicked.connect(lambda _, rid=row[0]: self.edit_chit_batch(rid))
            btn_edit.setStyleSheet("background-color: #2196F3; color: white; padding: 4px 8px;")
            
            btn_delete = QPushButton("Delete")
            btn_delete.clicked.connect(lambda _, rid=row[0]: self.delete_chit_batch(rid))
            btn_delete.setStyleSheet("background-color: #f44336; color: white; padding: 4px 8px;")
            
            action_layout.addWidget(btn_manage)
            action_layout.addWidget(btn_edit)
            action_layout.addWidget(btn_delete)
            self.batches_table.setCellWidget(r_idx, 5, action_widget)
        conn.close()

    def edit_chit_batch(self, batch_id):
        # We can reuse the main app's method if we pass self correctly, 
        # but for consistency we implement it here or call the parent.
        if hasattr(self.parent(), "edit_chit_batch"):
            self.parent().edit_chit_batch(batch_id)
            self.load_batches()
        else:
            # Fallback implementation if no parent method
            conn = scheme_db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT batch_name, chit_value, starting_date FROM chit_batches WHERE id = ?", (batch_id,))
            row = cursor.fetchone()
            conn.close()
            if row:
                data = {'name': row[0], 'value': row[1], 'start_date': row[2]}
                dialog = ChitBatchDialog(self)
                dialog.set_data(data)
                if dialog.exec_() == QDialog.Accepted:
                    new_data = dialog.get_data()
                    conn = scheme_db.get_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE chit_batches SET batch_name=?, chit_value=?, starting_date=? WHERE id=?", 
                                 (new_data['name'], new_data['value'], new_data['start_date'], batch_id))
                    conn.commit()
                    conn.close()
                    self.load_batches()

    def delete_chit_batch(self, batch_id):
        if hasattr(self.parent(), "delete_chit_batch"):
            self.parent().delete_chit_batch(batch_id)
            self.load_batches()
        else:
            # Fallback
            reply = QMessageBox.question(self, "Confirm", "Delete this batch?", QMessageBox.Yes|QMessageBox.No)
            if reply == QMessageBox.Yes:
                conn = scheme_db.get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM chit_batches WHERE id=?", (batch_id,))
                conn.commit()
                conn.close()
                self.load_batches()

    def manage_members(self, batch_id, batch_name):
        dialog = ManageBatchMembersDialog(batch_id, batch_name, self.parent())
        dialog.exec_()
        self.load_batches()

    def add_chit_batch(self):
        dialog = ChitBatchDialog(self)
        if getattr(self, 'filter_value', None):
            idx = dialog.value_combo.findData(self.filter_value)
            if idx >= 0: dialog.value_combo.setCurrentIndex(idx)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if not data['name']: return
            
            conn = scheme_db.get_connection()
            cursor = conn.cursor()
            try:
                # 1. Create Batch
                cursor.execute("""
                    INSERT INTO chit_batches (batch_name, chit_value, starting_date) 
                    VALUES (?, ?, ?)
                """, (data['name'], data['value'], data['start_date']))
                batch_id = cursor.lastrowid
                
                # 2. Create Account for this Batch
                acc_name = f"Batch: {data['name']} Account"
                cursor.execute("INSERT OR IGNORE INTO accounts (account_name, account_type) VALUES (?, 'CHIT_FUND')", (acc_name,))
                cursor.execute("SELECT id FROM accounts WHERE account_name = ?", (acc_name,))
                acc_id = cursor.fetchone()[0]
                
                # 3. Link Account to Batch
                cursor.execute("UPDATE chit_batches SET account_id = ? WHERE id = ?", (acc_id, batch_id))
                
                conn.commit()
                self.load_batches()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))
            finally:
                conn.close()

    def open_manage_funds(self):
        row = self.batches_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Selection Required", "Please select a batch from the table first.")
            return
            
        batch_id = int(self.batches_table.item(row, 0).text())
        batch_name = self.batches_table.item(row, 1).text()
        batch_value_str = self.batches_table.item(row, 2).text()
        
        dialog = ManageFundsDialog(batch_id, batch_name, batch_value_str, self.parent(), self)
        dialog.exec_()
        self.load_batches()

class BatchAccountDetailsDialog(QDialog):
    def __init__(self, account_id, account_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Account Details: {account_name}")
        self.setMinimumSize(900, 700)
        self.account_id = account_id
        
        layout = QVBoxLayout(self)
        
        # Summary Header
        self.summary_layout = QHBoxLayout()
        layout.addLayout(self.summary_layout)
        
        # Split View
        splitter_layout = QHBoxLayout()
        
        # Left: Members Summary
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("<b>Batch Members & Contributions:</b>"))
        self.members_table = QTableWidget()
        self.members_table.setColumnCount(3)
        self.members_table.setHorizontalHeaderLabels(["Member Name", "CIF", "Total Paid"])
        self.members_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.members_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.members_table.itemSelectionChanged.connect(self.on_member_selected)
        left_layout.addWidget(self.members_table)
        
        # Right: Transactions
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("<b>Recent Transactions (Specific to this Batch):</b>"))
        self.txn_table = QTableWidget()
        self.txn_table.setColumnCount(4)
        self.txn_table.setHorizontalHeaderLabels(["Type", "Amount", "Description", "Date"])
        self.txn_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_layout.addWidget(self.txn_table)
        
        splitter_layout.addLayout(left_layout, 2)
        splitter_layout.addLayout(right_layout, 3)
        layout.addLayout(splitter_layout)
        
        self.load_data()

    def load_data(self):
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        
        # 1. Fetch Batch Info via Account ID
        cursor.execute("SELECT id, batch_name, chit_value FROM chit_batches WHERE account_id = ?", (self.account_id,))
        batch_res = cursor.fetchone()
        if not batch_res:
            conn.close()
            return
        
        batch_id, batch_name, chit_val = batch_res
        
        # 2. Fetch Account Balance
        cursor.execute("SELECT balance FROM accounts WHERE id = ?", (self.account_id,))
        balance = cursor.fetchone()[0]
        
        # 3. Calculate Collection vs Distribution
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE account_id = ? AND transaction_type IN ('PAYMENT', 'DEPOSIT')", (self.account_id,))
        total_collection = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE account_id = ? AND transaction_type IN ('PAYOUT', 'WITHDRAW')", (self.account_id,))
        total_distribution = cursor.fetchone()[0] or 0
        
        # Update Header
        for i in reversed(range(self.summary_layout.count())): 
            self.summary_layout.itemAt(i).widget().setParent(None)
            
        self.summary_layout.addWidget(self.create_mini_card("Net Balance", balance, "#2196f3"))
        self.summary_layout.addWidget(self.create_mini_card("Total Collected", total_collection, "#4caf50"))
        self.summary_layout.addWidget(self.create_mini_card("Total Distributed", total_distribution, "#f44336"))
        
        # 4. Fetch Members and their total paid for this specific batch
        cursor.execute("""
            SELECT c.id, c.name, c.cif_number, SUM(l.paid_amount)
            FROM customers c
            JOIN batch_enrollments e ON c.id = e.customer_id
            LEFT JOIN customer_ledgers l ON c.id = l.customer_id AND l.batch_id = ?
            WHERE e.batch_id = ?
            GROUP BY c.id
        """, (batch_id, batch_id))
        members = cursor.fetchall()
        self.members_table.setRowCount(0)
        for r_idx, (c_id, m_name, m_cif, m_paid) in enumerate(members):
            self.members_table.insertRow(r_idx)
            item_name = QTableWidgetItem(m_name)
            item_name.setData(Qt.UserRole, c_id)
            self.members_table.setItem(r_idx, 0, item_name)
            self.members_table.setItem(r_idx, 1, QTableWidgetItem(str(m_cif)))
            self.members_table.setItem(r_idx, 2, QTableWidgetItem(f"₹{m_paid or 0:,.2f}"))
            
        # 5. Fetch Account Transactions
        cursor.execute("""
            SELECT transaction_type, amount, description, transaction_date 
            FROM transactions 
            WHERE account_id = ? 
            ORDER BY id DESC LIMIT 500
        """, (self.account_id,))
        self.all_txns = cursor.fetchall()
        
        self.filter_transactions(None)
        conn.close()

    def filter_transactions(self, customer_id):
        self.txn_table.setRowCount(0)
        filtered = []
        for t_type, t_amt, t_desc, t_date in self.all_txns:
            if customer_id is None:
                filtered.append((t_type, t_amt, t_desc, t_date))
            else:
                if f"Customer {customer_id} " in t_desc or t_desc.endswith(f"Cust {customer_id}"):
                    filtered.append((t_type, t_amt, t_desc, t_date))
                    
        for r_idx, (t_type, t_amt, t_desc, t_date) in enumerate(filtered):
            self.txn_table.insertRow(r_idx)
            self.txn_table.setItem(r_idx, 0, QTableWidgetItem(t_type))
            self.txn_table.setItem(r_idx, 1, QTableWidgetItem(f"₹{t_amt:,.2f}"))
            self.txn_table.setItem(r_idx, 2, QTableWidgetItem(t_desc))
            self.txn_table.setItem(r_idx, 3, QTableWidgetItem(t_date))

    def on_member_selected(self):
        items = self.members_table.selectedItems()
        if not items:
            self.filter_transactions(None)
            return
            
        row = items[0].row()
        item_name = self.members_table.item(row, 0)
        c_id = item_name.data(Qt.UserRole)
        self.filter_transactions(c_id)

    def create_mini_card(self, title, value, color):
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setStyleSheet(f"background-color: white; border-radius: 8px; border: 1px solid #e0e0e0;")
        l = QVBoxLayout(card)
        t = QLabel(title)
        t.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 11px;")
        v = QLabel(f"₹{value:,.2f}")
        v.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a1a1a;")
        l.addWidget(t)
        l.addWidget(v)
        return card

STYLESHEET = """
QMainWindow {
    background-color: #f0f2f5;
}

#Sidebar {
    background-color: #ffffff;
    border-right: 1px solid #e0e0e0;
    min-width: 250px;
    max-width: 250px;
}

#SidebarTitle {
    padding: 20px;
    color: #1a1a1a;
    font-size: 20px;
    font-weight: bold;
}

QListWidget {
    border: none;
    background-color: transparent;
    outline: none;
}

QListWidget::item {
    padding: 15px 20px;
    margin: 4px 10px;
    border-radius: 8px;
    color: #5f6368;
    font-weight: 500;
}

QListWidget::item:selected {
    background-color: #e8f0fe;
    color: #1a73e8;
}

QListWidget::item:hover {
    background-color: #f1f3f4;
}

#MainContent {
    background-color: #f8f9fa;
    padding: 20px;
}

#HeaderLabel {
    font-size: 24px;
    font-weight: bold;
    color: #1a1a1a;
    margin-bottom: 20px;
}

QFrame#Card {
    background-color: #ffffff;
    border-radius: 12px;
    padding: 20px;
}

QPushButton {
    background-color: #00875a;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #006b47;
}

QPushButton:disabled {
    background-color: #cccccc;
}

QTableWidget {
    background-color: white;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    gridline-color: #f0f0f0;
}

QHeaderView::section {
    background-color: #f8f9fa;
    padding: 10px;
    border: none;
    border-bottom: 1px solid #e0e0e0;
    font-weight: bold;
}

QLineEdit, QDateEdit, QDoubleSpinBox, QComboBox {
    padding: 8px;
    border: 1px solid #dcdcdc;
    border-radius: 6px;
    background-color: white;
}
"""

class SchemeFinanceApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GC Finance Management")
        self.resize(1200, 800)
        self.setStyleSheet(STYLESHEET)
        
        # Initialize DB
        scheme_db.initialize_db()
        
        # Pagination State for Customers
        self.customer_offset = 0
        self.customer_limit = 10
        self.loading_customers = False
        self.all_customers_loaded = False
        
        self.setup_ui()
        self.load_dashboard_data()
        self.load_customers(reset=True)
        self.load_scheme_master()
        
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        
        sidebar_title = QLabel("GC FINANCE")
        sidebar_title.setObjectName("SidebarTitle")
        sidebar_layout.addWidget(sidebar_title)
        
        self.nav_list = QListWidget()
        self.nav_list.addItem("Dashboard")
        self.nav_list.addItem("Customers (CIF)")
        self.nav_list.addItem("Chit Scheme")
        self.nav_list.addItem("SHG Groups")
        self.nav_list.addItem("Individual Loans")
        self.nav_list.addItem("Accounting")
        self.nav_list.addItem("Batches")
        self.nav_list.addItem("Scheme Config")
        self.nav_list.addItem("Backup & Restore")
        
        self.nav_list.currentRowChanged.connect(self.change_page)
        sidebar_layout.addWidget(self.nav_list, 9) # Give 90% relative stretch to the list
        sidebar_layout.addStretch(1) # Give 10% relative stretch to the bottom gap
        
        main_layout.addWidget(sidebar)
        
        # Main Content Area
        content_area = QFrame()
        content_area.setObjectName("MainContent")
        self.content_layout = QVBoxLayout(content_area)
        
        header_layout = QHBoxLayout()
        self.header_label = QLabel("Dashboard")
        self.header_label.setObjectName("HeaderLabel")
        
        self.global_search_input = QLineEdit()
        self.global_search_input.setPlaceholderText("Global Search: Name, Phone, CIF, Batch, SHG...")
        self.global_search_input.setFixedWidth(350)
        self.global_search_input.returnPressed.connect(self.perform_global_search)
        self.global_search_input.setStyleSheet("padding: 8px 12px; border: 1px solid #c0c0c0; border-radius: 20px; background-color: white; font-size: 13px;")
        
        header_layout.addWidget(self.header_label)
        header_layout.addStretch()
        header_layout.addWidget(self.global_search_input)
        
        self.content_layout.addLayout(header_layout)
        
        self.stacked_widget = QStackedWidget()
        self.content_layout.addWidget(self.stacked_widget)
        
        main_layout.addWidget(content_area)
        
        # Initialize Pages
        self.page_dashboard = QWidget()
        self.setup_dashboard_tab()
        
        self.page_customers = QWidget()
        self.setup_customers_tab() # Now purely for CIF
        
        self.page_chit = QWidget()
        self.setup_chit_tab() # Now for Chit management
        
        self.page_shg = QWidget()
        self.setup_shg_tab()
        
        self.page_individual = QWidget()
        self.setup_individual_tab()
        
        self.page_batches = QWidget()
        self.setup_batches_tab()
        
        self.page_accounting = QWidget()
        self.setup_accounting_tab()
        
        self.page_config = QWidget()
        self.setup_scheme_master_tab()
        
        self.page_backup = QWidget()
        self.setup_backup_restore_tab()
        
        self.stacked_widget.addWidget(self.page_dashboard)    # 0
        self.stacked_widget.addWidget(self.page_customers)    # 1
        self.stacked_widget.addWidget(self.page_chit)         # 2
        self.stacked_widget.addWidget(self.page_shg)          # 3
        self.stacked_widget.addWidget(self.page_individual)   # 4
        self.stacked_widget.addWidget(self.page_accounting)   # 5
        self.stacked_widget.addWidget(self.page_batches)      # 6
        self.stacked_widget.addWidget(self.page_config)       # 7
        self.stacked_widget.addWidget(self.page_backup)       # 8
        
        self.nav_list.setCurrentRow(0)

    def change_page(self, index):
        self.stacked_widget.setCurrentIndex(index)
        self.header_label.setText(self.nav_list.item(index).text())

    def perform_global_search(self):
        query_text = self.global_search_input.text().strip()
        if not query_text:
            return
            
        search_pattern = f"%{query_text}%"
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        
        results = []
        
        # 1. Search Customers and their involvements
        cursor.execute("""
            SELECT id, name, cif_number, phone FROM customers 
            WHERE name LIKE ? OR phone LIKE ? OR cif_number LIKE ?
        """, (search_pattern, search_pattern, search_pattern))
        customers = cursor.fetchall()
        
        for c_id, c_name, c_cif, c_phone in customers:
            involvements_found = False
            
            # Batches
            cursor.execute("""
                SELECT b.id, b.batch_name 
                FROM batch_enrollments e
                JOIN chit_batches b ON e.batch_id = b.id
                WHERE e.customer_id = ?
            """, (c_id,))
            for b_id, b_name in cursor.fetchall():
                results.append(('Customer (Batch)', c_id, c_name, f"Batch: {b_name} | CIF: {c_cif} | Ph: {c_phone}", b_id))
                involvements_found = True
                
            # SHGs
            cursor.execute("""
                SELECT g.id, g.group_name 
                FROM shg_members m
                JOIN shg_groups g ON m.group_id = g.id
                WHERE m.customer_id = ?
            """, (c_id,))
            for g_id, g_name in cursor.fetchall():
                results.append(('Customer (SHG)', c_id, c_name, f"SHG: {g_name} | CIF: {c_cif} | Ph: {c_phone}", g_id))
                involvements_found = True
                
            # Individual Loans
            cursor.execute("SELECT id, loan_amount FROM individual_loans WHERE customer_id = ?", (c_id,))
            for l_id, l_amt in cursor.fetchall():
                results.append(('Customer (Ind. Loan)', c_id, c_name, f"Loan: ₹{l_amt:,.0f} | CIF: {c_cif} | Ph: {c_phone}", l_id))
                involvements_found = True
                
            if not involvements_found:
                results.append(('Customer (Profile)', c_id, c_name, f"CIF: {c_cif} | Ph: {c_phone}", None))
            
        # 2. Search Batches directly
        cursor.execute("SELECT id, batch_name, chit_value FROM chit_batches WHERE batch_name LIKE ?", (search_pattern,))
        for row in cursor.fetchall():
            results.append(('Batch', row[0], row[1], f"Value: ₹{row[2]:,.0f}", None))
            
        # 3. Search SHG Groups directly
        cursor.execute("SELECT id, group_name FROM shg_groups WHERE group_name LIKE ?", (search_pattern,))
        for row in cursor.fetchall():
            results.append(('SHG', row[0], row[1], "", None))
            
        conn.close()
        
        if not results:
            QMessageBox.information(self, "Search", f"No results found for '{query_text}'.")
            return
            
        dialog = GlobalSearchResultsDialog(results, self)
        dialog.exec_()
        self.global_search_input.clear()

    def highlight_customer(self, customer_id):
        self.nav_list.setCurrentRow(1) # Customers tab
        
        # Find row in customers_table
        for row in range(self.customers_table.rowCount()):
            if int(self.customers_table.item(row, 0).text()) == customer_id:
                self.customers_table.selectRow(row)
                self.customers_table.scrollToItem(self.customers_table.item(row, 0))
                break

    def expand_batch(self, batch_id, batch_name):
        self.nav_list.setCurrentRow(6) # Batches tab
        
        for row in range(self.batches_table.rowCount()):
            if int(self.batches_table.item(row, 0).text()) == batch_id:
                self.batches_table.selectRow(row)
                self.batches_table.scrollToItem(self.batches_table.item(row, 0))
                break

    def highlight_shg(self, shg_id):
        self.nav_list.setCurrentRow(3) # SHG tab
        
        for row in range(self.shg_table.rowCount()):
            if int(self.shg_table.item(row, 0).text()) == shg_id:
                self.shg_table.selectRow(row)
                self.shg_table.scrollToItem(self.shg_table.item(row, 0))
                break

    def highlight_ind_loan(self, loan_id):
        self.nav_list.setCurrentRow(4) # Individual Loan tab
        
        for row in range(self.ind_loan_table.rowCount()):
            if int(self.ind_loan_table.item(row, 0).text()) == loan_id:
                self.ind_loan_table.selectRow(row)
                self.ind_loan_table.scrollToItem(self.ind_loan_table.item(row, 0))
                break

    def setup_dashboard_tab(self):
        layout = QVBoxLayout(self.page_dashboard)
        
        # Row 1: Active Schemes
        schemes_layout = QHBoxLayout()
        self.card_chit = self.create_card("Active Chit Scheme", "0", "#2196f3")
        self.card_shg = self.create_card("Active SHG Loans", "0", "#9c27b0")
        self.card_ind = self.create_card("Active Ind. Loans", "0", "#f44336")
        
        schemes_layout.addWidget(self.card_chit)
        schemes_layout.addWidget(self.card_shg)
        schemes_layout.addWidget(self.card_ind)
        layout.addLayout(schemes_layout)
        
        # Row 2: Financials
        finance_layout = QHBoxLayout()
        self.card_cash = self.create_card("Cash in Hand", "₹0.00", "#4caf50")
        self.card_bank = self.create_card("Bank Balance", "₹0.00", "#ff9800")
        self.card_total_cust = self.create_card("Total CIFs", "0", "#607d8b")
        
        finance_layout.addWidget(self.card_cash)
        finance_layout.addWidget(self.card_bank)
        finance_layout.addWidget(self.card_total_cust)
        layout.addLayout(finance_layout)
        
        layout.addStretch()

    def create_card(self, title, value, color):
        card = QFrame()
        card.setObjectName("Card")
        card.setMinimumHeight(120)
        
        # Shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 20))
        card.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(card)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 14px;")
        
        val_lbl = QLabel(value)
        val_lbl.setStyleSheet("font-size: 24px; font-weight: bold; color: #1a1a1a;")
        
        layout.addWidget(title_lbl)
        layout.addWidget(val_lbl)
        layout.addStretch()
        
        # Store label for updates
        card.value_label = val_lbl
        
        return card

    def load_dashboard_data(self):
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        
        # Active counts
        cursor.execute("SELECT COUNT(*) FROM customers WHERE status = 'Active'")
        active_chit_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM shg_loans WHERE status = 'Active'")
        shg_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM individual_loans WHERE status = 'Active'")
        ind_count = cursor.fetchone()[0]
        
        # Financials
        cursor.execute("SELECT balance FROM accounts WHERE account_name = 'Cash in Hand'")
        cash_row = cursor.fetchone()
        cash = cash_row[0] if cash_row else 0.0
        
        cursor.execute("SELECT balance FROM accounts WHERE account_name = 'Bank Account'")
        bank_row = cursor.fetchone()
        bank = bank_row[0] if bank_row else 0.0
        
        cursor.execute("SELECT COUNT(*) FROM customers")
        total_cust_count = cursor.fetchone()[0]
        
        # Update Cards
        self.card_chit.value_label.setText(str(active_chit_count))
        self.card_shg.value_label.setText(str(shg_count))
        self.card_ind.value_label.setText(str(ind_count))
        self.card_cash.value_label.setText(f"₹{cash:,.2f}")
        self.card_bank.value_label.setText(f"₹{bank:,.2f}")
        self.card_total_cust.value_label.setText(str(total_cust_count))
        
        conn.close()

    def setup_customers_tab(self):
        # Purely for managing Customer Information (CIF)
        layout = QVBoxLayout(self.page_customers)
        
        btn_layout = QHBoxLayout()
        self.btn_add_customer = QPushButton("Add New CIF")
        self.btn_add_customer.clicked.connect(self.add_customer)
        
        self.btn_refresh_customers = QPushButton("Refresh")
        self.btn_refresh_customers.clicked.connect(lambda: self.load_customers(reset=True))
        
        btn_layout.addWidget(self.btn_add_customer)
        btn_layout.addWidget(self.btn_refresh_customers)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.customers_table = QTableWidget()
        self.customers_table.setColumnCount(8)
        self.customers_table.setHorizontalHeaderLabels(["ID", "Photo", "CIF", "Name", "Aadhar", "Phone", "Status", "Actions"])
        self.customers_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.customers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.customers_table.setIconSize(QSize(40, 40))
        self.customers_table.cellClicked.connect(self.on_customer_cell_clicked)
        self.customers_table.verticalScrollBar().valueChanged.connect(self.on_customer_scroll)
        layout.addWidget(self.customers_table)
        
    def setup_chit_tab(self):
        # Specific for Chit Scheme tracking
        layout = QVBoxLayout(self.page_chit)
        
        header_layout = QHBoxLayout()
        lbl = QLabel("Chit Scheme Management")
        lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a73e8;")
        header_layout.addWidget(lbl)
        header_layout.addStretch()
        
        self.btn_payments = QPushButton("Record Payment")
        self.btn_payments.clicked.connect(self.open_payment_recorder)
        self.btn_payments.setStyleSheet("background-color: #4caf50; color: white; font-weight: bold;")
        header_layout.addWidget(self.btn_payments)
        
        self.btn_manage_batches = QPushButton("Manage Batches")
        self.btn_manage_batches.clicked.connect(self.open_batch_management)
        self.btn_manage_batches.setStyleSheet("background-color: #e8f0fe; color: #1a73e8; font-weight: bold;")
        header_layout.addWidget(self.btn_manage_batches)
        
        layout.addLayout(header_layout)
        
        self.chit_values_layout = QHBoxLayout()
        layout.addLayout(self.chit_values_layout)
        
        self.chit_summary_table = QTableWidget()
        self.chit_summary_table.setColumnCount(6)
        self.chit_summary_table.setHorizontalHeaderLabels(["Chit Value", "Total Batches", "Batch Names", "Total Collection", "Totally Distributed", "In Circulation"])
        self.chit_summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.chit_summary_table.setMaximumHeight(250)
        self.chit_summary_table.setSelectionMode(QTableWidget.NoSelection)
        self.chit_summary_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.chit_summary_table)
        
        self.load_chit_data()

    def open_payment_recorder(self):
        selector = CIFSelectorDialog(self)
        if selector.exec_() == QDialog.Accepted:
            cust = selector.get_selected_customer()
            if cust:
                self.view_ledger(cust['id'])

    def open_batch_management(self):
        dialog = BatchManagementDialog(self)
        dialog.exec_()
        self.load_chit_data()

    def open_batch_management_for_value(self, value):
        dialog = BatchManagementDialog(self, filter_value=value)
        dialog.exec_()
        self.load_chit_data()

    def load_chit_data(self):
        # Clear existing boxes
        while self.chit_values_layout.count():
            item = self.chit_values_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
                
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        
        # Populate Value Boxes
        cursor.execute("SELECT DISTINCT total_value FROM scheme_master ORDER BY total_value")
        values = cursor.fetchall()
        
        for val in values:
            v = val[0]
            btn = QPushButton(f"₹{v:,.0f}")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #ffffff;
                    color: #1a73e8;
                    border: 2px solid #1a73e8;
                    padding: 15px 25px;
                    font-size: 16px;
                    font-weight: bold;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #1a73e8;
                    color: white;
                }
            """)
            btn.clicked.connect(lambda _, value=v: self.open_batch_management_for_value(value))
            self.chit_values_layout.addWidget(btn)
        self.chit_values_layout.addStretch()
        
        # Populate Summary Table
        self.chit_summary_table.setRowCount(0)
        r_idx = 0
        grand_total_batches = 0
        grand_total_collection = 0
        grand_total_distribution = 0
        
        for val in values:
            v = val[0]
            cursor.execute("SELECT id, batch_name, account_id FROM chit_batches WHERE chit_value = ?", (v,))
            batches = cursor.fetchall()
            
            if not batches:
                continue
                
            total_collection = 0
            total_distribution = 0
            batch_names = []
            
            for bid, bname, acc_id in batches:
                batch_names.append(bname)
                if acc_id:
                    cursor.execute("SELECT SUM(amount) FROM transactions WHERE account_id = ? AND transaction_type IN ('PAYMENT', 'DEPOSIT')", (acc_id,))
                    col = cursor.fetchone()[0] or 0
                    total_collection += col
                    
                    cursor.execute("SELECT SUM(amount) FROM transactions WHERE account_id = ? AND transaction_type IN ('PAYOUT', 'WITHDRAW')", (acc_id,))
                    dist = cursor.fetchone()[0] or 0
                    total_distribution += dist
                
            in_circulation = total_collection - total_distribution
            grand_total_batches += len(batches)
            grand_total_collection += total_collection
            grand_total_distribution += total_distribution
            
            self.chit_summary_table.insertRow(r_idx)
            v_item = QTableWidgetItem(f"₹{v:,.0f}")
            v_item.setFont(QFont("Arial", weight=QFont.Bold))
            self.chit_summary_table.setItem(r_idx, 0, v_item)
            self.chit_summary_table.setItem(r_idx, 1, QTableWidgetItem(str(len(batches))))
            self.chit_summary_table.setItem(r_idx, 2, QTableWidgetItem(", ".join(batch_names)))
            self.chit_summary_table.setItem(r_idx, 3, QTableWidgetItem(f"₹{total_collection:,.2f}"))
            self.chit_summary_table.setItem(r_idx, 4, QTableWidgetItem(f"₹{total_distribution:,.2f}"))
            
            circ_item = QTableWidgetItem(f"₹{in_circulation:,.2f}")
            if in_circulation > 0:
                circ_item.setForeground(QColor("#4caf50")) # Green
                circ_item.setFont(QFont("Arial", weight=QFont.Bold))
            elif in_circulation < 0:
                circ_item.setForeground(QColor("#f44336")) # Red
                circ_item.setFont(QFont("Arial", weight=QFont.Bold))
            self.chit_summary_table.setItem(r_idx, 5, circ_item)
            r_idx += 1
            
        if r_idx > 0:
            self.chit_summary_table.insertRow(r_idx)
            total_item = QTableWidgetItem("GRAND TOTAL")
            total_item.setFont(QFont("Arial", weight=QFont.Bold))
            total_item.setBackground(QColor("#e8f0fe"))
            self.chit_summary_table.setItem(r_idx, 0, total_item)
            
            b_item = QTableWidgetItem(str(grand_total_batches))
            b_item.setFont(QFont("Arial", weight=QFont.Bold))
            b_item.setBackground(QColor("#e8f0fe"))
            self.chit_summary_table.setItem(r_idx, 1, b_item)
            
            name_item = QTableWidgetItem("-")
            name_item.setBackground(QColor("#e8f0fe"))
            self.chit_summary_table.setItem(r_idx, 2, name_item)
            
            c_item = QTableWidgetItem(f"₹{grand_total_collection:,.2f}")
            c_item.setFont(QFont("Arial", weight=QFont.Bold))
            c_item.setBackground(QColor("#e8f0fe"))
            self.chit_summary_table.setItem(r_idx, 3, c_item)
            
            d_item = QTableWidgetItem(f"₹{grand_total_distribution:,.2f}")
            d_item.setFont(QFont("Arial", weight=QFont.Bold))
            d_item.setBackground(QColor("#e8f0fe"))
            self.chit_summary_table.setItem(r_idx, 4, d_item)
            
            grand_in_circ = grand_total_collection - grand_total_distribution
            circ_item = QTableWidgetItem(f"₹{grand_in_circ:,.2f}")
            circ_item.setFont(QFont("Arial", weight=QFont.Bold))
            circ_item.setBackground(QColor("#e8f0fe"))
            if grand_in_circ > 0:
                circ_item.setForeground(QColor("#4caf50"))
            elif grand_in_circ < 0:
                circ_item.setForeground(QColor("#f44336"))
            self.chit_summary_table.setItem(r_idx, 5, circ_item)

        conn.close()

    def allocate_batch_ledgers(self, batch_id, customer_ids):
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        try:
            # Get batch value and starting date
            cursor.execute("SELECT chit_value, starting_date FROM chit_batches WHERE id = ?", (batch_id,))
            b_row = cursor.fetchone()
            chit_value = b_row[0]
            start_date_str = b_row[1] or ""
            
            # Get template for this value
            cursor.execute("SELECT month_number, payable_amount FROM scheme_master WHERE total_value = ? ORDER BY month_number", (chit_value,))
            template = cursor.fetchall()
            
            for cid in customer_ids:
                # Check if already has ledger for THIS batch
                cursor.execute("SELECT COUNT(*) FROM customer_ledgers WHERE customer_id = ? AND batch_id = ?", (cid, batch_id))
                if cursor.fetchone()[0] == 0:
                    for month, amount in template:
                        due_date = calculate_due_date(start_date_str, month - 1)
                        cursor.execute("""
                        INSERT INTO customer_ledgers (customer_id, batch_id, month_number, due_date, due_amount, status)
                        VALUES (?, ?, ?, ?, ?, 'Pending')
                        """, (cid, batch_id, month, due_date, amount))
            conn.commit()
        except Exception as e:
            print(f"Ledger Allocation Error: {e}")
        finally:
            conn.close()

    def view_ledger(self, customer_id):
        # Generate or view ledgers for the customer
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT c.cif_number, c.name, c.withdrawn_month, b.chit_value 
            FROM customers c
            LEFT JOIN chit_batches b ON c.batch_id = b.id
            WHERE c.id = ?
        """, (customer_id,))
        cust = cursor.fetchone()
        
        if not cust:
            conn.close()
            return

    def on_customer_scroll(self, value):
        if not self.loading_customers and not self.all_customers_loaded:
            # Check if scrollbar is near the bottom
            if value >= self.customers_table.verticalScrollBar().maximum() - 2:
                self.load_customers(reset=False)

    def load_customers(self, reset=True):
        if self.loading_customers: return
        self.loading_customers = True
        
        if reset:
            self.customer_offset = 0
            self.customers_table.setRowCount(0)
            self.all_customers_loaded = False
            
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, photo_path, cif_number, name, aadhar_number, phone, status FROM customers LIMIT ? OFFSET ?", 
                       (self.customer_limit, self.customer_offset))
        rows = cursor.fetchall()
        
        if not rows:
            self.all_customers_loaded = True
        else:
            start_row = self.customers_table.rowCount()
            for row_idx, row_data in enumerate(rows):
                current_row = start_row + row_idx
                self.customers_table.insertRow(current_row)
                
                self.customers_table.setItem(current_row, 0, QTableWidgetItem(str(row_data[0])))
                
                photo_item = QTableWidgetItem()
                photo_item.setIcon(create_circular_avatar(row_data[1] if row_data[1] else "", 40))
                photo_item.setData(Qt.UserRole, row_data[1] if row_data[1] else "")
                self.customers_table.setItem(current_row, 1, photo_item)
                
                self.customers_table.setItem(current_row, 2, QTableWidgetItem(str(row_data[2])))
                self.customers_table.setItem(current_row, 3, QTableWidgetItem(str(row_data[3])))
                self.customers_table.setItem(current_row, 4, QTableWidgetItem(str(row_data[4])))
                self.customers_table.setItem(current_row, 5, QTableWidgetItem(str(row_data[5])))
                self.customers_table.setItem(current_row, 6, QTableWidgetItem(str(row_data[6])))
                
                # Actions Column
                action_widget = QWidget()
                action_layout = QHBoxLayout(action_widget)
                action_layout.setContentsMargins(0,0,0,0)
                
                btn_view = QPushButton("View")
                btn_view.setStyleSheet("background-color: #2196f3; color: white; padding: 4px 8px;")
                btn_view.clicked.connect(lambda _, cid=row_data[0]: self.view_customer(cid))
                
                btn_edit = QPushButton("Edit")
                btn_edit.setStyleSheet("padding: 4px 8px;")
                btn_edit.clicked.connect(lambda _, cid=row_data[0]: self.edit_customer(cid))
                
                btn_delete = QPushButton("Delete")
                btn_delete.clicked.connect(lambda _, cid=row_data[0]: self.delete_customer(cid))
                btn_delete.setStyleSheet("background-color: #f44336; color: white; padding: 4px 8px;")
                
                action_layout.addWidget(btn_view)
                action_layout.addWidget(btn_edit)
                action_layout.addWidget(btn_delete)
                self.customers_table.setCellWidget(current_row, 7, action_widget)
            
            self.customer_offset += len(rows)
            
            # If no scrollbar is visible yet, load more to fill the screen
            QTimer.singleShot(100, self.check_more_customers_needed)
            
        conn.close()
        self.loading_customers = False

    def on_customer_cell_clicked(self, row, column):
        if column == 1: # Photo column
            item = self.customers_table.item(row, column)
            if item:
                photo_path = item.data(Qt.UserRole)
                if photo_path and os.path.exists(photo_path):
                    dialog = QDialog(self)
                    dialog.setWindowTitle("Customer Photo Preview")
                    layout = QVBoxLayout(dialog)
                    label = QLabel()
                    pixmap = QPixmap(photo_path)
                    if not pixmap.isNull():
                        label.setPixmap(pixmap.scaled(600, 600, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    layout.addWidget(label)
                    dialog.exec_()

    def check_more_customers_needed(self):
        if not self.all_customers_loaded:
            if self.customers_table.verticalScrollBar().maximum() == 0:
                self.load_customers(reset=False)

    def add_customer(self):
        next_cif = self.get_next_cif_number()
        
        dialog = AddCustomerDialog(next_cif, self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if not data['cif'] or not data['name'] or len(data['aadhar_number']) < 12:
                QMessageBox.warning(self, "Error", "CIF, Name and a valid 12-digit Aadhar Number are required.")
                return
            
            # Handle Image/PDF Storage
            final_image_path = ""
            if data['aadhar_image_path']:
                if not os.path.exists("aadhar_documents"):
                    os.makedirs("aadhar_documents")
                
                ext = os.path.splitext(data['aadhar_image_path'])[1]
                filename = f"{data['cif']}_aadhar{ext}"
                final_image_path = os.path.join("aadhar_documents", filename)
                try:
                    shutil.copy2(data['aadhar_image_path'], final_image_path)
                except Exception as e:
                    QMessageBox.warning(self, "File Error", f"Could not save document: {e}")
                    
            final_photo_path = ""
            if data.get('photo_path') and os.path.exists(data['photo_path']):
                if not os.path.exists("uploads/customers"):
                    os.makedirs("uploads/customers")
                
                ext = os.path.splitext(data['photo_path'])[1].lower()
                timestamp = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
                filename = f"customer_{data['cif']}_{timestamp}{ext}"
                final_photo_path = os.path.join("uploads/customers", filename)
                
                pixmap = QPixmap(data['photo_path'])
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(500, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    fmt = ext.replace('.', '').upper()
                    if fmt == 'JPG': fmt = 'JPEG'
                    scaled_pixmap.save(final_photo_path, fmt, 80)
            
            conn = scheme_db.get_connection()
            cursor = conn.cursor()
            try:
                # 1. Insert/Update CIF
                cursor.execute("""
                INSERT OR IGNORE INTO customers (cif_number, name, surname, phone, address, join_date, aadhar_number, aadhar_image_path, photo_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (data['cif'], data['name'], data['surname'], data['phone'], data['address'], data['join_date'], data['aadhar_number'], final_image_path, final_photo_path))
                
                conn.commit()
                
                self.load_customers()
                self.load_dashboard_data()
            except Exception as e:
                conn.rollback()
                QMessageBox.warning(self, "Database Error", str(e))
            finally:
                conn.close()

    def get_next_cif_number(self):
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT cif_number FROM customers ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            try:
                last_cif = int(row[0])
                return str(last_cif + 1)
            except:
                return "1000"
        return "1000"

    def view_customer(self, customer_id):
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, cif_number, name, surname, phone, address, join_date, aadhar_number, aadhar_image_path, photo_path, status, created_at FROM customers WHERE id = ?", (customer_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Customer Details - {row[2]}")
            dialog.resize(600, 500)
            layout = QVBoxLayout(dialog)
            
            browser = QTextBrowser()
            layout.addWidget(browser)
            
            photo_path = row[9]
            photo_html = ""
            if photo_path and os.path.exists(photo_path):
                # Convert backslashes to forward slashes for HTML
                photo_url = QUrl.fromLocalFile(os.path.abspath(photo_path)).toString()
                photo_html = f'<img src="{photo_url}" width="150" height="150" style="float: right; border-radius: 8px; object-fit: cover; border: 2px solid #ccc;">'
            
            html_content = f"""
            <html>
            <head>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 10px; color: #333; }}
                .container {{ position: relative; }}
                h2 {{ margin-top: 0; color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 5px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ padding: 10px; border-bottom: 1px solid #eee; text-align: left; vertical-align: top; }}
                th {{ width: 35%; color: #555; font-weight: bold; background-color: #f9f9f9; }}
                td {{ font-size: 14px; }}
                .badge {{ display: inline-block; padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; color: white; }}
                .badge-active {{ background-color: #4caf50; }}
                .badge-inactive {{ background-color: #f44336; }}
                .print-btn {{
                    background-color: #4caf50;
                    color: white;
                    padding: 10px 20px;
                    border: none;
                    border-radius: 4px;
                    font-size: 14px;
                    font-weight: bold;
                    cursor: pointer;
                    margin-bottom: 15px;
                }}
                .print-btn:hover {{ background-color: #45a049; }}
                @media print {{
                    .no-print {{ display: none !important; }}
                    body {{ padding: 0; }}
                }}
            </style>
            </head>
            <body>
                <div class="no-print" style="text-align: right;">
                    <button class="print-btn" onclick="window.print()">🖨️ Print Profile</button>
                </div>
                <div class="container">
                    {photo_html}
                    <h2>{row[2]} {row[3] if row[3] else ''}</h2>
                    <p style="color: #666; font-size: 14px; margin-bottom: 20px;">
                        <b>CIF Number:</b> {row[1]}<br>
                        <b>ID:</b> {row[0]}
                    </p>
                    
                    <div style="clear: both;"></div>
                    
                    <table>
                        <tr><th>Status</th><td><span class="badge {'badge-active' if row[10] == 'Active' else 'badge-inactive'}">{row[10]}</span></td></tr>
                        <tr><th>Phone Number</th><td>{row[4]}</td></tr>
                        <tr><th>Address</th><td>{row[5] if row[5] else 'N/A'}</td></tr>
                        <tr><th>Join Date</th><td>{row[6]}</td></tr>
                        <tr><th>Aadhar Number</th><td>{row[7]}</td></tr>
                        <tr><th>Profile Created At</th><td>{row[11]}</td></tr>
                    </table>
                </div>
            </body>
            </html>
            """
            browser.setHtml(html_content)
            
            def do_print_preview():
                import tempfile
                import webbrowser
                import os
                
                temp_dir = tempfile.gettempdir()
                file_path = os.path.join(temp_dir, f"customer_preview_{row[0]}.html")
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                # Use file:// with forward slashes for better cross-platform browser support
                file_uri = 'file:///' + os.path.abspath(file_path).replace('\\', '/')
                webbrowser.open(file_uri)

            btn_layout = QHBoxLayout()
            btn_layout.addStretch()
            
            print_btn = QPushButton("Print Preview")
            print_btn.clicked.connect(do_print_preview)
            print_btn.setStyleSheet("padding: 8px 24px; background-color: #4caf50; color: white; border: none; border-radius: 4px; font-weight: bold;")
            
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dialog.accept)
            close_btn.setStyleSheet("""
                QPushButton {
                    background-color: #dc3545;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    padding: 8px 18px;
                }
                QPushButton:hover {
                    background-color: #b52a37;
                }
            """)
            close_btn.setCursor(Qt.PointingHandCursor)
            
            btn_layout.addWidget(print_btn)
            btn_layout.addWidget(close_btn)
            layout.addLayout(btn_layout)
            
            dialog.exec_()

    def edit_customer(self, customer_id):
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT cif_number, name, surname, phone, address, join_date, aadhar_number, aadhar_image_path, photo_path FROM customers WHERE id = ?", (customer_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            data = {
                'cif': row[0], 'name': row[1], 'surname': row[2], 'phone': row[3], 'address': row[4],
                'join_date': row[5], 'aadhar_number': row[6], 'aadhar_image_path': row[7], 'photo_path': row[8]
            }
            dialog = AddCustomerDialog(data['cif'], self)
            dialog.setWindowTitle("Edit CIF (Customer)")
            dialog.set_data(data)
            
            if dialog.exec_() == QDialog.Accepted:
                new_data = dialog.get_data()
                
                # Handle Image/PDF Storage
                final_path = new_data['aadhar_image_path']
                if final_path and not final_path.startswith("aadhar_documents"):
                    if not os.path.exists("aadhar_documents"):
                        os.makedirs("aadhar_documents")
                    ext = os.path.splitext(final_path)[1]
                    filename = f"{new_data['cif']}_aadhar{ext}"
                    new_final_path = os.path.join("aadhar_documents", filename)
                    try:
                        shutil.copy2(final_path, new_final_path)
                        final_path = new_final_path
                    except Exception as e:
                        QMessageBox.warning(self, "File Error", f"Could not save document: {e}")
                        
                final_photo_path = new_data.get('photo_path', '')
                if final_photo_path and not final_photo_path.startswith("uploads/customers") and not final_photo_path.startswith("uploads\\customers"):
                    if not os.path.exists("uploads/customers"):
                        os.makedirs("uploads/customers")
                        
                    ext = os.path.splitext(final_photo_path)[1].lower()
                    timestamp = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
                    filename = f"customer_{new_data['cif']}_{timestamp}{ext}"
                    new_final_photo_path = os.path.join("uploads/customers", filename)
                    
                    pixmap = QPixmap(final_photo_path)
                    if not pixmap.isNull():
                        scaled_pixmap = pixmap.scaled(500, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        fmt = ext.replace('.', '').upper()
                        if fmt == 'JPG': fmt = 'JPEG'
                        scaled_pixmap.save(new_final_photo_path, fmt, 80)
                        final_photo_path = new_final_photo_path
                
                conn = scheme_db.get_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("""
                    UPDATE customers 
                    SET name=?, surname=?, phone=?, address=?, join_date=?, aadhar_number=?, aadhar_image_path=?, photo_path=?
                    WHERE id=?
                    """, (new_data['name'], new_data['surname'], new_data['phone'], new_data['address'], new_data['join_date'], new_data['aadhar_number'], final_path, final_photo_path, customer_id))
                    conn.commit()
                    self.load_customers()
                    self.load_chit_data()
                    self.load_dashboard_data()
                except Exception as e:
                    QMessageBox.warning(self, "Database Error", str(e))
                finally:
                    conn.close()

    def delete_customer(self, customer_id):
        reply = QMessageBox.question(self, "Confirm Delete", "Are you sure you want to delete this customer? This cannot be undone.", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            conn = scheme_db.get_connection()
            cursor = conn.cursor()
            try:
                # Dependency Checks
                cursor.execute("SELECT COUNT(*) FROM customer_ledgers WHERE customer_id = ?", (customer_id,))
                if cursor.fetchone()[0] > 0:
                    QMessageBox.warning(self, "Error", "Cannot delete customer with existing ledger/payment records.")
                    return
                
                cursor.execute("SELECT COUNT(*) FROM individual_loans WHERE customer_id = ?", (customer_id,))
                if cursor.fetchone()[0] > 0:
                    QMessageBox.warning(self, "Error", "Cannot delete customer with active individual loans.")
                    return
                
                cursor.execute("SELECT COUNT(*) FROM shg_groups WHERE leader_id = ?", (customer_id,))
                if cursor.fetchone()[0] > 0:
                    QMessageBox.warning(self, "Error", "Cannot delete customer who is a leader of an SHG group.")
                    return

                cursor.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
                conn.commit()
                self.load_customers()
                self.load_chit_data()
                self.load_dashboard_data()
                QMessageBox.information(self, "Success", "Customer deleted successfully.")
            except Exception as e:
                QMessageBox.warning(self, "Database Error", str(e))
            finally:
                conn.close()

    def view_ledger(self, customer_id, batch_id):
        # Generate or view ledgers for the customer in a specific batch
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT c.cif_number, c.name, e.withdrawn_month, b.chit_value 
            FROM customers c
            JOIN batch_enrollments e ON c.id = e.customer_id
            JOIN chit_batches b ON e.batch_id = b.id
            WHERE c.id = ? AND e.batch_id = ?
        """, (customer_id, batch_id))
        cust = cursor.fetchone()
        conn.close()
        
        if not cust:
            return
            
        cif_number, name, withdrawn_month, chit_value = cust
        
        dialog = CustomerLedgerDialog(customer_id, name, cif_number, chit_value or 0, batch_id, self)
        dialog.exec_()

    def record_payment(self, customer_id, month_number, due_amount, batch_id):
        dialog = PaymentDialog(customer_id, month_number, due_amount, self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            paid = data['amount']
            date = data['date']
            arrears = data['arrears']
            
            conn = scheme_db.get_connection()
            cursor = conn.cursor()
            try:
                # 0. Get Batch Account
                cursor.execute("SELECT account_id FROM chit_batches WHERE id = ?", (batch_id,))
                batch_res = cursor.fetchone()
                batch_acc_id = batch_res[0] if batch_res else None

                # 1. Update Ledger
                status = 'Paid' if arrears <= 0 else 'Partial'
                cursor.execute("""
                UPDATE customer_ledgers 
                SET paid_amount = ?, payment_date = ?, status = ?
                WHERE customer_id = ? AND batch_id = ? AND month_number = ?
                """, (paid, date, status, customer_id, batch_id, month_number))
                
                # 2. Carry forward arrears to NEXT month
                if arrears > 0 and month_number < 20:
                    cursor.execute("""
                    UPDATE customer_ledgers 
                    SET due_amount = due_amount + ?
                    WHERE customer_id = ? AND batch_id = ? AND month_number = ?
                    """, (arrears, customer_id, batch_id, month_number + 1))
                
                # 3. Accounting: Add to Cash in Hand
                cursor.execute("UPDATE accounts SET balance = balance + ? WHERE account_name = 'Cash in Hand'", (paid,))
                cursor.execute("SELECT id FROM accounts WHERE account_name = 'Cash in Hand'")
                cash_acc_id = cursor.fetchone()[0]
                
                desc = f"Customer {customer_id} Payment for Month {month_number}"
                cursor.execute("""
                INSERT INTO transactions (account_id, related_account_id, transaction_type, amount, description, transaction_date)
                VALUES (?, ?, 'PAYMENT', ?, ?, ?)
                """, (cash_acc_id, batch_acc_id, paid, desc, date))

                # 3a. Update Batch Account balance
                if batch_acc_id:
                    cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (paid, batch_acc_id))
                    cursor.execute("""
                    INSERT INTO transactions (account_id, related_account_id, transaction_type, amount, description, transaction_date)
                    VALUES (?, ?, 'PAYMENT', ?, ?, ?)
                    """, (batch_acc_id, cash_acc_id, paid, desc, date))
                
                # Special logic for Month 1 Commission
                if month_number == 1:
                    cursor.execute("SELECT id FROM accounts WHERE account_name = 'Company Commission'")
                    comm_acc_id = cursor.fetchone()[0]
                    cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (paid, comm_acc_id))
                    cursor.execute("""
                    INSERT INTO transactions (account_id, transaction_type, amount, description, transaction_date)
                    VALUES (?, 'COMMISSION', ?, ?, ?)
                    """, (comm_acc_id, paid, "Month 1 Commission from Cust " + str(customer_id), date))

                conn.commit()
                QMessageBox.information(self, "Success", "Payment recorded successfully!")
                self.load_chit_data()
                self.load_dashboard_data()
                return True
            except Exception as e:
                conn.rollback()
                QMessageBox.warning(self, "Database Error", str(e))
                return False
            finally:
                conn.close()
        return False

    def withdraw_loan(self, customer_id, batch_id):
        # Find which month they are in
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT MAX(l.month_number), e.batch_id, b.chit_value
            FROM batch_enrollments e
            LEFT JOIN customer_ledgers l ON e.customer_id = l.customer_id AND e.batch_id = l.batch_id AND l.status = 'Paid'
            JOIN chit_batches b ON e.batch_id = b.id
            WHERE e.customer_id = ? AND e.batch_id = ?
        """, (customer_id, batch_id))
        res = cursor.fetchone()
        last_month_paid, batch_id, chit_value = res
        
        current_month = (last_month_paid or 0) + 1
        
        if current_month < 2:
            QMessageBox.warning(self, "Warning", "Withdrawal not allowed before month 2 payment.")
            conn.close()
            return
            
        # Fetch from scheme_master using chit_value
        cursor.execute("""
            SELECT withdrawable_amount, liability_emi 
            FROM scheme_master 
            WHERE month_number = ? AND total_value = ?
        """, (current_month, chit_value))
        scheme = cursor.fetchone()
        
        if not scheme or scheme[0] <= 0:
            QMessageBox.warning(self, "Warning", "No withdrawable amount configured for month " + str(current_month))
            conn.close()
            return
            
        withdrawable_amount = scheme[0]
        new_emi = scheme[1]
        
        reply = QMessageBox.question(self, "Withdraw Loan", 
            f"Customer is eligible to withdraw ₹{withdrawable_amount:,.0f} in Month {current_month}.\n"
            f"Future EMI will be ₹{new_emi:,.0f}.\n\nProceed?", QMessageBox.Yes | QMessageBox.No)
            
        if reply == QMessageBox.Yes:
            # Payout Logic
            cursor.execute("SELECT id, balance FROM accounts WHERE account_name = 'Cash in Hand'")
            cash_acc = cursor.fetchone()
            
            if cash_acc[1] < withdrawable_amount:
                QMessageBox.warning(self, "Insufficient Funds", f"Cash in Hand (₹{cash_acc[1]:,.0f}) is insufficient for withdrawal (₹{withdrawable_amount:,.0f}).")
                conn.close()
                return
                
            # Get Batch Account
            cursor.execute("SELECT account_id FROM chit_batches WHERE id = ?", (batch_id,))
            batch_acc_res = cursor.fetchone()
            batch_acc_id = batch_acc_res[0] if batch_acc_res else None

            try:
                # 1. Update enrollment withdrawn_month
                cursor.execute("UPDATE batch_enrollments SET withdrawn_month = ? WHERE customer_id = ? AND batch_id = ?", (current_month, customer_id, batch_id))
                
                # 1a. Update future ledger entries with Liability EMI
                cursor.execute("SELECT month_number, liability_emi FROM scheme_master WHERE total_value = ? AND month_number > ?", (chit_value, current_month))
                future_emis = cursor.fetchall()
                for m, emi in future_emis:
                    cursor.execute("UPDATE customer_ledgers SET due_amount = ? WHERE customer_id = ? AND batch_id = ? AND month_number = ?", (emi, customer_id, batch_id, m))

                # 2. Update accounts
                cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (withdrawable_amount, cash_acc[0]))
                
                # 3. Add transaction
                desc = f"Loan Withdrawal for Customer {customer_id} in Month {current_month}"
                cursor.execute("""
                INSERT INTO transactions (account_id, related_account_id, transaction_type, amount, description)
                VALUES (?, ?, 'PAYOUT', ?, ?)
                """, (cash_acc[0], batch_acc_id, withdrawable_amount, desc))

                # 3a. Update Batch Account
                if batch_acc_id:
                    cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (withdrawable_amount, batch_acc_id))
                    cursor.execute("""
                    INSERT INTO transactions (account_id, related_account_id, transaction_type, amount, description)
                    VALUES (?, ?, 'PAYOUT', ?, ?)
                    """, (batch_acc_id, cash_acc[0], withdrawable_amount, desc))
                
                conn.commit()
                QMessageBox.information(self, "Success", "Loan withdrawal successful.")
                self.load_chit_data()
                self.load_dashboard_data()
            except Exception as e:
                conn.rollback()
                QMessageBox.warning(self, "Error", str(e))
                
        conn.close()

    def setup_shg_tab(self):
        layout = QVBoxLayout(self.page_shg)
        
        btn_layout = QHBoxLayout()
        self.btn_add_shg = QPushButton("Create New SHG Group")
        self.btn_add_shg.clicked.connect(self.add_shg_group)
        btn_layout.addWidget(self.btn_add_shg)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.shg_table = QTableWidget()
        self.shg_table.setColumnCount(7)
        self.shg_table.setHorizontalHeaderLabels(["ID", "Group Name", "Start Date", "Leader", "Deputy", "Members", "Actions"])
        self.shg_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.shg_table)
        
        self.load_shg_groups()

    def load_shg_groups(self):
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        # JOIN with customers to get leader and deputy details
        cursor.execute("""
            SELECT g.id, g.group_name, g.starting_date, l.name as leader, d.name as deputy,
                   (SELECT COUNT(*) FROM shg_members WHERE group_id = g.id) as member_count
            FROM shg_groups g
            LEFT JOIN customers l ON g.leader_id = l.id
            LEFT JOIN customers d ON g.deputy_leader_id = d.id
        """)
        rows = cursor.fetchall()
        self.shg_table.setRowCount(0)
        for r_idx, row in enumerate(rows):
            self.shg_table.insertRow(r_idx)
            for c_idx, val in enumerate(row):
                self.shg_table.setItem(r_idx, c_idx, QTableWidgetItem(str(val) if val else ""))
            
            # Action: Issue Loan
            btn_loan = QPushButton("Issue Loan")
            btn_loan.setStyleSheet("padding: 4px 8px;")
            btn_loan.clicked.connect(lambda _, gid=row[0]: self.issue_shg_loan(gid))
            self.shg_table.setCellWidget(r_idx, 6, btn_loan)
        conn.close()

    def add_shg_group(self):
        dialog = AddSHGGroupDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if not data['name'] or not data['members']:
                QMessageBox.warning(self, "Error", "Group Name and at least one member are required.")
                return
            
            conn = scheme_db.get_connection()
            cursor = conn.cursor()
            try:
                # 1. Insert Group
                cursor.execute("""
                    INSERT INTO shg_groups (group_name, leader_id, deputy_leader_id, starting_date) 
                    VALUES (?, ?, ?, ?)
                """, (data['name'], data['leader_id'], data['deputy_id'], data['start_date']))
                
                group_id = cursor.lastrowid
                
                # 2. Insert Members
                for mid in data['members']:
                    cursor.execute("INSERT INTO shg_members (group_id, customer_id) VALUES (?, ?)", (group_id, mid))
                
                conn.commit()
                QMessageBox.information(self, "Success", f"SHG Group '{data['name']}' created with {len(data['members'])} members.")
                self.load_shg_groups()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))
            finally:
                conn.close()

    def issue_shg_loan(self, group_id):
        # Simplified loan issuing for demo
        import PySide6.QtWidgets as qtw
        amount, ok = qtw.QInputDialog.getDouble(self, "Issue Loan", "Loan Amount:", 10000, 0, 1000000)
        if ok and amount > 0:
            conn = scheme_db.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO shg_loans (group_id, loan_amount, start_date) VALUES (?, ?, ?)", 
                             (group_id, amount, QDate.currentDate().toString("yyyy-MM-dd")))
                conn.commit()
                QMessageBox.information(self, "Success", "SHG Loan Issued")
                self.load_dashboard_data()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))
            finally:
                conn.close()

    def setup_individual_tab(self):
        layout = QVBoxLayout(self.page_individual)
        
        btn_layout = QHBoxLayout()
        self.btn_add_ind_loan = QPushButton("New Individual Loan")
        self.btn_add_ind_loan.clicked.connect(self.add_individual_loan)
        btn_layout.addWidget(self.btn_add_ind_loan)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.ind_loan_table = QTableWidget()
        self.ind_loan_table.setColumnCount(5)
        self.ind_loan_table.setHorizontalHeaderLabels(["ID", "Customer", "Amount", "Date", "Status"])
        self.ind_loan_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.ind_loan_table)
        self.load_individual_loans()

    def load_individual_loans(self):
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT l.id, c.name, l.loan_amount, l.start_date, l.status 
            FROM individual_loans l
            JOIN customers c ON l.customer_id = c.id
        """)
        rows = cursor.fetchall()
        self.ind_loan_table.setRowCount(0)
        for r_idx, row in enumerate(rows):
            self.ind_loan_table.insertRow(r_idx)
            for c_idx, val in enumerate(row):
                self.ind_loan_table.setItem(r_idx, c_idx, QTableWidgetItem(str(val)))
        conn.close()

    def add_individual_loan(self):
        # 1. Select CIF
        selector = CIFSelectorDialog(self)
        if selector.exec_() == QDialog.Accepted:
            customer = selector.get_selected_customer()
            if not customer: return
            
            # 2. Get Amount
            import PySide6.QtWidgets as qtw
            amount, ok = qtw.QInputDialog.getDouble(self, "Individual Loan", f"Loan Amount for {customer['name']}:", 5000, 0, 1000000)
            
            if ok and amount > 0:
                conn = scheme_db.get_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("INSERT INTO individual_loans (customer_id, loan_amount, start_date) VALUES (?, ?, ?)", 
                                 (customer['id'], amount, QDate.currentDate().toString("yyyy-MM-dd")))
                    conn.commit()
                    QMessageBox.information(self, "Success", "Individual Loan Issued")
                    self.load_individual_loans()
                    self.load_dashboard_data()
                except Exception as e:
                    QMessageBox.warning(self, "Error", str(e))
                finally:
                    conn.close()

    def setup_scheme_master_tab(self):
        layout = QVBoxLayout(self.page_config)
        
        header_layout = QHBoxLayout()
        lbl = QLabel("Scheme 20-Month Configuration")
        header_layout.addWidget(lbl)
        
        header_layout.addStretch()
        header_layout.addWidget(QLabel("Select Scheme Value:"))
        self.scheme_val_selector = QComboBox()
        for v in [200000, 500000, 1000000, 2000000]:
            self.scheme_val_selector.addItem(f"₹{v:,.0f}", v)
        self.scheme_val_selector.currentIndexChanged.connect(self.load_scheme_master)
        header_layout.addWidget(self.scheme_val_selector)
        
        layout.addLayout(header_layout)
        
        self.scheme_table = QTableWidget()
        self.scheme_table.setColumnCount(5)
        self.scheme_table.setHorizontalHeaderLabels(["Month (எண்)", "Installment (தவணை)", "Kasar (கசர்)", "Disbursement (பட்டுவாடா)", "Liability EMI"])
        self.scheme_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.scheme_table)
        
        self.btn_save_scheme = QPushButton("Save Config")
        self.btn_save_scheme.clicked.connect(self.save_scheme_master)
        layout.addWidget(self.btn_save_scheme)

    def load_scheme_master(self):
        val = self.scheme_val_selector.currentData()
        if val is None: return
        
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT month_number, payable_amount, benefit_amount, withdrawable_amount, liability_emi 
            FROM scheme_master 
            WHERE total_value = ? 
            ORDER BY month_number
        """, (val,))
        rows = cursor.fetchall()
        
        self.scheme_table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            for c_idx, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                if c_idx == 0:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable) # Make month non-editable
                self.scheme_table.setItem(r_idx, c_idx, item)
        conn.close()
        
    def save_scheme_master(self):
        val = self.scheme_val_selector.currentData()
        if val is None: return
        
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        try:
            for r_idx in range(self.scheme_table.rowCount()):
                month = int(self.scheme_table.item(r_idx, 0).text())
                payable = float(self.scheme_table.item(r_idx, 1).text() or 0)
                benefit = float(self.scheme_table.item(r_idx, 2).text() or 0)
                withdrawable = float(self.scheme_table.item(r_idx, 3).text() or 0)
                liability = float(self.scheme_table.item(r_idx, 4).text() or 0)
                
                cursor.execute("""
                UPDATE scheme_master 
                SET payable_amount=?, benefit_amount=?, withdrawable_amount=?, liability_emi=?
                WHERE month_number=? AND total_value=?
                """, (payable, benefit, withdrawable, liability, month, val))
            conn.commit()
            QMessageBox.information(self, "Success", "Scheme configuration saved.")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
        finally:
            conn.close()

    def setup_batches_tab(self):
        layout = QVBoxLayout(self.page_batches)
        
        btn_layout = QHBoxLayout()
        self.btn_add_batch = QPushButton("Create New Batch")
        self.btn_add_batch.clicked.connect(self.add_chit_batch)
        btn_layout.addWidget(self.btn_add_batch)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.batches_table = QTableWidget()
        self.batches_table.setColumnCount(6)
        self.batches_table.setHorizontalHeaderLabels(["ID", "Batch Name", "Value", "Start Date", "Status", "Actions"])
        self.batches_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.batches_table)
        
        self.load_batches()

    def load_batches(self):
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, batch_name, chit_value, starting_date, status FROM chit_batches")
        rows = cursor.fetchall()
        self.batches_table.setRowCount(0)
        for r_idx, row in enumerate(rows):
            self.batches_table.insertRow(r_idx)
            for c_idx, val in enumerate(row):
                if c_idx == 2: # Value
                    val = f"₹{val:,.0f}"
                self.batches_table.setItem(r_idx, c_idx, QTableWidgetItem(str(val)))
            
            # Actions Column
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(2, 2, 2, 2)
            action_layout.setSpacing(5)

            btn_manage = QPushButton("Members")
            btn_manage.setStyleSheet("padding: 4px 8px;")
            btn_manage.clicked.connect(lambda _, rid=row[0], rname=row[1]: self.manage_batch_members(rid, rname))
            
            btn_edit = QPushButton("Edit")
            btn_edit.clicked.connect(lambda _, rid=row[0]: self.edit_chit_batch(rid))
            btn_edit.setStyleSheet("background-color: #2196F3; color: white; padding: 4px 8px;")
            
            btn_delete = QPushButton("Delete")
            btn_delete.clicked.connect(lambda _, rid=row[0]: self.delete_chit_batch(rid))
            btn_delete.setStyleSheet("background-color: #f44336; color: white; padding: 4px 8px;")
            
            action_layout.addWidget(btn_manage)
            action_layout.addWidget(btn_edit)
            action_layout.addWidget(btn_delete)
            self.batches_table.setCellWidget(r_idx, 5, action_widget)
        conn.close()

    def manage_batch_members(self, batch_id, batch_name):
        dialog = ManageBatchMembersDialog(batch_id, batch_name, self)
        dialog.exec_()
        self.load_chit_data()

    def add_chit_batch(self):
        dialog = ChitBatchDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if not data['name']: return
            
            conn = scheme_db.get_connection()
            cursor = conn.cursor()
            try:
                # 1. Create Batch
                cursor.execute("""
                    INSERT INTO chit_batches (batch_name, chit_value, starting_date) 
                    VALUES (?, ?, ?)
                """, (data['name'], data['value'], data['start_date']))
                batch_id = cursor.lastrowid
                
                # 2. Create Account for this Batch
                acc_name = f"Batch: {data['name']} Account"
                cursor.execute("INSERT OR IGNORE INTO accounts (account_name, account_type) VALUES (?, 'CHIT_FUND')", (acc_name,))
                cursor.execute("SELECT id FROM accounts WHERE account_name = ?", (acc_name,))
                acc_id = cursor.fetchone()[0]
                
                # 3. Link Account to Batch
                cursor.execute("UPDATE chit_batches SET account_id = ? WHERE id = ?", (acc_id, batch_id))
                
                conn.commit()
                self.load_batches()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))
            finally:
                conn.close()

    def edit_chit_batch(self, batch_id):
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT batch_name, chit_value, starting_date FROM chit_batches WHERE id = ?", (batch_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            data = {'name': row[0], 'value': row[1], 'start_date': row[2]}
            dialog = ChitBatchDialog(self)
            dialog.set_data(data)
            if dialog.exec_() == QDialog.Accepted:
                new_data = dialog.get_data()
                if not new_data['name']: return
                
                conn = scheme_db.get_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("""
                        UPDATE chit_batches 
                        SET batch_name = ?, chit_value = ?, starting_date = ?
                        WHERE id = ?
                    """, (new_data['name'], new_data['value'], new_data['start_date'], batch_id))
                    conn.commit()
                    self.load_batches()
                    self.load_chit_data()
                except Exception as e:
                    QMessageBox.warning(self, "Error", str(e))
                finally:
                    conn.close()

    def delete_chit_batch(self, batch_id):
        reply = QMessageBox.question(self, "Confirm Delete", 
            "Are you sure you want to delete this batch? This will fail if there are members or ledger records associated with it.", 
            QMessageBox.Yes | QMessageBox.No)
            
        if reply == QMessageBox.Yes:
            conn = scheme_db.get_connection()
            cursor = conn.cursor()
            try:
                # Check for members
                cursor.execute("SELECT COUNT(*) FROM customers WHERE batch_id = ?", (batch_id,))
                if cursor.fetchone()[0] > 0:
                    QMessageBox.warning(self, "Error", "Cannot delete batch with assigned members. Remove members first.")
                    return
                
                cursor.execute("DELETE FROM chit_batches WHERE id = ?", (batch_id,))
                conn.commit()
                self.load_batches()
                QMessageBox.information(self, "Success", "Batch deleted successfully.")
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))
            finally:
                conn.close()

    def setup_accounting_tab(self):
        layout = QVBoxLayout(self.page_accounting)
        
        # Account Balances Table
        layout.addWidget(QLabel("<b>Account Balances:</b>"))
        self.acc_table = QTableWidget()
        self.acc_table.setColumnCount(3)
        self.acc_table.setHorizontalHeaderLabels(["Account Name", "Type", "Balance"])
        self.acc_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.acc_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.acc_table.setSelectionMode(QTableWidget.SingleSelection)
        self.acc_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.acc_table.itemDoubleClicked.connect(self.show_account_details)
        layout.addWidget(self.acc_table, 1) # Give it some stretch
        
        btn_layout = QHBoxLayout()
        self.btn_deposit = QPushButton("Deposit Cash to Bank")
        self.btn_deposit.clicked.connect(self.deposit_cash)
        self.btn_withdraw_bank = QPushButton("Withdraw Cash from Bank")
        self.btn_withdraw_bank.clicked.connect(self.withdraw_cash)
        
        btn_layout.addWidget(self.btn_deposit)
        btn_layout.addWidget(self.btn_withdraw_bank)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        layout.addWidget(QLabel("<b>Recent Transactions:</b>"))
        self.txn_table = QTableWidget()
        self.txn_table.setColumnCount(5)
        self.txn_table.setHorizontalHeaderLabels(["ID", "Type", "Amount", "Description", "Date"])
        self.txn_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.txn_table, 2) # Give it more stretch
        
        self.load_transactions()
        
    def load_transactions(self):
        conn = scheme_db.get_connection()
        cursor = conn.cursor()
        
        # Load Account Balances
        cursor.execute("SELECT id, account_name, account_type, balance FROM accounts")
        acc_rows = cursor.fetchall()
        self.acc_table.setRowCount(0)
        for r_idx, (aid, aname, atype, abal) in enumerate(acc_rows):
            self.acc_table.insertRow(r_idx)
            
            name_item = QTableWidgetItem(aname)
            name_item.setData(Qt.UserRole, aid)
            name_item.setData(Qt.UserRole + 1, atype)
            
            type_item = QTableWidgetItem(atype)
            bal_item = QTableWidgetItem(f"₹{abal:,.2f}")
            
            self.acc_table.setItem(r_idx, 0, name_item)
            self.acc_table.setItem(r_idx, 1, type_item)
            self.acc_table.setItem(r_idx, 2, bal_item)

        # Load Transactions
        cursor.execute("SELECT id, transaction_type, amount, description, transaction_date FROM transactions ORDER BY id DESC LIMIT 50")
        rows = cursor.fetchall()
        
        self.txn_table.setRowCount(0)
        for r_idx, row in enumerate(rows):
            self.txn_table.insertRow(r_idx)
            for c_idx, val in enumerate(row):
                if c_idx == 2: val = f"₹{val:,.2f}"
                self.txn_table.setItem(r_idx, c_idx, QTableWidgetItem(str(val)))
        conn.close()

    def show_account_details(self, item):
        # We always check column 0 for the ID and Type
        row = item.row()
        id_item = self.acc_table.item(row, 0)
        acc_id = id_item.data(Qt.UserRole)
        acc_type = id_item.data(Qt.UserRole + 1)
        acc_name = id_item.text()
        
        if acc_type == 'CHIT_FUND':
            dialog = BatchAccountDetailsDialog(acc_id, acc_name, self)
            dialog.exec_()
        else:
            QMessageBox.information(self, "Account Info", f"Detailed view only available for Chit Scheme (Batch) accounts.\n\nAccount: {acc_name}\nBalance: {self.acc_table.item(row, 2).text()}")
        
    def deposit_cash(self):
        amount, ok = QDoubleSpinBox(), True # using a simple input dialog logic
        import PySide6.QtWidgets as qtw
        val, ok = qtw.QInputDialog.getDouble(self, "Deposit Cash", "Amount to deposit into Bank:", 0, 0, 10000000)
        if ok and val > 0:
            conn = scheme_db.get_connection()
            cursor = conn.cursor()
            try:
                # check cash
                cursor.execute("SELECT id, balance FROM accounts WHERE account_name='Cash in Hand'")
                cash_acc = cursor.fetchone()
                if cash_acc[1] < val:
                    QMessageBox.warning(self, "Error", "Not enough cash in hand!")
                    return
                    
                cursor.execute("SELECT id FROM accounts WHERE account_name='Bank Account'")
                bank_acc = cursor.fetchone()
                
                # Move money
                cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id=?", (val, cash_acc[0]))
                cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id=?", (val, bank_acc[0]))
                
                # log txns
                cursor.execute("INSERT INTO transactions (account_id, related_account_id, transaction_type, amount, description) VALUES (?, ?, 'DEPOSIT', ?, 'Deposit Cash to Bank')", (bank_acc[0], cash_acc[0], val))
                conn.commit()
                self.load_dashboard_data()
                self.load_transactions()
            finally:
                conn.close()

    def withdraw_cash(self):
        import PySide6.QtWidgets as qtw
        val, ok = qtw.QInputDialog.getDouble(self, "Withdraw Cash", "Amount to withdraw from Bank:", 0, 0, 10000000)
        if ok and val > 0:
            conn = scheme_db.get_connection()
            cursor = conn.cursor()
            try:
                # check bank
                cursor.execute("SELECT id, balance FROM accounts WHERE account_name='Bank Account'")
                bank_acc = cursor.fetchone()
                if bank_acc[1] < val:
                    QMessageBox.warning(self, "Error", "Not enough balance in bank!")
                    return
                    
                cursor.execute("SELECT id FROM accounts WHERE account_name='Cash in Hand'")
                cash_acc = cursor.fetchone()
                
                # Move money
                cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id=?", (val, bank_acc[0]))
                cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id=?", (val, cash_acc[0]))
                
                # log txns
                cursor.execute("INSERT INTO transactions (account_id, related_account_id, transaction_type, amount, description) VALUES (?, ?, 'WITHDRAW', ?, 'Withdraw Cash from Bank')", (cash_acc[0], bank_acc[0], val))
                conn.commit()
                self.load_dashboard_data()
                self.load_transactions()
            finally:
                conn.close()

    # --- Backup & Restore Methods ---
    def setup_backup_restore_tab(self):
        layout = QVBoxLayout(self.page_backup)
        
        # Email Settings Group
        settings_frame = QFrame()
        settings_frame.setStyleSheet("background-color: white; border-radius: 8px;")
        settings_layout = QFormLayout(settings_frame)
        settings_layout.setContentsMargins(15, 15, 15, 15)
        
        lbl_title = QLabel("Email Settings for Backup")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #333;")
        settings_layout.addRow(lbl_title)
        
        self.email_sender_input = QLineEdit()
        self.email_sender_input.setPlaceholderText("sender@gmail.com")
        self.email_password_input = QLineEdit()
        self.email_password_input.setEchoMode(QLineEdit.Password)
        self.email_password_input.setPlaceholderText("App Password")
        self.email_receiver_input = QLineEdit()
        self.email_receiver_input.setPlaceholderText("receiver@gmail.com")
        self.smtp_server_input = QLineEdit()
        self.smtp_server_input.setText("smtp.gmail.com")
        self.smtp_port_input = QLineEdit()
        self.smtp_port_input.setText("465")
        
        settings_layout.addRow("Sender Email:", self.email_sender_input)
        settings_layout.addRow("App Password:", self.email_password_input)
        settings_layout.addRow("Receiver Email:", self.email_receiver_input)
        settings_layout.addRow("SMTP Server:", self.smtp_server_input)
        settings_layout.addRow("SMTP Port:", self.smtp_port_input)
        
        self.btn_save_email = QPushButton("Save Settings")
        self.btn_save_email.setFixedWidth(150)
        self.btn_save_email.clicked.connect(self.save_email_config)
        self.btn_save_email.setStyleSheet("padding: 8px; background-color: #2196f3; color: white; border-radius: 4px; font-weight: bold;")
        settings_layout.addRow("", self.btn_save_email)
        
        layout.addWidget(settings_frame)
        
        # Actions Group
        actions_layout = QHBoxLayout()
        self.btn_backup = QPushButton("Backup & Send Mail")
        self.btn_backup.setStyleSheet("padding: 15px; background-color: #4caf50; color: white; border-radius: 6px; font-weight: bold; font-size: 14px;")
        self.btn_backup.clicked.connect(self.run_backup)
        
        self.btn_restore = QPushButton("Restore Backup")
        self.btn_restore.setStyleSheet("padding: 15px; background-color: #f44336; color: white; border-radius: 6px; font-weight: bold; font-size: 14px;")
        self.btn_restore.clicked.connect(self.run_restore)
        
        actions_layout.addWidget(self.btn_backup)
        actions_layout.addWidget(self.btn_restore)
        layout.addLayout(actions_layout)
        
        # Status Label
        self.backup_status_label = QLabel("")
        self.backup_status_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.backup_status_label)
        
        # History Table
        history_lbl = QLabel("Backup History (Local)")
        history_lbl.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(history_lbl)
        
        self.backup_history_table = QTableWidget()
        self.backup_history_table.setColumnCount(4)
        self.backup_history_table.setHorizontalHeaderLabels(["File Name", "Date", "Size (KB)", "Status"])
        self.backup_history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.backup_history_table)
        
        self.load_email_config()
        self.load_backup_history()

    def load_email_config(self):
        config_path = "config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                    self.email_sender_input.setText(config.get("sender_email", ""))
                    # Simple obfuscation decode
                    import base64
                    encoded_pwd = config.get("app_password", "")
                    if encoded_pwd:
                        try:
                            self.email_password_input.setText(base64.b64decode(encoded_pwd).decode('utf-8'))
                        except:
                            self.email_password_input.setText(encoded_pwd)
                    self.email_receiver_input.setText(config.get("receiver_email", ""))
                    self.smtp_server_input.setText(config.get("smtp_server", "smtp.gmail.com"))
                    self.smtp_port_input.setText(config.get("smtp_port", "465"))
            except Exception as e:
                print(f"Error loading config: {e}")

    def save_email_config(self):
        import base64
        config = {
            "sender_email": self.email_sender_input.text().strip(),
            "app_password": base64.b64encode(self.email_password_input.text().encode('utf-8')).decode('utf-8'),
            "receiver_email": self.email_receiver_input.text().strip(),
            "smtp_server": self.smtp_server_input.text().strip(),
            "smtp_port": self.smtp_port_input.text().strip()
        }
        with open("config.json", "w") as f:
            json.dump(config, f)
        QMessageBox.information(self, "Success", "Email settings saved securely.")

    def run_backup(self):
        self.save_email_config() # Auto save before run
        config_path = "config.json"
        config = {}
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config = json.load(f)
                import base64
                if config.get("app_password"):
                    try:
                        config["app_password"] = base64.b64decode(config["app_password"]).decode('utf-8')
                    except:
                        pass
                        
        self.btn_backup.setEnabled(False)
        self.backup_status_label.setText("Starting backup...")
        
        self.backup_worker = backup_restore.BackupWorker("scheme_finance.db", "backups", config)
        self.backup_worker.progress.connect(self.on_backup_progress)
        self.backup_worker.success.connect(self.on_backup_success)
        self.backup_worker.error.connect(self.on_backup_error)
        self.backup_worker.start()

    def on_backup_progress(self, msg):
        self.backup_status_label.setText(msg)

    def on_backup_success(self, msg):
        self.backup_status_label.setText("")
        self.btn_backup.setEnabled(True)
        QMessageBox.information(self, "Backup Complete", msg)
        self.load_backup_history()

    def on_backup_error(self, msg):
        self.backup_status_label.setText("")
        self.btn_backup.setEnabled(True)
        QMessageBox.critical(self, "Backup Error", msg)
        self.load_backup_history()

    def run_restore(self):
        reply = QMessageBox.question(self, 'Confirm Restore', 
                                     "Current database will be replaced. A safety backup will be created.\\nDo you want to continue?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return

        file_path, _ = QFileDialog.getOpenFileName(self, "Select Backup File", "backups", "Backup Files (*.db *.zip)")
        if not file_path:
            return

        self.btn_restore.setEnabled(False)
        self.backup_status_label.setText("Restoring database...")
        
        self.restore_worker = backup_restore.RestoreWorker(file_path, "scheme_finance.db")
        self.restore_worker.progress.connect(self.on_backup_progress)
        self.restore_worker.success.connect(self.on_restore_success)
        self.restore_worker.error.connect(self.on_backup_error) # reuse error handler
        self.restore_worker.start()

    def on_restore_success(self, msg):
        self.backup_status_label.setText("")
        self.btn_restore.setEnabled(True)
        QMessageBox.information(self, "Restore Complete", msg)
        self.reload_all_data()

    def reload_all_data(self):
        try:
            self.load_dashboard_data()
            self.load_customers()
            self.load_chit_data()
            self.load_shg_data()
            self.load_individual_data()
            self.load_batches()
            self.load_accounts()
        except Exception as e:
            QMessageBox.warning(self, "Reload Error", f"Data reloaded with some errors: {e}")

    def load_backup_history(self):
        self.backup_history_table.setRowCount(0)
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            return
            
        files = []
        for f in os.listdir(backup_dir):
            if f.endswith(".db") or f.endswith(".zip"):
                path = os.path.join(backup_dir, f)
                stat = os.stat(path)
                size_kb = stat.st_size / 1024
                date_str = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                files.append((f, date_str, size_kb, "Available"))
                
        files.sort(key=lambda x: x[1], reverse=True) # Sort newest first
        
        for r_idx, (fname, fdate, fsize, fstatus) in enumerate(files):
            self.backup_history_table.insertRow(r_idx)
            self.backup_history_table.setItem(r_idx, 0, QTableWidgetItem(fname))
            self.backup_history_table.setItem(r_idx, 1, QTableWidgetItem(fdate))
            self.backup_history_table.setItem(r_idx, 2, QTableWidgetItem(f"{fsize:.1f}"))
            self.backup_history_table.setItem(r_idx, 3, QTableWidgetItem(fstatus))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Simple Modern Styling
    app.setStyle("Fusion")
    
    window = SchemeFinanceApp()
    window.showMaximized()
    sys.exit(app.exec())
