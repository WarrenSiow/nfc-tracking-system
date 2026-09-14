import pygame
import sys
import random
from evdev import InputDevice, ecodes

# 1. Initialize NFC Reader (USB HID Device via evdev)
NFC_DEVICE_PATH = '/dev/input/by-id/usb-IC_Reader_IC_Reader_08FF20171101-event-kbd'

try:
    nfc_reader = InputDevice(NFC_DEVICE_PATH)
    nfc_reader.grab()  # Intercept reader keystrokes from typing into terminal windows
    print(f"Successfully connected to NFC Reader: {nfc_reader.name}")
except Exception as e:
    print(f"Error opening NFC device: {e}")
    sys.exit(1)

# 2. Initialize Pygame & Fonts
pygame.init()
pygame.font.init()
font = pygame.font.SysFont('Arial', 24)
large_font = pygame.font.SysFont('Arial', 36)

# Display Setup
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 400
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Raspberry Pi 4 NFC Dino Game")
clock = pygame.time.Clock()

# Game Constants
GROUND_Y = 300
DINO_X = 100

# Game State Variables
dino_y = GROUND_Y
is_jumping = False
jump_velocity = 0
score = 0
game_over = False

# Obstacle Properties (Cactus)
obstacle_x = SCREEN_WIDTH
obstacle_width = 25
obstacle_height = 50
obstacle_speed = 7

# NFC Scan Trigger Flag
nfc_scanned_trigger = False

while True:
    # Clear screen (Light grey background)
    screen.fill((230, 230, 230))
    
    # Draw Ground Line
    pygame.draw.line(screen, (100, 100, 100), (0, GROUND_Y + 40), (SCREEN_WIDTH, GROUND_Y + 40), 2)
    
    # Check Pygame Window Events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            # Release reader grab before exiting
            try:
                nfc_reader.ungrab()
            except Exception:
                pass
            pygame.quit()
            sys.exit()

    # 3. Read NFC Reader non-blockingly
    nfc_scanned_trigger = False
    try:
        for ev in nfc_reader.read():
            if ev.type == ecodes.EV_KEY and ev.value == 1:  # Key press down event
                key_name = ecodes.KEY[ev.code]
                # When the NFC scanner finishes transmitting a UID tag, it sends KEY_ENTER
                if key_name == 'KEY_ENTER':
                    nfc_scanned_trigger = True
    except BlockingIOError:
        # No input data waiting on this frame tick; continue loop smoothly
        pass
            
    # 4. Gameplay Logic
    if not game_over:
        # Trigger jump when any NFC tag is swiped
        if nfc_scanned_trigger and not is_jumping:
            is_jumping = True
            jump_velocity = -13  # High jump

        # Jump Physics
        if is_jumping:
            dino_y += jump_velocity
            jump_velocity += 0.8  # Gravity increment
            if dino_y >= GROUND_Y:
                dino_y = GROUND_Y
                is_jumping = False

        # Move Obstacle & Increment Score
        obstacle_x -= obstacle_speed
        if obstacle_x < -obstacle_width:
            obstacle_x = SCREEN_WIDTH + random.randint(0, 300) # Respawn obstacle off-screen
            obstacle_height = random.randint(40, 70)           # Vary cactus heights
            score += 1
            # Gradually speed up game as score increases
            if score % 5 == 0:
                obstacle_speed += 1

        # Collision Detection
        dino_rect = pygame.Rect(DINO_X, dino_y, 40, 40)
        obstacle_rect = pygame.Rect(obstacle_x, (GROUND_Y + 40) - obstacle_height, obstacle_width, obstacle_height)
        
        if dino_rect.colliderect(obstacle_rect):
            game_over = True

    else:
        # GAME OVER STATE: Swipe any tag to reset the game
        if nfc_scanned_trigger:
            game_over = False
            score = 0
            obstacle_speed = 7
            obstacle_x = SCREEN_WIDTH
            dino_y = GROUND_Y
            is_jumping = False

    # 5. Rendering Graphics
    # Draw Player (Dinosaur Placeholder)
    pygame.draw.rect(screen, (50, 150, 50), (DINO_X, dino_y, 40, 40)) 
    
    # Draw Obstacle (Cactus Placeholder)
    pygame.draw.rect(screen, (200, 50, 50), (obstacle_x, (GROUND_Y + 40) - obstacle_height, obstacle_width, obstacle_height))
    
    # Render Scoreboard text
    score_surface = font.render(f"Score: {score}", True, (0, 0, 0))
    screen.blit(score_surface, (10, 10))
    
    # Render Game Over UI Overlay
    if game_over:
        go_surface = large_font.render("GAME OVER", True, (200, 0, 0))
        reset_surface = font.render("Scan NFC Tag to Reset", True, (50, 50, 50))
        screen.blit(go_surface, (SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 - 40))
        screen.blit(reset_surface, (SCREEN_WIDTH // 2 - 110, SCREEN_HEIGHT // 2 + 10))

    pygame.display.flip()
    clock.tick(60)