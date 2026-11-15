"""Export the Scrip flow-companion identity; never replace installed product artwork."""

import copy
import os
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .export_brand import BRAND, element, inline, label, render_png, svg, write

DIRECTORY = BRAND / "v2"
INK = "#101619"
MINT = "#80DFBF"
PAPER = "#F4F7F3"


def recolor(source: ET.Element, original: str, color: str) -> ET.Element:
    result = copy.deepcopy(source)
    for node in result.iter():
        for key, value in tuple(node.attrib.items()):
            if value == original:
                node.set(key, color)
    return result


def make_board(logos: dict[str, ET.Element], symbol: ET.Element, icon: ET.Element) -> ET.Element:
    board = svg("0 0 1800 1280", "Scrip / The flow companion / Identity 02")
    board.set("font-family", "Segoe UI, sans-serif")
    board.append(element("rect", width="1800", height="1280", fill=PAPER))
    label(
        board, 80, 76, "SCRIP / IDENTITY 02", fill=INK, **{"font-size": "18", "letter-spacing": "4"}
    )
    label(
        board,
        1720,
        76,
        "THE FLOW COMPANION",
        fill="#62726C",
        **{"font-size": "15", "letter-spacing": "3", "text-anchor": "end"},
    )
    board.append(element("rect", x="64", y="124", width="1672", height="560", rx="28", fill=INK))
    board.append(inline(logos["dark"], "translate(432 222) scale(1.7)", "hero"))
    label(
        board,
        900,
        612,
        "From intent to shipped.",
        fill="#A5BDB3",
        **{"font-size": "24", "text-anchor": "middle", "letter-spacing": "1"},
    )
    for x, width, fill in ((64, 780, "#FFFFFF"), (868, 420, "#E5ECE6"), (1312, 424, INK)):
        board.append(
            element("rect", x=str(x), y="712", width=str(width), height="380", rx="24", fill=fill)
        )
    board.append(inline(logos["ink"], "translate(193 786) scale(.94)", "single"))
    board.append(inline(icon, "translate(984 748) scale(.73)", "app"))
    board.append(inline(symbol, "translate(1436 756) scale(.68)", "solo"))
    for x, text, color in (
        (104, "ONE COLOR / PRINT + PRODUCT", "#62726C"),
        (908, "APP / DESKTOP + MOBILE", "#62726C"),
        (1352, "S + COMPANION", "#A5BDB3"),
    ):
        label(board, x, 1048, text, fill=color, **{"font-size": "13", "letter-spacing": "2"})
    for x, color, text in ((80, MINT, "MINT  #80DFBF"), (390, INK, "INK  #101619")):
        board.append(
            element("rect", x=str(x), y="1164", width="28", height="28", rx="8", fill=color)
        )
        label(board, x + 44, 1185, text, fill=INK, **{"font-size": "15"})
    label(
        board,
        1720,
        1185,
        "CONTINUOUS S / CALM EYES / FORWARD CUT",
        fill="#62726C",
        **{"font-size": "13", "letter-spacing": "2", "text-anchor": "end"},
    )
    return board


def main() -> None:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    master = ET.parse(DIRECTORY / "scrip-symbol-v2.svg").getroot()
    wordmark = ET.parse(DIRECTORY / "scrip-wordmark-v2.svg").getroot()
    symbols = {
        "mint": master,
        "ink": recolor(master, MINT, INK),
        "white": recolor(master, MINT, "#FFFFFF"),
    }
    for name in ("ink", "white"):
        write(f"scrip-symbol-{name}-v2.svg", symbols[name], directory=DIRECTORY)
    words = {"ink": wordmark, "white": recolor(wordmark, INK, "#FFFFFF")}
    write("scrip-wordmark-white-v2.svg", words["white"], directory=DIRECTORY)
    logos = {}
    for name, symbol_color, word_color in (
        ("primary", "mint", "ink"),
        ("dark", "mint", "white"),
        ("ink", "ink", "ink"),
        ("white", "white", "white"),
    ):
        logo = svg("0 0 550 200", "scrip")
        logo.append(inline(symbols[symbol_color], "translate(4 -2) scale(.8)", "symbol"))
        lettering = copy.deepcopy(words[word_color])
        for parent in lettering.iter():
            for child in list(parent):
                if child.attrib.get("id") == "letter-s":
                    parent.remove(child)
        logo.append(inline(lettering, "translate(96 3) scale(1.13)", "word"))
        suffix = "" if name == "primary" else "-" + name
        write(f"scrip-logo{suffix}-v2.svg", logo, directory=DIRECTORY)
        logos[name] = logo
    icon = svg("0 0 256 256", "Scrip app icon")
    icon.append(element("rect", width="256", height="256", rx="56", fill=INK))
    icon.append(inline(master, "translate(10.24 10.24) scale(.92)", "icon"))
    write("scrip-app-icon-v2.svg", icon, directory=DIRECTORY)
    board = make_board(logos, master, icon)
    write("scrip-brand-board-v2.svg", board, directory=DIRECTORY)
    # A quiet presentation image for chat, social cards, or a brand handoff.
    hero = svg("0 0 1600 800", "Scrip logo")
    hero.append(element("rect", width="1600", height="800", fill=INK))
    hero.append(inline(logos["dark"], "translate(332 218) scale(1.7)", "hero"))
    write("scrip-logo-presentation-v2.svg", hero, directory=DIRECTORY)

    # Separate eye layers for motion imports, on the canonical ink composition plate.
    geometry = next(node for node in master.iter() if node.attrib.get("id") == "scrip-flow")
    ribbon, left_eye, right_eye = geometry.attrib["d"].split(" M")
    motion = svg("0 0 256 256", "Scrip motion layers on ink")
    motion.append(element("rect", id="ink-plate", width="256", height="256", fill=INK))
    motion.append(element("path", id="ribbon", d=ribbon, fill=MINT))
    eyes = element("g", id="eyes", fill=INK)
    eyes.append(element("path", id="eye-left", d="M" + left_eye))
    eyes.append(element("path", id="eye-right", d="M" + right_eye))
    motion.append(eyes)
    write("scrip-motion-layers-v2.svg", motion, directory=DIRECTORY)

    app = QApplication(["scrip-brand-v2-export"])
    if sys.platform == "win32":
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/segoeui.ttf"
        families = QFontDatabase.applicationFontFamilies(
            QFontDatabase.addApplicationFont(str(font))
        )
        if families:
            app.setFont(QFont(families[0]))
    for path in DIRECTORY.glob("*.svg"):
        width = 1800 if "board" in path.name else 1600 if "logo" in path.name else 1024
        render_png(path, path.with_suffix(".png"), width)
    icons = DIRECTORY / "icons"
    icons.mkdir(exist_ok=True)
    for size in (16, 24, 32, 48, 64, 128, 256, 512, 1024):
        render_png(DIRECTORY / "scrip-app-icon-v2.svg", icons / f"scrip-icon-{size}.png", size)
    output = BRAND.parents[1] / "dist/brand-v2/Scrip-logo-v2-kit.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(DIRECTORY.rglob("*")):
            if path.is_file():
                archive.write(
                    path, arcname="scrip-brand-v2/" + path.relative_to(DIRECTORY).as_posix()
                )
    print(f"Exported {DIRECTORY}\nKit: {output}")


if __name__ == "__main__":
    main()
