"""Erkennt Platzhalter von Cloud-Speichern (Dropbox, OneDrive "nur online").

Solche Dateien haben unter Windows die volle Groesse, aber keinen Inhalt auf
der Platte. Beim Lesen holt der Cloud-Client sie nach. Laeuft er nicht oder
klemmt er, scheitert das Lesen - und pygame meldet dann irrefuehrend
"corrupt mp3 file (bad tags)".
"""

from __future__ import annotations

import os
from pathlib import Path

# Windows-Dateiattribute, siehe winnt.h
_FILE_ATTRIBUTE_OFFLINE = 0x1000
_FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x40000
_FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x400000
_CLOUD_ONLY_MASK = _FILE_ATTRIBUTE_OFFLINE | _FILE_ATTRIBUTE_RECALL_ON_OPEN | _FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS


def is_cloud_placeholder(path: Path) -> bool:
    """Prueft, ob die Datei nur in der Cloud liegt (ausserhalb von Windows immer False)."""
    try:
        attributes = getattr(os.stat(path), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & _CLOUD_ONLY_MASK)
