"""Export the Scrip brand kit from its two editable SVG masters."""

import copy
import os
import re
import shutil
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "assets/brand"
NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)


def element(tag: str, **attributes: str) -> ET.Element:
    return ET.Element(f"{{{NS}}}{tag}", attributes)


def svg(view_box: str, title: str) -> ET.Element:
    root = element("svg", viewBox=view_box, role="img", **{"aria-label": title})
    ET.SubElement(root, f"{{{NS}}}title").text = title
    return root


def write(name: str, root: ET.Element, *, directory: Path = BRAND) -> Path:
    path = directory / name
    ET.indent(root)
    path.write_text(ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8", newline="\n")
    return path


def inline(source: ET.Element, transform: str, prefix: str) -> ET.Element:
    group = element("g", transform=transform)
    for attribute in ("fill", "stroke", "color"):
        if attribute in source.attrib:
            group.set(attribute, source.attrib[attribute])
    for child in source:
        if child.tag not in (f"{{{NS}}}title", f"{{{NS}}}desc"):
            group.append(copy.deepcopy(child))
    for node in group.iter():
        if "id" in node.attrib:
            node.set("id", f"{prefix}-{node.attrib['id']}")
        for key, value in tuple(node.attrib.items()):
            node.set(key, re.sub(r"url\(#([^)]+)\)", rf"url(#{prefix}-\1)", value))
    return group


def single_color(master: ET.Element, color: str) -> ET.Element:
    parts = {node.attrib["id"]: node for node in master.iter() if "id" in node.attrib}
    root = svg("0 0 1024 1024", "Scrip robot symbol, single color")
    definitions = ET.SubElement(root, f"{{{NS}}}defs")
    mask = element(
        "mask",
        id="face-cutouts",
        maskUnits="userSpaceOnUse",
        x="0",
        y="0",
        width="1024",
        height="1024",
    )
    mask.append(element("rect", width="1024", height="1024", fill="white"))
    for name in ("s-fold", "visor", "eye-left", "eye-right"):
        part = copy.deepcopy(parts[name])
        part.set("fill", "white" if name.startswith("eye-") else "black")
        mask.append(part)
    definitions.append(mask)
    shape = element("g", fill=color, mask="url(#face-cutouts)")
    for name in ("body-loop", "ear-left", "ear-right", "helmet"):
        part = copy.deepcopy(parts[name])
        part.attrib.pop("fill", None)
        shape.append(part)
    root.append(shape)
    return root


def label(parent: ET.Element, x: int, y: int, text: str, **attributes: str) -> None:
    node = element("text", x=str(x), y=str(y), **attributes)
    node.text = text
    parent.append(node)


def render_png(source: Path, destination: Path, width: int) -> None:
    """Render a vector export without changing source artwork or application assets."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(str(source))
    if not renderer.isValid():
        raise ValueError(f"Invalid SVG: {source}")
    view = renderer.viewBoxF()
    height = round(width * view.height() / view.width())
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    if not image.save(str(destination)):
        raise OSError(f"Could not export {destination}")


def main() -> None:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    master = ET.parse(BRAND / "scrip-symbol-v1.svg").getroot()
    wordmark = ET.parse(BRAND / "scrip-wordmark-v1.svg").getroot()
    variants = {"ink": "#101619", "mint": "#80DFBF", "white": "#FFFFFF"}
    monochrome = {}
    for name, color in variants.items():
        monochrome[name] = single_color(master, color)
        write(f"scrip-symbol-{name}-v1.svg", monochrome[name])
    white_wordmark = copy.deepcopy(wordmark)
    for node in white_wordmark.iter():
        for key, value in tuple(node.attrib.items()):
            if value == "#101619":
                node.set(key, "#FFFFFF")
    write("scrip-wordmark-white-v1.svg", white_wordmark)
    lockups = {}
    for name, symbol, word in (
        ("", master, wordmark),
        ("-white", monochrome["white"], white_wordmark),
    ):
        lockup = svg("0 0 704 240", "scrip")
        lockup.append(inline(symbol, "scale(.234375)", "symbol"))
        lockup.append(inline(word, "translate(198 26) scale(1.125)", "word"))
        write(f"scrip-lockup{name}-v1.svg", lockup)
        lockups[name] = lockup
    icon = svg("0 0 512 512", "Scrip application icon")
    icon.append(element("rect", width="512", height="512", rx="112", fill="#101619"))
    icon.append(inline(monochrome["mint"], "matrix(.6 0 0 .6 -45.8 -42.2)", "icon"))
    write("scrip-app-icon-v1.svg", icon)

    board = svg("0 0 1440 1080", "Scrip identity — S-loop robot")
    board.set("font-family", "Segoe UI, sans-serif")
    board.append(element("rect", width="1440", height="1080", fill="#F4F7F3"))
    label(
        board,
        72,
        70,
        "SCRIP / IDENTITY 01",
        fill="#101619",
        **{
            "font-size": "18",
            "font-weight": "600",
            "letter-spacing": "4",
        },
    )
    label(
        board,
        1368,
        70,
        "S-LOOP ROBOT",
        fill="#68766E",
        **{
            "font-size": "14",
            "text-anchor": "end",
            "letter-spacing": "2",
        },
    )
    board.append(inline(lockups[""], "translate(100 130) scale(1.76)", "hero"))
    label(
        board,
        720,
        570,
        "A robot identity for the complete product loop.",
        fill="#526158",
        **{
            "font-size": "22",
            "text-anchor": "middle",
        },
    )
    for x, color in ((72, "#FFFFFF"), (512, "#101619"), (952, "#E5ECE5")):
        board.append(
            element("rect", x=str(x), y="626", width="416", height="324", rx="24", fill=color)
        )
    board.append(inline(monochrome["ink"], "translate(166 636) scale(.22)", "mono"))
    board.append(inline(monochrome["mint"], "translate(606 636) scale(.22)", "dark"))
    board.append(inline(icon, "translate(1076 656) scale(.32)", "app"))
    for x, text, color in (
        (280, "SINGLE INK", "#526158"),
        (720, "ON DARK", "#A9BEB2"),
        (1160, "APP ICON", "#526158"),
    ):
        label(
            board,
            x,
            912,
            text,
            fill=color,
            **{
                "font-size": "13",
                "letter-spacing": "3",
                "text-anchor": "middle",
            },
        )
    for x, color, text in ((72, "#80DFBF", "MINT / #80DFBF"), (392, "#101619", "INK / #101619")):
        board.append(
            element("rect", x=str(x), y="1005", width="28", height="28", rx="8", fill=color)
        )
        label(board, x + 42, 1025, text, fill="#526158", **{"font-size": "14"})
    label(
        board,
        1368,
        1025,
        "FLAT MASTER • VECTOR LETTERING • MOTION LAYERS",
        fill="#526158",
        **{
            "font-size": "12",
            "text-anchor": "end",
            "letter-spacing": "1",
        },
    )
    write("scrip-brand-board-v1.svg", board)

    app = QApplication(["scrip-brand-export"])
    if sys.platform == "win32":
        font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/segoeui.ttf"
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0]))
    for path in BRAND.glob("*.svg"):
        width = 1440 if "board" in path.name else 1024
        render_png(path, path.with_suffix(".png"), width)
    icons = BRAND / "icons"
    icons.mkdir(exist_ok=True)
    for size in (16, 24, 32, 64, 128, 256, 512):
        render_png(BRAND / "scrip-app-icon-v1.svg", icons / f"scrip-icon-{size}.png", size)
    desktop_assets = ROOT / "src/scrip_core/desktop/assets"
    desktop_assets.mkdir(exist_ok=True)
    shutil.copyfile(icons / "scrip-icon-512.png", desktop_assets / "scrip-icon.png")
    print(f"Brand kit exported to {BRAND}")


if __name__ == "__main__":
    main()
