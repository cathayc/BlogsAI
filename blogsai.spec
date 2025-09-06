# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['standalone_app_new.py'],
    pathex=[],
    binaries=[],
    datas=[('data/config', 'config'), ('assets', 'assets'), ('blogsai/config/defaults/settings.yaml', 'defaults/settings.yaml'), ('blogsai/config/defaults/sources.yaml', 'defaults/sources.yaml'), ('blogsai/config/defaults/prompts', 'defaults/prompts')],
    hiddenimports=['PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets', 'PyQt5.QtPrintSupport', 'blogsai.gui.main_window', 'blogsai.gui.setup_dialog', 'blogsai.gui.api_key_dialog', 'blogsai.gui.tabs.analysis_tab', 'blogsai.gui.tabs.dashboard_tab', 'blogsai.gui.tabs.collection_tab', 'blogsai.gui.tabs.reports_tab', 'blogsai.gui.workers.analysis_worker', 'blogsai.gui.workers.base_worker', 'blogsai.gui.workers.scraping_worker', 'blogsai.gui.dialogs.first_time_setup_dialog', 'blogsai.gui.dialogs.article_dialog', 'blogsai.gui.dialogs.manual_article_dialog', 'blogsai.gui.dialogs.report_dialog', 'blogsai.core', 'blogsai.config.config', 'blogsai.config.distribution', 'blogsai.config.env_manager', 'blogsai.config.credential_manager', 'blogsai.config.app_dirs', 'blogsai.scrapers.manager', 'blogsai.scrapers.base', 'blogsai.scrapers.doj_scraper', 'blogsai.scrapers.sec_scraper', 'blogsai.scrapers.cftc_scraper', 'blogsai.scrapers.url_scraper', 'blogsai.analysis.analyzer', 'blogsai.analysis.openai_client', 'blogsai.analysis.verifier', 'blogsai.database.models', 'blogsai.database.database', 'blogsai.reporting.generator', 'blogsai.utils.logging_config', 'blogsai.utils.error_handling', 'blogsai.utils.database_helpers', 'blogsai.utils.timezone_utils', 'sqlite3', 'sqlalchemy', 'sqlalchemy.dialects.sqlite', 'openai', 'pydantic', 'yaml', 'pytz', 'dotenv', 'keyring', 'keyring.backends', 'keyring.backends.macOS', 'keyring.backends.Windows', 'keyring.backends.SecretService', 'keyring.backends.chainer', 'keyring.backends.fail', 'keyrings.alt', 'keyrings.alt.file', 'keyrings.alt.Gnome', 'keyrings.alt.Google', 'keyrings.alt.pyfs', 'cryptography', 'cryptography.fernet', 'cryptography.hazmat.primitives', 'cryptography.hazmat.primitives.kdf.pbkdf2', 'cryptography.hazmat.primitives.hashes', 'platformdirs', 'requests', 'beautifulsoup4', 'pathlib', 'json', 'base64', 'hashlib', 'getpass', 'selenium', 'selenium.webdriver', 'selenium.webdriver.chrome.options', 'selenium.webdriver.chrome.service', 'selenium.webdriver.common.by', 'selenium.webdriver.support.ui', 'selenium.webdriver.support.expected_conditions', 'selenium.common.exceptions', 'webdriver_manager', 'webdriver_manager.chrome', 'jinja2', 'reportlab', 'reportlab.lib', 'reportlab.platypus', 'markdown.extensions', 'markdown.extensions.tables', 'markdown.extensions.fenced_code', 'markdown.extensions.codehilite', 'markdown.extensions.extra', 'encodings.utf_8', 'encodings.ascii', 'encodings.cp1252', 'msvcrt', 'winreg', '_winapi', 'nt'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['hooks/runtime_distribution.py', 'hooks/runtime_windows_dll.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BlogsAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BlogsAI',
)
app = BUNDLE(
    coll,
    name='BlogsAI.app',
    icon='assets/icon.icns',
    bundle_identifier=None,
)
