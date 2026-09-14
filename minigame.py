import pygame
import serial
import sys
import random

# 1. Initialize Serial Communication
try:
    # Adjusted to /dev/ttyUSB0 for your new Linux setup
    ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=0.1)
except Exception as e:
    print(f"Error opening serial port: {e}")
    sys.exit()

# 2. Initialize Pygame & Font
pygame.init()
pygame.font.init()
font = pygame.font.SysFont('Arial', 24)
large_font = pygame.font.SysFont('Arial', 36)

# Display Setup
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 400
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("STM32 Flex Sensor Dino Game")
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

while True:
    # Clear screen (Light grey background)
    screen.fill((230, 230, 230))
    
    # Draw Ground Line
    pygame.draw.line(screen, (100, 100, 100), (0, GROUND_Y + 40), (SCREEN_WIDTH, GROUND_Y + 40), 2)
    
    # Check Window Events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
            
    # 3. Read Data from STM32 & Handle Gameplay Logic
    if not game_over:
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            
            if "Value:" in line:
                try:
                    value_str = line.split("Value: ")[1]
                    flex_value = int(value_str)
                    
                    # PROPORTIONAL JUMP: Harder bend (>75) = massive jump. Medium bend (>45) = short hop.
                    if not is_jumping:
                        if flex_value > 75:
                            is_jumping = True
                            jump_velocity = -13  # High jump
                except (ValueError, IndexError):
                    pass

        # 4. Jump Physics
        if is_jumping:
            dino_y += jump_velocity
            jump_velocity += 0.8  # Gravity increment
            if dino_y >= GROUND_Y:
                dino_y = GROUND_Y
                is_jumping = False

        # 5. Move Obstacle & Increment Score
        obstacle_x -= obstacle_speed
        if obstacle_x < -obstacle_width:
            obstacle_x = SCREEN_WIDTH + random.randint(0, 300) # Respawn obstacle off-screen randomly
            obstacle_height = random.randint(40, 70)           # Vary cactus heights
            score += 1
            # Gradually speed up the game as score increases
            if score % 5 == 0:
                obstacle_speed += 1

        # 6. Collision Detection
        dino_rect = pygame.Rect(DINO_X, dino_y, 40, 40)
        obstacle_rect = pygame.Rect(obstacle_x, (GROUND_Y + 40) - obstacle_height, obstacle_width, obstacle_height)
        
        if dino_rect.colliderect(obstacle_rect):
            game_over = True

    else:
        # GAME OVER STATE: Wait for a sharp flex release/re-bend to reset the game
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if "Value:" in line:
                try:
                    flex_value = int(line.split("Value: ")[1])
                    # Flattening or bending the sensor past a threshold restarts the game
                    if flex_value > 75: 
                        game_over = False
                        score = 0
                        obstacle_speed = 7
                        obstacle_x = SCREEN_WIDTH
                        dino_y = GROUND_Y
                        is_jumping = False
                except (ValueError, IndexError):
                    pass

    # 7. Rendering Graphics < 15 or flex_value > 60
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
        reset_surface = font.render("Flex/Straighten sensor to Reset", True, (50, 50, 50))
        screen.blit(go_surface, (SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 - 40))
        screen.blit(reset_surface, (SCREEN_WIDTH // 2 - 140, SCREEN_HEIGHT // 2 + 10))

    pygame.display.flip()
    clock.tick(60)