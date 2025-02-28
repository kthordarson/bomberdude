# panels.py

import pygame
from loguru import logger
from game import Bomberdude

class Mainmenu:
    def __init__(self, screen, args, eventq):
        self.screen = screen
        self.args = args
        self.eventq = eventq
        self.options = ["Start", "Setup", "Quit"]
        self.selected_option = 0
        self.font = pygame.font.Font(None, 36)
        self.running = True
        self.option_rects = []

    def draw(self):
        self.screen.fill((0, 0, 0))
        self.option_rects = []
        for i, option in enumerate(self.options):
            color = (255, 0, 0) if i == self.selected_option else (255, 255, 255)
            text = self.font.render(option, True, color)
            rect = text.get_rect(center=(self.screen.get_width() // 2, 150 + i * 50))
            self.screen.blit(text, rect)
            self.option_rects.append(rect)
        pygame.display.flip()

    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    self.selected_option = (self.selected_option - 1) % len(self.options)
                elif event.key == pygame.K_DOWN:
                    self.selected_option = (self.selected_option + 1) % len(self.options)
                elif event.key == pygame.K_RETURN:
                    return self.select_option()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left mouse button
                    return self.handle_mouse_click(event.pos)
        return None

    def handle_mouse_click(self, mouse_pos):
        for i, rect in enumerate(self.option_rects):
            if rect.collidepoint(mouse_pos):
                self.selected_option = i
                return self.select_option()
        return None

    def select_option(self):
        if self.options[self.selected_option] == "Start":
            return "start"
        elif self.options[self.selected_option] == "Setup":
            return "setup"
        elif self.options[self.selected_option] == "Quit":
            self.running = False
        return None

    def run(self):
        while self.running:
            self.draw()
            action = self.handle_input()
            if action:
                return action
        return None

class Panel:
    def __init__(self, screen, position, size, color):
        self.screen = screen
        self.position = position
        self.size = size
        self.color = color

    def draw(self):
        pygame.draw.rect(self.screen, self.color, (*self.position, *self.size))
