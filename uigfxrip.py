import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
import struct

FILE = None
blob = None

WIDTH = 320
HEIGHT = 256

offset = 0
planes = 5

palette_hits = []
palette_index = 0
current_palette = None


# ------------------------
# File
# ------------------------

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


# ------------------------
# Amiga palette
# ------------------------

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


# ------------------------
# Renderer
# ------------------------

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


# ------------------------
# Palette display
# ------------------------

def draw_palette():

    palette_canvas.delete("all")

    if not current_palette:
        return

    colors = 2 ** planes
    box = WIDTH // colors

    for i in range(colors):

        r = current_palette[i * 3]
        g = current_palette[i * 3 + 1]
        b = current_palette[i * 3 + 2]

        color = f"#{r:02x}{g:02x}{b:02x}"

        x0 = i * box
        x1 = x0 + box

        palette_canvas.create_rectangle(x0, 0, x1, 40, fill=color, outline="")


# ------------------------
# Image update
# ------------------------

def update_image():

    global offset

    if blob is None:
        return

    size = body_size()

    if offset + size >= len(blob):
        return

    block = blob[offset:offset + size]

    img = render(block)

    preview = ImageTk.PhotoImage(img)

    canvas.delete("all")
    canvas.create_image(0, 0, anchor="nw", image=preview)
    canvas.image = preview

    offset_label.config(text=f"Offset: {hex(offset)}")

    draw_palette()


# ------------------------
# Offset controls
# ------------------------

def set_offset():

    global offset

    try:
        offset = int(offset_entry.get(), 16)
    except:
        offset = 0

    update_image()


def next_offset():

    global offset

    step = int(video_step_entry.get())

    offset += step

    update_image()


def prev_offset():

    global offset

    step = int(video_step_entry.get())

    offset -= step

    if offset < 0:
        offset = 0

    update_image()


# ------------------------
# Bitplanes
# ------------------------

def change_planes(v):

    global planes

    planes = int(v)

    update_image()


# ------------------------
# Palette search
# ------------------------

def search_palettes():

    global palette_hits, palette_index

    palette_hits = []

    if blob is None:
        return

    colors = 2 ** planes
    size = colors * 2

    for i in range(len(blob) - size):

        words = struct.unpack(">" + "H" * colors, blob[i:i + size])

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

    words = struct.unpack(">" + "H" * colors, blob[pos:pos + size])

    current_palette = build_palette(words)

    update_image()


def next_palette():

    global palette_index

    if not palette_hits:
        return

    step = int(palette_step_entry.get())

    palette_index += step
    palette_index %= len(palette_hits)

    apply_palette()


def prev_palette():

    global palette_index

    if not palette_hits:
        return

    step = int(palette_step_entry.get())

    palette_index -= step
    palette_index %= len(palette_hits)

    apply_palette()


# ------------------------
# Keyboard controls
# ------------------------

def keypress(event):

    if event.keysym == "Up":
        prev_offset()

    elif event.keysym == "Down":
        next_offset()

    elif event.keysym == "Prior":
        prev_palette()

    elif event.keysym == "Next":
        next_palette()


# ------------------------
# UI
# ------------------------

root = tk.Tk()
root.title("uigfxrip")

main = tk.Frame(root)
main.pack(padx=10, pady=10)

canvas = tk.Canvas(main, width=WIDTH, height=HEIGHT, bg="black")
canvas.grid(row=0, column=0)

palette_canvas = tk.Canvas(main, width=WIDTH, height=40, bg="black")
palette_canvas.grid(row=1, column=0, pady=5)

ui = tk.Frame(main)
ui.grid(row=0, column=1, rowspan=2, padx=15, sticky="n")

tk.Button(ui, text="Open File", command=open_file).pack(fill="x")

offset_label = tk.Label(ui, text="Offset: 0x0")
offset_label.pack()

tk.Label(ui, text="Offset (hex)").pack()

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

tk.Label(ui, text="Palette").pack()

tk.Button(ui, text="Search", command=search_palettes).pack(fill="x")

tk.Label(ui, text="Palette Step").pack()

palette_step_entry = tk.Entry(ui)
palette_step_entry.insert(0, "1")
palette_step_entry.pack()

palframe = tk.Frame(ui)
palframe.pack()

tk.Button(palframe, text="Prev", command=prev_palette).pack(side="left")
tk.Button(palframe, text="Next", command=next_palette).pack(side="left")

root.bind("<Key>", keypress)

root.mainloop()
