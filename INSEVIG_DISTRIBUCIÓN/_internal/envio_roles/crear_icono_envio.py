"""
Genera icon_envio.ico para el sistema de envío de roles.
Ejecutar una sola vez: python crear_icono_envio.py
"""
from PIL import Image, ImageDraw
import os

def crear_frame(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    s = size
    pad = max(2, s // 16)          # margen exterior
    r = max(3, s // 10)            # radio de esquinas redondeadas del fondo

    # ── Fondo circular azul ──────────────────────────────────────────────────
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=r,
                        fill=(26, 73, 142, 255))   # azul oscuro corporativo

    # ── Cuerpo del sobre ────────────────────────────────────────────────────
    ex0 = pad * 2
    ey0 = int(s * 0.28)
    ex1 = s - pad * 2 - 1
    ey1 = int(s * 0.75)

    d.rectangle([ex0, ey0, ex1, ey1], fill=(255, 255, 255, 255),
                outline=(200, 220, 255, 200), width=max(1, s // 48))

    # ── Solapa superior (triángulo "V") ──────────────────────────────────────
    mid_x = s // 2
    mid_y = int(s * 0.50)
    flap_pts = [(ex0, ey0), (ex1, ey0), (mid_x, mid_y)]
    d.polygon(flap_pts, fill=(26, 115, 232, 255))  # azul claro
    # borde inferior del triángulo
    d.line([(ex0, ey0), (mid_x, mid_y), (ex1, ey0)],
           fill=(255, 255, 255, 200), width=max(1, s // 48))

    # ── Líneas de texto simuladas ────────────────────────────────────────────
    lpad = ex0 + max(2, s // 12)
    rpad = ex1 - max(2, s // 12)
    lh = max(1, s // 20)           # altura de cada línea
    gap = max(2, s // 14)          # separación entre líneas

    line_y = int(s * 0.56)
    for _ in range(2):
        d.rectangle([lpad, line_y, rpad, line_y + lh],
                    fill=(26, 73, 142, 160))
        line_y += lh + gap

    return img


def generar_ico(ruta_salida="icon_envio.ico"):
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [crear_frame(s) for s in sizes]
    frames[0].save(
        ruta_salida,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=frames[1:],
    )
    print(f"Icono generado: {os.path.abspath(ruta_salida)}")


if __name__ == "__main__":
    generar_ico()
