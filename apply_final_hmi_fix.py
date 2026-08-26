#!/usr/bin/env python3
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

ROOT = Path.home() / "SEGWAY HMI V2"
UI = ROOT / "ui"

EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]")

def load(name):
    return ET.parse(UI / name)

def widgets(root):
    return {w.get("name"): w for w in root.iter("widget") if w.get("name")}

def set_rect(w, x, y, width, height):
    r = w.find("property[@name='geometry']/rect")
    if r is not None:
        r.find("x").text = str(x)
        r.find("y").text = str(y)
        r.find("width").text = str(width)
        r.find("height").text = str(height)

def set_text(w, text):
    p = w.find("property[@name='text']")
    if p is None:
        p = ET.SubElement(w, "property", {"name": "text"})
        ET.SubElement(p, "string")
    s = p.find("string")
    if s is None:
        s = ET.SubElement(p, "string")
    s.text = text

def set_font(w, size):
    p = w.find("property[@name='font']")
    if p is not None:
        f = p.find("font")
        if f is not None:
            ps = f.find("pointsize")
            if ps is not None:
                ps.text = str(size)

def hide(w):
    if w is None:
        return
    p = w.find("property[@name='visible']")
    if p is None:
        p = ET.SubElement(w, "property", {"name": "visible"})
        ET.SubElement(p, "bool")
    p.find("bool").text = "false"

def strip_emojis(root):
    for w in root.iter("widget"):
        p = w.find("property[@name='text']/string")
        if p is not None and p.text:
            p.text = EMOJI_RE.sub("", p.text).strip()

def save(tree, name):
    tree.write(UI / name, encoding="UTF-8", xml_declaration=True)

def backup(path):
    if path.exists():
        dst = path.with_name(path.name + ".before_final_fix")
        if not dst.exists():
            shutil.copy2(path, dst)

# ------------------------------------------------------------
# BACKUPS
# ------------------------------------------------------------
for name in ("home.ui", "battery.ui", "camera.ui", "graph.ui", "main.py"):
    backup((UI / name) if name.endswith(".ui") else (ROOT / name))

# ------------------------------------------------------------
# HOME
# ------------------------------------------------------------
t = load("home.ui")
r = t.getroot()
w = widgets(r)
strip_emojis(r)

if "lblhome" in w:
    set_rect(w["lblhome"], 390, 20, 220, 40)

if "speedTitleLabel" in w:
    set_rect(w["speedTitleLabel"], 380, 85, 260, 35)
    set_font(w["speedTitleLabel"], 20)

if "speedValueLabel" in w:
    set_rect(w["speedValueLabel"], 330, 125, 360, 65)

for name, x, y in (
    ("frameVoltage", 70, 230),
    ("frameCurrent", 310, 230),
    ("tempeatuereframe", 550, 230),
    ("LefRPMframe", 70, 350),
    ("frameRightRPM", 310, 350),
    ("frameYaw", 550, 350),
    ("framePitch", 70, 470),
    ("frameRoll_2", 310, 470),
    ("Modeframe", 550, 470),
):
    if name in w:
        set_rect(w[name], x, y, 180, 80)

if "statusLabel" in w:
    set_rect(w["statusLabel"], 310, 585, 400, 35)
    set_text(w["statusLabel"], "STATUS : READY")

if "label" in w:
    set_rect(w["label"], 250, 635, 520, 45)

# Same clock area as Motor Control.
if "timeLabel" in w:
    set_rect(w["timeLabel"], 660, 30, 121, 31)
if "dateLabel" in w:
    set_rect(w["dateLabel"], 650, 60, 161, 31)

save(t, "home.ui")

# ------------------------------------------------------------
# BATTERY
# ------------------------------------------------------------
t = load("battery.ui")
r = t.getroot()
w = widgets(r)
strip_emojis(r)

# Remove Battery Voltage Graph button.
if "btnHome" in w:
    hide(w["btnHome"])

# Remove duplicate/old RPM cards.
for name in (
    "LefRPMframe", "frameRightRPM",
    "LefRPMframe_2", "frameRightRPM_2",
):
    if name in w:
        hide(w[name])

# Final 3 x 3 battery layout:
# Voltage | Current | Power
# Temperature | Capacity | Health
# Charging | BMS Status | Cycles
for name, x, y in (
    ("frameVoltage", 70, 210),
    ("frameCurrent", 310, 210),
    ("tempeatuereframe", 550, 210),
    ("framePitch", 70, 310),
    ("frameRoll_2", 310, 310),
    ("frameYaw", 550, 310),
    ("framePitch_2", 70, 410),
    ("frameRoll_3", 310, 410),
    ("frameYaw_2", 550, 410),
):
    if name in w:
        set_rect(w[name], x, y, 180, 80)

for name in (
    "leftRPMTitleLabel", "leftRPMTitleLabel_2",
    "rightRPMTitleLabel", "rightRPMValueLabel",
    "leftRPMTitleLabel_3", "leftRPMTitleLabel_4",
    "rightRPMTitleLabel_2", "rightRPMValueLabel_2",
):
    if name in w:
        hide(w[name])

for name, text in (
    ("temperatureTitleLabel", "Power"),
    ("pitchTitleLabel", "Temperature"),
    ("rollTitleLabel_2", "Capacity"),
    ("yawTitleLabel", "Health"),
    ("pitchTitleLabel_2", "Charging"),
    ("rollTitleLabel_3", "BMS Status"),
    ("yawTitleLabel_2", "Cycles"),
):
    if name in w:
        set_text(w[name], text)

if "lblTime" in w:
    set_rect(w["lblTime"], 380, 20, 220, 40)
    set_text(w["lblTime"], "BATTERY")

if "speedTitleLabel" in w:
    set_rect(w["speedTitleLabel"], 330, 75, 360, 35)
    set_text(w["speedTitleLabel"], "BATTERY STATUS")
    set_font(w["speedTitleLabel"], 20)

if "timeLabel" in w:
    set_rect(w["timeLabel"], 660, 30, 121, 31)
if "dateLabel" in w:
    set_rect(w["dateLabel"], 650, 60, 161, 31)

save(t, "battery.ui")

# ------------------------------------------------------------
# CAMERA
# ------------------------------------------------------------
t = load("camera.ui")
r = t.getroot()
w = widgets(r)
strip_emojis(r)

# Permanently remove FPS and Status.
for name in ("fpsframe", "statusframe"):
    if name in w:
        hide(w[name])

# Remove old decorative duplicate cards.
for name in (
    "frameYaw_2", "frameRightRPM_2",
    "frameRoll_3", "LefRPMframe_2", "framePitch_2",
):
    if name in w:
        hide(w[name])

if "lblcameramonitor" in w:
    set_rect(w["lblcameramonitor"], 320, 20, 320, 35)
    set_font(w["lblcameramonitor"], 22)

if "speedTitleLabel" in w:
    set_rect(w["speedTitleLabel"], 300, 65, 360, 35)
    set_font(w["speedTitleLabel"], 18)

if "cameraFeedLabel" in w:
    set_rect(w["cameraFeedLabel"], 50, 120, 924, 380)

for name, x in (
    ("btnStartCamera", 70),
    ("btnCaptureImage", 387),
    ("btnRecordvideo", 704),
):
    if name in w:
        set_rect(w[name], x, 520, 250, 60)

for name in ("btnHome", "label"):
    if name in w:
        hide(w[name])

if "menuLabel" in w:
    set_rect(w["menuLabel"], 20, 30, 171, 41)

if "timeLabel" in w:
    set_rect(w["timeLabel"], 660, 30, 121, 31)
if "dateLabel" in w:
    set_rect(w["dateLabel"], 650, 60, 161, 31)

save(t, "camera.ui")

# ------------------------------------------------------------
# GRAPH MONITOR
# ------------------------------------------------------------
t = load("graph.ui")
r = t.getroot()
w = widgets(r)
strip_emojis(r)

if "lblcameramonitor" in w:
    set_rect(w["lblcameramonitor"], 320, 20, 320, 35)
    set_font(w["lblcameramonitor"], 22)

if "realtimmonitoringTitleLabel" in w:
    set_rect(w["realtimmonitoringTitleLabel"], 300, 65, 424, 40)
    set_font(w["realtimmonitoringTitleLabel"], 20)

if "graphFrame" in w:
    set_rect(w["graphFrame"], 50, 115, 924, 360)

# 3 columns x 2 rows, larger buttons.
for name, x, y in (
    ("btnSpeed", 70, 495),
    ("btnCurrent", 317, 495),
    ("btnVoltage", 564, 495),
    ("btnTemperature", 70, 565),
    ("btnBattery", 317, 565),
    ("btnPower", 564, 565),
):
    if name in w:
        set_rect(w[name], x, y, 230, 60)

for name in (
    "leftRPMTitleLabel_3", "yawTitleLabel_2",
    "rollTitleLabel_3", "leftRPMTitleLabel_6",
    "rollTitleLabel_4", "yawTitleLabel_3",
):
    if name in w:
        set_font(w[name], 18)

# Remove Update Rate, Samples and Logging permanently.
for name in (
    "label_2", "frameSamples", "framelogging",
    "lblUpdateRate", "lblSamples", "lblLoggingStatus",
):
    if name in w:
        hide(w[name])

if "menuLabel" in w:
    set_rect(w["menuLabel"], 20, 30, 171, 41)

if "timeLabel" in w:
    set_rect(w["timeLabel"], 660, 30, 121, 31)
if "dateLabel" in w:
    set_rect(w["dateLabel"], 650, 60, 161, 31)

save(t, "graph.ui")

# ------------------------------------------------------------
# MAIN.PY
# ------------------------------------------------------------
main = ROOT / "main.py"
text = main.read_text(encoding="utf-8")

# Gallery button replaces the removed FPS/Status area.
old_gallery = """self.gallery_button.setGeometry(
            650,
            650,
            180,
            45
        )"""
new_gallery = """self.gallery_button.setGeometry(
            70,
            595,
            854,
            55
        )"""
if old_gallery in text:
    text = text.replace(old_gallery, new_gallery, 1)

# Make the gallery button visually consistent.
anchor = """self.gallery_button.setFont(
            QFont("Arial", 13, QFont.Weight.Bold)
        )"""

replacement = '''self.gallery_button.setFont(
            QFont("Arial", 15, QFont.Weight.Bold)
        )

        self.gallery_button.setStyleSheet("""
            QPushButton {
                background-color: #2B2B2B;
                color: #FFFFFF;
                border: 3px solid #9C27B0;
                border-radius: 15px;
            }
            QPushButton:pressed {
                background-color: #3A3A3A;
            }
        """)'''

if anchor in text:
    text = text.replace(anchor, replacement, 1)

# Stop updating labels that have been permanently removed.
text = re.sub(
    r'\n\s*self\.window\.lblSamples\.setText\(\s*str\(self\.graph\.samples\(\)\)\s*\)\s*',
    '\n',
    text,
    count=1,
)
text = re.sub(
    r'\n\s*self\.window\.lblLoggingStatus\.setText\("Logging\.\.\."\)\s*',
    '\n',
    text,
    count=1,
)

main.write_text(text, encoding="utf-8")

print("==============================================")
print("SEGWAY HMI FINAL FIX APPLIED")
print("==============================================")
print("HOME      : emojis removed + layout cleaned")
print("BATTERY   : neat 3x3 grid + graph button removed")
print("CAMERA    : FPS/status removed + Gallery replaces them")
print("GRAPH     : logging/update-rate/samples removed")
print("GRAPH     : monitoring titles enlarged")
print("CLOCK     : top-right, same position as Motor")
print("MOTOR     : untouched")
print("DIAGNOSTICS: untouched")
print("SETTINGS  : untouched")
print("==============================================")
print("Backups created as *.before_final_fix")
print("Restart: python main.py")
