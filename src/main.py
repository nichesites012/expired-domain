#!/usr/bin/env python3
"""
Advanced Web Scraping GUI Tool
A PyQt5-based interface for the Scrapy web scraper with external domain extraction
"""

import sys
import os
import json
import threading
import time
from datetime import datetime
import io
import contextlib

# Redirect stderr to suppress Qt font warnings
@contextlib.contextmanager
def suppress_qt_warnings():
    """Context manager to suppress Qt font warnings"""
    old_stderr = sys.stderr
    sys.stderr = io.StringIO()
    try:
        yield
    finally:
        sys.stderr = old_stderr

# Configure Qt for Windows GUI environment
# Only use offscreen platform if running in truly headless environment
import platform
if platform.system() == 'Windows' and os.environ.get('DISPLAY') is None and os.environ.get('HEADLESS') == 'true':
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
# Remove problematic environment variables
os.environ.pop('XDG_RUNTIME_DIR', None)  # Remove XDG runtime which causes issues on Linux

# Suppress Qt font warnings more effectively
os.environ['QT_LOGGING_RULES'] = 'qt.qpa.fonts.*=false;qt5ct.*=false'
# Use system font configuration on Windows
if platform.system() == 'Windows':
    # Let Windows handle font discovery
    os.environ.pop('QT_QPA_FONTDIR', None)
else:
    os.environ['QT_QPA_FONTDIR'] = ''  # Prevent font directory search warnings on other systems

# Import PyQt5 with suppressed warnings
with suppress_qt_warnings():
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                                 QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                                 QTextEdit, QSpinBox, QProgressBar, QTabWidget,
                                 QGroupBox, QGridLayout, QFileDialog, QMessageBox,
                                 QComboBox, QCheckBox, QTableWidget, QTableWidgetItem,
                                 QHeaderView, QFrame, QSplitter, QRadioButton,
                                 QPlainTextEdit)
    from PyQt5.QtCore import QThread, pyqtSignal, QTimer, Qt, QCoreApplication
    from PyQt5 import QtCore
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor, QFontDatabase, QTextCursor, QTextBlock
from concurrent.futures import ThreadPoolExecutor
import subprocess
from dns_checker import AsyncDNSChecker, DNSCheckerThread
from indexing_checker import IndexingChecker, IndexingCheckerThread
from domain_availability_checker import DomainAvailabilityChecker

# Suppress Qt warnings globally
import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

# Software OpenGL will be set via environment variable if needed


# Register Qt meta types used in queued connections to avoid warnings (safe on all versions)
try:
    _qregister = getattr(QtCore, 'qRegisterMetaType', None)
    if callable(_qregister):
        # Template/container types must be registered by name
        _qregister('QVector<int>')
        # Register GUI types passed across threads in signals/slots
        _qregister(QTextBlock)
        _qregister(QTextCursor)
except Exception:
    # Non-fatal: continue even if registration isn't needed in this environment
    pass

class ScrapingThread(QThread):
    """Thread for running Scrapy spider without blocking the GUI"""
    
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)  # current, total
    external_domain_signal = pyqtSignal(str, str, str)  # domain, protocol, extension
    dns_status_signal = pyqtSignal(str, bool)  # domain, status (True/False)
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.is_running = False
        self.is_paused = False
        
    def run(self):
        """Execute the scraping process with high-speed optimizations"""
        self.is_running = True
        self.status_signal.emit("Starting...")
        
        try:
            # Create Scrapy command with speed optimizations
            cmd = [
                'scrapy', 'crawl', 'domain_spider',
                '--set', 'settings=webscraper.speed_settings',  # Use speed settings
                '-a', f'start_url={self.config["start_url"]}',
                '-a', f'allowed_domain={self.config["allowed_domain"]}',
                '-a', f'max_concurrent={self.config["max_concurrent"]}',
                '-a', f'delay_min={self.config["delay_min"]}',
                '-a', f'delay_max={self.config["delay_max"]}',
                '-a', f'exclude_subdomains={self.config["exclude_subdomains"]}',
                '-a', f'min_chars={self.config["min_chars"]}',
                '-a', f'max_chars={self.config["max_chars"]}',
                '-a', f'exclude_extensions={self.config["exclude_extensions"]}',
                '-a', f'target_extensions={self.config["target_extensions"]}',
                '-a', f'excluded_words={self.config["excluded_words"]}',
                '-a', f'hidden_words={self.config["hidden_words"]}',
                '-a', f'check_dns={self.config["check_dns"]}',
                '-o', 'external_domains.json'
            ]
            
            # Add ultra speed mode settings via command line
            if self.config.get('ultra_speed_mode', False):
                cmd.extend([
                    '--set', 'ROBOTSTXT_OBEY=False',
                    '--set', 'CONCURRENT_REQUESTS=200',
                    '--set', 'CONCURRENT_REQUESTS_PER_DOMAIN=100',
                    '--set', 'DOWNLOAD_DELAY=0',
                    '--set', 'AUTOTHROTTLE_ENABLED=False',
                    '--set', 'REACTOR_THREADPOOL_MAXSIZE=200'
                ])
            
            # Execute Scrapy spider with high priority
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                cwd=os.getcwd(),
                creationflags=subprocess.HIGH_PRIORITY_CLASS if os.name == 'nt' else 0
            )
            
            while True:
                if not self.is_running:
                    process.terminate()
                    break
                    
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                    
                if output:
                    self.log_signal.emit(output.strip())
                    
                    # Parse output for progress and external domains
                    if "External domain found:" in output:
                        try:
                            # Extract the domain info after the log message
                            # Format: "2025-09-18 01:51:25 [domain_spider] INFO: External domain found: domain.com|http|com"
                            domain_part = output.split("External domain found:")[-1].strip()
                            if "|" in domain_part:
                                parts = domain_part.split('|')
                                if len(parts) >= 3:
                                    domain = parts[0].strip()
                                    protocol = parts[1].strip()
                                    extension = parts[2].strip()
                                    self.external_domain_signal.emit(domain, protocol, extension)
                        except Exception:
                            # If parsing fails, skip this line
                            pass
                    
                    # Parse DNS status messages from spider
                    elif "DNS status:" in output:
                        try:
                            # Extract DNS status info
                            # Format: "2025-09-18 01:51:25 [domain_spider] INFO: DNS status: domain.com|True"
                            dns_part = output.split("DNS status:")[-1].strip()
                            if "|" in dns_part:
                                parts = dns_part.split('|')
                                if len(parts) >= 2:
                                    domain = parts[0].strip()
                                    status = parts[1].strip().lower() == 'true'
                                    self.dns_status_signal.emit(domain, status)
                        except Exception:
                            # If parsing fails, skip this line
                            pass
                    
                    # Parse performance statistics
                    elif "Request rate:" in output or "requests/second" in output.lower():
                        try:
                            # Extract speed from log messages like "Request rate: 45.67 requests/second"
                            import re
                            speed_match = re.search(r'(\d+\.?\d*)\s*req', output.lower())
                            if speed_match:
                                speed = float(speed_match.group(1))
                                self.progress_signal.emit(int(speed), 100)  # Emit speed as progress
                        except Exception:
                            pass
                    
            self.status_signal.emit("Completed" if self.is_running else "Stopped")
            
        except Exception as e:
            self.log_signal.emit(f"Error: {str(e)}")
            self.status_signal.emit("Error")
        finally:
            self.is_running = False
            self.finished_signal.emit()
    
    def stop(self):
        """Stop the scraping process"""
        self.is_running = False
        
    def pause(self):
        """Pause the scraping process"""
        self.is_paused = True
        
    def resume(self):
        """Resume the scraping process"""
        self.is_paused = False


class WebScrapingGUI(QMainWindow):
    """Main GUI application for the web scraper"""
    
    def __init__(self):
        super().__init__()
        self.scraping_thread = None
        self.external_domains = {}  # Store as dict with domain info
        self.failed_domains = {}  # Store domains that failed to load
        self.total_domains_found = 0  # Track total domains found (independent of table)
        self.dns_checker_thread = None  # DNS checker thread
        self.domains_pending_dns = []  # Domains waiting for DNS check
        self.max_table_rows = 100000  # Increased to 100k for unlimited domain capture
        
        # Indexing checker for HTTP domains
        self.indexing_checker = IndexingChecker()
        self.indexing_checker_thread = None
        self.rapidapi_key = ""  # Store API key
        
        # Availability checker for domains
        self.availability_checker = DomainAvailabilityChecker()
        self.availability_api_key = ""
        
        # Real-time backup system
        self.backup_file_path = os.path.join(os.getcwd(), "backup_domains.txt")
        self.backup_batch_size = 10  # Save every 10 domains for performance
        self.backup_counter = 0
        # Ensure log buffer exists before any method uses add_log during init
        self._log_buffer = []
        self.log_cleanup_timer = QTimer()
        self.log_cleanup_timer.timeout.connect(self.cleanup_logs)
        self.log_cleanup_timer.start(600000)  # 10 minutes = 600,000 ms
        self.scraped_urls = []
        self.dark_theme = False
        self.init_ui()
        self.initialize_backup_file()
        # Thread pool for DNS checks to avoid blocking GUI
        self.dns_executor = ThreadPoolExecutor(max_workers=10)
        
        # UI update helpers for smooth table scrolling
        self.row_insert_counter = 0
        self.autoscroll_pending = False
        self.autoscroll_timer = QTimer()
        self.autoscroll_timer.setInterval(200)  # debounce auto-scroll
        self.autoscroll_timer.timeout.connect(self.perform_debounced_autoscroll)
        # Start/stop based on checkbox in UI lifecycle

        # Buffered logging to prevent UI lag
        self._log_buffer = []
        self._log_timer = QTimer()
        self._log_timer.setInterval(500)
        self._log_timer.timeout.connect(self.flush_log_buffer)
        self._log_timer.start()
        # Buffer for rendering operations when live update is paused
        self._pending_table_domains = set()
        
    def initialize_backup_file(self):
        """Initialize the backup file with header information"""
        try:
            with open(self.backup_file_path, 'w', encoding='utf-8') as f:
                f.write(f"# WebScrapeWizard Domain Backup\n")
                f.write(f"# Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Format: domain|protocol|extension|timestamp\n")
                f.write(f"# ==========================================\n\n")
            self.add_log(f"Backup file initialized: {self.backup_file_path}")
        except Exception as e:
            self.add_log(f"Warning: Could not initialize backup file: {e}")
    
    def save_domain_to_backup(self, domain, protocol, extension):
        """Save domain to backup file immediately for crash protection"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            backup_line = f"{domain}|{protocol}|{extension}|{timestamp}\n"
            
            # Append to backup file immediately
            with open(self.backup_file_path, 'a', encoding='utf-8') as f:
                f.write(backup_line)
            
            # Increment backup counter
            self.backup_counter += 1
            
            # Show backup status every 100 domains
            if self.backup_counter % 100 == 0:
                self.add_log(f"✓ Backup: {self.backup_counter} domains saved to {os.path.basename(self.backup_file_path)}")
                # Update backup status in GUI
                self.update_backup_status(f"Saved ({self.backup_counter})")
                
        except Exception as e:
            print(f"Backup error for domain {domain}: {e}")  # Silent backup - don't crash main process
    
    def load_domains_from_backup(self):
        """Load previously found domains from backup file"""
        if not os.path.exists(self.backup_file_path):
            return 0
            
        try:
            loaded_count = 0
            with open(self.backup_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split('|')
                        if len(parts) >= 3:
                            domain, protocol, extension = parts[0], parts[1], parts[2]
                            if domain not in self.external_domains:
                                self.external_domains[domain] = {'protocol': protocol, 'extension': extension}
                                self.total_domains_found += 1
                                loaded_count += 1
            
            if loaded_count > 0:
                self.add_log(f"📂 Loaded {loaded_count} domains from previous backup")
                self.update_domains_count()
                
            return loaded_count
        except Exception as e:
            self.add_log(f"Error loading backup: {e}")
            return 0
        
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Advanced Web Scraping Tool")
        self.setGeometry(100, 100, 1200, 800)
        
        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create tabs
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Configuration tab (with results integrated)
        self.create_config_tab()
        
        # Settings tab
        self.create_settings_tab()
        
        # Monitor tab
        self.create_monitor_tab()
        
        # Apply initial theme
        self.apply_theme()
        
        # Removed manual processEvents timer to prevent UI thrashing
        
        # Status bar
        self.statusBar().showMessage("Ready")
        
    def create_config_tab(self):
        """Create the configuration tab with integrated results"""
        config_tab = QWidget()
        self.tab_widget.addTab(config_tab, "Configuration & Results")
        
        # Main splitter to divide config and results
        splitter = QSplitter(Qt.Horizontal)
        config_tab_layout = QVBoxLayout(config_tab)
        config_tab_layout.addWidget(splitter)
        
        # Left panel - Configuration
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Theme toggle button
        theme_button = QPushButton("🌙 Dark Theme")
        theme_button.clicked.connect(self.toggle_theme)
        left_layout.addWidget(theme_button)
        
        # Basic Configuration Group
        basic_group = QGroupBox("Basic Configuration")
        basic_layout = QGridLayout(basic_group)
        
        # URL Configuration
        basic_layout.addWidget(QLabel("Start URL:"), 0, 0)
        self.start_url_input = QLineEdit("https://example.com")
        basic_layout.addWidget(self.start_url_input, 0, 1)
        
        basic_layout.addWidget(QLabel("Allowed Domain:"), 1, 0)
        self.allowed_domain_input = QLineEdit("example.com")
        basic_layout.addWidget(self.allowed_domain_input, 1, 1)
        
        # Advanced Configuration Group
        advanced_group = QGroupBox("Advanced Filtering")
        advanced_layout = QGridLayout(advanced_group)
        
        # Target Extensions Input - NEW FEATURE
        advanced_layout.addWidget(QLabel("Target Extensions:"), 0, 0)
        self.target_extensions_input = QLineEdit(".com")
        self.target_extensions_input.setPlaceholderText("e.g., .com,.org,.net (leave empty for all)")
        self.target_extensions_input.setToolTip("Filter domains by specific extensions. Use comma-separated values like .com,.org,.net")
        advanced_layout.addWidget(self.target_extensions_input, 0, 1)
        
        # Character Limits - NEW FEATURE
        advanced_layout.addWidget(QLabel("Min Characters:"), 1, 0)
        self.min_chars_spinbox = QSpinBox()
        self.min_chars_spinbox.setMinimum(1)
        self.min_chars_spinbox.setMaximum(100)
        self.min_chars_spinbox.setValue(4)
        self.min_chars_spinbox.setToolTip("Minimum number of characters in domain name")
        advanced_layout.addWidget(self.min_chars_spinbox, 1, 1)
        
        advanced_layout.addWidget(QLabel("Max Characters:"), 2, 0)
        self.max_chars_spinbox = QSpinBox()
        self.max_chars_spinbox.setMinimum(1)
        self.max_chars_spinbox.setMaximum(100)
        self.max_chars_spinbox.setValue(50)
        self.max_chars_spinbox.setToolTip("Maximum number of characters in domain name")
        advanced_layout.addWidget(self.max_chars_spinbox, 2, 1)
        
        # Exclude Extensions
        advanced_layout.addWidget(QLabel("Exclude Extensions:"), 3, 0)
        self.exclude_extensions_input = QLineEdit()
        self.exclude_extensions_input.setPlaceholderText("e.g., .jpg,.png,.pdf")
        advanced_layout.addWidget(self.exclude_extensions_input, 3, 1)
        
        # Word Filters
        advanced_layout.addWidget(QLabel("Excluded Words:"), 4, 0)
        self.excluded_words_input = QLineEdit()
        self.excluded_words_input.setPlaceholderText("e.g., spam,ads,tracker")
        advanced_layout.addWidget(self.excluded_words_input, 4, 1)
        
        advanced_layout.addWidget(QLabel("Hidden Words:"), 5, 0)
        self.hidden_words_input = QLineEdit()
        self.hidden_words_input.setPlaceholderText("Domains with these words will be crawled but not displayed")
        advanced_layout.addWidget(self.hidden_words_input, 5, 1)
        
        # Performance Configuration Group
        performance_group = QGroupBox("Performance Settings")
        performance_layout = QGridLayout(performance_group)
        
        performance_layout.addWidget(QLabel("Max Concurrent:"), 0, 0)
        self.max_concurrent_spinbox = QSpinBox()
        self.max_concurrent_spinbox.setMinimum(1)
        self.max_concurrent_spinbox.setMaximum(500)
        self.max_concurrent_spinbox.setValue(200)
        performance_layout.addWidget(self.max_concurrent_spinbox, 0, 1)
        
        performance_layout.addWidget(QLabel("Delay Min (sec):"), 1, 0)
        self.delay_min_spinbox = QSpinBox()
        self.delay_min_spinbox.setMinimum(0)
        self.delay_min_spinbox.setMaximum(60)
        self.delay_min_spinbox.setValue(0)
        performance_layout.addWidget(self.delay_min_spinbox, 1, 1)
        
        performance_layout.addWidget(QLabel("Delay Max (sec):"), 2, 0)
        self.delay_max_spinbox = QSpinBox()
        self.delay_max_spinbox.setMinimum(0)
        self.delay_max_spinbox.setMaximum(60)
        self.delay_max_spinbox.setValue(0)
        performance_layout.addWidget(self.delay_max_spinbox, 2, 1)
        
        # Options
        self.exclude_subdomains_checkbox = QCheckBox("Exclude Subdomains")
        self.exclude_subdomains_checkbox.setChecked(True)
        performance_layout.addWidget(self.exclude_subdomains_checkbox, 3, 0, 1, 2)
        
        self.ultra_speed_checkbox = QCheckBox("Ultra Speed Mode")
        self.ultra_speed_checkbox.setChecked(True)
        performance_layout.addWidget(self.ultra_speed_checkbox, 4, 0, 1, 2)
        
        # DNS checking option
        self.check_dns_checkbox = QCheckBox("Check DNS Resolution")
        self.check_dns_checkbox.setChecked(True)
        self.check_dns_checkbox.setToolTip("Check if domains resolve via DNS (adds DNS status column)")
        performance_layout.addWidget(self.check_dns_checkbox, 5, 0, 1, 2)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        self.start_button = QPushButton("🚀 Start Scraping")
        self.start_button.clicked.connect(self.start_scraping)
        self.start_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        
        self.stop_button = QPushButton("⏹️ Stop")
        self.stop_button.clicked.connect(self.stop_scraping)
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; }")
        
        self.export_button = QPushButton("💾 Export Results")
        self.export_button.clicked.connect(self.export_results)
        
        self.clear_button = QPushButton("🗑️ Clear Results")
        self.clear_button.clicked.connect(self.clear_results)
        
        controls_layout.addWidget(self.start_button)
        controls_layout.addWidget(self.stop_button)
        controls_layout.addWidget(self.export_button)
        controls_layout.addWidget(self.clear_button)
        
        # Add to left layout
        left_layout.addWidget(basic_group)
        left_layout.addWidget(advanced_group)
        left_layout.addWidget(performance_group)
        left_layout.addLayout(controls_layout)
        left_layout.addStretch()
        
        # Right panel - Results
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # Results header
        results_header = QHBoxLayout()
        results_title = QLabel("📊 External Domains Found")
        results_title.setFont(QFont("Arial", 12, QFont.Bold))
        results_header.addWidget(results_title)
        
        self.domains_count_label = QLabel("Total: 0")
        self.domains_count_label.setFont(QFont("Arial", 10))
        results_header.addWidget(self.domains_count_label)
        
        # Live update controls
        self.live_update_checkbox = QCheckBox("Live Update")
        self.live_update_checkbox.setChecked(True)
        results_header.addWidget(self.live_update_checkbox)
        self.apply_updates_button = QPushButton("Apply Updates")
        self.apply_updates_button.setEnabled(False)
        self.apply_updates_button.clicked.connect(self.apply_pending_table_updates)
        results_header.addWidget(self.apply_updates_button)
        results_header.addStretch()
        
        # Filter controls for results
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter domains...")
        self.search_input.textChanged.connect(self.filter_domains)
        filter_layout.addWidget(self.search_input)
        
        right_layout.addLayout(results_header)
        right_layout.addLayout(filter_layout)
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels(['Domain', 'Protocol', 'Extension', 'DNS Status', 'Indexing Status', 'Availability'])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSortingEnabled(False)  # enable after scraping completes
        # Performance tweaks for smooth scrolling
        from PyQt5.QtWidgets import QAbstractItemView
        self.results_table.setWordWrap(False)
        self.results_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.results_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        # Fixed row height for faster painting
        try:
            self.results_table.verticalHeader().setDefaultSectionSize(22)
        except Exception:
            pass
        right_layout.addWidget(self.results_table)
        
        # Add to splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)  # Left panel
        splitter.setStretchFactor(1, 2)  # Right panel gets more space
        
    def create_monitor_tab(self):
        """Create the monitoring tab"""
        monitor_tab = QWidget()
        self.tab_widget.addTab(monitor_tab, "Monitor & Logs")
        
        monitor_layout = QVBoxLayout(monitor_tab)
        
        # Status section
        status_group = QGroupBox("Status")
        status_layout = QGridLayout(status_group)
        
        self.status_label = QLabel("Ready")
        self.status_label.setFont(QFont("Arial", 12, QFont.Bold))
        status_layout.addWidget(QLabel("Status:"), 0, 0)
        status_layout.addWidget(self.status_label, 0, 1)
        
        self.progress_bar = QProgressBar()
        status_layout.addWidget(QLabel("Progress:"), 1, 0)
        status_layout.addWidget(self.progress_bar, 1, 1)
        
        monitor_layout.addWidget(status_group)
        
        # Logs section
        logs_group = QGroupBox("Scraping Logs")
        logs_layout = QVBoxLayout(logs_group)
        
        # Log controls
        log_controls = QHBoxLayout()
        self.auto_scroll_checkbox = QCheckBox("Auto-scroll")
        self.auto_scroll_checkbox.setChecked(False)
        self.auto_scroll_checkbox.toggled.connect(self.toggle_autoscroll)
        log_controls.addWidget(self.auto_scroll_checkbox)
        
        clear_logs_button = QPushButton("Clear Logs")
        clear_logs_button.clicked.connect(self.clear_logs)
        log_controls.addWidget(clear_logs_button)
        log_controls.addStretch()
        
        logs_layout.addLayout(log_controls)
        
        # Log display
        self.log_display = QPlainTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMaximumBlockCount(300)  # Tighter log size to reduce memory/lag
        logs_layout.addWidget(self.log_display)
        
        monitor_layout.addWidget(logs_group)
        
    def toggle_theme(self):
        """Toggle between light and dark themes"""
        self.dark_theme = not self.dark_theme
        self.apply_theme()
        
    def apply_theme(self):
        """Apply the current theme"""
        if self.dark_theme:
            # Dark theme
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QWidget {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QGroupBox {
                    border: 1px solid #555555;
                    border-radius: 5px;
                    margin-top: 10px;
                    font-weight: bold;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }
                QLineEdit, QSpinBox, QComboBox {
                    background-color: #404040;
                    border: 1px solid #555555;
                    border-radius: 3px;
                    padding: 5px;
                    color: #ffffff;
                }
                QPushButton {
                    background-color: #404040;
                    border: 1px solid #555555;
                    border-radius: 3px;
                    padding: 8px;
                    color: #ffffff;
                }
                QPushButton:hover {
                    background-color: #505050;
                }
                QTableWidget {
                    background-color: #404040;
                    alternate-background-color: #353535;
                    gridline-color: #555555;
                }
                QHeaderView::section {
                    background-color: #505050;
                    border: 1px solid #555555;
                    padding: 5px;
                }
                QPlainTextEdit {
                    background-color: #1e1e1e;
                    border: 1px solid #555555;
                    color: #ffffff;
                }
                QTabWidget::pane {
                    border: 1px solid #555555;
                }
                QTabBar::tab {
                    background-color: #404040;
                    border: 1px solid #555555;
                    padding: 8px;
                    margin-right: 2px;
                }
                QTabBar::tab:selected {
                    background-color: #505050;
                }
            """)
        else:
            # Light theme (default)
            self.setStyleSheet("")
            
    def start_scraping(self):
        """Start the scraping process"""
        # Validate inputs
        if not self.start_url_input.text().strip():
            QMessageBox.warning(self, "Input Error", "Please enter a start URL")
            return
            
        if not self.allowed_domain_input.text().strip():
            QMessageBox.warning(self, "Input Error", "Please enter an allowed domain")
            return
        
        # Validate character limits
        min_chars = self.min_chars_spinbox.value()
        max_chars = self.max_chars_spinbox.value()
        
        if min_chars > max_chars:
            QMessageBox.warning(self, "Input Error", "Minimum characters cannot be greater than maximum characters")
            return
        
        # Prepare configuration
        config = {
            'start_url': self.start_url_input.text().strip(),
            'allowed_domain': self.allowed_domain_input.text().strip(),
            'max_concurrent': self.max_concurrent_spinbox.value(),
            'delay_min': self.delay_min_spinbox.value(),
            'delay_max': self.delay_max_spinbox.value(),
            'exclude_subdomains': self.exclude_subdomains_checkbox.isChecked(),
            'min_chars': min_chars,
            'max_chars': max_chars,
            'exclude_extensions': self.exclude_extensions_input.text().strip(),
            'target_extensions': self.target_extensions_input.text().strip(),
            'excluded_words': self.excluded_words_input.text().strip(),
            'hidden_words': self.hidden_words_input.text().strip(),
            'ultra_speed_mode': self.ultra_speed_checkbox.isChecked(),
            'check_dns': self.check_dns_checkbox.isChecked()
        }
        
        # Clear previous results
        self.external_domains.clear()
        self.total_domains_found = 0
        self.results_table.setRowCount(0)
        self.update_domains_count()
        
        # Start scraping thread
        self.scraping_thread = ScrapingThread(config)
        self.scraping_thread.log_signal.connect(self.add_log)
        self.scraping_thread.progress_signal.connect(self.update_progress)
        self.scraping_thread.external_domain_signal.connect(self.add_external_domain)
        self.scraping_thread.dns_status_signal.connect(self.update_dns_status)
        self.scraping_thread.status_signal.connect(self.update_status)
        self.scraping_thread.finished_signal.connect(self.scraping_finished)
        
        self.scraping_thread.start()
        
        # Update UI state
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.update_status("Starting...")
        
        self.add_log("🚀 Scraping started with configuration:")
        self.add_log(f"   • Start URL: {config['start_url']}")
        self.add_log(f"   • Allowed Domain: {config['allowed_domain']}")
        self.add_log(f"   • Target Extensions: {config['target_extensions'] or 'All'}")
        self.add_log(f"   • Character Limits: {config['min_chars']}-{config['max_chars']}")
        self.add_log(f"   • Max Concurrent: {config['max_concurrent']}")
        self.add_log(f"   • Ultra Speed Mode: {'Enabled' if config['ultra_speed_mode'] else 'Disabled'}")
        
    def stop_scraping(self):
        """Stop the scraping process"""
        if self.scraping_thread:
            self.scraping_thread.stop()
            self.scraping_thread.wait(3000)  # Wait up to 3 seconds
            
        self.scraping_finished()
        self.add_log("⏹️ Scraping stopped by user")
        # Stop autoscroll to allow manual scrolling comfortably
        try:
            if self.autoscroll_timer.isActive():
                self.autoscroll_timer.stop()
        except Exception:
            pass
        
    def scraping_finished(self):
        """Handle scraping completion"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.update_status("Completed")
        try:
            # Ensure table updates are enabled after any batched updates
            self.results_table.setUpdatesEnabled(True)
        except Exception:
            pass
        self.add_log(f"✅ Scraping completed. Total domains found: {self.total_domains_found}")
        
    def add_external_domain(self, domain, protocol, extension):
        """Add an external domain to storage, render later only if HTTP + DNS False"""
        if domain not in self.external_domains:
            # Store domain info with initial DNS status as 'Checking...'
            self.external_domains[domain] = {
                'protocol': protocol, 
                'extension': extension,
                'dns_status': 'Checking...'
            }
            self.total_domains_found += 1
            # Update count and backup only; do NOT render yet to reduce memory/lag
            self.update_domains_count()
            self.save_domain_to_backup(domain, protocol, extension)
            # Start DNS check if enabled
            if hasattr(self, 'check_dns_checkbox') and self.check_dns_checkbox.isChecked():
                self.check_domain_dns(domain)
                
    def update_domains_count(self):
        """Update the domains count label"""
        self.domains_count_label.setText(f"Total: {self.total_domains_found}")
        
    def is_domain_eligible_for_indexing(self, protocol_text: str, dns_status_text: str) -> bool:
        """Return True if domain meets criteria to send to indexing API.
        Criteria: protocol is HTTP and DNS is False.
        """
        if not protocol_text or dns_status_text is None:
            return False
        return protocol_text.lower() == 'http' and dns_status_text == 'False'

    def find_row_by_domain(self, domain: str):
        """Return row index for domain in table, or None if not found"""
        for row in range(self.results_table.rowCount()):
            item = self.results_table.item(row, 0)
            if item and item.text() == domain:
                return row
        return None
        
    def filter_domains(self):
        """Filter domains based on search input"""
        search_text = self.search_input.text().lower()
        
        for row in range(self.results_table.rowCount()):
            domain = self.results_table.item(row, 0).text().lower()
            show_row = search_text in domain
            self.results_table.setRowHidden(row, not show_row)
            
    def export_results(self):
        """Export results to file"""
        if not self.external_domains:
            QMessageBox.information(self, "No Data", "No domains to export")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Results", "external_domains.txt", 
            "Text Files (*.txt);;CSV Files (*.csv);;JSON Files (*.json)"
        )
        
        if file_path:
            try:
                if file_path.endswith('.json'):
                    # Build a JSON array from the table to include status columns
                    data = []
                    for row in range(self.results_table.rowCount()):
                        entry = {
                            'domain': self.results_table.item(row, 0).text() if self.results_table.item(row, 0) else '',
                            'protocol': self.results_table.item(row, 1).text() if self.results_table.item(row, 1) else '',
                            'extension': self.results_table.item(row, 2).text() if self.results_table.item(row, 2) else '',
                            'dns_status': self.results_table.item(row, 3).text() if self.results_table.item(row, 3) else '',
                            'indexing_status': self.results_table.item(row, 4).text() if self.results_table.item(row, 4) else '',
                            'availability': self.results_table.item(row, 5).text() if self.results_table.item(row, 5) else ''
                        }
                        data.append(entry)
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2)
                elif file_path.endswith('.csv'):
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write("Domain,Protocol,Extension,DNS Status,Indexing Status,Availability\n")
                        # Iterate over table to capture rendered/eligible domains with statuses
                        for row in range(self.results_table.rowCount()):
                            domain = self.results_table.item(row, 0).text() if self.results_table.item(row, 0) else ''
                            protocol = self.results_table.item(row, 1).text() if self.results_table.item(row, 1) else ''
                            extension = self.results_table.item(row, 2).text() if self.results_table.item(row, 2) else ''
                            dns_status = self.results_table.item(row, 3).text() if self.results_table.item(row, 3) else ''
                            indexing_status = self.results_table.item(row, 4).text() if self.results_table.item(row, 4) else ''
                            availability = self.results_table.item(row, 5).text() if self.results_table.item(row, 5) else ''
                            f.write(f"{domain},{protocol},{extension},{dns_status},{indexing_status},{availability}\n")
                else:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        # Text export mirrors CSV columns in pipe-separated format
                        f.write("Domain|Protocol|Extension|DNS Status|Indexing Status|Availability\n")
                        for row in range(self.results_table.rowCount()):
                            domain = self.results_table.item(row, 0).text() if self.results_table.item(row, 0) else ''
                            protocol = self.results_table.item(row, 1).text() if self.results_table.item(row, 1) else ''
                            extension = self.results_table.item(row, 2).text() if self.results_table.item(row, 2) else ''
                            dns_status = self.results_table.item(row, 3).text() if self.results_table.item(row, 3) else ''
                            indexing_status = self.results_table.item(row, 4).text() if self.results_table.item(row, 4) else ''
                            availability = self.results_table.item(row, 5).text() if self.results_table.item(row, 5) else ''
                            f.write(f"{domain}|{protocol}|{extension}|{dns_status}|{indexing_status}|{availability}\n")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export: {str(e)}")
                return

            QMessageBox.information(self, "Export Complete", f"Results exported to {file_path}")
            self.add_log(f"📁 Results exported to {file_path}")
                
    def clear_results(self):
        """Clear all results"""
        self.external_domains.clear()
        self.total_domains_found = 0
        self.results_table.setRowCount(0)
        self.update_domains_count()
        self.add_log("🗑️ Results cleared")
    
    def check_domain_dns(self, domain):
        """Check DNS status for a single domain"""
        try:
            if not hasattr(self, 'dns_executor'):
                self.dns_executor = ThreadPoolExecutor(max_workers=10)
            dns_checker = AsyncDNSChecker(timeout=2.0, max_workers=10)
            def task():
                try:
                    result = dns_checker.check_domain_sync(domain)
                    status = result.get('status', False)
                except Exception:
                    status = False
                # Marshal back to GUI thread
                QtCore.QTimer.singleShot(0, lambda: self.update_dns_status(domain, status))
            self.dns_executor.submit(task)
        except Exception:
            QtCore.QTimer.singleShot(0, lambda: self.update_dns_status(domain, False))
            
    def update_dns_status(self, domain, status):
        """Update DNS status for a domain in the table"""
        # Update the stored domain info
        if domain in self.external_domains:
            self.external_domains[domain]['dns_status'] = status
            
        # If HTTP + DNS False: render and proceed. Else: skip rendering to save memory
        protocol = self.external_domains.get(domain, {}).get('protocol', '')
        if protocol.lower() == 'http' and not status:
            # Buffer row updates if live update is off, to keep UI responsive while scraping
            if hasattr(self, 'live_update_checkbox') and not self.live_update_checkbox.isChecked():
                if not hasattr(self, '_pending_table_domains'):
                    self._pending_table_domains = set()
                self._pending_table_domains.add(domain)
                if hasattr(self, 'apply_updates_button'):
                    self.apply_updates_button.setEnabled(True)
                return
            # Ensure row exists or create it
            row = self.find_row_by_domain(domain)
            self.results_table.setUpdatesEnabled(False)
            sorting_prev = self.results_table.isSortingEnabled()
            if sorting_prev:
                self.results_table.setSortingEnabled(False)
            if row is None:
                row = self.results_table.rowCount()
                self.results_table.insertRow(row)
                self.results_table.setItem(row, 0, QTableWidgetItem(domain))
                self.results_table.setItem(row, 1, QTableWidgetItem(protocol))
                self.results_table.setItem(row, 2, QTableWidgetItem(self.external_domains.get(domain, {}).get('extension', '')))
            # Set DNS False
            dns_item = QTableWidgetItem('False')
            dns_item.setTextAlignment(Qt.AlignCenter)
            dns_item.setBackground(QColor(144, 238, 144))
            self.results_table.setItem(row, 3, dns_item)
            # Prepare indexing column
            indexing_item = QTableWidgetItem('Checking...' if (self.rapidapi_key and hasattr(self, 'auto_check_indexing') and self.auto_check_indexing.isChecked()) else 'Pending')
            indexing_item.setTextAlignment(Qt.AlignCenter)
            self.results_table.setItem(row, 4, indexing_item)
            # Prepare availability column
            if self.results_table.columnCount() < 6:
                self.results_table.setColumnCount(6)
                self.results_table.setHorizontalHeaderLabels(['Domain', 'Protocol', 'Extension', 'DNS Status', 'Indexing Status', 'Availability'])
            availability_item = QTableWidgetItem('Pending')
            availability_item.setTextAlignment(Qt.AlignCenter)
            self.results_table.setItem(row, 5, availability_item)
            # Auto-start indexing for HTTP + DNS False
            if (self.rapidapi_key and hasattr(self, 'auto_check_indexing') and self.auto_check_indexing.isChecked()):
                self.check_domain_indexing(domain, protocol)
                self.add_log(f"🔍 Starting indexing check for HTTP domain with DNS False: {domain}")
            if sorting_prev:
                self.results_table.setSortingEnabled(True)
            self.results_table.setUpdatesEnabled(True)
        else:
            # Skip rendering for non-eligible domains to reduce memory footprint
            pass

    def apply_pending_table_updates(self):
        """Apply buffered table updates when live update is turned off."""
        try:
            if not hasattr(self, '_pending_table_domains') or not self._pending_table_domains:
                if hasattr(self, 'apply_updates_button'):
                    self.apply_updates_button.setEnabled(False)
                return
            self.results_table.setUpdatesEnabled(False)
            sorting_prev = self.results_table.isSortingEnabled()
            if sorting_prev:
                self.results_table.setSortingEnabled(False)
            for domain in list(self._pending_table_domains):
                protocol = self.external_domains.get(domain, {}).get('protocol', '')
                status = self.external_domains.get(domain, {}).get('dns_status', True)
                if protocol.lower() == 'http' and not status:
                    row = self.find_row_by_domain(domain)
                    if row is None:
                        row = self.results_table.rowCount()
                        self.results_table.insertRow(row)
                        self.results_table.setItem(row, 0, QTableWidgetItem(domain))
                        self.results_table.setItem(row, 1, QTableWidgetItem(protocol))
                        self.results_table.setItem(row, 2, QTableWidgetItem(self.external_domains.get(domain, {}).get('extension', '')))
                    dns_item = QTableWidgetItem('False')
                    dns_item.setTextAlignment(Qt.AlignCenter)
                    dns_item.setBackground(QColor(144, 238, 144))
                    self.results_table.setItem(row, 3, dns_item)
                    indexing_item = QTableWidgetItem('Pending')
                    indexing_item.setTextAlignment(Qt.AlignCenter)
                    self.results_table.setItem(row, 4, indexing_item)
                    if self.results_table.columnCount() < 6:
                        self.results_table.setColumnCount(6)
                        self.results_table.setHorizontalHeaderLabels(['Domain', 'Protocol', 'Extension', 'DNS Status', 'Indexing Status', 'Availability'])
                    availability_item = QTableWidgetItem('Pending')
                    availability_item.setTextAlignment(Qt.AlignCenter)
                    self.results_table.setItem(row, 5, availability_item)
                self._pending_table_domains.discard(domain)
            if sorting_prev:
                self.results_table.setSortingEnabled(True)
        finally:
            self.results_table.setUpdatesEnabled(True)
            if hasattr(self, 'apply_updates_button'):
                self.apply_updates_button.setEnabled(bool(self._pending_table_domains))
        
    def add_log(self, message):
        """Add a log message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        # Buffer logs to reduce UI updates
        self._log_buffer.append(formatted_message)
        # Prevent unbounded growth in worst case
        if len(self._log_buffer) > 500:
            self.flush_log_buffer()

    def flush_log_buffer(self):
        """Flush buffered logs to the UI in batches"""
        if not self._log_buffer:
            return
        try:
            text = "\n".join(self._log_buffer)
            self._log_buffer.clear()
            self.log_display.appendPlainText(text)
            if hasattr(self, 'auto_scroll_checkbox') and self.auto_scroll_checkbox.isChecked():
                self.log_display.ensureCursorVisible()
        except Exception:
            # If anything goes wrong, clear buffer to avoid repeated failures
            self._log_buffer.clear()
            
    def clear_logs(self):
        """Clear log display"""
        self.log_display.clear()
        
    def toggle_autoscroll(self, enabled: bool):
        """Start/stop autoscroll timer based on checkbox"""
        try:
            if enabled:
                if not self.autoscroll_timer.isActive():
                    self.autoscroll_timer.start()
            else:
                if self.autoscroll_timer.isActive():
                    self.autoscroll_timer.stop()
        except Exception:
            pass
        
    def update_status(self, status):
        """Update status label"""
        self.status_label.setText(status)
        self.statusBar().showMessage(status)
        
    def update_progress(self, current, total):
        """Update progress bar"""
        if total > 0:
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)
        else:
            self.progress_bar.setValue(0)
            
    def update_backup_status(self, status):
        """Update backup status (placeholder)"""
        # This could be implemented to show backup status in the GUI
        pass
        
    def cleanup_logs(self):
        """Cleanup old log entries to prevent memory issues"""
        # Limit log display to last 1000 lines
        if self.log_display.blockCount() > 1000:
            cursor = self.log_display.textCursor()
            cursor.movePosition(cursor.Start)
            for _ in range(200):  # Remove first 200 lines
                cursor.select(cursor.BlockUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()  # Remove the newline
                
    def process_events(self):
        """Process GUI events to keep interface responsive"""
        QCoreApplication.processEvents()
        # Perform debounced autoscroll if requested
        if self.autoscroll_pending:
            self.perform_debounced_autoscroll()
            self.autoscroll_pending = False

    def perform_debounced_autoscroll(self):
        """Smoothly autoscroll to bottom without thrashing the view"""
        try:
            if hasattr(self, 'auto_scroll_checkbox') and self.auto_scroll_checkbox.isChecked():
                self.results_table.scrollToBottom()
        except Exception:
            pass
        
    def closeEvent(self, event):
        """Handle application close"""
        if self.scraping_thread and self.scraping_thread.isRunning():
            reply = QMessageBox.question(
                self, "Confirm Exit", 
                "Scraping is in progress. Are you sure you want to exit?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.scraping_thread.stop()
                self.scraping_thread.wait(3000)
                try:
                    if hasattr(self, 'dns_executor'):
                        self.dns_executor.shutdown(wait=False)
                except Exception:
                    pass
                event.accept()
            else:
                event.ignore()
        else:
            try:
                if hasattr(self, 'dns_executor'):
                    self.dns_executor.shutdown(wait=False)
            except Exception:
                pass
            event.accept()


    def create_settings_tab(self):
        """Create the settings tab for API configuration"""
        settings_tab = QWidget()
        self.tab_widget.addTab(settings_tab, "Settings")
        
        settings_layout = QVBoxLayout(settings_tab)
        
        # RapidAPI Configuration Group
        api_group = QGroupBox("RapidAPI Configuration")
        api_layout = QGridLayout(api_group)
        
        # API Key Input
        api_layout.addWidget(QLabel("RapidAPI Key:"), 0, 0)
        self.rapidapi_key_input = QLineEdit()
        self.rapidapi_key_input.setEchoMode(QLineEdit.Password)
        self.rapidapi_key_input.setPlaceholderText("Enter your RapidAPI key for Google Search API")
        self.rapidapi_key_input.textChanged.connect(self.on_api_key_changed)
        api_layout.addWidget(self.rapidapi_key_input, 0, 1)
        
        # Show/Hide API Key Button
        self.show_key_button = QPushButton("Show")
        self.show_key_button.clicked.connect(self.toggle_api_key_visibility)
        api_layout.addWidget(self.show_key_button, 0, 2)
        
        # Test API Button
        self.test_api_button = QPushButton("Test API Connection")
        self.test_api_button.clicked.connect(self.test_api_connection)
        self.test_api_button.setEnabled(False)
        api_layout.addWidget(self.test_api_button, 1, 1)
        
        # API Status Label
        self.api_status_label = QLabel("API Status: Not configured")
        self.api_status_label.setWordWrap(True)
        api_layout.addWidget(self.api_status_label, 2, 0, 1, 3)
        
        settings_layout.addWidget(api_group)
        
        # Indexing Configuration Group
        indexing_group = QGroupBox("Indexing Checker Configuration")
        indexing_layout = QGridLayout(indexing_group)
        
        # Auto-check indexing checkbox
        self.auto_check_indexing = QCheckBox("Auto-check indexing for HTTP domains with DNS False")
        self.auto_check_indexing.setChecked(True)
        self.auto_check_indexing.setToolTip("When enabled, only HTTP domains with DNS resolution failures will be automatically checked for Google indexing status")
        indexing_layout.addWidget(self.auto_check_indexing, 0, 0, 1, 2)
        
        # Check All Eligible Domains Button
        self.check_all_http_button = QPushButton("Check HTTP Domains (DNS False)")
        self.check_all_http_button.clicked.connect(self.check_all_http_domains)
        self.check_all_http_button.setEnabled(False)
        self.check_all_http_button.setToolTip("Only checks HTTP domains with DNS resolution failures")
        indexing_layout.addWidget(self.check_all_http_button, 1, 0)
        
        # Clear Indexing Results Button
        self.clear_indexing_button = QPushButton("Clear Indexing Results")
        self.clear_indexing_button.clicked.connect(self.clear_indexing_results)
        indexing_layout.addWidget(self.clear_indexing_button, 1, 1)
        
        settings_layout.addWidget(indexing_group)

        # Availability Configuration Group
        availability_group = QGroupBox("Domain Availability Checker Configuration")
        availability_layout = QGridLayout(availability_group)

        # API Key Input
        availability_layout.addWidget(QLabel("RapidAPI Key (Domain Status):"), 0, 0)
        self.availability_key_input = QLineEdit()
        self.availability_key_input.setEchoMode(QLineEdit.Password)
        self.availability_key_input.setPlaceholderText("Enter your RapidAPI key for domainstatus API")
        self.availability_key_input.textChanged.connect(self.on_availability_key_changed)
        availability_layout.addWidget(self.availability_key_input, 0, 1)

        # Show/Hide API Key Button
        self.show_availability_key_button = QPushButton("Show")
        self.show_availability_key_button.clicked.connect(self.toggle_availability_key_visibility)
        availability_layout.addWidget(self.show_availability_key_button, 0, 2)

        # Test API Button
        self.test_availability_button = QPushButton("Test Availability API")
        self.test_availability_button.clicked.connect(self.test_availability_api_connection)
        self.test_availability_button.setEnabled(False)
        availability_layout.addWidget(self.test_availability_button, 1, 1)

        # Auto-check availability checkbox
        self.auto_check_availability = QCheckBox("Auto-check availability for domains confirmed as Indexed")
        self.auto_check_availability.setChecked(True)
        self.auto_check_availability.setToolTip("Availability is only checked after indexing marks the domain as Indexed")
        availability_layout.addWidget(self.auto_check_availability, 2, 0, 1, 2)

        # Clear Availability Results Button
        self.clear_availability_button = QPushButton("Clear Availability Results")
        self.clear_availability_button.clicked.connect(self.clear_availability_results)
        availability_layout.addWidget(self.clear_availability_button, 2, 2)

        settings_layout.addWidget(availability_group)
        
        # Instructions Group
        instructions_group = QGroupBox("Instructions")
        instructions_layout = QVBoxLayout(instructions_group)
        
        instructions_text = QLabel("""
        <b>RapidAPI Setup Instructions:</b><br>
        1. Go to <a href="https://rapidapi.com/rapidapi/api/google-search116">RapidAPI Google Search</a><br>
        2. Subscribe to the Google Search API<br>
        3. Copy your API key from the dashboard<br>
        4. Paste the key above and test the connection<br><br>
        
        <b>Indexing Checker:</b><br>
        • Only HTTP domains with DNS False status are checked for indexing<br>
        • HTTPS domains and HTTP domains with DNS True are skipped<br>
        • Green highlighting indicates indexed domains<br>
        • Use the "Test API Connection" button to verify your setup<br>
        • Check "Auto check indexing" to automatically verify eligible HTTP domains<br><br>

        <b>Availability Checker:</b><br>
        • Uses RapidAPI domainstatus to check registration availability<br>
        • Runs only after a domain is confirmed as Indexed (post-indexing)<br>
        • Enable auto-check to run automatically after indexing checks
        """)
        instructions_text.setWordWrap(True)
        instructions_text.setOpenExternalLinks(True)
        instructions_layout.addWidget(instructions_text)
        
        settings_layout.addWidget(instructions_group)
        settings_layout.addStretch()
    
    def on_api_key_changed(self, text):
        """Handle API key input changes"""
        self.rapidapi_key = text.strip()
        self.indexing_checker.set_api_key(self.rapidapi_key)
        
        # Enable/disable buttons based on API key
        has_key = bool(self.rapidapi_key)
        self.test_api_button.setEnabled(has_key)
        self.check_all_http_button.setEnabled(has_key)
        
        if has_key:
            self.api_status_label.setText("API Status: Key configured (not tested)")
        else:
            self.api_status_label.setText("API Status: Not configured")
    
    def toggle_api_key_visibility(self):
        """Toggle API key visibility"""
        if self.rapidapi_key_input.echoMode() == QLineEdit.Password:
            self.rapidapi_key_input.setEchoMode(QLineEdit.Normal)
            self.show_key_button.setText("Hide")
        else:
            self.rapidapi_key_input.setEchoMode(QLineEdit.Password)
            self.show_key_button.setText("Show")
    
    def test_api_connection(self):
        """Test the RapidAPI connection"""
        if not self.rapidapi_key:
            QMessageBox.warning(self, "No API Key", "Please enter your RapidAPI key first.")
            return
        
        self.api_status_label.setText("API Status: Testing connection...")
        self.test_api_button.setEnabled(False)
        
        # Test in a separate thread to avoid blocking GUI
        def test_connection():
            try:
                result = self.indexing_checker.test_api_connection()
                
                # Update UI in main thread
                if result['success']:
                    self.api_status_label.setText(f"API Status: ✓ {result['message']}")
                    QMessageBox.information(self, "API Test Success", result['message'])
                else:
                    self.api_status_label.setText(f"API Status: ✗ {result['message']}")
                    QMessageBox.warning(self, "API Test Failed", result['message'])
                    
            except Exception as e:
                self.api_status_label.setText(f"API Status: ✗ Test failed: {str(e)}")
                QMessageBox.critical(self, "API Test Error", f"Failed to test API: {str(e)}")
            
            self.test_api_button.setEnabled(True)
        
        # Run test in background thread
        import threading
        threading.Thread(target=test_connection, daemon=True).start()
    
    def check_domain_indexing(self, domain, protocol):
        """Check indexing status for a specific domain (only HTTP domains with DNS False)"""
        if not self.rapidapi_key or protocol.lower() != 'http':
            return
        
        # Additional check: Only process domains with DNS False
        domain_dns_status = None
        for row in range(self.results_table.rowCount()):
            if self.results_table.item(row, 0).text() == domain:
                dns_item = self.results_table.item(row, 3)
                if dns_item:
                    domain_dns_status = dns_item.text()
                break
        
        if domain_dns_status != 'False':
            self.add_log(f"Skipping indexing check for {domain} - DNS status is not False (current: {domain_dns_status})")
            return
        
        def check_indexing():
            try:
                result = self.indexing_checker.check_domain_indexing(domain, protocol)
                
                # Update the table with results
                self.update_indexing_status(domain, result)
                
            except Exception as e:
                self.add_log(f"Indexing check error for {domain}: {str(e)}")
        
        # Run check in background thread
        import threading
        threading.Thread(target=check_indexing, daemon=True).start()
    
    def update_indexing_status(self, domain, result):
        """Update indexing status for a domain in the table"""
        # Find the domain in the table and update indexing status
        self.results_table.setUpdatesEnabled(False)
        for row in range(self.results_table.rowCount()):
            if self.results_table.item(row, 0).text() == domain:
                if result['skipped']:
                    status_text = result['reason']
                    indexing_item = QTableWidgetItem(status_text)
                elif result['indexed']:
                    status_text = "✓ Indexed"
                    indexing_item = QTableWidgetItem(status_text)
                    # Green background for indexed HTTP domains
                    indexing_item.setBackground(QColor(144, 238, 144))  # Light green
                else:
                    status_text = "✗ Not Indexed"
                    indexing_item = QTableWidgetItem(status_text)
                
                indexing_item.setTextAlignment(Qt.AlignCenter)
                self.results_table.setItem(row, 4, indexing_item)
                
                # Log the result
                if not result['skipped']:
                    self.add_log(f"Indexing check: {domain} - {status_text} ({result['response_time']}ms)")

                # If indexed, optionally trigger availability check
                if result.get('indexed') and self.availability_api_key and hasattr(self, 'auto_check_availability') and self.auto_check_availability.isChecked():
                    if self.results_table.columnCount() >= 6:
                        availability_item = QTableWidgetItem('Checking...')
                        availability_item.setTextAlignment(Qt.AlignCenter)
                        self.results_table.setItem(row, 5, availability_item)
                    self.check_domain_availability(domain)
                    self.add_log(f"🔍 Starting availability check after indexing success: {domain}")
                break
        self.results_table.setUpdatesEnabled(True)
    
    def check_all_http_domains(self):
        """Check indexing status for HTTP domains with DNS False status only"""
        if not self.rapidapi_key:
            QMessageBox.warning(self, "No API Key", "Please configure your RapidAPI key first.")
            return
        
        eligible_domains = []
        for row in range(self.results_table.rowCount()):
            domain = self.results_table.item(row, 0).text()
            protocol = self.results_table.item(row, 1).text()
            dns_status_item = self.results_table.item(row, 3)
            
            # Only check domains that are HTTP AND have DNS False
            if (protocol.lower() == 'http' and 
                dns_status_item and 
                dns_status_item.text() == 'False'):
                eligible_domains.append({'domain': domain, 'protocol': protocol})
        
        if not eligible_domains:
            QMessageBox.information(self, "No Eligible Domains", 
                                  "No HTTP domains with DNS False status found to check.\n\n"
                                  "Only HTTP domains with DNS resolution failures are checked for indexing.")
            return
        
        self.add_log(f"Starting indexing check for {len(eligible_domains)} HTTP domains with DNS False status...")
        
        # Check domains in batches to avoid overwhelming the API
        for domain_info in eligible_domains:
            # Only start indexing here; availability will be triggered after an Indexed result
            self.check_domain_indexing(domain_info['domain'], domain_info['protocol'])
    
    def clear_indexing_results(self):
        """Clear all indexing results from the table"""
        for row in range(self.results_table.rowCount()):
            protocol_item = self.results_table.item(row, 1)
            if protocol_item and protocol_item.text().lower() == 'http':
                # Reset HTTP domains to 'Pending'
                indexing_item = QTableWidgetItem('Pending')
                indexing_item.setTextAlignment(Qt.AlignCenter)
                indexing_item.setBackground(QColor())  # Clear background
                self.results_table.setItem(row, 4, indexing_item)
            
        self.add_log("Indexing results cleared for all HTTP domains")

    def on_availability_key_changed(self, text):
        """Handle availability API key input changes"""
        self.availability_api_key = text.strip()
        self.availability_checker.set_api_key(self.availability_api_key)
        has_key = bool(self.availability_api_key)
        self.test_availability_button.setEnabled(has_key)

    def toggle_availability_key_visibility(self):
        """Toggle availability API key visibility"""
        if self.availability_key_input.echoMode() == QLineEdit.Password:
            self.availability_key_input.setEchoMode(QLineEdit.Normal)
            self.show_availability_key_button.setText("Hide")
        else:
            self.availability_key_input.setEchoMode(QLineEdit.Password)
            self.show_availability_key_button.setText("Show")

    def test_availability_api_connection(self):
        """Test the availability RapidAPI connection"""
        if not self.availability_api_key:
            QMessageBox.warning(self, "No API Key", "Please enter your RapidAPI key first.")
            return
        
        self.test_availability_button.setEnabled(False)
        
        def test_connection():
            try:
                result = self.availability_checker.test_api_connection()
                if result['success']:
                    QMessageBox.information(self, "API Test Success", result['message'])
                else:
                    QMessageBox.warning(self, "API Test Failed", result['message'])
            except Exception as e:
                QMessageBox.critical(self, "API Test Error", f"Failed to test API: {str(e)}")
            self.test_availability_button.setEnabled(True)
        
        import threading
        threading.Thread(target=test_connection, daemon=True).start()

    def check_domain_availability(self, domain: str):
        """Check availability status for a specific domain"""
        if not self.availability_api_key:
            return
        
        def do_check():
            try:
                result = self.availability_checker.check_domain_availability(domain)
                self.update_availability_status(domain, result)
            except Exception as e:
                self.add_log(f"Availability check error for {domain}: {str(e)}")
        
        import threading
        threading.Thread(target=do_check, daemon=True).start()

    def update_availability_status(self, domain: str, result: dict):
        """Update availability status in the table"""
        self.results_table.setUpdatesEnabled(False)
        for row in range(self.results_table.rowCount()):
            if self.results_table.item(row, 0).text() == domain:
                status_text = '✓ Available' if result.get('available') else ('⚠ Skipped' if result.get('skipped') else '✗ Unavailable')
                availability_item = QTableWidgetItem(status_text)
                availability_item.setTextAlignment(Qt.AlignCenter)
                if result.get('available'):
                    availability_item.setBackground(QColor(173, 216, 230))  # Light blue for available
                self.results_table.setItem(row, 5, availability_item)
                if not result.get('skipped'):
                    self.add_log(f"Availability check: {domain} - {status_text} ({result.get('response_time', 0)}ms)")
                break
        self.results_table.setUpdatesEnabled(True)

    def clear_availability_results(self):
        """Clear availability results column"""
        if self.results_table.columnCount() < 6:
            return
        for row in range(self.results_table.rowCount()):
            protocol_item = self.results_table.item(row, 1)
            if protocol_item and protocol_item.text().lower() == 'http':
                availability_item = QTableWidgetItem('Pending')
                availability_item.setTextAlignment(Qt.AlignCenter)
                availability_item.setBackground(QColor())
                self.results_table.setItem(row, 5, availability_item)
        self.add_log("Availability results cleared for all HTTP domains")


def main():
    """Main application entry point"""
    # Set software OpenGL for compatibility
    if os.name == 'nt':  # Windows
        os.environ['QT_OPENGL'] = 'software'
    
    # Create QApplication with suppressed font warnings
    with suppress_qt_warnings():
        app = QApplication(sys.argv)
        
        # Configure font handling to prevent database errors
        try:
            # Use system default font to avoid font directory issues
            font_db = QFontDatabase()
            default_font = app.font()
            default_font.setFamily("Arial")  # Use common system font
            default_font.setPointSize(9)
            app.setFont(default_font)
        except Exception as e:
            # Silently handle any font-related errors
            pass
        try:
            # Ensure QVector<int> is registered for queued connections
            from PyQt5 import QtCore as _QtCore
            _qregister2 = getattr(_QtCore, 'qRegisterMetaType', None)
            if callable(_qregister2):
                _qregister2('QVector<int>')
        except Exception:
            pass
    
    app.setApplicationName("Advanced Web Scraping Tool")
    app.setApplicationVersion("2.0")
    
    # Set application icon if available
    try:
        if os.path.exists('icon.ico'):
            app.setWindowIcon(QIcon('icon.ico'))
    except:
        pass
    
    # Create and show main window
    window = WebScrapingGUI()
    window.show()
    
    # Load previous backup data
    window.load_domains_from_backup()
    
    # Run the application
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()