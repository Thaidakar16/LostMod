#specifically made to export the exact lost vikings splash title
import sys
from PIL import Image

def parse_hex_file(filepath):
    """Reads a text file containing hex values and returns raw bytes."""
    with open(filepath, 'r') as f:
        hex_str = f.read().replace('0x', '').replace(' ', '').replace('\n', '')
    return bytes.fromhex(hex_str)

def decode_snes_palette(palette_bytes):
    """Converts SNES 15-bit BGR colors into standard RGB tuples."""
    palette = []
    for i in range(0, len(palette_bytes), 2):
        if i + 1 >= len(palette_bytes):
            break
        color_word = palette_bytes[i] | (palette_bytes[i + 1] << 8)
        
        r = (color_word & 0x001F) << 3
        g = ((color_word >> 5) & 0x001F) << 3
        b = ((color_word >> 10) & 0x001F) << 3
        
        palette.append((r, g, b))
    return palette

def decode_snes_4bpp_tile(tile_bytes):
    """Decodes a single 32-byte SNES 4bpp tile into an 8x8 pixel index map."""
    pixels = [[0] * 8 for _ in range(8)]
    for row in range(8):
        bp0 = tile_bytes[row * 2]
        bp1 = tile_bytes[row * 2 + 1]
        bp2 = tile_bytes[16 + row * 2]
        bp3 = tile_bytes[16 + row * 2 + 1]
        
        for col in range(8):
            bit_mask = 1 << (7 - col)
            p0 = 1 if (bp0 & bit_mask) else 0
            p1 = 1 if (bp1 & bit_mask) else 0
            p2 = 1 if (bp2 & bit_mask) else 0
            p3 = 1 if (bp3 & bit_mask) else 0
            
            palette_index = p0 | (p1 << 1) | (p2 << 2) | (p3 << 3)
            pixels[row][col] = palette_index
    return pixels

def render_snes_image(gfx_file, pal_file, output_file="output_256x64.png"):
    gfx_bytes = parse_hex_file(gfx_file)
    pal_bytes = parse_hex_file(pal_file)
    
    palette = decode_snes_palette(pal_bytes)
    
    # Exact target canvas: 256x64 pixels (32 tiles wide x 8 tiles high)
    img = Image.new('RGB', (256, 64))
    
    # Loop through the two halves (pages)
    for page in range(2):
        page_base_offset = page * 0x1000  # Each half is 0x1000 bytes
        page_x_offset = page * 16         # Second half starts 16 tile columns to the right
        
        # 8 rows of tiles per page
        for row_y in range(8):
            # 16 tiles per row (0x200 bytes total per row)
            for col_x in range(16):
                tile_index_in_page = row_y * 16 + col_x
                tile_offset = page_base_offset + (tile_index_in_page * 32)
                
                if tile_offset + 32 > len(gfx_bytes):
                    break
                
                tile_data = gfx_bytes[tile_offset:tile_offset + 32]
                tile_pixels = decode_snes_4bpp_tile(tile_data)
                
                # Determine absolute tile position on the 256x64 canvas
                tile_x = page_x_offset + col_x
                tile_y = row_y
                
                # Draw the 8x8 tile onto the canvas
                for y in range(8):
                    for x in range(8):
                        color_idx = tile_pixels[y][x]
                        color = palette[color_idx] if color_idx < len(palette) else (0, 0, 0)
                        img.putpixel((tile_x * 8 + x, tile_y * 8 + y), color)

    img.save(output_file)
    print(f"256x64 image successfully rendered and saved to {output_file}")

if __name__ == "__main__":
    render_snes_image('graphics.txt', 'palette.txt')