import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
import struct

blob = None

WIDTH = 320
HEIGHT = 256

offset = 0
planes = 5
zoom = 2

palette_hits = []
palette_index = 0
current_palette = None

last_image = None


# ------------------------------------------------
# File
# ------------------------------------------------

def open_file():
    global blob

    path = filedialog.askopenfilename()
    if not path:
        return

    with open(path, "rb") as f:
        blob = f.read()

    update_image()


def body_size():
    return (WIDTH // 8) * HEIGHT * planes


# ------------------------------------------------
# Amiga palette helpers
# ------------------------------------------------

def amiga_to_rgb(word):

    r = (word >> 8) & 0xF
    g = (word >> 4) & 0xF
    b = word & 0xF

    return (r * 17, g * 17, b * 17)


def build_palette(words):

    palette = []

    for w in words:
        palette.extend(amiga_to_rgb(w))

    while len(palette) < 256 * 3:
        palette.extend((0, 0, 0))

    return palette


def default_palette():

    palette = []

    for i in range(256):
        palette.extend((i, i, i))

    return palette


# ------------------------------------------------
# Bitplane renderer
# ------------------------------------------------

def render(data):

    img = Image.new("P", (WIDTH, HEIGHT))
    pixels = img.load()

    if current_palette:
        img.putpalette(current_palette)
    else:
        img.putpalette(default_palette())

    row_bytes = WIDTH // 8

    for y in range(HEIGHT):

        row_base = y * row_bytes * planes

        for x in range(WIDTH):

            bit = 7 - (x & 7)
            byte = x >> 3

            color = 0

            for p in range(planes):

                off = row_base + p * row_bytes + byte

                if off < len(data) and data[off] & (1 << bit):
                    color |= (1 << p)

            pixels[x, y] = color

    return img


# ------------------------------------------------
# Copper scan
# ------------------------------------------------

def scan_copper():

    if blob is None:
        return None

    pos = offset
    palette = [0] * 32
    timeline = []

    while pos + 4 <= len(blob):

        reg, val = struct.unpack(">HH", blob[pos:pos+4])
        pos += 4

        if reg == 0xFFFF and val == 0xFFFE:
            break

        if 0x0180 <= reg <= 0x01BE and reg % 2 == 0:

            idx = (reg - 0x0180) // 2

            if idx < 32:
                palette[idx] = val
                timeline.append(palette.copy())

    return timeline


# ------------------------------------------------
# Copper visualizer
# ------------------------------------------------

def draw_copper():

    copper_canvas.delete("all")

    timeline = scan_copper()

    if not timeline:
        return

    height = HEIGHT * zoom

    scale_y = height // 32
    scale_x = 4

    for x, pal in enumerate(timeline):

        for y in range(32):

            word = pal[y]

            r = ((word >> 8) & 0xF) * 17
            g = ((word >> 4) & 0xF) * 17
            b = (word & 0xF) * 17

            color = f"#{r:02x}{g:02x}{b:02x}"

            copper_canvas.create_rectangle(
                x * scale_x,
                y * scale_y,
                (x + 1) * scale_x,
                (y + 1) * scale_y,
                fill=color,
                outline=""
            )


# ------------------------------------------------
# Palette preview
# ------------------------------------------------

def draw_palette():

    palette_canvas.delete("all")

    if not current_palette:
        return

    colors = 2 ** planes
    box = WIDTH // colors

    for i in range(colors):

        r = current_palette[i*3]
        g = current_palette[i*3+1]
        b = current_palette[i*3+2]

        color = f"#{r:02x}{g:02x}{b:02x}"

        palette_canvas.create_rectangle(
            i*box,
            0,
            (i+1)*box,
            40,
            fill=color,
            outline=""
        )


# ------------------------------------------------
# Update image
# ------------------------------------------------

def update_image():

    global last_image

    if blob is None:
        return

    size = body_size()

    if offset + size >= len(blob):
        return

    block = blob[offset:offset+size]

    img = render(block)

    last_image = img

    scaled = img.resize((WIDTH * zoom, HEIGHT * zoom), Image.NEAREST)

    preview = ImageTk.PhotoImage(scaled)

    canvas.config(width=WIDTH * zoom, height=HEIGHT * zoom)
    copper_canvas.config(height=HEIGHT * zoom)

    canvas.delete("all")
    canvas.create_image(0, 0, anchor="nw", image=preview)
    canvas.image = preview

    offset_label.config(text=f"Offset: {hex(offset)}")

    draw_palette()
    draw_copper()


# ------------------------------------------------
# Save PNG
# ------------------------------------------------

def save_png():

    if last_image is None:
        return

    path = filedialog.asksaveasfilename(
        defaultextension=".png",
        filetypes=[("PNG", "*.png")]
    )

    if not path:
        return

    last_image.save(path)


# ------------------------------------------------
# Dump copper
# ------------------------------------------------

def dump_copper():

    if blob is None:
        return

    pos = offset

    entries = []
    palette = [0] * 32
    timeline = []

    while pos + 4 <= len(blob):

        r, v = struct.unpack(">HH", blob[pos:pos+4])
        pos += 4

        entries.append((r, v))

        if r == 0xFFFF and v == 0xFFFE:
            break

        if 0x0180 <= r <= 0x01BE and r % 2 == 0:

            idx = (r - 0x0180) // 2

            if idx < 32:
                palette[idx] = v
                timeline.append(palette.copy())

    base = f"copper_{offset:08X}"

    with open(base + ".bin", "wb") as f:
        for r, v in entries:
            f.write(struct.pack(">HH", r, v))

    with open(base + ".asm", "w") as f:

        f.write(f"; copper list at offset ${offset:08X}\n\n")

        for r, v in entries:

            if r == 0xFFFF and v == 0xFFFE:
                f.write("dc.w $FFFF,$FFFE ; END\n")
                break

            if r & 1:
                f.write(f"dc.w ${r:04X},${v:04X} ; WAIT/SKIP\n")
            else:
                f.write(f"dc.w ${r:04X},${v:04X}\n")

    if not timeline:
        timeline.append(palette.copy())

    width = len(timeline)
    height = 32

    img = Image.new("RGB", (width, height))
    pixels = img.load()

    for x, pal in enumerate(timeline):

        for y in range(32):

            word = pal[y]

            r = ((word >> 8) & 0xF) * 17
            g = ((word >> 4) & 0xF) * 17
            b = (word & 0xF) * 17

            pixels[x, y] = (r, g, b)

    img = img.resize((width * 6, height * 6), Image.NEAREST)
    img.save(base + ".png")

    print("Copper dumped:", base)


# ------------------------------------------------
# Controls
# ------------------------------------------------

def next_offset():
    global offset
    offset += int(video_step_entry.get())
    update_image()


def prev_offset():
    global offset
    offset -= int(video_step_entry.get())

    if offset < 0:
        offset = 0

    update_image()


def set_offset():
    global offset

    try:
        offset = int(offset_entry.get(), 16)
    except:
        offset = 0

    update_image()


def change_planes(v):
    global planes
    planes = int(v)
    update_image()


def change_zoom(v):
    global zoom
    zoom = int(v)
    update_image()


# ------------------------------------------------
# Keyboard
# ------------------------------------------------

def keypress(event):

    if event.keysym == "Up":
        prev_offset()

    elif event.keysym == "Down":
        next_offset()

    elif event.keysym == "Prior":
        prev_palette()

    elif event.keysym == "Next":
        next_palette()


# ------------------------------------------------
# Palette search
# ------------------------------------------------

def search_palettes():

    global palette_hits, palette_index

    palette_hits = []

    if blob is None:
        return

    colors = 2 ** planes
    size = colors * 2

    for i in range(len(blob) - size):

        words = struct.unpack(">" + "H" * colors, blob[i:i+size])

        if all(w <= 0x0FFF for w in words):

            if len(set(words)) > 3:
                palette_hits.append(i)

    palette_index = 0

    if palette_hits:
        apply_palette()


def apply_palette():

    global current_palette

    pos = palette_hits[palette_index]

    colors = 2 ** planes
    size = colors * 2

    words = struct.unpack(">" + "H" * colors, blob[pos:pos+size])

    current_palette = build_palette(words)

    update_image()


def next_palette():
    global palette_index
    if palette_hits:
        palette_index = (palette_index + 1) % len(palette_hits)
        apply_palette()


def prev_palette():
    global palette_index
    if palette_hits:
        palette_index = (palette_index - 1) % len(palette_hits)
        apply_palette()


# ------------------------------------------------
# UI
# ------------------------------------------------

root = tk.Tk()
root.title("uigfxrip")

main = tk.Frame(root)
main.pack(padx=10, pady=10)

copper_canvas = tk.Canvas(main, width=256, height=HEIGHT * zoom, bg="black")
copper_canvas.grid(row=0, column=0, rowspan=2, padx=10)

canvas = tk.Canvas(main, width=WIDTH, height=HEIGHT, bg="black")
canvas.grid(row=0, column=1)

palette_canvas = tk.Canvas(main, width=WIDTH, height=40, bg="black")
palette_canvas.grid(row=1, column=1, pady=5)

ui = tk.Frame(main)
ui.grid(row=0, column=2, rowspan=2, padx=15, sticky="n")

tk.Button(ui, text="Open File", command=open_file).pack(fill="x")
tk.Button(ui, text="Save PNG", command=save_png).pack(fill="x")
tk.Button(ui, text="Dump Copper", command=dump_copper).pack(fill="x")

offset_label = tk.Label(ui, text="Offset: 0x0")
offset_label.pack()

offset_entry = tk.Entry(ui)
offset_entry.insert(0, "0x0")
offset_entry.pack()

tk.Button(ui, text="Set Offset", command=set_offset).pack(fill="x")

tk.Label(ui, text="Video Step").pack()

video_step_entry = tk.Entry(ui)
video_step_entry.insert(0, "40")
video_step_entry.pack()

tk.Button(ui, text="Prev", command=prev_offset).pack(fill="x")
tk.Button(ui, text="Next", command=next_offset).pack(fill="x")

tk.Label(ui, text="Bitplanes").pack()

plane_slider = tk.Scale(ui, from_=1, to=5, orient="horizontal", command=change_planes)
plane_slider.set(5)
plane_slider.pack()

tk.Label(ui, text="Zoom").pack()

zoom_slider = tk.Scale(ui, from_=1, to=6, orient="horizontal", command=change_zoom)
zoom_slider.set(2)
zoom_slider.pack()

tk.Label(ui, text="Palette").pack()

tk.Button(ui, text="Search", command=search_palettes).pack(fill="x")

palframe = tk.Frame(ui)
palframe.pack()

tk.Button(palframe, text="Prev", command=prev_palette).pack(side="left")
tk.Button(palframe, text="Next", command=next_palette).pack(side="left")

root.bind("<Key>", keypress)

root.mainloop()
