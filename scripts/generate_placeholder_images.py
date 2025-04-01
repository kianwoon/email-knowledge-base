from PIL import Image, ImageDraw, ImageFont
import os

def create_placeholder_image(filename, text, size=(800, 600), bg_color=(70, 130, 180), text_color=(255, 255, 255)):
    # Create a new image with the given size and background color
    image = Image.new('RGB', size, bg_color)
    draw = ImageDraw.Draw(image)
    
    # Try to create a font size that will look good
    font_size = int(min(size) / 10)
    try:
        font = ImageFont.truetype("Arial", font_size)
    except:
        # Fallback to default font if Arial is not available
        font = ImageFont.load_default()
    
    # Get text size
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    # Calculate text position to center it
    x = (size[0] - text_width) / 2
    y = (size[1] - text_height) / 2
    
    # Draw the text
    draw.text((x, y), text, font=font, fill=text_color)
    
    # Save the image
    os.makedirs('public/images', exist_ok=True)
    image.save(f'public/images/{filename}')

# Generate the placeholder images
images = [
    ('happy-man.png', 'Happy Man\nMaking OK Gesture'),
    ('collaboration.png', 'Team Collaboration\nVisualization'),
    ('productivity.png', 'Productivity\nVisualization')
]

for filename, text in images:
    create_placeholder_image(filename, text) 