import re
from pathlib import Path

p = Path("ui/main_menu.ui")
text = p.read_text()

old_w = 900
old_h = 741

new_w = 1024
new_h = 768

scale = min(new_w / old_w, new_h / old_h)

# Size of the complete UI after proportional scaling
fit_w = round(old_w * scale)
fit_h = round(old_h * scale)

offset_x = round((new_w - fit_w) / 2)
offset_y = round((new_h - fit_h) / 2)

print("Scale:", scale)
print("Fitted:", fit_w, "x", fit_h)
print("Offset:", offset_x, offset_y)

# Scale every <rect> geometry in the UI.
def scale_rect(match):
    block = match.group(0)

    x = int(re.search(r"<x>(-?\d+)</x>", block).group(1))
    y = int(re.search(r"<y>(-?\d+)</y>", block).group(1))
    w = int(re.search(r"<width>(\d+)</width>", block).group(1))
    h = int(re.search(r"<height>(\d+)</height>", block).group(1))

    # Root widget gets the fitted canvas size.
    if x == 0 and y == 0 and w == old_w and h == old_h:
        nx = 0
        ny = 0
        nw = fit_w
        nh = fit_h
    else:
        nx = round(x * scale)
        ny = round(y * scale)
        nw = round(w * scale)
        nh = round(h * scale)

    block = re.sub(r"<x>-?\d+</x>", f"<x>{nx}</x>", block, count=1)
    block = re.sub(r"<y>-?\d+</y>", f"<y>{ny}</y>", block, count=1)
    block = re.sub(r"<width>\d+</width>", f"<width>{nw}</width>", block, count=1)
    block = re.sub(r"<height>\d+</height>", f"<height>{nh}</height>", block, count=1)

    return block

text = re.sub(
    r"<rect>\s*<x>-?\d+</x>\s*<y>-?\d+</y>\s*<width>\d+</width>\s*<height>\d+</height>\s*</rect>",
    scale_rect,
    text
)

# Update root canvas to fitted size.
text = re.sub(
    r"(<widget class=\"QPushButton\" name=\"btnHome\">)",
    r"\1",
    text
)

p.write_text(text)

print("MAIN MENU GEOMETRY SCALED")
